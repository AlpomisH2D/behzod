from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.support import start_awaiting_admin_message
from bot.i18n import t
from bot.keyboards import help_menu_keyboard
from bot.language_utils import get_user_language


async def help_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """The '❓ Yordam' persistent-menu button - a menu, not a /help command."""
    lang = get_user_language(update)
    await update.message.reply_text(t("help.intro", lang), reply_markup=help_menu_keyboard(lang))


async def help_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """All three options (bug / suggestion / contact admin) are just
    different labels for the same "send a message to admin" flow - the
    admin's identity is never revealed to the user."""
    await start_awaiting_admin_message(update, context)
