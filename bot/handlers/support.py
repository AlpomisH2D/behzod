import logging

from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

import config
from bot.i18n import t
from bot.language_utils import get_user_language

logger = logging.getLogger(__name__)

_AWAITING_KEY = "awaiting_admin_message"


async def start_awaiting_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """All three '❓ Yordam' options (bug report / suggestion / contact admin)
    funnel into this same flow - they're just different labels for "send a
    message to the admin". The admin's identity is never shown to the user;
    everything routes through the bot.
    """
    context.user_data[_AWAITING_KEY] = True
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(t("support.route_prompt", get_user_language(update)))


async def admin_message_capture_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registered in its own priority group, after onboarding (language/phone)
    but before the normal menu/conversation handling. While a chat is in the
    "awaiting message for admin" state, the very next message (text or media)
    is forwarded to config.ADMIN_USER_ID instead of being processed normally.
    """
    if not context.user_data.get(_AWAITING_KEY):
        return

    message = update.message
    if message is None:
        return  # only a real message counts as the reply - ignore anything else

    context.user_data.pop(_AWAITING_KEY, None)
    user = update.effective_user
    lang = get_user_language(update)

    if not config.ADMIN_USER_ID:
        logger.warning("ADMIN_USER_ID sozlanmagan - foydalanuvchi xabari yuborilmadi")
        await message.reply_text(t("support.forward_failed", lang))
        raise ApplicationHandlerStop

    try:
        username_part = f"@{user.username}" if user.username else "username yo'q"
        header = f"\U0001F4E9 Yangi xabar\nKimdan: {user.first_name} ({username_part}, ID: {user.id})"
        await context.bot.send_message(config.ADMIN_USER_ID, header)
        await context.bot.forward_message(
            chat_id=config.ADMIN_USER_ID,
            from_chat_id=update.effective_chat.id,
            message_id=message.message_id,
        )
        await message.reply_text(t("support.forwarded_confirm", lang))
    except Exception:  # noqa: BLE001 - a failed forward must never look like a hang to the user
        logger.exception("Adminga xabar yuborishda xato")
        await message.reply_text(t("support.forward_failed", lang))

    raise ApplicationHandlerStop
