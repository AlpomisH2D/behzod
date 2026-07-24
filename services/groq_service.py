import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable

from groq import Groq

import config
from models.types import TranscriptionResult, Word
from services import ffmpeg_service
from utils.tempfiles import cleanup_session_dir, new_session_dir

logger = logging.getLogger(__name__)

# The source audio is always Uzbek speech, regardless of which subtitle
# language the user picked in the bot (that setting only controls the later
# translation step). Auto-detection has been observed to misidentify Uzbek
# audio as Arabic or Turkish, so the source language is always forced here.
_SOURCE_LANGUAGE = "uz"

# A gap this large between two consecutive words usually means Groq lost track
# of a stretch of audio (silence misdetected as speech-end, a segment it
# failed to transcribe, etc).
_BIG_GAP_THRESHOLD_SECONDS = 1.5

# Real speech has naturally varying word lengths. This many consecutive words
# sharing the exact same duration is a strong signal that Groq did not actually
# produce fine-grained per-word timestamps for this stretch (a known limitation
# of the faster "turbo" models), rather than a bug in how we use its response.
_UNIFORM_DURATION_RUN_THRESHOLD = 5

# Standalone punctuation tokens are folded into a neighboring word so they
# never count as their own "word" in line-splitting or word-count limits, and
# never accidentally act as a line/block boundary by themselves.
# Trailing marks (sentence punctuation, a closing quote) attach to the word
# before them; a leading opening quote attaches to the word after it.
_TRAILING_PUNCTUATION_CHARS = set(",.!?;:»”’\"")
_LEADING_PUNCTUATION_CHARS = set("«“‘")


class TranscriptionError(Exception):
    pass


def transcribe(
    audio_path: Path, api_key: str | None = None, timeout: float | None = None
) -> TranscriptionResult:
    """Sends audio to Groq Whisper and returns word-level timestamps plus audio duration.

    Audio longer than config.GROQ_CHUNK_THRESHOLD_SECONDS is split into
    config.GROQ_CHUNK_DURATION_SECONDS chunks and transcribed chunk by chunk,
    then stitched back together with corrected time offsets - Whisper's
    word-level timestamps are estimated from attention weights and drift more
    the longer the audio is, so this bounds how much any one call can drift.

    `timeout` bounds each individual Groq request (defaults to
    config.GROQ_REQUEST_TIMEOUT_SECONDS) so a stalled connection raises
    TranscriptionError instead of leaving the conversation hanging forever.
    """
    duration = ffmpeg_service.get_duration(audio_path)
    if duration is not None and duration > config.GROQ_CHUNK_THRESHOLD_SECONDS:
        result = _transcribe_chunked(audio_path, duration, api_key=api_key, timeout=timeout)
    else:
        result = _transcribe_raw(audio_path, api_key=api_key, timeout=timeout)
        if duration is not None:
            result = TranscriptionResult(words=result.words, duration=duration)

    _log_raw_words(audio_path, result.words, result.duration)
    _warn_on_timing_anomalies(audio_path, result.words)
    return result


def _transcribe_chunked(
    audio_path: Path,
    total_duration: float,
    api_key: str | None = None,
    timeout: float | None = None,
) -> TranscriptionResult:
    session_dir = new_session_dir()
    try:
        chunk_paths = ffmpeg_service.split_into_chunks(
            audio_path, session_dir, config.GROQ_CHUNK_DURATION_SECONDS
        )
        logger.info(
            "Groq: %.1fs audio %d ta bo'lakka bo'lib transkripsiya qilinmoqda (%s)",
            total_duration, len(chunk_paths), audio_path.name,
        )
        all_words: list[Word] = []
        for index, chunk_path in enumerate(chunk_paths):
            try:
                chunk_result = _transcribe_raw(chunk_path, api_key=api_key, timeout=timeout)
            except TranscriptionError:
                logger.exception("Groq: %d/%d bo'lakni transkripsiya qilishda xato", index + 1, len(chunk_paths))
                raise
            logger.debug("Groq: bo'lak %d/%d tayyor, %d so'z", index + 1, len(chunk_paths), len(chunk_result.words))
            offset = index * config.GROQ_CHUNK_DURATION_SECONDS
            all_words.extend(
                Word(text=w.text, start=w.start + offset, end=w.end + offset)
                for w in chunk_result.words
            )
        return TranscriptionResult(words=all_words, duration=total_duration)
    finally:
        cleanup_session_dir(session_dir)


async def transcribe_async(
    audio_path: Path,
    api_key: str | None = None,
    timeout: float | None = None,
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    max_concurrency: int | None = None,
) -> TranscriptionResult:
    """Async counterpart to transcribe() - long audio's chunks are transcribed
    in PARALLEL (bounded by `max_concurrency`) instead of one after another,
    so a ~2min clip doesn't take as long as 8-12 sequential API round-trips.

    `on_progress(completed, total)` is awaited each time a chunk finishes (in
    completion order, not necessarily chunk order) so the caller can show real
    "N/M qism" progress instead of a generic animation. Only called for the
    chunked path - short, unchunked audio has nothing meaningful to report.
    """
    duration = await asyncio.to_thread(ffmpeg_service.get_duration, audio_path)
    if duration is not None and duration > config.GROQ_CHUNK_THRESHOLD_SECONDS:
        result = await _transcribe_chunked_async(
            audio_path, duration, api_key=api_key, timeout=timeout,
            on_progress=on_progress, max_concurrency=max_concurrency,
        )
    else:
        result = await asyncio.to_thread(_transcribe_raw, audio_path, api_key, timeout)
        if duration is not None:
            result = TranscriptionResult(words=result.words, duration=duration)

    _log_raw_words(audio_path, result.words, result.duration)
    _warn_on_timing_anomalies(audio_path, result.words)
    return result


async def _transcribe_chunked_async(
    audio_path: Path,
    total_duration: float,
    api_key: str | None = None,
    timeout: float | None = None,
    on_progress: Callable[[int, int], Awaitable[None]] | None = None,
    max_concurrency: int | None = None,
) -> TranscriptionResult:
    max_concurrency = max_concurrency or config.GROQ_MAX_CONCURRENT_CHUNKS
    session_dir = new_session_dir()
    try:
        chunk_paths = await asyncio.to_thread(
            ffmpeg_service.split_into_chunks, audio_path, session_dir, config.GROQ_CHUNK_DURATION_SECONDS
        )
        total = len(chunk_paths)
        logger.info(
            "Groq: %.1fs audio %d ta bo'lakka bo'lib PARALLEL transkripsiya qilinmoqda (max %d bir vaqtda, %s)",
            total_duration, total, max_concurrency, audio_path.name,
        )

        semaphore = asyncio.Semaphore(max_concurrency)
        progress_lock = asyncio.Lock()
        completed_count = 0

        async def _run_one(index: int, chunk_path: Path):
            nonlocal completed_count
            async with semaphore:
                try:
                    chunk_result = await asyncio.to_thread(_transcribe_raw, chunk_path, api_key, timeout)
                except TranscriptionError:
                    logger.exception("Groq: %d/%d bo'lakni transkripsiya qilishda xato", index + 1, total)
                    raise
            async with progress_lock:
                completed_count += 1
                done = completed_count
            logger.debug("Groq: bo'lak %d/%d tayyor, %d so'z", index + 1, total, len(chunk_result.words))
            if on_progress is not None:
                await on_progress(done, total)
            return index, chunk_result

        results = await asyncio.gather(*(_run_one(i, p) for i, p in enumerate(chunk_paths)))
        results.sort(key=lambda r: r[0])  # gather() itself already preserves this order; sort is just explicit

        all_words: list[Word] = []
        for index, chunk_result in results:
            offset = index * config.GROQ_CHUNK_DURATION_SECONDS
            all_words.extend(
                Word(text=w.text, start=w.start + offset, end=w.end + offset)
                for w in chunk_result.words
            )
        return TranscriptionResult(words=all_words, duration=total_duration)
    finally:
        cleanup_session_dir(session_dir)


def _transcribe_raw(
    audio_path: Path, api_key: str | None = None, timeout: float | None = None
) -> TranscriptionResult:
    """One raw Groq API call for a single audio file - no chunking, no logging."""
    client = Groq(api_key=api_key or config.GROQ_API_KEY)
    try:
        with open(audio_path, "rb") as audio_file:
            response = client.audio.transcriptions.create(
                file=(audio_path.name, audio_file.read()),
                model=config.GROQ_TRANSCRIBE_MODEL,
                language=_SOURCE_LANGUAGE,
                # Deterministic decoding - temperature>0 lets Whisper "guess" a
                # plausible-sounding word when it's unsure, which is the main
                # source of misheard-word substitutions on Uzbek audio.
                temperature=0,
                response_format="verbose_json",
                timestamp_granularities=["word"],
                timeout=timeout if timeout is not None else config.GROQ_REQUEST_TIMEOUT_SECONDS,
            )
    except Exception as exc:  # noqa: BLE001 - re-raised as a domain error for callers
        raise TranscriptionError(f"Groq transkripsiya xatosi: {exc}") from exc

    words = _merge_punctuation_tokens(_parse_words(response))
    duration = _parse_duration(response)
    return TranscriptionResult(words=words, duration=duration)


def _parse_words(response) -> list[Word]:
    raw_words = getattr(response, "words", None) or []
    words: list[Word] = []
    for raw in raw_words:
        text = raw.get("word") if isinstance(raw, dict) else raw.word
        start = raw.get("start") if isinstance(raw, dict) else raw.start
        end = raw.get("end") if isinstance(raw, dict) else raw.end
        words.append(Word(text=text.strip(), start=float(start), end=float(end)))
    return words


def _is_only_chars(text: str, allowed: set[str]) -> bool:
    stripped = text.strip()
    return bool(stripped) and all(ch in allowed for ch in stripped)


def _merge_punctuation_tokens(words: list[Word]) -> list[Word]:
    """Folds a standalone punctuation token into a neighboring word so it's
    never treated as its own word downstream - neither in word-count limits
    nor as an accidental line/block split point. Trailing marks (a lone ",",
    ".", closing quote "»"/'"') attach to the word before them; a leading
    opening quote ("«") attaches to the word after it.
    """
    # Pass 1: fold trailing punctuation onto the previous word.
    trailing_merged: list[Word] = []
    for w in words:
        if trailing_merged and _is_only_chars(w.text, _TRAILING_PUNCTUATION_CHARS):
            prev = trailing_merged[-1]
            trailing_merged[-1] = Word(text=prev.text + w.text, start=prev.start, end=w.end)
        else:
            trailing_merged.append(w)

    # Pass 2: fold a leading opening quote onto the next word.
    result: list[Word] = []
    i = 0
    n = len(trailing_merged)
    while i < n:
        w = trailing_merged[i]
        if _is_only_chars(w.text, _LEADING_PUNCTUATION_CHARS) and i + 1 < n:
            nxt = trailing_merged[i + 1]
            result.append(Word(text=w.text + nxt.text, start=w.start, end=nxt.end))
            i += 2
        else:
            result.append(w)
            i += 1
    return result


def _parse_duration(response) -> float | None:
    raw_duration = getattr(response, "duration", None)
    return float(raw_duration) if raw_duration is not None else None


def _log_raw_words(audio_path: Path, words: list[Word], duration: float | None) -> None:
    logger.debug("Groq transkripsiya: %s, duration=%s, %d so'z", audio_path.name, duration, len(words))
    for i, w in enumerate(words):
        logger.debug("  [%d] %r start=%.3f end=%.3f", i, w.text, w.start, w.end)


def _warn_on_timing_anomalies(audio_path: Path, words: list[Word]) -> None:
    """Flags Groq responses whose own word timings look unreliable.

    These checks exist to tell "our code fabricated a bad timestamp" apart
    from "Groq's own response already has bad/imprecise timestamps" - the
    former is a bug to fix here, the latter is an upstream data-quality issue
    we can only detect and log, not correct.
    """
    for prev, cur in zip(words, words[1:]):
        if cur.start < prev.end:
            logger.warning(
                "Groq vaqt ketma-ketligi buzilgan (%s): %r end=%.3f -> %r start=%.3f",
                audio_path.name, prev.text, prev.end, cur.text, cur.start,
            )
        else:
            gap = cur.start - prev.end
            if gap > _BIG_GAP_THRESHOLD_SECONDS:
                logger.warning(
                    "Groq so'zlar orasida katta bo'shliq bor (%s): %r end=%.3f -> "
                    "%r start=%.3f (%.2fs farq) - Groq audio oralig'ini yo'qotgan bo'lishi mumkin",
                    audio_path.name, prev.text, prev.end, cur.text, cur.start, gap,
                )
    for w in words:
        if w.end < w.start:
            logger.warning(
                "Groq so'zining end vaqti start'dan oldin (%s): %r start=%.3f end=%.3f",
                audio_path.name, w.text, w.start, w.end,
            )

    _warn_if_suspiciously_uniform(audio_path, words)


def _warn_if_suspiciously_uniform(audio_path: Path, words: list[Word]) -> None:
    run_length = 1
    for prev, cur in zip(words, words[1:]):
        prev_duration = round(prev.end - prev.start, 3)
        cur_duration = round(cur.end - cur.start, 3)
        if cur_duration == prev_duration:
            run_length += 1
        else:
            run_length = 1
        if run_length == _UNIFORM_DURATION_RUN_THRESHOLD:
            logger.warning(
                "Groq so'z davomiyliklari shubhali darajada bir xil (%s): kamida %d ta "
                "ketma-ket so'z %.3fs davomiylikka ega - bu odatda Groq'ning o'zi "
                "(ayniqsa 'turbo' model) haqiqiy so'z darajasidagi vaqtni bermayotganini "
                "bildiradi, bizning kodimizdagi xato emas",
                audio_path.name, _UNIFORM_DURATION_RUN_THRESHOLD, cur_duration,
            )
            return
