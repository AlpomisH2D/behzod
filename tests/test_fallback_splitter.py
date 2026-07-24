from models.types import AlignedWord, SubtitleStyle, Word
from services.fallback_splitter import (
    blocks_from_lines,
    detect_number_unit_pairs,
    enforce_pause_aware_breaks,
    enforce_sentence_boundaries,
    split,
)
from services.groq_service import _merge_punctuation_tokens


def _words(texts: list[str]) -> list[AlignedWord]:
    return [AlignedWord(t, i * 0.5, (i + 1) * 0.5) for i, t in enumerate(texts)]


def _natural_words(specs: list[tuple[str, float]], gap: float = 0.05) -> list[AlignedWord]:
    """Builds words with realistic, naturally varying durations and small gaps
    between them - unlike `_words()`, no two words end up the same length."""
    words = []
    t = 0.0
    for text, duration in specs:
        words.append(AlignedWord(text, t, t + duration))
        t += duration + gap
    return words


def test_word_by_word_gives_one_word_per_block():
    words = _words(["Salom", "yaxshi", "dunyo"])
    blocks = split(words, SubtitleStyle.WORDS_1)

    assert [b.lines for b in blocks] == [["Salom"], ["yaxshi"], ["dunyo"]]
    assert all(len(b.lines) == 1 for b in blocks)


def test_word_by_word_preserves_each_words_own_real_varying_duration():
    """Regression test for the 'all words the same length' report: word_by_word
    must reflect each word's own real, naturally varying duration - never a
    flattened, averaged, or otherwise synthetic per-word duration.
    """
    specs = [
        ("Men", 0.18), ("bugun", 0.32), ("bozorga", 0.61), ("bordim", 0.44),
        ("va", 0.12), ("juda", 0.27), ("ko'p", 0.19), ("sabzavot", 0.58),
        ("sotib", 0.25), ("oldim", 0.40),
    ]
    words = _natural_words(specs)
    blocks = split(words, SubtitleStyle.WORDS_1)

    for block, w in zip(blocks, words):
        assert block.start == w.start
        assert block.end == w.end

    durations = [round(b.end - b.start, 3) for b in blocks]
    assert durations == [round(d, 3) for _, d in specs]
    assert len(set(durations)) > 1  # they genuinely vary - proves nothing got averaged


def test_short_style_keeps_lines_within_three_words():
    words = _words(["Bugun", "men", "bozorga", "bordim", "va", "non", "oldim"])
    blocks = split(words, SubtitleStyle.WORDS_3)

    all_words = [w for b in blocks for line in b.lines for w in line.split()]
    assert all_words == [w.text for w in words]
    for block in blocks:
        for line in block.lines:
            assert len(line.split()) <= 3


def test_short_style_pushes_conjunction_off_a_line_when_more_words_follow():
    words = _words(["Bugun", "men", "bozorga", "bordim", "va", "non", "oldim"])
    blocks = split(words, SubtitleStyle.WORDS_3)

    all_lines = [line for block in blocks for line in block.lines]
    for line, next_line in zip(all_lines, all_lines[1:]):
        assert line.split()[-1].lower() != "va"


def test_short_style_never_exceeds_word_cap_even_for_a_trailing_conjunction():
    """The word-count cap is a hard rule: it must hold even in the one case
    (a lone conjunction as the very last word) where honoring it means the
    conjunction ends up alone on its own line instead of tucked onto the
    previous one.
    """
    words = _words(["Salom", "dunyo", "katta", "va"])
    blocks = split(words, SubtitleStyle.WORDS_3)

    all_words = [w for b in blocks for line in b.lines for w in line.split()]
    assert all_words == [w.text for w in words]
    for block in blocks:
        for line in block.lines:
            assert len(line.split()) <= 3


def test_medium_style_allows_up_to_two_lines_per_block():
    words = _words([f"soz{i}" for i in range(9)])
    blocks = split(words, SubtitleStyle.WORDS_4_2L)

    for block in blocks:
        assert len(block.lines) <= 2
        for line in block.lines:
            assert len(line.split()) <= 4
    all_words = [w for b in blocks for line in b.lines for w in line.split()]
    assert all_words == [w.text for w in words]


def test_medium_style_block_timing_spans_both_lines():
    words = _words([f"soz{i}" for i in range(8)])
    blocks = split(words, SubtitleStyle.WORDS_4_2L)

    first_block = blocks[0]
    assert first_block.start == words[0].start
    last_word_in_block = sum(len(l.split()) for l in first_block.lines)
    assert first_block.end == words[last_word_in_block - 1].end


def test_blocks_from_lines_uses_custom_render_word_when_given():
    words = _words(["Bugun", "men", "bordim"])
    blocks = blocks_from_lines([words], lines_per_block=1, render_word=lambda w: w.text.upper())

    assert blocks[0].lines == ["BUGUN MEN BORDIM"]


def test_blocks_from_lines_defaults_to_plain_text():
    words = _words(["Bugun", "men"])
    blocks = blocks_from_lines([words], lines_per_block=1)

    assert blocks[0].lines == ["Bugun men"]


def test_short_style_never_exceeds_word_cap_with_real_groq_style_punctuation():
    """End-to-end regression test for the 'punctuation inflates word count'
    bug: raw Groq-style tokens (with punctuation as its own token, as Groq
    sometimes emits it) must be merged before splitting, so a 'short' block
    (cap 3) never ends up with more than 3 real words even when the sentence
    has commas."""
    raw_groq_words = [
        Word("Bugun", 0.0, 0.3), Word(",", 0.3, 0.32), Word("ertalab", 0.32, 0.7),
        Word("men", 0.7, 0.9), Word("uyg'ondim", 0.9, 1.3), Word(".", 1.3, 1.32),
        Word("va", 1.4, 1.5), Word("nonushta", 1.5, 1.9), Word("qildim", 1.9, 2.2),
    ]
    merged = _merge_punctuation_tokens(raw_groq_words)
    words = [AlignedWord(w.text, w.start, w.end) for w in merged]

    blocks = split(words, SubtitleStyle.WORDS_3)

    for block in blocks:
        for line in block.lines:
            assert len(line.split()) <= 3

    all_words = [w for b in blocks for line in b.lines for w in line.split()]
    assert all_words == [w.text for w in words]  # nothing lost, punctuation stayed attached
    assert "," in all_words[0]  # "Bugun," - punctuation attached, not a separate token


def test_ai_choice_style_breaks_at_punctuation_within_limit():
    words = _words(["Bugun", "ob-havo", "yaxshi,", "shuning", "uchun", "biz", "bordik", "va", "o'ynadik"])
    blocks = split(words, SubtitleStyle.AI_CHOICE)

    assert blocks[0].lines == ["Bugun ob-havo yaxshi,"]
    for block in blocks:
        assert len(block.lines) == 1


def test_ai_choice_style_respects_max_words_when_no_punctuation():
    words = _words([f"soz{i}" for i in range(30)])
    blocks = split(words, SubtitleStyle.AI_CHOICE)

    for block in blocks:
        assert len(block.lines[0].split()) <= 12  # generous fallback ceiling, no fixed cap communicated to Claude


def test_split_empty_input_returns_empty_list():
    assert split([], SubtitleStyle.WORDS_3) == []


# --- Sentence-ending punctuation as a mandatory block boundary ---


def test_short_style_sentence_end_forces_line_to_end_early():
    """'.', '!', '?' must end the line right there, even mid-window, instead
    of letting the next sentence's words get pulled into the same line."""
    words = _words(["Salom", "dunyo.", "Bugun", "ob-havo", "yaxshi"])
    blocks = split(words, SubtitleStyle.WORDS_3)

    all_lines = [line for block in blocks for line in block.lines]
    assert all_lines[0] == "Salom dunyo."  # stops right after the period, not at the 3-word cap
    assert "Bugun" not in all_lines[0]


def test_medium_style_sentence_end_forces_new_block_even_with_room_left():
    """MEDIUM allows up to 4 total words across up to 2 lines per block, but a
    sentence end must still close the BLOCK early - two different sentences
    must never share one cue even if there'd be room for more words."""
    words = _words(["Assalomu", "alaykum", "hammaga.", "Bugun", "kun", "issiq"])
    blocks = split(words, SubtitleStyle.WORDS_4_2L)

    all_words_in_block0 = " ".join(blocks[0].lines).split()
    assert all_words_in_block0 == ["Assalomu", "alaykum", "hammaga."]  # never stretched into "Bugun..."
    assert len(blocks[0].lines) <= 2  # wrapping across lines is cosmetic only, never more than the style allows
    assert blocks[0].end == words[2].end  # "hammaga." - not stretched into the next sentence
    assert " ".join(blocks[1].lines).split() == ["Bugun", "kun", "issiq"]


def test_exclamation_and_question_marks_also_force_a_break():
    words = _words(["Voy!", "Bu", "juda", "qiziq?", "Davom", "etamiz"])
    blocks = split(words, SubtitleStyle.WORDS_3)

    all_lines = [line for block in blocks for line in block.lines]
    assert all_lines[0] == "Voy!"
    assert all_lines[1] == "Bu juda qiziq?"


def test_free_style_sentence_end_wins_over_a_later_comma_in_the_same_window():
    words = _words(["Bugun.", "Keyin,", "biz", "bordik", "va", "o'ynadik", "juda"])
    blocks = split(words, SubtitleStyle.AI_CHOICE)

    assert blocks[0].lines == ["Bugun."]  # the period wins, not the later comma


def test_enforce_sentence_boundaries_splits_a_line_with_mid_line_period():
    line = _words(["Salom.", "Qalaysiz", "yaxshimisiz"])
    result = enforce_sentence_boundaries([line])

    assert len(result) == 2
    assert [w.text for w in result[0]] == ["Salom."]
    assert [w.text for w in result[1]] == ["Qalaysiz", "yaxshimisiz"]


def test_enforce_sentence_boundaries_leaves_line_without_sentence_end_alone():
    line = _words(["Salom", "dunyo"])
    result = enforce_sentence_boundaries([line])

    assert result == [line]


def test_blocks_from_lines_ends_block_early_on_sentence_end_line():
    lines = [_words(["Salom", "dunyo."]), _words(["Bugun", "kun", "issiq"])]
    blocks = blocks_from_lines(lines, lines_per_block=2)

    assert len(blocks) == 2
    assert blocks[0].lines == ["Salom dunyo."]
    assert blocks[1].lines == ["Bugun kun issiq"]


# --- Pause-aware early break (Section C: refines the word-count ceiling) ---


def test_pause_aware_break_shrinks_4_word_line_to_2_on_comma_at_floor():
    # "so'z0," ends with a comma at position 2, which is exactly the floor
    # (max(2, 4-2)=2) for a 4-word line - must break there, not pad to 4.
    line = _words(["so'z0", "so'z1,", "so'z2", "so'z3"])
    result = enforce_pause_aware_breaks([line])

    assert [[w.text for w in l] for l in result] == [["so'z0", "so'z1,"], ["so'z2", "so'z3"]]


def test_pause_aware_break_ignores_comma_before_the_floor():
    # Comma is on the very first word (position 1), before the floor (2) for a
    # 4-word line - too early to count as a valid shrink point, line stays full.
    line = _words(["so'z0,", "so'z1", "so'z2", "so'z3"])
    result = enforce_pause_aware_breaks([line])

    assert len(result) == 1
    assert [w.text for w in result[0]] == ["so'z0,", "so'z1", "so'z2", "so'z3"]


def test_pause_aware_break_shrinks_on_real_timing_gap():
    words = [
        AlignedWord("so'z0", 0.0, 0.3),
        AlignedWord("so'z1", 0.3, 0.6),
        AlignedWord("so'z2", 0.6, 0.9),
        AlignedWord("so'z3", 1.5, 1.8),  # 0.6s gap after so'z2 - well past the 0.4s threshold
    ]
    result = enforce_pause_aware_breaks([words])

    assert [[w.text for w in l] for l in result] == [["so'z0", "so'z1", "so'z2"], ["so'z3"]]


def test_pause_aware_break_leaves_2_word_lines_untouched():
    line = _words(["so'z0,", "so'z1"])
    result = enforce_pause_aware_breaks([line])

    assert result == [line]


def test_pause_aware_break_leaves_line_unchanged_with_no_trigger():
    line = _words(["so'z0", "so'z1", "so'z2", "so'z3"])
    result = enforce_pause_aware_breaks([line])

    assert result == [line]


def test_pause_aware_break_applies_5_2_2_formula_to_5_word_line():
    # floor = max(2, 5-2) = 3 - a comma at position 3 must trigger the shrink.
    line = _words(["so'z0", "so'z1", "so'z2,", "so'z3", "so'z4"])
    result = enforce_pause_aware_breaks([line])

    assert [[w.text for w in l] for l in result] == [
        ["so'z0", "so'z1", "so'z2,"],
        ["so'z3", "so'z4"],
    ]


# --- Regression: block-total ceiling must never be multiplied by line count ---


def test_words_4_2l_never_exceeds_4_total_words_per_block_not_8():
    """The reported bug: '4 ta so'z (2 qator)' was producing 8 words across 3
    lines (4 words/line * 2 lines) instead of a 4-word TOTAL ceiling."""
    words = _words([f"soz{i}" for i in range(20)])  # plenty of plain words, no punctuation
    blocks = split(words, SubtitleStyle.WORDS_4_2L)

    for block in blocks:
        total_words = sum(len(line.split()) for line in block.lines)
        assert total_words <= 4, f"block has {total_words} words, expected <= 4: {block.lines}"
        assert len(block.lines) <= 2


def test_words_5_2l_and_5_3l_never_exceed_5_total_words_per_block():
    words = _words([f"soz{i}" for i in range(20)])

    for style, max_lines in [(SubtitleStyle.WORDS_5_2L, 2), (SubtitleStyle.WORDS_5_3L, 3)]:
        blocks = split(words, style)
        for block in blocks:
            total_words = sum(len(line.split()) for line in block.lines)
            assert total_words <= 5, f"{style}: block has {total_words} words: {block.lines}"
            assert len(block.lines) <= max_lines


def test_words_6_7_styles_never_exceed_7_total_words_per_block():
    words = _words([f"soz{i}" for i in range(30)])

    for style, max_lines in [
        (SubtitleStyle.WORDS_6_7_2L, 2), (SubtitleStyle.WORDS_6_7_3L, 3), (SubtitleStyle.WORDS_6_7_4L, 4),
    ]:
        blocks = split(words, style)
        for block in blocks:
            total_words = sum(len(line.split()) for line in block.lines)
            assert total_words <= 7, f"{style}: block has {total_words} words: {block.lines}"
            assert len(block.lines) <= max_lines


def test_words_4_2l_full_block_wraps_as_2_plus_2():
    words = _words([f"soz{i}" for i in range(4)])
    blocks = split(words, SubtitleStyle.WORDS_4_2L)

    assert len(blocks) == 1
    assert [len(line.split()) for line in blocks[0].lines] == [2, 2]


def test_words_5_2l_full_block_wraps_as_3_plus_2():
    words = _words([f"soz{i}" for i in range(5)])
    blocks = split(words, SubtitleStyle.WORDS_5_2L)

    assert len(blocks) == 1
    assert [len(line.split()) for line in blocks[0].lines] == [3, 2]


def test_words_5_3l_full_block_wraps_as_2_plus_2_plus_1():
    words = _words([f"soz{i}" for i in range(5)])
    blocks = split(words, SubtitleStyle.WORDS_5_3L)

    assert len(blocks) == 1
    assert [len(line.split()) for line in blocks[0].lines] == [2, 2, 1]


# --- Number + unit words must never split across a block boundary ---


def test_number_and_unit_word_stay_in_the_same_block():
    """Regression test for the real-world report: "mashinadagi bolani 26" /
    "yosh bo'lishi mumkin bo'ladi" - "26" and "yosh" must stay together."""
    words = _words(["mashinadagi", "bolani", "26", "yosh", "bo'lishi", "mumkin", "bo'ladi", "ekan"])
    blocks = split(words, SubtitleStyle.WORDS_3)

    all_lines = [line for block in blocks for line in block.lines]
    for line in all_lines:
        if "26" in line.split():
            assert "yosh" in line.split(), f"'26' split away from 'yosh': {all_lines}"


def test_number_and_unit_word_pulled_together_within_the_ceiling():
    # Without protection, a 3-word ceiling would cut "...bolani 26" | "yosh...".
    words = _words(["Bugun", "u", "26", "yosh", "to'ldi"])
    blocks = split(words, SubtitleStyle.WORDS_3)

    all_lines = [line for block in blocks for line in block.lines]
    assert not any(line.split()[-1] == "26" for line in all_lines)


def test_detect_number_unit_pairs_finds_the_number_index():
    words = _words(["U", "26", "yosh", "edi"])
    assert detect_number_unit_pairs(words) == {1}


def test_detect_number_unit_pairs_ignores_numbers_not_followed_by_a_unit():
    words = _words(["Xona", "26", "raqamli", "edi"])
    assert detect_number_unit_pairs(words) == set()


def test_number_and_suffixed_unit_word_stay_on_the_same_line_not_just_block():
    """Regression test for the real production bug: 'qilib, 26' / 'yoshli
    singlisi' - "26" and "yoshli" (a suffixed form of "yosh") ended up on
    different DISPLAY LINES of the same block, which reads just as broken as
    a different-block split. Also verifies suffix matching ("yoshli", not
    just the bare "yosh") is honored, not only exact matches."""
    words = _words(["qilib,", "26", "yoshli", "singlisi", "va", "uning", "31", "yoshli", "turmush", "o'rtog'i"])
    blocks = split(words, SubtitleStyle.WORDS_6_7_2L)

    all_lines = [line for block in blocks for line in block.lines]
    for line in all_lines:
        tokens = line.split()
        if "26" in tokens:
            assert "yoshli" in tokens, f"'26' split away from 'yoshli': {all_lines}"
        if "31" in tokens:
            assert "yoshli" in tokens, f"'31' split away from 'yoshli': {all_lines}"


def test_protected_pairs_never_break_the_word_count_ceiling():
    """The pair-protection shift must never push a block over its ceiling."""
    words = _words(["so'z0", "so'z1", "26", "yosh", "so'z4", "so'z5", "so'z6"])
    blocks = split(words, SubtitleStyle.WORDS_3)

    for block in blocks:
        total_words = sum(len(line.split()) for line in block.lines)
        assert total_words <= 3


def test_split_with_words_4_style_shrinks_on_mid_block_pause():
    """End-to-end regression test: the rule-based fallback splitter honors the
    pause-aware refinement for a fixed word-count style, not just the raw
    helper function in isolation."""
    words = _words(["Salom", "qalaysiz,", "bugun", "kun"])  # comma right at the floor (2)
    blocks = split(words, SubtitleStyle.WORDS_4)

    assert blocks[0].lines == ["Salom qalaysiz,"]
    assert blocks[1].lines == ["bugun kun"]
