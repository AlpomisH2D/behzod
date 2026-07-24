import asyncio
import contextlib
import logging
import re
from datetime import datetime, timezone

from telegram import Message, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import config
from bot.i18n import animation_frames, t
from bot.keyboards import (
    NAV_BACK,
    NAV_CANCEL,
    TRANSCRIPT_CONFIRM,
    TRANSCRIPT_EDIT,
    feedback_keyboard,
    format_choice_keyboard,
    hub_menu_keyboard,
    script_source_keyboard,
    style_choice_keyboard,
    subtitle_language_keyboard,
    transcript_confirm_keyboard,
)
from bot.language_utils import get_user_language
from bot.states import State
from db import repository
from models.types import (
    OUTPUT_FORMATS,
    SUPPORTED_OUTPUT_FORMATS,
    AlignedWord,
    SubtitleBlock,
    SubtitleStyle,
    Word,
)
from services import align_service, claude_service, elevenlabs_service, ffmpeg_service, srt_service
from services.ffmpeg_service import FfmpegError, UnsupportedFormatError
from services.groq_service import TranscriptionError
from utils.tempfiles import cleanup_session_dir, new_session_dir

logger = logging.getLogger(__name__)

_ANIMATION_INTERVAL_SECONDS = 1.5
_DEFAULT_STYLE = SubtitleStyle.AI_CHOICE
_DEFAULT_FORMAT = "srt"
_DEFAULT_SUBLANG = "uz"

# Telegram's own hard limit is ~4096 chars per message - stay well under it so
# the confirm/edit keyboard always fits in the same message as the transcript.
_TRANSCRIPT_PREVIEW_LIMIT = 3500


class _JobFailed(Exception):
    """Raised internally to short-circuit `_run_transcription_phase`/`_finish_job`
    with a user-facing message, without losing the animation-cleanup `finally` block."""


def _pick_media(message: Message):
    if message.video:
        return message.video, message.video.file_name or f"{message.video.file_unique_id}.mp4", "video"
    if message.audio:
        return message.audio, message.audio.file_name or f"{message.audio.file_unique_id}.mp3", "audio"
    if message.voice:
        return message.voice, f"{message.voice.file_unique_id}.ogg", "voice"
    if message.document:
        return (
            message.document,
            message.document.file_name or message.document.file_unique_id,
            "document",
        )
    return None, None, None


async def receive_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    message = update.message
    lang = get_user_language(update)
    media, filename, media_kind = _pick_media(message)
    if media is None:
        await message.reply_text(t("media.unsupported", lang))
        return ConversationHandler.END

    session_dir = new_session_dir()
    context.user_data["session_dir"] = session_dir

    # A flat timeout sized for a short clip kills a large file on a slow
    # connection well before it's actually done downloading - scale it by the
    # file's own reported size instead.
    file_size_mb = (getattr(media, "file_size", None) or 0) / (1024 * 1024)
    download_timeout = max(config.FILE_DOWNLOAD_TIMEOUT_SECONDS, file_size_mb * config.FILE_DOWNLOAD_SECONDS_PER_MB)

    input_path = session_dir / filename
    try:
        tg_file = await asyncio.wait_for(media.get_file(), timeout=download_timeout)
        await asyncio.wait_for(
            tg_file.download_to_drive(custom_path=input_path),
            timeout=download_timeout,
        )
    except asyncio.TimeoutError:
        logger.warning("Fayl yuklab olish timeout bo'ldi (%.0fs): %s", download_timeout, filename)
        await message.reply_text(t("media.download_timeout", lang))
        cleanup_session_dir(session_dir)
        context.user_data.clear()
        return ConversationHandler.END
    except Exception:
        logger.exception("Faylni yuklab olishda kutilmagan xato: %s", filename)
        await message.reply_text(t("media.download_timeout", lang))
        cleanup_session_dir(session_dir)
        context.user_data.clear()
        return ConversationHandler.END
    logger.debug("Fayl yuklab olindi: %s (%.1f MB)", filename, file_size_mb)

    try:
        # ensure_audio() shells out to ffmpeg for video inputs - run it off the
        # event loop so a slow transcode doesn't stall every other chat the bot
        # is serving at the same time.
        audio_path = await asyncio.to_thread(ffmpeg_service.ensure_audio, input_path, session_dir)
    except UnsupportedFormatError:
        await message.reply_text(t("media.unsupported", lang))
        cleanup_session_dir(session_dir)
        context.user_data.clear()
        return ConversationHandler.END
    except FfmpegError:
        logger.exception("ffmpeg audio ajratishda xato: %s", filename)
        await message.reply_text(t("media.ffmpeg_error", lang))
        cleanup_session_dir(session_dir)
        context.user_data.clear()
        return ConversationHandler.END
    logger.debug("Audio tayyor: %s", audio_path.name)

    size_mb = audio_path.stat().st_size / (1024 * 1024)
    if size_mb > config.MAX_AUDIO_FILE_SIZE_MB:
        await message.reply_text(
            t("media.too_large", lang, size=f"{size_mb:.1f}", limit=config.MAX_AUDIO_FILE_SIZE_MB)
        )
        cleanup_session_dir(session_dir)
        context.user_data.clear()
        return ConversationHandler.END

    context.user_data["audio_path"] = audio_path
    context.user_data["original_filename"] = filename
    context.user_data["media_kind"] = media_kind

    # Section D: if the user has saved defaults and turned on auto-apply, skip
    # the hub entirely and go straight to the transcription-source question,
    # using their saved style/language/format instead of per-job choices.
    settings = repository.get_settings(update.effective_user.id)
    if settings.auto_apply_enabled:
        context.user_data["style"] = SubtitleStyle(settings.default_word_style)
        context.user_data["output_format"] = settings.default_format
        context.user_data["subtitle_language"] = settings.default_language
        await message.reply_text(t("script_source.prompt", lang), reply_markup=script_source_keyboard(lang))
        return State.WAITING_SCRIPT_SOURCE_CHOICE

    # The style row pre-selects whichever word/line style this user last
    # explicitly picked in the hub (not yet "touched" this session, so no
    # checkmark shows) - "AI ixtiyorida" until they've ever picked one.
    context.user_data["style"] = SubtitleStyle(settings.last_word_style)

    await message.reply_text(t("hub.intro", lang), reply_markup=_hub_keyboard(context, lang))
    return State.WAITING_HUB_MENU


# --- Settings hub: one message, 3 sub-menus (style / subtitle language / format) + Tayyor ---


def _hub_keyboard(context: ContextTypes.DEFAULT_TYPE, lang: str):
    style = context.user_data.get("style", _DEFAULT_STYLE)
    output_format = context.user_data.get("output_format", _DEFAULT_FORMAT)
    subtitle_language = context.user_data.get("subtitle_language", _DEFAULT_SUBLANG)
    touched = context.user_data.setdefault("hub_touched", set())
    return hub_menu_keyboard(style, subtitle_language, output_format, touched, lang)


async def _show_hub(query, context: ContextTypes.DEFAULT_TYPE, lang: str) -> int:
    await query.edit_message_text(t("hub.intro", lang), reply_markup=_hub_keyboard(context, lang))
    return State.WAITING_HUB_MENU


async def hub_row_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_user_language(update)
    target = query.data.split(":", 1)[1]
    if target == "style":
        await query.edit_message_text(t("hub.style_prompt", lang), reply_markup=style_choice_keyboard(lang))
        return State.WAITING_STYLE_CHOICE
    if target == "sublang":
        await query.edit_message_text(t("hub.sublang_prompt", lang), reply_markup=subtitle_language_keyboard(lang))
        return State.WAITING_SUBLANG_CHOICE
    await query.edit_message_text(t("hub.format_prompt", lang), reply_markup=format_choice_keyboard(lang))
    return State.WAITING_FORMAT_CHOICE


async def hub_done_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_user_language(update)
    await query.edit_message_text(
        t("script_source.prompt", lang),
        reply_markup=script_source_keyboard(lang),
    )
    return State.WAITING_SCRIPT_SOURCE_CHOICE


async def hub_cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _cancel_from_nav(update, context)


async def hub_submenu_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await _show_hub(query, context, get_user_language(update))


# --- Sub-menu: style ---


async def style_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    style = SubtitleStyle(query.data.split(":", 1)[1])
    context.user_data["style"] = style
    context.user_data.setdefault("hub_touched", set()).add("style")
    # Remembered for next time - independent of the Settings-screen default.
    repository.update_last_word_style(update.effective_user.id, style.value)
    return await _show_hub(query, context, get_user_language(update))


# --- Sub-menu: output format ---


async def format_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    fmt = query.data.split(":", 1)[1]
    context.user_data["output_format"] = fmt
    context.user_data.setdefault("hub_touched", set()).add("format")
    return await _show_hub(query, context, get_user_language(update))


# --- Sub-menu: subtitle output language (independent of bot UI language) ---


async def sublang_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    sublang = query.data.split(":", 1)[1]
    context.user_data["subtitle_language"] = sublang
    context.user_data.setdefault("hub_touched", set()).add("sublang")
    return await _show_hub(query, context, get_user_language(update))


# --- Step 4: transcription source ---


async def script_source_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_user_language(update)
    choice = query.data.split(":", 1)[1]
    if choice == "manual":
        await query.edit_message_text(t("script_source.manual_prompt", lang))
        return State.WAITING_SCRIPT_TEXT

    await query.edit_message_text(t("script_source.auto_starting", lang))
    return await _run_transcription_phase(update, context, original_text=None)


async def receive_script_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await _run_transcription_phase(update, context, original_text=update.message.text)


# --- Processing animation (section F) - the fallback shown until real chunk
# progress (section A) is known, or for engines that don't chunk at all ---


async def _animate_processing(chat_id: int, message_id: int, context: ContextTypes.DEFAULT_TYPE, lang: str) -> None:
    frames = animation_frames(lang)
    frame_index = 0
    try:
        while True:
            await asyncio.sleep(_ANIMATION_INTERVAL_SECONDS)
            frame_index = (frame_index + 1) % len(frames)
            await context.bot.edit_message_text(frames[frame_index], chat_id=chat_id, message_id=message_id)
    except asyncio.CancelledError:
        pass
    except Exception:  # noqa: BLE001 - a failed animation tick must never crash the job
        logger.exception("Animatsiya xabarini yangilashda xato")


def _build_transcript_text(words) -> str:
    return " ".join(w.text for w in words)


def _truncate_transcript(text: str, lang: str) -> str:
    if len(text) <= _TRANSCRIPT_PREVIEW_LIMIT:
        return text
    note = t("transcript.truncated_note", lang)
    return text[: _TRANSCRIPT_PREVIEW_LIMIT - len(note)].rstrip() + note


async def _run_transcription_phase(
    update: Update, context: ContextTypes.DEFAULT_TYPE, original_text: str | None
) -> int:
    """Phase 1: download -> transcribe (parallel chunks + real progress, see
    Section A) -> align. Ends at a transcript-confirmation prompt (Section B)
    instead of going straight to line-splitting - `_finish_job` only runs
    once the user has confirmed or corrected the transcript.
    """
    chat_id = update.effective_chat.id
    lang = get_user_language(update)

    progress_message = await context.bot.send_message(chat_id, animation_frames(lang)[0])
    animation_task = asyncio.create_task(
        _animate_processing(chat_id, progress_message.message_id, context, lang)
    )

    async def on_chunk_progress(done: int, total: int) -> None:
        # Real per-chunk progress replaces the generic dot animation the
        # moment the total chunk count is actually known.
        if not animation_task.done():
            animation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await animation_task
        try:
            await context.bot.edit_message_text(
                t("job.chunk_progress", lang, done=done, total=total),
                chat_id=chat_id, message_id=progress_message.message_id,
            )
        except Exception:  # noqa: BLE001 - a failed progress tick must never crash the job
            logger.exception("Progress xabarini yangilashda xato")

    error_text: str | None = None
    try:
        audio_path = context.user_data["audio_path"]

        # A flat timeout sized for a short clip fires well before a longer one
        # (~2min+) finishes transcribing - ElevenLabs transcribes the whole
        # clip in a single call (not chunked), so its timeout must scale with
        # the audio's own duration. Groq's per-chunk timeout stays flat since
        # each chunk is a fixed short length regardless of the clip's total
        # length (see groq_service._transcribe_chunked_async).
        audio_duration_hint = await asyncio.to_thread(ffmpeg_service.get_duration, audio_path)
        elevenlabs_timeout = max(
            config.ELEVENLABS_REQUEST_TIMEOUT_SECONDS,
            (audio_duration_hint or 0) * config.ELEVENLABS_TIMEOUT_SECONDS_PER_AUDIO_SECOND,
        )
        logger.info(
            "Transkripsiya boshlandi: %s (davomiylik=%s, timeout=%.0fs)",
            audio_path.name, audio_duration_hint, elevenlabs_timeout,
        )
        try:
            # ElevenLabs Scribe v2 is the primary engine; on any failure it
            # falls back to Groq automatically for this one job. Groq's own
            # chunks (if the clip is long enough to need them) are
            # transcribed in parallel, reporting real progress as they finish.
            transcription = await elevenlabs_service.transcribe_with_fallback_async(
                audio_path, timeout=elevenlabs_timeout, on_progress=on_chunk_progress
            )
        except TranscriptionError as exc:
            logger.exception("Transkripsiya muvaffaqiyatsiz bo'ldi: %s", audio_path.name)
            raise _JobFailed(t("job.transcription_error", lang, error=exc)) from exc
        logger.info("Transkripsiya tugadi: %s, %d so'z", audio_path.name, len(transcription.words))

        context.user_data["groq_words"] = transcription.words
        context.user_data["audio_duration"] = transcription.duration
        aligned = align_service.align_words(original_text, transcription.words, transcription.duration)
        context.user_data["aligned_words"] = aligned
        context.user_data["transcript_text"] = _build_transcript_text(aligned)
    except _JobFailed as exc:
        error_text = str(exc)
    except Exception:  # noqa: BLE001 - last-resort guard so the animation always gets cleaned up
        logger.exception("Kutilmagan xato")
        error_text = t("job.unexpected_error", lang)
    finally:
        if not animation_task.done():
            animation_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await animation_task

    if error_text:
        await context.bot.edit_message_text(error_text, chat_id=chat_id, message_id=progress_message.message_id)
        _cleanup(context)
        return ConversationHandler.END

    preview = _truncate_transcript(context.user_data["transcript_text"], lang)
    await context.bot.edit_message_text(
        t("transcript.confirm_prompt", lang, text=preview),
        chat_id=chat_id, message_id=progress_message.message_id,
        reply_markup=transcript_confirm_keyboard(lang),
    )
    return State.WAITING_TRANSCRIPT_CONFIRMATION


# --- Transcript confirmation (Section B) ---


async def transcript_confirm_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    return await _finish_job(update, context)


async def transcript_edit_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = get_user_language(update)
    await query.edit_message_text(t("transcript.edit_prompt", lang))
    return State.WAITING_TRANSCRIPT_CORRECTION


async def receive_transcript_correction(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    corrected_text = update.message.text
    raw_words = context.user_data.get("groq_words", [])
    audio_duration = context.user_data.get("audio_duration")
    aligned = align_service.align_words(corrected_text, raw_words, audio_duration)
    context.user_data["aligned_words"] = aligned
    context.user_data["transcript_text"] = _build_transcript_text(aligned)
    return await _finish_job(update, context)


# --- Phase 2: line-splitting -> translate -> format -> deliver ---


async def _finish_job(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    lang = get_user_language(update)
    aligned: list[AlignedWord] = context.user_data.get("aligned_words", [])
    style = context.user_data.get("style", SubtitleStyle.AI_CHOICE)

    progress_message = await context.bot.send_message(chat_id, animation_frames(lang)[0])
    animation_task = asyncio.create_task(
        _animate_processing(chat_id, progress_message.message_id, context, lang)
    )

    error_text: str | None = None
    blocks: list[SubtitleBlock] = []
    format_notice: str | None = None
    out_path = None

    try:
        settings = repository.get_settings(user_id)
        claude_timeout = max(
            config.CLAUDE_REQUEST_TIMEOUT_SECONDS, len(aligned) * config.CLAUDE_TIMEOUT_SECONDS_PER_WORD
        )
        try:
            blocks = await asyncio.to_thread(
                lambda: claude_service.split_with_fallback(
                    aligned, style, visual_template=settings.visual_template, timeout=claude_timeout
                )
            )
        except Exception as exc:  # noqa: BLE001 - last-resort guard, fallback already tried internally
            logger.exception("Subtitr qatorlarga bo'lishda kutilmagan xato")
            raise _JobFailed(t("job.split_error", lang)) from exc
        logger.info("Qatorlarga bo'lindi: %d blok", len(blocks))

        subtitle_language = context.user_data.get("subtitle_language", "uz")
        if subtitle_language != "uz":
            try:
                blocks = await asyncio.to_thread(
                    lambda: claude_service.translate_lines(blocks, subtitle_language, timeout=claude_timeout)
                )
                logger.info("Tarjima tugadi: %s", subtitle_language)
            except claude_service.TranslationError:
                logger.exception("Subtitr tarjimasida xato, o'zbekcha matn bilan davom etilmoqda")

        _log_block_timing_diagnostics(blocks, context.user_data.get("groq_words", []))

        requested_format = context.user_data.get("output_format", "srt")
        output_format = requested_format if requested_format in SUPPORTED_OUTPUT_FORMATS else "srt"
        if requested_format != output_format:
            format_notice = t("job.format_notice", lang, requested=OUTPUT_FORMATS[requested_format])

        session_dir = context.user_data["session_dir"]
        extension = srt_service.file_extension_for_format(output_format)
        out_path = session_dir / f"subtitr.{extension}"
        try:
            srt_service.write_subtitle_file(blocks, out_path, output_format)
        except Exception as exc:  # noqa: BLE001 - last-resort guard, subtitle-writing must never fail silently
            logger.exception("Subtitr faylini yozishda xato: %s", out_path)
            raise _JobFailed(t("job.unexpected_error", lang)) from exc
        logger.info("Subtitr fayli yozildi: %s", out_path.name)
    except _JobFailed as exc:
        error_text = str(exc)
    except Exception:  # noqa: BLE001 - last-resort guard so the animation always gets cleaned up
        logger.exception("Kutilmagan xato")
        error_text = t("job.unexpected_error", lang)
    finally:
        animation_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await animation_task

    if error_text:
        await context.bot.edit_message_text(error_text, chat_id=chat_id, message_id=progress_message.message_id)
        _cleanup(context)
        return ConversationHandler.END

    await context.bot.edit_message_text(t("job.done", lang), chat_id=chat_id, message_id=progress_message.message_id)
    if format_notice:
        await context.bot.send_message(chat_id, format_notice)

    with open(out_path, "rb") as subtitle_file:
        await context.bot.send_document(chat_id, document=subtitle_file, filename=out_path.name)

    job_identifier = datetime.now(timezone.utc).isoformat()
    repository.save_last_job(
        user_id,
        filename=context.user_data.get("original_filename", out_path.name),
        media_kind=context.user_data.get("media_kind", "document"),
        duration_seconds=context.user_data.get("audio_duration"),
        style=style,
        blocks=blocks,
        completed_at=job_identifier,
    )
    # Admin usage statistics (Section: per-user usage) - only counted once the
    # subtitle file has actually been delivered, never on a failed job.
    repository.record_usage(user_id, context.user_data.get("audio_duration"))

    await context.bot.send_message(
        chat_id, t("job.feedback_prompt", lang), reply_markup=feedback_keyboard(job_identifier)
    )

    _cleanup(context)
    return ConversationHandler.END


_MARKUP_RE = re.compile(r"<[^>]+>")
_NON_WORD_RE = re.compile(r"[^\w']+", re.UNICODE)


def _normalize_for_match(text: str) -> str:
    """Strips emphasis markup and punctuation so a block's display word can be
    matched back against the transcript's raw token for the same word."""
    return _NON_WORD_RE.sub("", _MARKUP_RE.sub("", text)).lower()


def _find_matching_raw_word(
    raw_words: list[Word], normalized_text: str, start_index: int
) -> tuple[int, Word] | None:
    if not normalized_text:
        return None
    for idx in range(start_index, len(raw_words)):
        if _normalize_for_match(raw_words[idx].text) == normalized_text:
            return idx, raw_words[idx]
    return None


def _log_block_timing_diagnostics(blocks: list[SubtitleBlock], raw_words: list[Word]) -> None:
    """Diagnostic only - does not change any timing. For each final block,
    logs its own assigned start/end next to the transcript's real raw
    timestamp for the same word (matched by text), so an off-by-one drift can
    be spotted by eye from a real clip's DEBUG log instead of guessed at again.
    """
    if not logger.isEnabledFor(logging.DEBUG) or not raw_words:
        return

    cursor = 0
    for i, block in enumerate(blocks):
        first_line = block.lines[0] if block.lines else ""
        last_line = block.lines[-1] if block.lines else ""
        first_word = first_line.split()[0] if first_line.split() else ""
        last_word = last_line.split()[-1] if last_line.split() else ""

        first_match = _find_matching_raw_word(raw_words, _normalize_for_match(first_word), cursor)
        last_match = _find_matching_raw_word(
            raw_words, _normalize_for_match(last_word), first_match[0] if first_match else cursor
        )

        logger.debug(
            "[Blok %d] matn=%r | belgilangan vaqt=%.3f-%.3f | xom vaqt: "
            "boshlanish %r=%s, tugash %r=%s",
            i,
            " / ".join(block.lines),
            block.start,
            block.end,
            first_word,
            f"{first_match[1].start:.3f}" if first_match else "topilmadi",
            last_word,
            f"{last_match[1].end:.3f}" if last_match else "topilmadi",
        )
        if first_match:
            cursor = first_match[0]


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(t("cancel.done", get_user_language(update)))
    _cleanup(context)
    return ConversationHandler.END


async def _cancel_from_nav(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(t("cancel.process_cancelled", get_user_language(update)))
    _cleanup(context)
    return ConversationHandler.END


async def script_source_nav_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query.data != NAV_BACK:
        return await _cancel_from_nav(update, context)
    await query.answer()
    return await _show_hub(query, context, get_user_language(update))


async def restart_with_new_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Fires when media arrives while the conversation is stuck in a state that
    doesn't expect it (e.g. a video sent while a style-choice keyboard is still
    pending). Without a fallback for this, python-telegram-bot silently drops
    the update - the bot looks hung, with no reply and no error. This instead
    discards the stale session and re-runs the normal entry point on the new file.
    """
    _cleanup(context)
    await update.message.reply_text(t("restart.new_media", get_user_language(update)))
    return await receive_media(update, context)


async def unexpected_text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _cleanup(context)
    await update.message.reply_text(t("fallback.send_media", get_user_language(update)))
    return ConversationHandler.END


async def unexpected_callback_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()  # stops the button's loading spinner on a now-stale keyboard
    _cleanup(context)
    await context.bot.send_message(update.effective_chat.id, t("fallback.send_media", get_user_language(update)))
    return ConversationHandler.END


async def unexpected_input_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    _cleanup(context)
    if update.message:
        await update.message.reply_text(t("fallback.send_media", get_user_language(update)))
    return ConversationHandler.END


def _cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    session_dir = context.user_data.pop("session_dir", None)
    if session_dir:
        cleanup_session_dir(session_dir)
    context.user_data.pop("audio_path", None)
    context.user_data.pop("groq_words", None)
    context.user_data.pop("audio_duration", None)
    context.user_data.pop("original_filename", None)
    context.user_data.pop("media_kind", None)
    context.user_data.pop("style", None)
    context.user_data.pop("output_format", None)
    context.user_data.pop("subtitle_language", None)
    context.user_data.pop("hub_touched", None)
    context.user_data.pop("aligned_words", None)
    context.user_data.pop("transcript_text", None)


def build_conversation_handler() -> ConversationHandler:
    media_filter = (
        filters.VIDEO
        | filters.AUDIO
        | filters.VOICE
        | filters.Document.VIDEO
        | filters.Document.AUDIO
    )
    return ConversationHandler(
        entry_points=[MessageHandler(media_filter, receive_media)],
        states={
            State.WAITING_HUB_MENU: [
                CallbackQueryHandler(hub_row_callback, pattern=r"^hub:(style|sublang|format)$"),
                CallbackQueryHandler(hub_done_callback, pattern=r"^hub:done$"),
                CallbackQueryHandler(hub_cancel_callback, pattern=r"^nav:"),
            ],
            State.WAITING_STYLE_CHOICE: [
                CallbackQueryHandler(style_choice_callback, pattern=r"^style:"),
                CallbackQueryHandler(hub_submenu_back_callback, pattern=r"^nav:"),
            ],
            State.WAITING_FORMAT_CHOICE: [
                CallbackQueryHandler(format_choice_callback, pattern=r"^format:"),
                CallbackQueryHandler(hub_submenu_back_callback, pattern=r"^nav:"),
            ],
            State.WAITING_SUBLANG_CHOICE: [
                CallbackQueryHandler(sublang_choice_callback, pattern=r"^sublang:"),
                CallbackQueryHandler(hub_submenu_back_callback, pattern=r"^nav:"),
            ],
            State.WAITING_SCRIPT_SOURCE_CHOICE: [
                CallbackQueryHandler(script_source_callback, pattern=r"^scriptsrc:"),
                CallbackQueryHandler(script_source_nav_callback, pattern=r"^nav:"),
            ],
            State.WAITING_SCRIPT_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_script_text)],
            State.WAITING_TRANSCRIPT_CONFIRMATION: [
                CallbackQueryHandler(transcript_confirm_callback, pattern=rf"^{TRANSCRIPT_CONFIRM}$"),
                CallbackQueryHandler(transcript_edit_callback, pattern=rf"^{TRANSCRIPT_EDIT}$"),
            ],
            State.WAITING_TRANSCRIPT_CORRECTION: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_transcript_correction)
            ],
        },
        fallbacks=[
            CommandHandler("cancel", cancel),
            # Anything that doesn't match the current state falls through to
            # here instead of being silently dropped (the original "hang" bug).
            MessageHandler(media_filter, restart_with_new_media),
            CallbackQueryHandler(unexpected_callback_fallback),
            MessageHandler(filters.TEXT & ~filters.COMMAND, unexpected_text_fallback),
            MessageHandler(filters.ALL, unexpected_input_fallback),
        ],
        conversation_timeout=15 * 60,
    )
