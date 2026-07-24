import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable

from elevenlabs import ElevenLabs

import config
from models.types import CharacterTiming, TranscriptionResult, Word
from services import groq_service

logger = logging.getLogger(__name__)

# The source audio is always Uzbek speech - forced unconditionally, same
# reasoning and same rule as groq_service._SOURCE_LANGUAGE. ElevenLabs accepts
# both ISO-639-1 ("uz") and ISO-639-3 ("uzb"); "uzb" is what was requested.
_SOURCE_LANGUAGE = "uzb"


class ElevenLabsTranscriptionError(Exception):
    pass


def transcribe(
    audio_path: Path, api_key: str | None = None, timeout: float | None = None
) -> TranscriptionResult:
    """Sends audio to ElevenLabs Scribe v2 and returns word-level timestamps
    (derived from its more precise character-level timestamps) plus the real
    audio duration.

    `timeout` bounds the request itself (defaults to
    config.ELEVENLABS_REQUEST_TIMEOUT_SECONDS) so a stalled connection raises
    ElevenLabsTranscriptionError instead of hanging forever.
    """
    client = ElevenLabs(
        api_key=api_key or config.ELEVENLABS_API_KEY,
        timeout=timeout if timeout is not None else config.ELEVENLABS_REQUEST_TIMEOUT_SECONDS,
    )
    try:
        with open(audio_path, "rb") as audio_file:
            response = client.speech_to_text.convert(
                file=audio_file,
                model_id=config.ELEVENLABS_STT_MODEL,
                language_code=_SOURCE_LANGUAGE,
                # Character-level is Scribe's most precise mode - word-level
                # timing below is derived from it, not requested directly.
                timestamps_granularity="character",
                diarize=True,
            )
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error for callers
        raise ElevenLabsTranscriptionError(f"ElevenLabs transkripsiya xatosi: {exc}") from exc

    words = _words_from_response(response)
    characters = _characters_from_response(response)
    duration = _get(response, "audio_duration_secs")
    return TranscriptionResult(
        words=words,
        duration=float(duration) if duration is not None else None,
        characters=characters,
    )


def transcribe_with_fallback(
    audio_path: Path, api_key: str | None = None, timeout: float | None = None
) -> TranscriptionResult:
    """Same as transcribe(), but falls back to Groq on any ElevenLabs failure
    (auth error, timeout, rate limit, outage, etc.) so a single job is never
    lost just because ElevenLabs is unavailable - Groq stays fully intact as
    the fallback engine.
    """
    try:
        return transcribe(audio_path, api_key=api_key, timeout=timeout)
    except ElevenLabsTranscriptionError:
        logger.exception(
            "ElevenLabs transkripsiyasi muvaffaqiyatsiz bo'ldi, Groq'ga zaxira sifatida o'tilmoqda"
        )
        return groq_service.transcribe(audio_path)


async def transcribe_with_fallback_async(
    audio_path: Path,
    api_key: str | None = None,
    timeout: float | None = None,
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
) -> TranscriptionResult:
    """Async counterpart to transcribe_with_fallback(). ElevenLabs' own call
    is a single request for the whole clip (not chunked), so `on_progress` has
    nothing to report there - it only fires once the Groq fallback path splits
    long audio into chunks and transcribes them in parallel.
    """
    try:
        return await asyncio.to_thread(transcribe, audio_path, api_key, timeout)
    except ElevenLabsTranscriptionError:
        logger.exception(
            "ElevenLabs transkripsiyasi muvaffaqiyatsiz bo'ldi, Groq'ga zaxira sifatida o'tilmoqda"
        )
        return await groq_service.transcribe_async(audio_path, on_progress=on_progress)


def _get(obj, name: str):
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)


def _words_from_response(response) -> list[Word]:
    raw_words = _get(response, "words") or []
    words: list[Word] = []
    for raw in raw_words:
        if _get(raw, "type") != "word":
            continue  # skip "spacing" and "audio_event" entries - not real words
        text = (_get(raw, "text") or "").strip()
        if not text:
            continue
        raw_characters = _get(raw, "characters")
        if raw_characters:
            start = _get(raw_characters[0], "start")
            end = _get(raw_characters[-1], "end")
        else:
            # No character breakdown for this word (shouldn't normally happen
            # with timestamps_granularity="character") - fall back to the
            # word's own start/end rather than dropping it.
            start = _get(raw, "start")
            end = _get(raw, "end")
        words.append(Word(text=text, start=float(start), end=float(end)))
    return words


def _characters_from_response(response) -> list[CharacterTiming]:
    raw_words = _get(response, "words") or []
    characters: list[CharacterTiming] = []
    for raw in raw_words:
        for raw_char in _get(raw, "characters") or []:
            characters.append(
                CharacterTiming(
                    text=_get(raw_char, "text"),
                    start=float(_get(raw_char, "start")),
                    end=float(_get(raw_char, "end")),
                )
            )
    return characters
