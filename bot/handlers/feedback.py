from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from bot.i18n import t
from bot.language_utils import get_user_language
from db import repository


async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    _, choice, job_identifier = query.data.split(":", 2)
    user = update.effective_user
    repository.save_feedback(
        user.id, user.username, job_identifier, choice, datetime.now(timezone.utc).isoformat()
    )
    await query.edit_message_text(t("feedback.thanks", get_user_language(update)))
