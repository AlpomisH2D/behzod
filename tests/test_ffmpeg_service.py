import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

import config
from services.ffmpeg_service import (
    FfmpegError,
    UnsupportedFormatError,
    ensure_audio,
    extract_audio,
    get_duration,
    split_into_chunks,
)


def test_ensure_audio_skips_extraction_for_audio_input(tmp_path):
    audio_path = tmp_path / "input.mp3"
    audio_path.write_bytes(b"fake mp3 bytes")

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        result = ensure_audio(audio_path, tmp_path)

    mock_run.assert_not_called()
    assert result == audio_path


def test_ensure_audio_extracts_for_video_input(tmp_path):
    video_path = tmp_path / "input.mp4"
    video_path.write_bytes(b"fake mp4 bytes")

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        result = ensure_audio(video_path, tmp_path)

    mock_run.assert_called_once()
    assert result == tmp_path / "input.mp3"


def test_ensure_audio_rejects_unsupported_format(tmp_path):
    bad_path = tmp_path / "input.txt"
    bad_path.write_text("not media")

    with pytest.raises(UnsupportedFormatError):
        ensure_audio(bad_path, tmp_path)


def test_extract_audio_builds_correct_command(tmp_path):
    input_path = tmp_path / "clip.mp4"
    output_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        extract_audio(input_path, output_path)

    args = mock_run.call_args[0][0]
    assert args[0] == "ffmpeg"
    assert "-i" in args and str(input_path) in args
    assert "-ar" in args and "16000" in args
    assert "-ac" in args and "1" in args
    assert args[-1] == str(output_path)


def test_extract_audio_raises_on_ffmpeg_failure(tmp_path):
    input_path = tmp_path / "clip.mp4"
    output_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="Invalid data found")
        with pytest.raises(FfmpegError, match="Invalid data found"):
            extract_audio(input_path, output_path)


def test_get_duration_parses_ffprobe_output(tmp_path):
    audio_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="45.231000\n", stderr="")
        duration = get_duration(audio_path)

    assert duration == 45.231
    args = mock_run.call_args[0][0]
    assert args[0] == "ffprobe"


def test_get_duration_returns_none_on_ffprobe_failure(tmp_path):
    audio_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="No such file")
        assert get_duration(audio_path) is None


def test_get_duration_returns_none_on_unparsable_output(tmp_path):
    audio_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="N/A\n", stderr="")
        assert get_duration(audio_path) is None


def test_split_into_chunks_creates_one_chunk_per_interval(tmp_path):
    input_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.get_duration", return_value=30.0), patch(
        "services.ffmpeg_service.subprocess.run"
    ) as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        chunks = split_into_chunks(input_path, tmp_path, chunk_seconds=12.0)

    # 30s of audio in 12s chunks -> starts at 0, 12, 24 (3 chunks)
    assert chunks == [
        tmp_path / "chunk_000.mp3",
        tmp_path / "chunk_001.mp3",
        tmp_path / "chunk_002.mp3",
    ]
    assert mock_run.call_count == 3
    start_values = [call.args[0][call.args[0].index("-ss") + 1] for call in mock_run.call_args_list]
    assert start_values == ["0.0", "12.0", "24.0"]


def test_split_into_chunks_raises_when_duration_unknown(tmp_path):
    input_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.get_duration", return_value=None):
        with pytest.raises(FfmpegError):
            split_into_chunks(input_path, tmp_path, chunk_seconds=12.0)


def test_split_into_chunks_raises_on_ffmpeg_failure(tmp_path):
    input_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.get_duration", return_value=20.0), patch(
        "services.ffmpeg_service.subprocess.run"
    ) as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stderr="boom")
        with pytest.raises(FfmpegError, match="boom"):
            split_into_chunks(input_path, tmp_path, chunk_seconds=12.0)


def test_extract_audio_passes_a_subprocess_timeout(tmp_path):
    """A hung ffmpeg process must not block forever - see the ~2min-audio hang fix."""
    input_path = tmp_path / "clip.mp4"
    output_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        extract_audio(input_path, output_path)

    assert mock_run.call_args.kwargs["timeout"] == config.FFMPEG_SUBPROCESS_TIMEOUT_SECONDS


def test_extract_audio_raises_ffmpeg_error_on_subprocess_timeout(tmp_path):
    input_path = tmp_path / "clip.mp4"
    output_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffmpeg", timeout=180)
        with pytest.raises(FfmpegError):
            extract_audio(input_path, output_path)


def test_get_duration_returns_none_on_subprocess_timeout(tmp_path):
    audio_path = tmp_path / "clip.mp3"

    with patch("services.ffmpeg_service.subprocess.run") as mock_run:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="ffprobe", timeout=180)
        assert get_duration(audio_path) is None
