import logging
from datetime import datetime

from telegram import Update
from telegram.ext import ContextTypes

import config
from db import repository
from models.types import UsageStats, UserProfile

logger = logging.getLogger(__name__)

# Telegram's hard limit is ~4096 chars per message - stay well under it.
_MESSAGE_CHAR_LIMIT = 3500

_NO_USERS_TEXT = "Hali birorta ham foydalanuvchi ro'yxatdan o'tmagan."
_REPLY_USAGE_TEXT = "Foydalanish: /reply <user_id> <xabar matni>"
_REPLY_BAD_USER_ID_TEXT = "user_id butun son bo'lishi kerak."
_REPLY_SENT_TEXT = "Yuborildi."
_REPLY_FAILED_TEXT = "Yuborishda xatolik yuz berdi - foydalanuvchi botni bloklagan bo'lishi mumkin."
_NO_STATS_TEXT = "Hali birorta ham ish yakunlanmagan."
_STATS_TITLE = "\U0001F4CA Foydalanuvchilar statistikasi"


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user) and bool(config.ADMIN_USER_ID) and user.id == config.ADMIN_USER_ID


def _format_joined_at(joined_at: str) -> str:
    try:
        return datetime.fromisoformat(joined_at).strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return joined_at


def _format_profile(profile: UserProfile) -> str:
    name = profile.first_name
    if profile.last_name:
        name = f"{name} {profile.last_name}"
    username = f"@{profile.username}" if profile.username else "username yo'q"
    phone = profile.phone_number or "kiritilmagan"
    return (
        f"\U0001F464 {name}\n"
        f"{username}\n"
        f"ID: {profile.user_id}\n"
        f"Tel: {phone}\n"
        f"Qo'shildi: {_format_joined_at(profile.joined_at)}"
    )


def _paginate_messages(header: str, blocks: list[str], limit: int | None = None) -> list[str]:
    """Packs `header` + as many `blocks` as fit into the first message, then
    keeps starting new messages for the rest - so a long user list is split
    across several messages instead of hitting Telegram's length limit."""
    limit = limit if limit is not None else _MESSAGE_CHAR_LIMIT
    messages: list[str] = []
    current = header
    for block in blocks:
        candidate = f"{current}\n\n{block}"
        if len(candidate) > limit:
            messages.append(current)
            current = block
        else:
            current = candidate
    messages.append(current)
    return messages


async def users_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: lists every registered user's profile (name, username,
    id, phone number, join date), with a total-count summary at the top.

    Silently does nothing for anyone else - the command is also left out of
    the public command menu, so it's effectively invisible to non-admins.
    """
    if not _is_admin(update):
        return

    profiles = repository.list_user_profiles()
    if not profiles:
        await update.message.reply_text(_NO_USERS_TEXT)
        return

    header = f"Jami foydalanuvchilar soni: {len(profiles)}"
    blocks = [_format_profile(p) for p in profiles]
    for message in _paginate_messages(header, blocks):
        await update.message.reply_text(message)


def _format_stats_entry(rank: int, stats: UsageStats) -> str:
    name = stats.first_name
    if stats.last_name:
        name = f"{name} {stats.last_name}"
    username = f"@{stats.username}" if stats.username else "username yo'q"
    minutes = stats.total_duration_seconds / 60
    return (
        f"{rank}. {name} ({username}) — [{stats.user_id}]\n"
        f"   Jami: {stats.total_media_count} ta fayl, {minutes:.1f} daqiqa"
    )


async def statistika_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: per-user cumulative usage (file count + total minutes
    subtitled), most active users first.

    Silently does nothing for anyone else - the command is also left out of
    the public command menu, so it's effectively invisible to non-admins,
    same as /users and /reply.
    """
    if not _is_admin(update):
        return

    stats = repository.list_usage_stats()
    if not stats:
        await update.message.reply_text(_NO_STATS_TEXT)
        return

    total_files = sum(s.total_media_count for s in stats)
    total_minutes = sum(s.total_duration_seconds for s in stats) / 60
    footer = f"Umumiy: {len(stats)} foydalanuvchi, {total_files} ta fayl, {total_minutes:.1f} daqiqa"

    blocks = [_format_stats_entry(i, s) for i, s in enumerate(stats, start=1)]
    blocks.append(footer)
    for message in _paginate_messages(_STATS_TITLE, blocks):
        await update.message.reply_text(message)


async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Admin-only: /reply <user_id> <text> - the admin's way of answering a
    message that was forwarded from a user via the Yordam menu (see
    bot/handlers/support.py), without ever needing the user's own contact info.
    """
    if not _is_admin(update):
        return

    args = context.args or []
    if len(args) < 2:
        await update.message.reply_text(_REPLY_USAGE_TEXT)
        return

    try:
        target_user_id = int(args[0])
    except ValueError:
        await update.message.reply_text(_REPLY_BAD_USER_ID_TEXT)
        return

    text = " ".join(args[1:])
    try:
        await context.bot.send_message(target_user_id, text)
        await update.message.reply_text(_REPLY_SENT_TEXT)
    except Exception:  # noqa: BLE001 - normalized into a plain-language reply, never a raw traceback
        logger.exception("Foydalanuvchiga javob yuborishda xato")
        await update.message.reply_text(_REPLY_FAILED_TEXT)
