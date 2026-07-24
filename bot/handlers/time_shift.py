import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.i18n import t
from bot.keyboards import TIME_SHIFT_CANCEL, TIME_SHIFT_DONE, time_shift_keyboard
from bot.language_utils import get_user_language
from db import repository
from services import srt_service
from utils.tempfiles import cleanup_session_dir, new_session_dir

logger = logging.getLogger(__name__)


async def time_shift_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(update)
    job = repository.get_last_job(update.effective_user.id)
    if job is None:
        await update.message.reply_text(t("time_shift.no_last_job", lang))
        return
    context.user_data["shift_offset_ms"] = 0
    await update.message.reply_text(t("time_shift.offset_text", lang, offset=0), reply_markup=time_shift_keyboard(lang))


async def time_shift_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = get_user_language(update)

    if query.data == TIME_SHIFT_CANCEL:
        context.user_data.pop("shift_offset_ms", None)
        await query.edit_message_text(t("cancel.done", lang))
        return

    if query.data == TIME_SHIFT_DONE:
        await _apply_and_send(update, context, lang)
        return

    delta = int(query.data.split(":", 1)[1])
    offset_ms = context.user_data.get("shift_offset_ms", 0) + delta
    context.user_data["shift_offset_ms"] = offset_ms
    await query.edit_message_text(
        t("time_shift.offset_text", lang, offset=offset_ms), reply_markup=time_shift_keyboard(lang)
    )


async def _apply_and_send(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    offset_ms = context.user_data.pop("shift_offset_ms", 0)

    job = repository.get_last_job(user_id)
    if job is None:
        await query.edit_message_text(t("time_shift.no_last_job", lang))
        return

    shifted = srt_service.shift_blocks(job.blocks, offset_ms / 1000)
    session_dir = new_session_dir()
    try:
        srt_path = session_dir / "subtitr_tuzatilgan.srt"
        srt_service.write_srt(shifted, srt_path)
        await query.edit_message_text(t("time_shift.result", lang, offset=offset_ms))
        with open(srt_path, "rb") as srt_file:
            await context.bot.send_document(
                update.effective_chat.id, document=srt_file, filename="subtitr_tuzatilgan.srt"
            )
    finally:
        cleanup_session_dir(session_dir)
