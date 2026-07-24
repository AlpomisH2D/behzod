"""Rule-based subtitle line splitter, used when the Claude API is unavailable."""

from typing import Callable

import config
from models.types import AlignedWord, SubtitleBlock, SubtitleStyle

_PAUSE_PUNCTUATION = {",", ".", "!", "?", ";", ":"}

# These always end the line (and the block) they appear in - never treated as
# merely optional break points like comma/semicolon/colon are.
_SENTENCE_END_PUNCTUATION = {".", "!", "?"}

# Punctuation that, on top of a real timing gap, counts as a "natural pause"
# for the early-break refinement (enforce_pause_aware_breaks) - narrower than
# _PAUSE_PUNCTUATION, matching the product spec's exact trigger list.
_EARLY_BREAK_PUNCTUATION = {",", ".", "!", "?"}

# A gap this large between two consecutive words is treated as a real pause in
# speech, not just natural variation in word-to-word timing.
_PAUSE_GAP_THRESHOLD_SECONDS = 0.4

# Common unit/measure words - the fallback (no-LLM) path can't reason about
# grammar generally, but a number immediately followed by one of these is a
# narrow, reliably-detectable case worth a dedicated safety net (see
# detect_number_unit_pairs). General-purpose grammatical pairing is Claude's
# job (see claude_service.py's protected_pair_indices).
_UNIT_WORDS = {
    "yosh", "kun", "oy", "yil", "soat", "daqiqa", "soniya", "so'm", "dollar",
    "foiz", "dona", "marta", "metr", "kilometr", "kilogramm", "litr",
}

_STRIP_CHARS = ",.!?;:\"'»«"


def _is_standalone_number(text: str) -> bool:
    return text.strip(_STRIP_CHARS).isdigit()


def detect_number_unit_pairs(words: list[AlignedWord]) -> set[int]:
    """Indices `i` where words[i] is a standalone number and words[i+1] is a
    common unit word or a suffixed form of one (e.g. "26 yosh", "26 yoshli",
    "26 yoshda" - Uzbek is agglutinative, so a prefix match is needed to catch
    suffixed forms, not just the bare word) - these must never end up split
    across a block OR a display-line boundary. Returned as a set of
    "protected pair" indices in the same shape _group_words_for_block and
    _wrap_words_into_lines expect."""
    pairs = set()
    for i in range(len(words) - 1):
        if not _is_standalone_number(words[i].text):
            continue
        next_word = words[i + 1].text.strip(_STRIP_CHARS).lower()
        if any(next_word.startswith(unit) for unit in _UNIT_WORDS):
            pairs.add(i)
    return pairs


def split(words: list[AlignedWord], style: SubtitleStyle) -> list[SubtitleBlock]:
    if not words:
        return []
    if style == SubtitleStyle.WORDS_1:
        return [SubtitleBlock([w.text], w.start, w.end) for w in words]
    _, max_words, lines_per_block = config.STYLE_WORD_LIMITS[style.value]
    if style == SubtitleStyle.AI_CHOICE:
        return _split_free(words, max_words_per_line=max_words)
    protected_pairs = detect_number_unit_pairs(words)
    return regroup_into_blocks(
        words, max_words_total=max_words, lines_per_block=lines_per_block, protected_pairs=protected_pairs
    )


def _is_conjunction(text: str) -> bool:
    return text.strip("".join(_PAUSE_PUNCTUATION)).lower() in config.UZBEK_CONJUNCTIONS


def _ends_with_pause(text: str) -> bool:
    return bool(text) and text[-1] in _PAUSE_PUNCTUATION


def _ends_sentence(text: str) -> bool:
    return bool(text) and text.rstrip()[-1:] in _SENTENCE_END_PUNCTUATION


def _sentence_end_offset(words: list[AlignedWord], start: int, take: int) -> int | None:
    """Length (1-based) up to and including the first sentence-ending word in
    words[start:start+take], or None if there isn't one. A period/exclamation/
    question mark always ends the line right there, even if that's short of
    the style's max word count."""
    for offset in range(1, take + 1):
        if _ends_sentence(words[start + offset - 1].text):
            return offset
    return None


def _protected_id_pairs(
    words: list[AlignedWord], protected_pairs: set[int] | None
) -> set[tuple[int, int]]:
    """Converts index-based protected pairs (relative to the full transcript)
    into word-OBJECT-identity pairs, so both the block-grouping stage and the
    (separately indexed, per-block) line-wrapping stage can recognize the same
    protected pair without needing to track index offsets between the two."""
    if not protected_pairs:
        return set()
    return {(id(words[i]), id(words[i + 1])) for i in protected_pairs if 0 <= i < len(words) - 1}


def _group_words_for_block(
    words: list[AlignedWord], max_words_total: int, protected_pairs: set[int] | None = None
) -> list[list[AlignedWord]]:
    """Groups `words` into per-BLOCK chunks, each capped at `max_words_total`
    words TOTAL - this is the style's whole-block ceiling (e.g. 4, 5, 6-7),
    never a per-line count. How that total is later wrapped across display
    lines is a separate, purely cosmetic step (see _wrap_words_into_lines) -
    it must never change how many words end up in the group here.

    `protected_pairs` (word index i, meaning words[i] and words[i+1] form a
    tight grammatical/semantic unit - "26 yosh", "katta uy", "bo'lishi
    mumkin", etc.) is a soft preference: when the ceiling allows a boundary
    at more than one nearby spot, prefer the one that doesn't split such a
    pair, by shifting ±1 word. A mandatory sentence end still always wins.
    """
    protected_pairs = protected_pairs or set()
    groups: list[list[AlignedWord]] = []
    i = 0
    n = len(words)
    while i < n:
        take = min(max_words_total, n - i)
        sentence_end = _sentence_end_offset(words, i, take)
        if sentence_end is not None:
            take = sentence_end
        else:
            # Don't end a block on a conjunction when more words follow - push
            # it to the next block instead. (Can never grow past max_words_total
            # - the strict word cap always wins.)
            while take > 1 and (i + take) < n and _is_conjunction(words[i + take - 1].text):
                take -= 1
            # Don't end a block in the middle of a protected pair either -
            # pull the bound word in if the ceiling allows, else push the
            # whole pair out to the next block.
            cut_index = i + take - 1
            if (i + take) < n and cut_index in protected_pairs:
                if take < max_words_total:
                    take += 1
                elif take > 1:
                    take -= 1
        groups.append(list(words[i : i + take]))
        i += take
    return groups


def _wrap_words_into_lines(
    words: list[AlignedWord],
    lines_per_block: int,
    max_words_total: int,
    protected_id_pairs: set[tuple[int, int]] | None = None,
) -> list[list[AlignedWord]]:
    """Distributes one block's words (already at or under the style's total
    ceiling) across display lines, as evenly as possible - purely cosmetic
    wrapping, it never changes the total word count. A FULL block (word count
    == max_words_total) uses all `lines_per_block` lines (e.g. 5 words / 2
    lines -> 3+2); a block that ended early (a sentence/pause boundary cut it
    short) scales the line count down proportionally instead of stretching
    a couple of leftover words across every line just because the style
    allows more.

    This wrapping is purely cosmetic - two words end up on different LINES of
    the same block, still shown at the same time - but a grammatically bound
    pair (protected_id_pairs, e.g. "26 yosh") split across even just a line
    boundary still reads as broken to anyone looking at the raw text, so the
    same shift-by-one preference used for block boundaries applies here too.
    """
    n = len(words)
    if n == 0:
        return [[]]
    if lines_per_block <= 1:
        return [words]
    proportional = -(-n * lines_per_block // max_words_total)  # ceil division
    num_lines = max(1, min(lines_per_block, proportional, n))
    base, extra = divmod(n, num_lines)

    boundaries: list[int] = []
    cum = 0
    for line_index in range(num_lines):
        take = base + (1 if line_index < extra else 0)
        cum += take
        boundaries.append(cum)

    if protected_id_pairs:
        for b in range(len(boundaries) - 1):
            cut = boundaries[b]
            if not (0 < cut < n):
                continue
            if (id(words[cut - 1]), id(words[cut])) in protected_id_pairs:
                next_limit = boundaries[b + 1] if b + 1 < len(boundaries) else n
                prev_limit = boundaries[b - 1] if b > 0 else 0
                if cut + 1 < next_limit:
                    boundaries[b] = cut + 1
                elif cut - 1 > prev_limit:
                    boundaries[b] = cut - 1

    lines: list[list[AlignedWord]] = []
    start = 0
    for end in boundaries:
        lines.append(words[start:end])
        start = end
    return lines


def enforce_sentence_boundaries(lines: list[list[AlignedWord]]) -> list[list[AlignedWord]]:
    """Hard safety net: `.`, `!`, `?` always end the line they appear in, no
    matter which logic produced the line (Claude's own grouping or our
    rule-based splitter). A line with one of these mid-line is split right
    after it, same as the word-count safety net does for oversized lines.
    """
    enforced: list[list[AlignedWord]] = []
    for line in lines:
        start = 0
        for offset, word in enumerate(line):
            if _ends_sentence(word.text):
                enforced.append(line[start : offset + 1])
                start = offset + 1
        if start < len(line):
            enforced.append(line[start:])
    return enforced


def regroup_into_blocks(
    words: list[AlignedWord],
    max_words_total: int,
    lines_per_block: int,
    render_word: Callable[[AlignedWord], str] | None = None,
    protected_pairs: set[int] | None = None,
) -> list[SubtitleBlock]:
    """The authoritative word-count-ceiling enforcement for every fixed-count
    style (everything except "AI ixtiyorida" and the deterministic 1-word
    case). `max_words_total` is a hard ceiling on the WHOLE block, e.g. 4, 5,
    or 6-7 - never a per-line count multiplied by `lines_per_block`. That
    total is then only wrapped across up to `lines_per_block` display lines
    for cosmetic purposes (see _wrap_words_into_lines).

    Used both by the rule-based fallback splitter and (see claude_service.py)
    to enforce this same hard ceiling on Claude's output, regardless of
    whatever line/block structure Claude itself proposed - Claude cannot be
    trusted to have followed the ceiling exactly, so this always has the
    final word.

    `protected_pairs` - see _group_words_for_block - keeps grammatically/
    semantically bound word pairs (e.g. "26 yosh") from being split across a
    block boundary OR a display-line boundary within a block, within the
    ceiling (a pair split across two lines of the SAME block reads just as
    broken as being split across two different blocks would).
    """
    protected_id_pairs = _protected_id_pairs(words, protected_pairs)
    groups = _group_words_for_block(words, max_words_total, protected_pairs)
    groups = enforce_sentence_boundaries(groups)
    groups = enforce_max_words_per_line(groups, max_words_total)
    groups = enforce_pause_aware_breaks(groups)

    render_word = render_word or (lambda w: w.text)
    blocks = []
    for group in groups:
        lines = _wrap_words_into_lines(group, lines_per_block, max_words_total, protected_id_pairs)
        blocks.append(_build_block(lines, render_word))
    return blocks


def _has_early_break_trigger(word: AlignedWord, next_word: AlignedWord | None) -> bool:
    text = word.text.rstrip()
    if text and text[-1] in _EARLY_BREAK_PUNCTUATION:
        return True
    if next_word is not None and (next_word.start - word.end) > _PAUSE_GAP_THRESHOLD_SECONDS:
        return True
    return False


def enforce_pause_aware_breaks(lines: list[list[AlignedWord]]) -> list[list[AlignedWord]]:
    """Layered on top of a style's word-count ceiling (never raises it - lines
    arriving here are already at or under it): if a natural pause (sentence or
    comma punctuation attached to a word, or a real timing gap) falls at or
    after this line's own shrink floor `max(2, N-2)` (N = this line's current
    length), the line ends there instead of padding out to the full N. Lines
    of 2 words or fewer are untouched - "1 ta so'z"/"2 ta so'z" are already at
    minimum, nothing to shrink to.
    """
    result: list[list[AlignedWord]] = []
    for line in lines:
        remaining = line
        while remaining:
            n = len(remaining)
            if n <= 2:
                result.append(remaining)
                break
            floor = max(2, n - 2)
            break_at = None
            for offset in range(floor, n):
                word = remaining[offset - 1]
                next_word = remaining[offset] if offset < n else None
                if _has_early_break_trigger(word, next_word):
                    break_at = offset
                    break
            if break_at is None:
                result.append(remaining)
                break
            result.append(remaining[:break_at])
            remaining = remaining[break_at:]
    return result


def enforce_max_words_per_line(
    lines: list[list[AlignedWord]], max_words_per_line: int
) -> list[list[AlignedWord]]:
    """Hard safety net: no line may ever exceed the style's word cap, no matter
    which logic produced it (Claude ignoring its own instructions, or an edge
    case in our own grouping). Oversized lines are force-rechunked in place.
    """
    enforced: list[list[AlignedWord]] = []
    for line in lines:
        if len(line) <= max_words_per_line:
            enforced.append(line)
            continue
        for i in range(0, len(line), max_words_per_line):
            enforced.append(line[i : i + max_words_per_line])
    return enforced


def blocks_from_lines(
    lines: list[list[AlignedWord]],
    lines_per_block: int,
    render_word: Callable[[AlignedWord], str] | None = None,
) -> list[SubtitleBlock]:
    """Groups already-split lines of words into SRT cues, up to `lines_per_block`
    lines at a time - a block also always ends right after any line that ends
    in `.`, `!`, or `?`, even if fewer than `lines_per_block` lines have been
    collected yet, so two different sentences never share one cue.

    `render_word` controls how each word becomes display text (defaults to its
    plain `.text`) - callers that know which words are semantically emphasized
    can pass a renderer that wraps those in markup.
    """
    render_word = render_word or (lambda w: w.text)
    blocks = []
    current: list[list[AlignedWord]] = []
    for line in lines:
        current.append(line)
        if len(current) >= lines_per_block or _ends_sentence(line[-1].text):
            blocks.append(_build_block(current, render_word))
            current = []
    if current:
        blocks.append(_build_block(current, render_word))
    return blocks


def _build_block(
    block_lines: list[list[AlignedWord]], render_word: Callable[[AlignedWord], str]
) -> SubtitleBlock:
    text_lines = [" ".join(render_word(w) for w in line) for line in block_lines]
    start = block_lines[0][0].start
    end = block_lines[-1][-1].end
    return SubtitleBlock(text_lines, start, end)


def _split_free(words: list[AlignedWord], max_words_per_line: int) -> list[SubtitleBlock]:
    blocks = []
    i = 0
    n = len(words)
    while i < n:
        take = min(max_words_per_line, n - i)
        # A sentence end always wins and breaks right there, even if a later
        # comma within the same window would otherwise be picked.
        sentence_end = _sentence_end_offset(words, i, take)
        if sentence_end is not None:
            take = sentence_end
            chunk = words[i : i + take]
            blocks.append(SubtitleBlock([" ".join(w.text for w in chunk)], chunk[0].start, chunk[-1].end))
            i += take
            continue
        break_at = None
        for offset in range(1, take):
            if _ends_with_pause(words[i + offset - 1].text):
                break_at = offset
        if break_at:
            take = break_at
        chunk = words[i : i + take]
        blocks.append(SubtitleBlock([" ".join(w.text for w in chunk)], chunk[0].start, chunk[-1].end))
        i += take
    return blocks
