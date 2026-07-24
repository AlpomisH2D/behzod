from telegram import Update
from telegram.ext import ContextTypes

from bot.handlers.registration import register_user_profile
from bot.i18n import t
from bot.keyboards import main_reply_keyboard
from bot.language_utils import get_user_language


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await register_user_profile(update)  # no-op if already registered
    language = get_user_language(update)
    await update.message.reply_text(t("start.greeting", language), reply_markup=main_reply_keyboard(language))
