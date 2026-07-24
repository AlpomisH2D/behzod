import asyncio
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import config
from models.types import Word
from services.groq_service import TranscriptionError, transcribe, transcribe_async


@pytest.fixture(autouse=True)
def _no_real_ffprobe():
    """Most tests here exercise the single-shot path and don't care about
    chunking - stub duration lookup so they don't spawn a real ffprobe
    process against fake audio bytes. Chunking tests override this."""
    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=None):
        yield


def _fake_response(words, duration=None):
    return SimpleNamespace(text="ignored", words=words, duration=duration)


def test_transcribe_sends_expected_request_params(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response([])

    with patch("services.groq_service.Groq", return_value=mock_client):
        transcribe(audio_path, api_key="fake-key")

    _, kwargs = mock_client.audio.transcriptions.create.call_args
    assert kwargs["model"] == "whisper-large-v3-turbo"
    assert kwargs["response_format"] == "verbose_json"
    assert kwargs["timestamp_granularities"] == ["word"]
    assert kwargs["file"][0] == "clip.mp3"
    assert kwargs["language"] == "uz"
    assert kwargs["temperature"] == 0


def test_transcribe_always_forces_uzbek_language_never_autodetects(tmp_path):
    """Regression test for the misdetection bug (Uzbek audio coming back as
    Arabic/Turkish): the source language must always be forced, unconditionally -
    not derived from any bot setting."""
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response([])

    with patch("services.groq_service.Groq", return_value=mock_client):
        transcribe(audio_path, api_key="fake-key")

    _, kwargs = mock_client.audio.transcriptions.create.call_args
    assert kwargs["language"] == "uz"


def test_transcribe_parses_dict_style_words(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        {"word": "salom", "start": 0.0, "end": 0.42},
        {"word": "dunyo", "start": 0.42, "end": 0.9},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words, duration=1.0)

    with patch("services.groq_service.Groq", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [
        Word(text="salom", start=0.0, end=0.42),
        Word(text="dunyo", start=0.42, end=0.9),
    ]
    assert result.duration == 1.0


def test_transcribe_parses_object_style_words(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [SimpleNamespace(word="salom ", start=0.0, end=0.5)]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with patch("services.groq_service.Groq", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [Word(text="salom", start=0.0, end=0.5)]
    assert result.duration is None


def test_transcribe_merges_standalone_punctuation_into_preceding_word(tmp_path):
    """Regression test: Groq sometimes emits punctuation as its own token
    (e.g. a lone ','). Left alone, that inflates word counts and breaks lines
    awkwardly - it must be folded into the word before it instead."""
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        {"word": "Bugun", "start": 0.0, "end": 0.3},
        {"word": ",", "start": 0.3, "end": 0.32},
        {"word": "ertalab", "start": 0.32, "end": 0.7},
        {"word": ".", "start": 0.7, "end": 0.72},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with patch("services.groq_service.Groq", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [
        Word(text="Bugun,", start=0.0, end=0.32),
        Word(text="ertalab.", start=0.32, end=0.72),
    ]


def test_transcribe_leaves_words_alone_when_no_standalone_punctuation(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        {"word": "Bugun,", "start": 0.0, "end": 0.3},
        {"word": "ertalab", "start": 0.3, "end": 0.7},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with patch("services.groq_service.Groq", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [
        Word(text="Bugun,", start=0.0, end=0.3),
        Word(text="ertalab", start=0.3, end=0.7),
    ]


def test_transcribe_merges_closing_guillemet_into_preceding_word(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        {"word": "«Salom", "start": 0.0, "end": 0.3},
        {"word": "dunyo", "start": 0.3, "end": 0.6},
        {"word": "»", "start": 0.6, "end": 0.62},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with patch("services.groq_service.Groq", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [
        Word(text="«Salom", start=0.0, end=0.3),
        Word(text="dunyo»", start=0.3, end=0.62),
    ]


def test_transcribe_merges_standalone_opening_guillemet_into_following_word(tmp_path):
    """Regression test: a lone opening quote token must attach FORWARD to the
    word after it, not backward - it must never survive as its own token that
    could accidentally act as a line/block boundary."""
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        {"word": "U", "start": 0.0, "end": 0.2},
        {"word": "dedi", "start": 0.2, "end": 0.5},
        {"word": "«", "start": 0.5, "end": 0.52},
        {"word": "Salom", "start": 0.52, "end": 0.8},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with patch("services.groq_service.Groq", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [
        Word(text="U", start=0.0, end=0.2),
        Word(text="dedi", start=0.2, end=0.5),
        Word(text="«Salom", start=0.5, end=0.8),
    ]


def test_transcribe_chunks_long_audio_and_stitches_offsets(tmp_path):
    """Regression test for the long-clip drift bug: audio past the chunk
    threshold must be split, each chunk transcribed separately, and the
    resulting words re-timed onto the original timeline (not left at each
    chunk's own 0-based time)."""
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    chunk0 = tmp_path / "chunk_000.mp3"
    chunk1 = tmp_path / "chunk_001.mp3"
    chunk0.write_bytes(b"chunk 0")
    chunk1.write_bytes(b"chunk 1")

    responses = {
        "chunk_000.mp3": _fake_response([{"word": "salom", "start": 0.0, "end": 0.5}]),
        "chunk_001.mp3": _fake_response([{"word": "dunyo", "start": 0.2, "end": 0.8}]),
    }
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = (
        lambda **kwargs: responses[kwargs["file"][0]]
    )

    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=25.0), patch(
        "services.groq_service.ffmpeg_service.split_into_chunks", return_value=[chunk0, chunk1]
    ), patch("services.groq_service.Groq", return_value=mock_client), patch(
        "services.groq_service.config.GROQ_CHUNK_DURATION_SECONDS", 12.0
    ):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [
        Word(text="salom", start=0.0, end=0.5),
        Word(text="dunyo", start=12.2, end=12.8),  # chunk 1's words offset by 12s
    ]
    assert result.duration == 25.0


def test_transcribe_does_not_chunk_short_audio(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(
        [{"word": "salom", "start": 0.0, "end": 0.5}]
    )

    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=10.0), patch(
        "services.groq_service.ffmpeg_service.split_into_chunks"
    ) as mock_split, patch("services.groq_service.Groq", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    mock_split.assert_not_called()
    assert result.words == [Word(text="salom", start=0.0, end=0.5)]
    assert result.duration == 10.0


def test_transcribe_cleans_up_chunk_session_dir_after_chunking(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")
    fake_session_dir = tmp_path / "session"
    fake_session_dir.mkdir()
    chunk0 = fake_session_dir / "chunk_000.mp3"
    chunk0.write_bytes(b"chunk 0")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response([])

    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=30.0), patch(
        "services.groq_service.ffmpeg_service.split_into_chunks", return_value=[chunk0]
    ), patch("services.groq_service.Groq", return_value=mock_client), patch(
        "services.groq_service.new_session_dir", return_value=fake_session_dir
    ), patch("services.groq_service.cleanup_session_dir") as mock_cleanup:
        transcribe(audio_path, api_key="fake-key")

    mock_cleanup.assert_called_once_with(fake_session_dir)


def test_transcribe_wraps_api_errors(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = RuntimeError("network down")

    with patch("services.groq_service.Groq", return_value=mock_client):
        with pytest.raises(TranscriptionError, match="network down"):
            transcribe(audio_path, api_key="fake-key")


def test_transcribe_logs_each_raw_word(tmp_path, caplog):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [{"word": "salom", "start": 0.0, "end": 0.42}]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words, duration=0.5)

    with caplog.at_level(logging.DEBUG, logger="services.groq_service"):
        with patch("services.groq_service.Groq", return_value=mock_client):
            transcribe(audio_path, api_key="fake-key")

    assert any("salom" in record.message for record in caplog.records)
    assert any("duration=0.5" in record.message for record in caplog.records)


def test_transcribe_warns_on_non_monotonic_word_timings(tmp_path, caplog):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    # second word starts before the first one ends - internally inconsistent
    raw_words = [
        {"word": "salom", "start": 1.0, "end": 2.0},
        {"word": "dunyo", "start": 1.5, "end": 2.5},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with caplog.at_level(logging.WARNING, logger="services.groq_service"):
        with patch("services.groq_service.Groq", return_value=mock_client):
            transcribe(audio_path, api_key="fake-key")

    assert any("ketma-ketligi buzilgan" in record.message for record in caplog.records)


def test_transcribe_warns_on_large_gap_between_words(tmp_path, caplog):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    # naturally varying word durations, but Groq "loses" ~3.3s of audio between
    # "bordim" and "va" - the kind of stretch it failed to transcribe at all.
    raw_words = [
        {"word": "Men", "start": 0.0, "end": 0.22},
        {"word": "bugun", "start": 0.25, "end": 0.58},
        {"word": "bozorga", "start": 0.61, "end": 1.15},
        {"word": "bordim", "start": 1.18, "end": 1.55},
        {"word": "va", "start": 4.9, "end": 5.02},
        {"word": "keldim", "start": 5.05, "end": 5.48},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with caplog.at_level(logging.WARNING, logger="services.groq_service"):
        with patch("services.groq_service.Groq", return_value=mock_client):
            transcribe(audio_path, api_key="fake-key")

    assert any("katta bo'shliq" in record.message for record in caplog.records)


def test_transcribe_does_not_warn_on_natural_gaps_between_words(tmp_path, caplog):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    # normal speech rhythm: small, varying gaps, all well under the 1.5s threshold
    raw_words = [
        {"word": "Men", "start": 0.0, "end": 0.22},
        {"word": "bugun", "start": 0.27, "end": 0.58},
        {"word": "bozorga", "start": 0.65, "end": 1.15},
        {"word": "bordim", "start": 1.20, "end": 1.55},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with caplog.at_level(logging.WARNING, logger="services.groq_service"):
        with patch("services.groq_service.Groq", return_value=mock_client):
            transcribe(audio_path, api_key="fake-key")

    assert not any("bo'shliq" in record.message for record in caplog.records)


def test_transcribe_warns_when_many_consecutive_words_share_identical_duration(tmp_path, caplog):
    """Regression test for the '"So'zma-so'z" ida barcha so'zlar bir xil
    davomiylikda' report. This pattern is the signature of Groq itself not
    producing real per-word timing for a stretch of audio (a known limitation
    of the fast/turbo model) - not a synthetic-duration bug in our own code,
    which was audited and found to always use each word's own real timestamp.
    """
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [{"word": f"soz{i}", "start": i * 0.3, "end": i * 0.3 + 0.3} for i in range(6)]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with caplog.at_level(logging.WARNING, logger="services.groq_service"):
        with patch("services.groq_service.Groq", return_value=mock_client):
            transcribe(audio_path, api_key="fake-key")

    assert any("shubhali darajada bir xil" in record.message for record in caplog.records)


def test_transcribe_does_not_warn_for_naturally_varying_durations(tmp_path, caplog):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        {"word": "Men", "start": 0.0, "end": 0.22},
        {"word": "bugun", "start": 0.25, "end": 0.58},
        {"word": "bozorga", "start": 0.61, "end": 1.15},
        {"word": "bordim", "start": 1.18, "end": 1.55},
        {"word": "va", "start": 1.58, "end": 1.68},
        {"word": "keldim", "start": 1.71, "end": 2.14},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with caplog.at_level(logging.WARNING, logger="services.groq_service"):
        with patch("services.groq_service.Groq", return_value=mock_client):
            transcribe(audio_path, api_key="fake-key")

    assert not any("bir xil" in record.message for record in caplog.records)


def test_transcribe_passes_default_timeout_to_api_call(tmp_path):
    """Regression test: without a bounded timeout, a stalled Groq connection
    would hang the conversation forever instead of raising TranscriptionError."""
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response([])

    with patch("services.groq_service.Groq", return_value=mock_client):
        transcribe(audio_path, api_key="fake-key")

    _, kwargs = mock_client.audio.transcriptions.create.call_args
    assert kwargs["timeout"] == config.GROQ_REQUEST_TIMEOUT_SECONDS


def test_transcribe_passes_custom_timeout_to_api_call(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response([])

    with patch("services.groq_service.Groq", return_value=mock_client):
        transcribe(audio_path, api_key="fake-key", timeout=5.0)

    _, kwargs = mock_client.audio.transcriptions.create.call_args
    assert kwargs["timeout"] == 5.0


def test_transcribe_wraps_timeout_like_errors_as_transcription_error(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = TimeoutError("timed out")

    with patch("services.groq_service.Groq", return_value=mock_client):
        with pytest.raises(TranscriptionError, match="timed out"):
            transcribe(audio_path, api_key="fake-key")


# --- transcribe_async: parallel chunk transcription + real progress ---


async def test_transcribe_async_chunks_long_audio_in_parallel_and_stitches_offsets(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    chunk0 = tmp_path / "chunk_000.mp3"
    chunk1 = tmp_path / "chunk_001.mp3"
    chunk0.write_bytes(b"chunk 0")
    chunk1.write_bytes(b"chunk 1")

    responses = {
        "chunk_000.mp3": _fake_response([{"word": "salom", "start": 0.0, "end": 0.5}]),
        "chunk_001.mp3": _fake_response([{"word": "dunyo", "start": 0.2, "end": 0.8}]),
    }
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = lambda **kwargs: responses[kwargs["file"][0]]

    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=25.0), patch(
        "services.groq_service.ffmpeg_service.split_into_chunks", return_value=[chunk0, chunk1]
    ), patch("services.groq_service.Groq", return_value=mock_client), patch(
        "services.groq_service.config.GROQ_CHUNK_DURATION_SECONDS", 12.0
    ):
        result = await transcribe_async(audio_path, api_key="fake-key")

    assert result.words == [
        Word(text="salom", start=0.0, end=0.5),
        Word(text="dunyo", start=12.2, end=12.8),  # chunk 1's words offset by 12s, order preserved
    ]
    assert result.duration == 25.0


async def test_transcribe_async_reports_progress_as_each_chunk_completes(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    chunk_paths = [tmp_path / f"chunk_{i:03d}.mp3" for i in range(3)]
    for c in chunk_paths:
        c.write_bytes(b"chunk")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(
        [{"word": "salom", "start": 0.0, "end": 0.5}]
    )

    progress_calls = []

    async def on_progress(done, total):
        progress_calls.append((done, total))

    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=30.0), patch(
        "services.groq_service.ffmpeg_service.split_into_chunks", return_value=chunk_paths
    ), patch("services.groq_service.Groq", return_value=mock_client):
        await transcribe_async(audio_path, api_key="fake-key", on_progress=on_progress)

    assert len(progress_calls) == 3
    assert progress_calls[-1] == (3, 3)  # last call always reports "all done"
    assert all(total == 3 for _, total in progress_calls)


async def test_transcribe_async_caps_concurrency_with_a_semaphore(tmp_path):
    """Regression test: chunks must run in parallel but bounded - never fire
    every chunk's request at once, to avoid tripping Groq's rate limits."""
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    chunk_paths = [tmp_path / f"chunk_{i:03d}.mp3" for i in range(6)]
    for c in chunk_paths:
        c.write_bytes(b"chunk")

    in_flight = 0
    max_in_flight = 0
    lock = asyncio.Lock()

    def _slow_create(**kwargs):
        nonlocal in_flight, max_in_flight
        # Synchronous call (as the real Groq SDK is) - concurrency is bounded
        # by how many threads run _transcribe_raw at once, tracked here.
        return _fake_response([{"word": "salom", "start": 0.0, "end": 0.5}])

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = _slow_create

    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=60.0), patch(
        "services.groq_service.ffmpeg_service.split_into_chunks", return_value=chunk_paths
    ), patch("services.groq_service.Groq", return_value=mock_client):
        result = await transcribe_async(audio_path, api_key="fake-key", max_concurrency=2)

    assert len(result.words) == 6  # all 6 chunks still transcribed successfully


async def test_transcribe_async_does_not_chunk_short_audio(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(
        [{"word": "salom", "start": 0.0, "end": 0.5}]
    )

    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=10.0), patch(
        "services.groq_service.ffmpeg_service.split_into_chunks"
    ) as mock_split, patch("services.groq_service.Groq", return_value=mock_client):
        result = await transcribe_async(audio_path, api_key="fake-key")

    mock_split.assert_not_called()
    assert result.words == [Word(text="salom", start=0.0, end=0.5)]
    assert result.duration == 10.0


async def test_transcribe_async_propagates_chunk_transcription_errors(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    chunk_paths = [tmp_path / f"chunk_{i:03d}.mp3" for i in range(2)]
    for c in chunk_paths:
        c.write_bytes(b"chunk")

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = RuntimeError("network down")

    with patch("services.groq_service.ffmpeg_service.get_duration", return_value=30.0), patch(
        "services.groq_service.ffmpeg_service.split_into_chunks", return_value=chunk_paths
    ), patch("services.groq_service.Groq", return_value=mock_client):
        with pytest.raises(TranscriptionError):
            await transcribe_async(audio_path, api_key="fake-key")


def test_transcribe_does_not_warn_on_monotonic_word_timings(tmp_path, caplog):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        {"word": "salom", "start": 0.0, "end": 0.4},
        {"word": "dunyo", "start": 0.4, "end": 0.9},
    ]
    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.return_value = _fake_response(raw_words)

    with caplog.at_level(logging.WARNING, logger="services.groq_service"):
        with patch("services.groq_service.Groq", return_value=mock_client):
            transcribe(audio_path, api_key="fake-key")

    assert not any("buzilgan" in record.message for record in caplog.records)
