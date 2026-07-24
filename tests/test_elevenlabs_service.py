from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import config
from models.types import CharacterTiming, TranscriptionResult, Word
from services.elevenlabs_service import (
    ElevenLabsTranscriptionError,
    transcribe,
    transcribe_with_fallback,
    transcribe_with_fallback_async,
)


def _char(text, start, end):
    return {"text": text, "start": start, "end": end}


def _word(text, start, end, word_type="word", characters=None):
    return {"text": text, "start": start, "end": end, "type": word_type, "characters": characters}


def _fake_response(words, duration=None):
    return SimpleNamespace(words=words, audio_duration_secs=duration)


def test_transcribe_sends_expected_request_params(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.speech_to_text.convert.return_value = _fake_response([])

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client):
        transcribe(audio_path, api_key="fake-key")

    _, kwargs = mock_client.speech_to_text.convert.call_args
    assert kwargs["model_id"] == config.ELEVENLABS_STT_MODEL
    assert kwargs["language_code"] == "uzb"
    assert kwargs["timestamps_granularity"] == "character"
    assert kwargs["diarize"] is True


def test_transcribe_builds_word_timing_from_character_level_timestamps(tmp_path):
    """Regression test for the spec requirement: word start/end must be
    derived from the first/last CHARACTER timestamp, not just copied from the
    word-level start/end ElevenLabs also provides."""
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        _word(
            "salom", 0.0, 1.0,  # word-level start/end deliberately wrong/coarse
            characters=[_char("s", 0.05, 0.1), _char("a", 0.1, 0.2), _char("lom", 0.2, 0.42)],
        )
    ]
    mock_client = MagicMock()
    mock_client.speech_to_text.convert.return_value = _fake_response(raw_words)

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [Word(text="salom", start=0.05, end=0.42)]


def test_transcribe_falls_back_to_word_level_when_no_characters(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [_word("salom", 0.1, 0.5, characters=None)]
    mock_client = MagicMock()
    mock_client.speech_to_text.convert.return_value = _fake_response(raw_words)

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [Word(text="salom", start=0.1, end=0.5)]


def test_transcribe_skips_spacing_and_audio_event_entries(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        _word("salom", 0.0, 0.3, characters=[_char("salom", 0.0, 0.3)]),
        _word(" ", 0.3, 0.32, word_type="spacing"),
        _word("[music]", 0.32, 1.0, word_type="audio_event"),
        _word("dunyo", 1.0, 1.4, characters=[_char("dunyo", 1.0, 1.4)]),
    ]
    mock_client = MagicMock()
    mock_client.speech_to_text.convert.return_value = _fake_response(raw_words)

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.words == [
        Word(text="salom", start=0.0, end=0.3),
        Word(text="dunyo", start=1.0, end=1.4),
    ]


def test_transcribe_returns_duration_from_audio_duration_secs(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.speech_to_text.convert.return_value = _fake_response([], duration=49.5)

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.duration == 49.5


def test_transcribe_exposes_character_level_timings(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [
        _word("hi", 0.0, 0.2, characters=[_char("h", 0.0, 0.1), _char("i", 0.1, 0.2)]),
    ]
    mock_client = MagicMock()
    mock_client.speech_to_text.convert.return_value = _fake_response(raw_words)

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client):
        result = transcribe(audio_path, api_key="fake-key")

    assert result.characters == [
        CharacterTiming(text="h", start=0.0, end=0.1),
        CharacterTiming(text="i", start=0.1, end=0.2),
    ]


def test_transcribe_wraps_api_errors(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.speech_to_text.convert.side_effect = RuntimeError("401 unauthorized")

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client):
        with pytest.raises(ElevenLabsTranscriptionError, match="401 unauthorized"):
            transcribe(audio_path, api_key="bad-key")


def test_transcribe_with_fallback_uses_elevenlabs_result_on_success(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [_word("salom", 0.0, 0.3, characters=[_char("salom", 0.0, 0.3)])]
    mock_client = MagicMock()
    mock_client.speech_to_text.convert.return_value = _fake_response(raw_words)

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client), patch(
        "services.elevenlabs_service.groq_service.transcribe"
    ) as mock_groq:
        result = transcribe_with_fallback(audio_path, api_key="fake-key")

    mock_groq.assert_not_called()
    assert result.words == [Word(text="salom", start=0.0, end=0.3)]


def test_transcribe_with_fallback_falls_back_to_groq_on_elevenlabs_failure(tmp_path):
    """Core regression test for the fallback requirement: a broken/invalid
    ElevenLabs key (or any other failure) must not break the job - it must
    fall through to Groq automatically."""
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.speech_to_text.convert.side_effect = RuntimeError("invalid_api_key")
    fallback_result = TranscriptionResult(words=[Word("salom", 0.0, 0.3)], duration=0.3)

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client), patch(
        "services.elevenlabs_service.groq_service.transcribe", return_value=fallback_result
    ) as mock_groq:
        result = transcribe_with_fallback(audio_path, api_key="bad-key")

    mock_groq.assert_called_once_with(audio_path)
    assert result == fallback_result


async def test_transcribe_with_fallback_async_uses_elevenlabs_result_on_success(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    raw_words = [_word("salom", 0.0, 0.3, characters=[_char("salom", 0.0, 0.3)])]
    mock_client = MagicMock()
    mock_client.speech_to_text.convert.return_value = _fake_response(raw_words)

    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client), patch(
        "services.elevenlabs_service.groq_service.transcribe_async"
    ) as mock_groq:
        result = await transcribe_with_fallback_async(audio_path, api_key="fake-key")

    mock_groq.assert_not_called()
    assert result.words == [Word(text="salom", start=0.0, end=0.3)]


async def test_transcribe_with_fallback_async_falls_back_to_groq_async_on_failure(tmp_path):
    audio_path = tmp_path / "clip.mp3"
    audio_path.write_bytes(b"fake audio bytes")

    mock_client = MagicMock()
    mock_client.speech_to_text.convert.side_effect = RuntimeError("invalid_api_key")
    fallback_result = TranscriptionResult(words=[Word("salom", 0.0, 0.3)], duration=0.3)

    progress_callback = AsyncMock()
    with patch("services.elevenlabs_service.ElevenLabs", return_value=mock_client), patch(
        "services.elevenlabs_service.groq_service.transcribe_async",
        new=AsyncMock(return_value=fallback_result),
    ) as mock_groq:
        result = await transcribe_with_fallback_async(audio_path, api_key="bad-key", on_progress=progress_callback)

    mock_groq.assert_awaited_once_with(audio_path, on_progress=progress_callback)
    assert result == fallback_result
