from telegram import Update

from bot.i18n import resolve_language
from db import repository


def get_user_language(update: Update) -> str:
    """The user's saved interface language if they've explicitly chosen one,
    otherwise their Telegram client's language, otherwise Uzbek. Used by every
    handler that sends text or builds a keyboard, so the whole UI - not just
    the /start greeting - follows the user's language choice."""
    user = update.effective_user
    if user is None:
        return "uz"
    settings = repository.get_settings(user.id)
    saved = settings.language if settings.language_chosen else None
    return resolve_language(saved, user.language_code)
