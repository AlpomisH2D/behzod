import re

import pytest

from models.types import SubtitleBlock
from services.srt_service import (
    build_ass,
    build_srt,
    build_subtitle_file,
    build_vtt,
    file_extension_for_format,
    shift_blocks,
    write_srt,
    write_subtitle_file,
)

_TIMESTAMP_RE = re.compile(r"\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}")


def test_build_srt_formats_timestamps_correctly():
    blocks = [
        SubtitleBlock(["Salom"], 0.0, 1.5),
        SubtitleBlock(["dunyo"], 1.5, 3.0),
    ]
    result = build_srt(blocks)

    timestamps = _TIMESTAMP_RE.findall(result)
    assert len(timestamps) == 2
    assert "00:00:00,000 --> 00:00:01,500" in result
    assert "00:00:01,500 --> 00:00:03,000" in result


def test_build_srt_numbers_blocks_sequentially():
    blocks = [
        SubtitleBlock(["bir"], 0.0, 1.0),
        SubtitleBlock(["ikki"], 1.0, 2.0),
        SubtitleBlock(["uch"], 2.0, 3.0),
    ]
    result = build_srt(blocks)
    lines = result.strip().split("\n\n")

    assert [entry.splitlines()[0] for entry in lines] == ["1", "2", "3"]


def test_build_srt_joins_multiline_blocks_with_newline():
    blocks = [SubtitleBlock(["birinchi qator", "ikkinchi qator"], 0.0, 2.0)]
    result = build_srt(blocks)

    assert "birinchi qator\nikkinchi qator" in result


def test_build_srt_strips_emphasis_markup_to_plain_text():
    """Regression test: emphasis markup (<font>/<b>/<i>) is an ASS/SSA-only
    styling concern - SRT must never leak literal tags into the cue text,
    which would otherwise mix bold-looking and plain-looking lines."""
    blocks = [SubtitleBlock(['<font color="#FFFF00"><b>Salom</b></font> dunyo'], 0.0, 1.0)]
    output = build_srt(blocks)

    assert "<font" not in output and "<b>" not in output and "</b>" not in output
    assert "Salom dunyo" in output


def test_build_vtt_strips_emphasis_markup_to_plain_text():
    blocks = [SubtitleBlock(["<i>Salom</i> dunyo"], 0.0, 1.0)]
    output = build_vtt(blocks)

    assert "<i>" not in output and "</i>" not in output
    assert "Salom dunyo" in output


def test_build_subtitle_file_strips_markup_for_formats_that_fall_back_to_srt():
    """XML/MCC-SCC-STL aren't implemented yet and fall back to plain SRT
    (see build_subtitle_file) - that fallback must also come out markup-free."""
    blocks = [SubtitleBlock(['<font color="#00FFFF"><b>Salom</b></font>'], 0.0, 1.0)]
    output = build_subtitle_file(blocks, "xml")

    assert "<font" not in output and "<b>" not in output
    assert "Salom" in output


def test_build_srt_empty_blocks_returns_empty_string():
    assert build_srt([]) == ""


def test_shift_blocks_moves_all_timestamps_by_offset():
    blocks = [SubtitleBlock(["Salom"], 1.0, 2.0), SubtitleBlock(["dunyo"], 2.0, 3.0)]

    shifted = shift_blocks(blocks, 0.5)

    assert (shifted[0].start, shifted[0].end) == (1.5, 2.5)
    assert (shifted[1].start, shifted[1].end) == (2.5, 3.5)
    assert shifted[0].lines == blocks[0].lines  # text is untouched


def test_shift_blocks_negative_offset_moves_earlier():
    blocks = [SubtitleBlock(["Salom"], 2.0, 3.0)]

    shifted = shift_blocks(blocks, -0.5)

    assert (shifted[0].start, shifted[0].end) == (1.5, 2.5)


def test_shift_blocks_clamps_start_at_zero_and_preserves_duration():
    """A shift large enough to push start below 0 must never collapse the
    cue's duration to zero - that would make the `srt` library silently drop
    the whole cue from the output instead of just clamping its timestamp."""
    blocks = [SubtitleBlock(["Salom"], 0.2, 0.8)]  # 0.6s duration

    shifted = shift_blocks(blocks, -5.0)

    assert shifted[0].start == 0.0
    assert shifted[0].end == pytest.approx(0.6)  # duration preserved, not collapsed to 0
    assert shifted[0].start <= shifted[0].end


def test_shift_blocks_preserves_order_when_only_start_clamps():
    blocks = [SubtitleBlock(["Salom"], 0.1, 2.0)]

    shifted = shift_blocks(blocks, -0.5)

    assert shifted[0].start == 0.0
    assert shifted[0].end == pytest.approx(1.9)  # original 1.9s duration preserved
    assert shifted[0].start <= shifted[0].end


def test_shift_blocks_never_produces_a_cue_the_srt_library_would_drop():
    """End-to-end regression test: even a large negative offset must yield
    subtitles that `build_srt` actually renders, not silently empty output."""
    from services.srt_service import build_srt

    blocks = [SubtitleBlock(["Salom"], 1.0, 2.0)]

    shifted = shift_blocks(blocks, -5000 / 1000)
    rendered = build_srt(shifted)

    assert "Salom" in rendered


def test_write_srt_creates_file_with_content(tmp_path):
    blocks = [SubtitleBlock(["Salom"], 0.0, 1.0)]
    output_path = tmp_path / "out.srt"

    result_path = write_srt(blocks, output_path)

    assert result_path == output_path
    assert output_path.exists()
    assert "Salom" in output_path.read_text(encoding="utf-8")


# --- VTT ---


def test_build_vtt_starts_with_webvtt_header():
    result = build_vtt([SubtitleBlock(["Salom"], 0.0, 1.5)])
    assert result.startswith("WEBVTT\n")


def test_build_vtt_uses_dot_separated_timestamps():
    result = build_vtt([SubtitleBlock(["Salom"], 0.0, 1.5)])
    assert "00:00:00.000 --> 00:00:01.500" in result
    assert "Salom" in result


def test_build_vtt_empty_blocks_still_has_header():
    assert build_vtt([]).strip() == "WEBVTT"


# --- ASS ---


def test_build_ass_includes_required_sections():
    result = build_ass([SubtitleBlock(["Salom"], 0.0, 1.5)])
    assert "[Script Info]" in result
    assert "[V4+ Styles]" in result
    assert "[Events]" in result
    assert "Dialogue: 0,0:00:00.00,0:00:01.50,Default,,0,0,0,,Salom" in result


def test_build_ass_converts_font_color_to_bgr_override_tag():
    result = build_ass([SubtitleBlock(['<font color="#FFFF00"><b>Salom</b></font>'], 0.0, 1.0)])
    assert "{\\c&H00FFFF&}{\\b1}Salom{\\b0}" in result


def test_build_ass_converts_italic_tags():
    result = build_ass([SubtitleBlock(["<i>Salom</i>"], 0.0, 1.0)])
    assert "{\\i1}Salom{\\i0}" in result


def test_build_ass_joins_multiline_blocks_with_ass_newline():
    result = build_ass([SubtitleBlock(["birinchi", "ikkinchi"], 0.0, 1.0)])
    assert "birinchi\\Nikkinchi" in result


# --- dispatcher ---


def test_build_subtitle_file_dispatches_to_correct_builder():
    blocks = [SubtitleBlock(["Salom"], 0.0, 1.0)]
    assert build_subtitle_file(blocks, "srt") == build_srt(blocks)
    assert build_subtitle_file(blocks, "vtt") == build_vtt(blocks)
    assert build_subtitle_file(blocks, "ass") == build_ass(blocks)


def test_build_subtitle_file_falls_back_to_srt_for_unknown_format():
    blocks = [SubtitleBlock(["Salom"], 0.0, 1.0)]
    assert build_subtitle_file(blocks, "mcc_scc_stl") == build_srt(blocks)


def test_file_extension_for_format():
    assert file_extension_for_format("srt") == "srt"
    assert file_extension_for_format("vtt") == "vtt"
    assert file_extension_for_format("ass") == "ass"
    assert file_extension_for_format("xml") == "srt"  # unsupported -> srt fallback extension


def test_write_subtitle_file_writes_requested_format(tmp_path):
    blocks = [SubtitleBlock(["Salom"], 0.0, 1.0)]
    output_path = tmp_path / "out.vtt"

    write_subtitle_file(blocks, output_path, "vtt")

    assert output_path.read_text(encoding="utf-8").startswith("WEBVTT")
