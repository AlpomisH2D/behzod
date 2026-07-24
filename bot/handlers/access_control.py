from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

import config
from bot.i18n import t
from bot.language_utils import get_user_language


def _is_admin(update: Update) -> bool:
    user = update.effective_user
    return bool(user) and bool(config.ADMIN_USER_ID) and user.id == config.ADMIN_USER_ID


def _is_allowed_username(update: Update) -> bool:
    user = update.effective_user
    return bool(user) and bool(user.username) and user.username.lower() in config.ALLOWED_USERNAMES


async def maintenance_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registered ahead of every other handler (group=-4, before the
    language/phone onboarding gates). While config.MAINTENANCE_MODE is true,
    the bot only responds to config.ADMIN_USER_ID and anyone listed in
    config.ALLOWED_USERNAMES - everyone else gets the maintenance message on
    every attempted interaction, every time (no normal flow runs for them at
    all). Flip MAINTENANCE_MODE off in .env to reopen the bot to everyone
    without touching this code.
    """
    if not config.MAINTENANCE_MODE:
        return
    if _is_admin(update) or _is_allowed_username(update):
        return

    text = t("maintenance.text", get_user_language(update))
    if update.callback_query:
        await update.callback_query.answer(text, show_alert=True)
    elif update.effective_message:
        await update.effective_message.reply_text(text)
    raise ApplicationHandlerStop
