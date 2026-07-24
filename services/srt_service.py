import re
from datetime import timedelta
from pathlib import Path

import srt

from models.types import SubtitleBlock

# Emphasis markup (<font color>, <b>, <i>) is meant for ASS/SSA styling only
# (see _convert_markup_to_ass below) - plain-text-based formats (SRT, VTT, and
# anything that falls back to SRT: XML, MCC/SCC/STL) must never carry it, or a
# cue with an emphasized word ends up mixing literal "<b>...</b>" text into an
# otherwise plain line.
_MARKUP_RE = re.compile(r"<[^>]+>")


def _strip_markup(text: str) -> str:
    return _MARKUP_RE.sub("", text)


def build_srt(blocks: list[SubtitleBlock]) -> str:
    subtitles = [
        srt.Subtitle(
            index=i,
            start=timedelta(seconds=block.start),
            end=timedelta(seconds=block.end),
            content="\n".join(_strip_markup(line) for line in block.lines),
        )
        for i, block in enumerate(blocks, start=1)
    ]
    return srt.compose(subtitles)


def _format_vtt_timestamp(seconds: float) -> str:
    total_ms = round(seconds * 1000)
    hours, rem = divmod(total_ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def build_vtt(blocks: list[SubtitleBlock]) -> str:
    lines = ["WEBVTT", ""]
    for block in blocks:
        lines.append(f"{_format_vtt_timestamp(block.start)} --> {_format_vtt_timestamp(block.end)}")
        lines.extend(_strip_markup(line) for line in block.lines)
        lines.append("")
    return "\n".join(lines).rstrip("\n") + "\n"


_ASS_HEADER = (
    "[Script Info]\n"
    "ScriptType: v4.00+\n"
    "PlayResX: 384\n"
    "PlayResY: 288\n\n"
    "[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
    "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
    "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
    "Style: Default,Arial,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
)

_FONT_COLOR_RE = re.compile(r'<font color="#([0-9A-Fa-f]{6})">')


def _format_ass_timestamp(seconds: float) -> str:
    total_cs = round(seconds * 100)
    hours, rem = divmod(total_cs, 360_000)
    minutes, rem = divmod(rem, 6_000)
    secs, cs = divmod(rem, 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{cs:02d}"


def _convert_markup_to_ass(text: str) -> str:
    """Converts the HTML-ish emphasis markup used for SRT/VTT (`<font color>`,
    `<b>`, `<i>`) into ASS override tags. ASS colours are `&HBBGGRR&` -
    reversed byte order from the `#RRGGBB` used elsewhere."""

    def _color_repl(match: re.Match) -> str:
        r, g, b = match.group(1)[0:2], match.group(1)[2:4], match.group(1)[4:6]
        return "{\\c&H" + (b + g + r).upper() + "&}"

    text = _FONT_COLOR_RE.sub(_color_repl, text)
    text = text.replace("</font>", "")
    text = text.replace("<b>", "{\\b1}").replace("</b>", "{\\b0}")
    text = text.replace("<i>", "{\\i1}").replace("</i>", "{\\i0}")
    return text


def build_ass(blocks: list[SubtitleBlock]) -> str:
    lines = [_ASS_HEADER]
    for block in blocks:
        text = "\\N".join(_convert_markup_to_ass(line) for line in block.lines)
        start = _format_ass_timestamp(block.start)
        end = _format_ass_timestamp(block.end)
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


_FORMAT_BUILDERS = {"srt": build_srt, "vtt": build_vtt, "ass": build_ass}
_FORMAT_EXTENSIONS = {"srt": "srt", "vtt": "vtt", "ass": "ass"}


def build_subtitle_file(blocks: list[SubtitleBlock], fmt: str) -> str:
    """Builds the subtitle file content for `fmt` (srt/vtt/ass). Any other
    format falls back to SRT - callers are expected to have already resolved
    unsupported formats (xml, mcc/scc/stl) down to "srt" before this point."""
    builder = _FORMAT_BUILDERS.get(fmt, build_srt)
    return builder(blocks)


def file_extension_for_format(fmt: str) -> str:
    return _FORMAT_EXTENSIONS.get(fmt, "srt")


def write_srt(blocks: list[SubtitleBlock], output_path: Path) -> Path:
    output_path.write_text(build_srt(blocks), encoding="utf-8")
    return output_path


def write_subtitle_file(blocks: list[SubtitleBlock], output_path: Path, fmt: str) -> Path:
    output_path.write_text(build_subtitle_file(blocks, fmt), encoding="utf-8")
    return output_path


def shift_blocks(blocks: list[SubtitleBlock], offset_seconds: float) -> list[SubtitleBlock]:
    """Shifts every cue's start/end by `offset_seconds` (negative moves earlier).

    When the shifted start would go negative, both timestamps are pushed
    forward by the same amount to land start at exactly 0 - this preserves
    the cue's original duration instead of independently clamping start and
    end, which could collapse a cue to zero duration and make the `srt`
    library silently drop it from the output entirely.
    """
    shifted = []
    for block in blocks:
        new_start = block.start + offset_seconds
        new_end = block.end + offset_seconds
        if new_start < 0:
            adjustment = -new_start
            new_start = 0.0
            new_end += adjustment
        shifted.append(SubtitleBlock(block.lines, new_start, max(0.0, new_end)))
    return shifted
