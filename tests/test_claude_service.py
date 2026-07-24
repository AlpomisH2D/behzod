from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import config
from models.types import AlignedWord, SubtitleBlock, SubtitleStyle
from services.claude_service import ClaudeSplitError, TranslationError, split, split_with_fallback, translate_lines


def _words(texts: list[str]) -> list[AlignedWord]:
    return [AlignedWord(t, i * 0.5, (i + 1) * 0.5) for i, t in enumerate(texts)]


def _natural_words(specs: list[tuple[str, float]], gap: float = 0.05) -> list[AlignedWord]:
    """Words with realistic, naturally varying durations - unlike `_words()`,
    no two words end up the same length."""
    words = []
    t = 0.0
    for text, duration in specs:
        words.append(AlignedWord(text, t, t + duration))
        t += duration + gap
    return words


def _tool_response(
    lines: list[list[int]],
    emphasis_indices: list[int] | None = None,
    protected_pair_indices: list[int] | None = None,
):
    payload = {"lines": lines}
    if emphasis_indices is not None:
        payload["emphasis_indices"] = emphasis_indices
    if protected_pair_indices is not None:
        payload["protected_pair_indices"] = protected_pair_indices
    block = SimpleNamespace(type="tool_use", name="return_subtitle_lines", input=payload)
    return SimpleNamespace(content=[block])


def test_word_by_word_skips_api_call_entirely():
    words = _words(["Salom", "dunyo"])

    with patch("services.claude_service.Anthropic") as mock_anthropic:
        blocks = split(words, SubtitleStyle.WORDS_1, api_key="fake")

    mock_anthropic.assert_not_called()
    assert [b.lines for b in blocks] == [["Salom"], ["dunyo"]]


def test_split_sends_numbered_words_and_forces_tool_choice():
    words = _words(["Bugun", "men", "bordim"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2]])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        split(words, SubtitleStyle.WORDS_3, api_key="fake")

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["tool_choice"] == {"type": "tool", "name": "return_subtitle_lines"}
    prompt = kwargs["messages"][0]["content"]
    assert "0: Bugun" in prompt and "1: men" in prompt and "2: bordim" in prompt


def test_split_builds_blocks_from_claude_line_groups():
    words = _words(["Bugun", "men", "bordim", "va", "keldim"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2], [3, 4]])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, api_key="fake")

    assert len(blocks) == 2
    assert blocks[0].lines == ["Bugun men bordim"]
    assert blocks[1].lines == ["va keldim"]
    assert blocks[0].start == words[0].start
    assert blocks[0].end == words[2].end


def test_split_force_rechunks_oversized_claude_group_to_respect_word_cap():
    """Regression test for the '3 so'z o'rniga 6-7 ta' report: Claude sometimes
    ignores the word-count instruction in the prompt and returns one oversized
    group. The style's word cap (3 for SHORT) must hold regardless, and the
    real, naturally varying per-word timestamps must survive the re-chunking.
    """
    specs = [
        ("Bugun", 0.2), ("ertalab", 0.35), ("men", 0.15), ("uyg'ondim", 0.5),
        ("va", 0.1), ("nonushta", 0.4), ("qildim", 0.3),
    ]
    words = _natural_words(specs)
    mock_client = MagicMock()
    # Claude ignores the "2-3 words per line" rule and returns one 7-word line.
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2, 3, 4, 5, 6]])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, api_key="fake")

    for block in blocks:
        for line in block.lines:
            assert len(line.split()) <= 3

    all_words = [w for b in blocks for line in b.lines for w in line.split()]
    assert all_words == [w.text for w in words]
    # timings must still come from each word's own real, varying timestamp
    assert blocks[0].start == words[0].start
    assert blocks[0].end == words[2].end


def test_split_wraps_emphasized_words_in_font_and_bold_tags():
    words = _words(["Bugun", "men", "bordim"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2]], emphasis_indices=[0])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, api_key="fake")

    assert blocks[0].lines == ['<font color="#FFFF00"><b>Bugun</b></font> men bordim']


def test_split_leaves_text_plain_when_emphasis_indices_missing():
    words = _words(["Bugun", "men", "bordim"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2]])  # no emphasis_indices at all

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, api_key="fake")

    assert blocks[0].lines == ["Bugun men bordim"]


def test_split_ignores_malformed_emphasis_indices_without_raising():
    words = _words(["Bugun", "men", "bordim"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response(
        [[0, 1, 2]], emphasis_indices="not-a-list"
    )

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, api_key="fake")

    assert blocks[0].lines == ["Bugun men bordim"]


def test_split_ignores_out_of_range_emphasis_indices():
    words = _words(["Bugun", "men", "bordim"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2]], emphasis_indices=[99, -1])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, api_key="fake")

    assert blocks[0].lines == ["Bugun men bordim"]


def test_split_emphasis_survives_oversized_group_rechunking():
    specs = [
        ("Bugun", 0.2), ("ertalab", 0.35), ("men", 0.15), ("uyg'ondim", 0.5),
        ("va", 0.1), ("nonushta", 0.4), ("qildim", 0.3),
    ]
    words = _natural_words(specs)
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response(
        [[0, 1, 2, 3, 4, 5, 6]], emphasis_indices=[3, 5]  # "uyg'ondim", "nonushta"
    )

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, api_key="fake")

    joined = " ".join(line for b in blocks for line in b.lines)
    assert '<b>uyg\'ondim</b>' in joined
    assert '<b>nonushta</b>' in joined
    assert '<b>Bugun</b>' not in joined


def test_split_hormozi_template_uses_cyan_emphasis():
    words = _words(["Bugun", "men", "bordim"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2]], emphasis_indices=[0])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, visual_template="hormozi", api_key="fake")

    assert blocks[0].lines == ['<font color="#00FFFF"><b>Bugun</b></font> men bordim']


def test_split_minimal_template_uses_italic_only():
    words = _words(["Bugun", "men", "bordim"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2]], emphasis_indices=[0])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, visual_template="minimal", api_key="fake")

    assert blocks[0].lines == ["<i>Bugun</i> men bordim"]


def test_split_unknown_template_falls_back_to_classic():
    words = _words(["Bugun", "men"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1]], emphasis_indices=[0])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_3, visual_template="does-not-exist", api_key="fake")

    assert blocks[0].lines == ['<font color="#FFFF00"><b>Bugun</b></font> men']


def test_split_corrects_claude_treating_the_ceiling_as_per_line_not_per_block():
    """Regression test for the reported bug: Claude returned 2 lines of 4
    words each (8 total) for '4 ta so'z (2 qator)', instead of a 4-word TOTAL
    ceiling wrapped across 2 lines. Our enforcement must discard Claude's
    incorrect structure and rebuild it with the correct 4-word block total."""
    words = _words([f"soz{i}" for i in range(8)])
    mock_client = MagicMock()
    # Claude's buggy response: exactly the reported failure mode (4 + 4 = 8).
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2, 3], [4, 5, 6, 7]])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_4_2L, api_key="fake")

    for block in blocks:
        total_words = sum(len(line.split()) for line in block.lines)
        assert total_words <= 4, f"block has {total_words} words, expected <= 4: {block.lines}"
        assert len(block.lines) <= 2


def test_split_respects_claudes_protected_pair_indices():
    """Claude flags a grammatically-bound pair (e.g. adjective+noun, not just
    the number+unit heuristic case) via protected_pair_indices - the final
    mechanical regrouping must keep that pair in the same block."""
    words = _words(["Bugun", "katta", "uy", "sotib", "oldik", "va", "xursandmiz"])
    mock_client = MagicMock()
    # Claude's own (buggy/irrelevant) line grouping is discarded regardless -
    # what matters is that it flagged "katta"(1)+"uy"(2) as a protected pair.
    mock_client.messages.create.return_value = _tool_response(
        [[0, 1], [2, 3], [4, 5, 6]], protected_pair_indices=[1]
    )

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_2, api_key="fake")

    all_lines = [line for block in blocks for line in block.lines]
    for line in all_lines:
        if "katta" in line.split():
            assert "uy" in line.split(), f"'katta' split away from 'uy': {all_lines}"


def test_split_forces_sentence_boundary_even_when_claude_groups_two_sentences():
    """Claude sometimes groups words spanning two sentences into one line/
    block - the hard safety net must split it right after the sentence-ending
    word regardless of what Claude returned."""
    words = _words(["Salom", "dunyo.", "Bugun", "kun", "issiq"])
    mock_client = MagicMock()
    # Claude returns one block containing both sentences.
    mock_client.messages.create.return_value = _tool_response([[0, 1, 2, 3, 4]])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split(words, SubtitleStyle.WORDS_4_2L, api_key="fake")

    assert blocks[0].lines == ["Salom dunyo."]
    assert blocks[0].end == words[1].end
    assert "Bugun" not in blocks[0].lines[0]


def test_split_raises_on_api_error():
    words = _words(["Salom", "dunyo"])
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("balans tugadi")

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        with pytest.raises(ClaudeSplitError, match="balans tugadi"):
            split(words, SubtitleStyle.WORDS_3, api_key="fake")


def test_split_passes_default_timeout_to_api_call():
    """Regression test: without a bounded timeout, a stalled Claude connection
    would hang the conversation forever instead of triggering the fallback."""
    words = _words(["Salom", "dunyo"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1]])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        split(words, SubtitleStyle.WORDS_3, api_key="fake")

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["timeout"] == config.CLAUDE_REQUEST_TIMEOUT_SECONDS


def test_split_passes_custom_timeout_to_api_call():
    words = _words(["Salom", "dunyo"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1]])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        split(words, SubtitleStyle.WORDS_3, api_key="fake", timeout=5.0)

    _, kwargs = mock_client.messages.create.call_args
    assert kwargs["timeout"] == 5.0


def test_split_with_fallback_falls_back_on_timeout_like_error():
    words = _words(["Salom", "dunyo", "katta", "olam"])
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = TimeoutError("timed out")

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split_with_fallback(words, SubtitleStyle.WORDS_3, api_key="fake")

    all_words = [w for b in blocks for line in b.lines for w in line.split()]
    assert all_words == [w.text for w in words]


def test_split_raises_on_incomplete_index_coverage():
    words = _words(["Salom", "dunyo", "katta"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 1]])  # missing index 2

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        with pytest.raises(ClaudeSplitError):
            split(words, SubtitleStyle.WORDS_3, api_key="fake")


def test_split_raises_on_non_contiguous_group():
    words = _words(["Salom", "dunyo", "katta"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0, 2], [1]])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        with pytest.raises(ClaudeSplitError):
            split(words, SubtitleStyle.WORDS_3, api_key="fake")


def test_split_with_fallback_uses_rule_based_splitter_on_claude_error():
    words = _words(["Salom", "dunyo", "katta", "olam"])
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("network error")

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split_with_fallback(words, SubtitleStyle.WORDS_3, api_key="fake")

    assert len(blocks) > 0
    all_words = [w for b in blocks for line in b.lines for w in line.split()]
    assert all_words == [w.text for w in words]


def _translate_tool_response(lines: list[str]):
    block = SimpleNamespace(type="tool_use", name="return_translated_lines", input={"lines": lines})
    return SimpleNamespace(content=[block])


def test_translate_lines_preserves_block_and_timing_structure():
    blocks = [
        SubtitleBlock(["salom", "dunyo"], 0.0, 1.0),
        SubtitleBlock(["yaxshimisiz"], 1.0, 2.0),
    ]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _translate_tool_response(["privet", "mir", "kak dela"])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        translated = translate_lines(blocks, "ru", api_key="fake")

    assert [b.lines for b in translated] == [["privet", "mir"], ["kak dela"]]
    assert translated[0].start == 0.0 and translated[0].end == 1.0
    assert translated[1].start == 1.0 and translated[1].end == 2.0


def test_translate_lines_returns_empty_for_no_blocks():
    with patch("services.claude_service.Anthropic") as mock_anthropic:
        assert translate_lines([], "ru", api_key="fake") == []
    mock_anthropic.assert_not_called()


def test_translate_lines_raises_on_api_error():
    blocks = [SubtitleBlock(["salom"], 0.0, 1.0)]
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = RuntimeError("balans tugadi")

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        with pytest.raises(TranslationError, match="balans tugadi"):
            translate_lines(blocks, "en", api_key="fake")


def test_translate_lines_raises_on_line_count_mismatch():
    blocks = [SubtitleBlock(["salom", "dunyo"], 0.0, 1.0)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _translate_tool_response(["only one line"])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        with pytest.raises(TranslationError):
            translate_lines(blocks, "en", api_key="fake")


def test_translate_lines_raises_when_tool_not_used():
    blocks = [SubtitleBlock(["salom"], 0.0, 1.0)]
    mock_client = MagicMock()
    mock_client.messages.create.return_value = SimpleNamespace(content=[])

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        with pytest.raises(TranslationError):
            translate_lines(blocks, "en", api_key="fake")


def test_split_with_fallback_uses_rule_based_splitter_on_malformed_response():
    words = _words(["Salom", "dunyo"])
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _tool_response([[0]])  # missing index 1

    with patch("services.claude_service.Anthropic", return_value=mock_client):
        blocks = split_with_fallback(words, SubtitleStyle.WORDS_3, api_key="fake")

    all_words = [w for b in blocks for line in b.lines for w in line.split()]
    assert all_words == [w.text for w in words]
