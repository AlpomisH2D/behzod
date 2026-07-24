from datetime import datetime, timezone

from telegram import Update
from telegram.ext import ContextTypes

from bot.i18n import media_kind_name, style_label, t
from bot.language_utils import get_user_language
from db import repository
from models.types import LastJob


async def last_job_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(update)
    job = repository.get_last_job(update.effective_user.id)
    if job is None:
        await update.message.reply_text(t("last_job.none", lang))
        return
    await update.message.reply_text(_format_job_summary(job, lang))


def _format_job_summary(job: LastJob, lang: str) -> str:
    duration_text = (
        f"{job.duration_seconds:.0f}s" if job.duration_seconds is not None else t("last_job.duration_unknown", lang)
    )
    kind_text = media_kind_name(job.media_kind, lang)
    style_text = style_label(job.style.value, lang)
    relative = _format_relative_time(job.completed_at, lang)
    return t("last_job.summary", lang, duration=duration_text, kind=kind_text, style=style_text, relative=relative)


def _format_relative_time(completed_at_iso: str, lang: str) -> str:
    completed_at = datetime.fromisoformat(completed_at_iso)
    if completed_at.tzinfo is None:
        completed_at = completed_at.replace(tzinfo=timezone.utc)
    delta_seconds = max(0.0, (datetime.now(timezone.utc) - completed_at).total_seconds())

    if delta_seconds < 60:
        return t("last_job.relative_now", lang)
    minutes = int(delta_seconds // 60)
    if minutes < 60:
        return t("last_job.relative_minutes", lang, n=minutes)
    hours = int(delta_seconds // 3600)
    if hours < 24:
        return t("last_job.relative_hours", lang, n=hours)
    days = int(delta_seconds // 86400)
    return t("last_job.relative_days", lang, n=days)
