from anthropic import Anthropic

import config
from models.types import AlignedWord, SubtitleBlock, SubtitleStyle
from services import fallback_splitter

_TOOL_NAME = "return_subtitle_lines"

_SENTENCE_END_RULE = (
    "Nuqta, undov (!) yoki so'roq (?) belgisi bilan tugagan so'zdan keyin "
    "har doim yangi qator boshlang - ikkita alohida gapni bitta qatorga "
    "hech qachon qo'shmang."
)

_CONJUNCTION_RULE = (
    "Bog'lovchi so'zni (va, lekin, ammo, biroq, ham, yoki, chunki kabi) "
    "hech qachon qator oxirida yolg'iz qoldirmang."
)

# General principle, not a fixed pattern list - Claude judges any adjacent
# word pair on any topic using its own understanding of Uzbek grammar. The
# examples below are calibration anchors, not an exhaustive whitelist.
_GRAMMAR_BINDING_RULE = (
    "Ikki so'z orasida chambarchas grammatik yoki ma'noviy bog'liqlik bo'lsa "
    "(masalan: son va undan keyingi birlik/ot - \"26 yosh\", \"3 kun\", \"10 million so'm\"; "
    "sifat va sifatlanmish ot - \"katta uy\", \"qizil mashina\"; ega va unga bevosita "
    "yondosh kesim; qo'shma yoki yordamchi fe'l birikmalari - \"bo'lishi mumkin\", "
    "\"qila boshladi\", \"ketib qoldi\"; bog'lovchili yoki izofali birikmalar, ismlar "
    "(kishi ismi va familiyasi, ikki so'zdan iborat joy nomlari) va tabiiy nutqda "
    "ajralmaydigan boshqa har qanday so'z juftliklari - mavzudan qat'i nazar), "
    "bu ikki so'zni turli bloklarga hech qachon ajratmang. Bunday juftliklarning "
    "birinchi so'zi indeksini protected_pair_indices ro'yxatiga qo'ying. Blok "
    "chegarasini tanlashda, agar so'z-soni chegarasi ichida bir nechta joyga "
    "chegara qo'yish mumkin bo'lsa, shu turdagi juftlikni ajratmaydigan variantni "
    "tanlang - chegaradan oshmagan holda ±1 so'zga siljiting."
)


def _exact_words_rule(n: int, lines_per_block: int | None = None) -> str:
    if lines_per_block:
        block_part = (
            f"Har bir blokda JAMI aynan {n} ta so'z bo'lsin (bu {lines_per_block} ta so'zdan emas!), "
            f"ular {lines_per_block} ta qatorga bo'lib yozilsin."
        )
    else:
        block_part = f"Har bir qatorda aynan {n} ta so'z bo'lsin."
    return f"{block_part} {_CONJUNCTION_RULE} {_SENTENCE_END_RULE}"


def _range_words_rule(low: int, high: int, lines_per_block: int) -> str:
    return (
        f"Har bir blokda JAMI {low}-{high} ta so'z bo'lsin, ular {lines_per_block} ta qatorga bo'lib yozilsin. "
        f"{_CONJUNCTION_RULE} {_SENTENCE_END_RULE}"
    )


_STYLE_RULES = {
    SubtitleStyle.WORDS_2: _exact_words_rule(2),
    SubtitleStyle.WORDS_3: _exact_words_rule(3),
    SubtitleStyle.WORDS_4: _exact_words_rule(4),
    SubtitleStyle.WORDS_4_2L: _exact_words_rule(4, lines_per_block=2),
    SubtitleStyle.WORDS_5_2L: _exact_words_rule(5, lines_per_block=2),
    SubtitleStyle.WORDS_5_3L: _exact_words_rule(5, lines_per_block=3),
    SubtitleStyle.WORDS_6_7_2L: _range_words_rule(6, 7, lines_per_block=2),
    SubtitleStyle.WORDS_6_7_3L: _range_words_rule(6, 7, lines_per_block=3),
    SubtitleStyle.WORDS_6_7_4L: _range_words_rule(6, 7, lines_per_block=4),
    SubtitleStyle.AI_CHOICE: (
        "So'zlarni tabiiy pauza va ma'no chegaralariga qarab, o'zingiz mos deb "
        f"bilgan uzunlikda qatorlarga bo'ling - qattiq so'z-soni chegarasi yo'q. {_SENTENCE_END_RULE}"
    ),
}

_TOOL_SCHEMA = {
    "name": _TOOL_NAME,
    "description": (
        "Berilgan raqamlangan so'zlarni subtitr qatorlariga guruhlaydi. "
        "Har bir guruh - bitta ekranda ko'rinadigan qator uchun ketma-ket so'z indekslari."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lines": {
                "type": "array",
                "items": {"type": "array", "items": {"type": "integer"}},
                "description": "Har bir ichki ro'yxat bitta qatorga tegishli, ketma-ket so'z indekslari.",
            },
            "emphasis_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Semantik jihatdan muhim (urg'u beriladigan) so'zlarning indekslari. "
                    "Ixtiyoriy - muhim so'z bo'lmasa bo'sh ro'yxat qaytaring."
                ),
            },
            "protected_pair_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "Grammatik/ma'noviy jihatdan chambarchas bog'liq bo'lgan qo'shni so'z "
                    "juftliklarining BIRINCHI so'zi indeksi (ya'ni i bu yerda bo'lsa, i va i+1 "
                    "so'zlar bir xil blokda qolishi shart - masalan son+birlik, sifat+ot, "
                    "qo'shma fe'l). Ixtiyoriy - topilmasa bo'sh ro'yxat qaytaring."
                ),
            },
        },
        "required": ["lines"],
    },
}

# Each visual template renders an emphasized word differently. There's no
# video burn-in yet (SRT only), so "template" only controls this SRT-safe
# inline markup - not font size, position, or outline.
_TEMPLATE_EMPHASIS_MARKUP = {
    "classic": ('<font color="#FFFF00"><b>', "</b></font>"),
    "hormozi": ('<font color="#00FFFF"><b>', "</b></font>"),
    "minimal": ("<i>", "</i>"),
}
_DEFAULT_VISUAL_TEMPLATE = "classic"


def _render_word(word: AlignedWord, emphasized_ids: set[int], visual_template: str) -> str:
    if id(word) not in emphasized_ids:
        return word.text
    open_tag, close_tag = _TEMPLATE_EMPHASIS_MARKUP.get(
        visual_template, _TEMPLATE_EMPHASIS_MARKUP[_DEFAULT_VISUAL_TEMPLATE]
    )
    return f"{open_tag}{word.text}{close_tag}"


class ClaudeSplitError(Exception):
    pass


class TranslationError(Exception):
    pass


_TRANSLATE_LANGUAGE_NAMES = {"ru": "rus", "en": "ingliz"}

_TRANSLATE_TOOL_NAME = "return_translated_lines"

_TRANSLATE_TOOL_SCHEMA = {
    "name": _TRANSLATE_TOOL_NAME,
    "description": (
        "Berilgan raqamlangan subtitr qatorlarini boshqa tilga tarjima qiladi, "
        "qatorlar sonini va tartibini o'zgartirmasdan."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "lines": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tarjima qilingan qatorlar, xuddi shu tartibda va sonda.",
            }
        },
        "required": ["lines"],
    },
}


def split(
    words: list[AlignedWord],
    style: SubtitleStyle,
    visual_template: str = _DEFAULT_VISUAL_TEMPLATE,
    api_key: str | None = None,
    timeout: float | None = None,
) -> list[SubtitleBlock]:
    """Splits words into subtitle blocks for the given style using Claude. Raises ClaudeSplitError on any failure.

    `timeout` bounds the request itself (defaults to config.CLAUDE_REQUEST_TIMEOUT_SECONDS)
    so a stalled connection raises ClaudeSplitError (and triggers the rule-based
    fallback) instead of hanging forever.
    """
    if not words:
        return []
    if style == SubtitleStyle.WORDS_1:
        # Deterministic 1-word-per-line case - no need to spend an API call on it.
        return [SubtitleBlock([w.text], w.start, w.end) for w in words]

    client = Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
    prompt = _build_prompt(words, style)

    try:
        response = client.messages.create(
            model=config.CLAUDE_SPLIT_MODEL,
            max_tokens=2048,
            system=(
                "Siz o'zbek tilidagi subtitr matnini qatorlarga bo'luvchi yordamchisiz. "
                "Faqat berilgan vositani (tool) chaqirib javob bering."
            ),
            messages=[{"role": "user", "content": prompt}],
            tools=[_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            timeout=timeout if timeout is not None else config.CLAUDE_REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - normalized into a domain error
        raise ClaudeSplitError(f"Claude API xatosi: {exc}") from exc

    line_groups = _extract_line_groups(response)
    lines = _validate_and_build_lines(line_groups, words)  # also validates word order/coverage
    _, max_words, lines_per_block = config.STYLE_WORD_LIMITS[style.value]
    # Missing/malformed emphasis data is never an error - it just means no
    # word gets highlighted, per the required fallback behavior.
    emphasized_ids = _extract_emphasized_word_ids(response, words)
    render_word = lambda w: _render_word(w, emphasized_ids, visual_template)  # noqa: E731

    if style == SubtitleStyle.AI_CHOICE:
        # No fixed word-count ceiling here - Claude's own natural-pause
        # grouping is kept, only the mandatory sentence-boundary safety net
        # and the generous fallback ceiling (12) are enforced on top of it.
        lines = fallback_splitter.enforce_sentence_boundaries(lines)
        lines = fallback_splitter.enforce_max_words_per_line(lines, max_words)
        return fallback_splitter.blocks_from_lines(lines, lines_per_block, render_word=render_word)

    # Every fixed-count style: Claude doesn't reliably follow the word-count
    # ceiling (the earlier bug where "4 ta so'z (2 qator)" came back as 8
    # words/block was Claude - and the old enforcement below it - both
    # treating the number as per-line instead of per-block). `words` is
    # already known to be in original transcript order (validated above), so
    # Claude's own line/block boundaries are discarded entirely in favor of
    # `regroup_into_blocks`, which is the single authoritative place the
    # block-total ceiling (never per-line * lines_per_block) is enforced.
    # Claude's grammatical judgment still matters, though: its
    # protected_pair_indices (union'd with the narrow built-in number+unit
    # heuristic, as a safety net for anything Claude missed) tells the
    # mechanical regrouping which adjacent words to avoid splitting apart.
    protected_pairs = _extract_protected_pairs(response, words) | fallback_splitter.detect_number_unit_pairs(words)
    return fallback_splitter.regroup_into_blocks(
        words, max_words, lines_per_block, render_word=render_word, protected_pairs=protected_pairs
    )


def split_with_fallback(
    words: list[AlignedWord],
    style: SubtitleStyle,
    visual_template: str = _DEFAULT_VISUAL_TEMPLATE,
    api_key: str | None = None,
    timeout: float | None = None,
) -> list[SubtitleBlock]:
    """Same as split(), but falls back to the rule-based splitter on any Claude failure."""
    try:
        return split(words, style, visual_template=visual_template, api_key=api_key, timeout=timeout)
    except ClaudeSplitError:
        return fallback_splitter.split(words, style)


def _build_prompt(words: list[AlignedWord], style: SubtitleStyle) -> str:
    numbered = "\n".join(f"{i}: {w.text}" for i, w in enumerate(words))
    rules = _STYLE_RULES[style]
    return (
        f"Quyidagi raqamlangan so'zlarni subtitr qatorlariga bo'ling.\n"
        f"Qoida: {rules}\n"
        f"Har bir so'z faqat bitta qatorga tegishli bo'lishi va barcha so'zlar "
        f"0 dan {len(words) - 1} gacha tartibda, bo'sh joysiz qamrab olinishi shart.\n\n"
        f"{_GRAMMAR_BINDING_RULE}\n\n"
        f"Shuningdek, gap ma'nosi uchun semantik jihatdan eng muhim so'zlarni "
        f"aniqlab, ularning indekslarini emphasis_indices ro'yxatiga qo'ying "
        f"(masalan, kalit otlar, raqamlar, harakatlar - bog'lovchi va yordamchi "
        f"so'zlar emas). Muhim so'z topilmasa, bo'sh ro'yxat qaytaring.\n\n"
        f"So'zlar:\n{numbered}"
    )


def _extract_line_groups(response) -> list[list[int]]:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == _TOOL_NAME:
            lines = block.input.get("lines")
            if lines is not None:
                return lines
    raise ClaudeSplitError("Claude javobida 'lines' topilmadi")


def _extract_emphasized_word_ids(response, words: list[AlignedWord]) -> set[int]:
    """Reads emphasis_indices from the same tool call as the line groups.

    Never raises: a missing field, wrong type, or out-of-range index just
    means fewer (or zero) words end up emphasized, per the required fallback
    behavior - emphasis is a cosmetic addition, not something worth failing
    the whole split over.
    """
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == _TOOL_NAME:
            raw_indices = block.input.get("emphasis_indices")
            if not isinstance(raw_indices, list):
                return set()
            valid = {i for i in raw_indices if isinstance(i, int) and 0 <= i < len(words)}
            return {id(words[i]) for i in valid}
    return set()


def _extract_protected_pairs(response, words: list[AlignedWord]) -> set[int]:
    """Reads protected_pair_indices from the same tool call as the line
    groups - see _GRAMMAR_BINDING_RULE. Never raises: a missing field, wrong
    type, or out-of-range index just means fewer (or zero) pairs are
    protected, same fallback behavior as _extract_emphasized_word_ids.
    """
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == _TOOL_NAME:
            raw_indices = block.input.get("protected_pair_indices")
            if not isinstance(raw_indices, list):
                return set()
            return {i for i in raw_indices if isinstance(i, int) and 0 <= i < len(words) - 1}
    return set()


def _validate_and_build_lines(
    line_groups: list[list[int]], words: list[AlignedWord]
) -> list[list[AlignedWord]]:
    flat = [idx for group in line_groups for idx in group]
    if flat != list(range(len(words))):
        raise ClaudeSplitError("Claude qaytargan indekslar so'zlar bilan mos kelmadi")
    for group in line_groups:
        if not group or group != list(range(group[0], group[0] + len(group))):
            raise ClaudeSplitError("Claude qaytargan guruh ketma-ket emas")
    return [[words[i] for i in group] for group in line_groups]


def translate_lines(
    blocks: list[SubtitleBlock],
    target_language: str,
    api_key: str | None = None,
    timeout: float | None = None,
) -> list[SubtitleBlock]:
    """Translates each display line of `blocks` into `target_language`; timing is untouched.

    Raises TranslationError on any failure (API error, malformed response, or a
    returned line count that doesn't match the input) - callers should fall back
    to the original text rather than ship mistimed or misaligned subtitles.
    """
    if not blocks:
        return []

    original_lines = [line for block in blocks for line in block.lines]
    language_name = _TRANSLATE_LANGUAGE_NAMES.get(target_language, target_language)
    prompt = _build_translate_prompt(original_lines, language_name)

    client = Anthropic(api_key=api_key or config.ANTHROPIC_API_KEY)
    try:
        response = client.messages.create(
            model=config.CLAUDE_SPLIT_MODEL,
            max_tokens=2048,
            system=(
                "Siz subtitr qatorlarini tabiiy va qisqa tarzda tarjima qiluvchi "
                "yordamchisiz. Faqat berilgan vositani (tool) chaqirib javob bering."
            ),
            messages=[{"role": "user", "content": prompt}],
            tools=[_TRANSLATE_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": _TRANSLATE_TOOL_NAME},
            timeout=timeout if timeout is not None else config.CLAUDE_REQUEST_TIMEOUT_SECONDS,
        )
    except Exception as exc:  # noqa: BLE001 - normalized into a domain error
        raise TranslationError(f"Claude tarjima xatosi: {exc}") from exc

    translated_lines = _extract_translated_lines(response)
    if len(translated_lines) != len(original_lines):
        raise TranslationError(
            f"Tarjima qatorlar soni mos kelmadi: kutilgan {len(original_lines)}, "
            f"kelgan {len(translated_lines)}"
        )

    return _rebuild_translated_blocks(blocks, translated_lines)


def _build_translate_prompt(lines: list[str], language_name: str) -> str:
    numbered = "\n".join(f"{i}: {line}" for i, line in enumerate(lines))
    return (
        f"Quyidagi raqamlangan subtitr qatorlarini {language_name} tiliga tarjima qiling.\n"
        f"Qoida: har bir qatorni alohida tarjima qiling, qatorlarni birlashtirmang yoki "
        f"bo'lmang - natijada aynan {len(lines)} ta qator, xuddi shu tartibda bo'lishi shart.\n\n"
        f"Qatorlar:\n{numbered}"
    )


def _extract_translated_lines(response) -> list[str]:
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == _TRANSLATE_TOOL_NAME:
            lines = block.input.get("lines")
            if lines is not None:
                return lines
    raise TranslationError("Claude javobida 'lines' topilmadi")


def _rebuild_translated_blocks(
    blocks: list[SubtitleBlock], translated_lines: list[str]
) -> list[SubtitleBlock]:
    rebuilt = []
    cursor = 0
    for block in blocks:
        count = len(block.lines)
        rebuilt.append(SubtitleBlock(translated_lines[cursor : cursor + count], block.start, block.end))
        cursor += count
    return rebuilt
