import logging
import re
from datetime import datetime, timezone

from telegram import KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove, Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from bot.i18n import t
from bot.keyboards import main_reply_keyboard
from bot.language_utils import get_user_language
from db import repository

logger = logging.getLogger(__name__)

# Exactly 9 digits, once whitespace is stripped out - the user is only
# expected to type what comes after "+998", e.g. "99 425 39 52" or
# "994253952". A leading "+998" is tolerated (stripped) rather than rejected.
_PHONE_DIGITS_REGEX = re.compile(r"\d{9}")


def phone_request_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton(t("registration.share_button", lang))]],
        resize_keyboard=True,
    )


async def send_phone_request(chat_id: int, context: ContextTypes.DEFAULT_TYPE, lang: str = "uz") -> None:
    example = t("registration.phone_example", lang)
    prompt = t("registration.phone_prompt", lang, example=example)
    await context.bot.send_message(chat_id, prompt, reply_markup=phone_request_keyboard(lang))


async def _reveal_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, lang: str) -> None:
    await update.effective_message.reply_text(t("registration.phone_saved", lang), reply_markup=ReplyKeyboardRemove())
    await context.bot.send_message(
        update.effective_chat.id, t("interface_language.main_menu_ready", lang), reply_markup=main_reply_keyboard(lang)
    )


def normalize_phone_number(raw: str) -> str | None:
    """Strips whitespace and an optional leading "+998" (typed unnecessarily
    but tolerated), then validates exactly 9 digits remain. Returns the full
    "+998XXXXXXXXX" number, or None if it doesn't match."""
    normalized = re.sub(r"\s+", "", raw)
    if normalized.startswith("+998"):
        normalized = normalized[4:]
    if _PHONE_DIGITS_REGEX.fullmatch(normalized):
        return f"+998{normalized}"
    return None


async def register_user_profile(update: Update) -> None:
    """Silently records a new user's profile the first time they're seen.
    Idempotent (INSERT OR IGNORE under the hood) - safe to call on every
    update regardless of whether this user is already registered."""
    user = update.effective_user
    if user is None:
        return
    repository.register_user(
        user.id,
        user.username,
        user.first_name or "Foydalanuvchi",
        user.last_name,
        joined_at=datetime.now(timezone.utc).isoformat(),
    )


async def phone_number_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registered in its own priority group, right after the language gate.
    Until a phone number is on file, every update from this user is
    intercepted here - either it's the phone submission itself (handled and
    let through to reveal the main menu), or it's replaced with the phone
    request, exactly mirroring how first_contact_language_gate works.
    """
    if update.callback_query and (update.callback_query.data or "").startswith("lang:"):
        return  # language selection itself - let it finish before asking for phone

    user = update.effective_user
    if user is None:
        return

    settings = repository.get_settings(user.id)
    if not settings.language_chosen:
        return  # language gate hasn't passed yet - nothing to do here

    await register_user_profile(update)

    if repository.get_phone_number(user.id):
        return  # already on file - let the update through

    lang = get_user_language(update)
    message = update.message

    if message and message.contact:
        if message.contact.user_id == user.id:
            phone = message.contact.phone_number
            if not phone.startswith("+"):
                phone = f"+{phone}"
            repository.save_phone_number(user.id, phone)
            await _reveal_main_menu(update, context, lang)
        else:
            await message.reply_text(t("registration.wrong_contact", lang))
            await send_phone_request(update.effective_chat.id, context, lang)
        raise ApplicationHandlerStop

    if message and message.text and not message.text.startswith("/"):
        normalized = normalize_phone_number(message.text)
        if normalized:
            repository.save_phone_number(user.id, normalized)
            await _reveal_main_menu(update, context, lang)
        else:
            example = t("registration.phone_example", lang)
            await message.reply_text(
                t("registration.phone_invalid", lang, example=example), reply_markup=phone_request_keyboard(lang)
            )
        raise ApplicationHandlerStop

    # Anything else (media, callback, a bare command, etc.) while the phone
    # number is still missing: intercept and (re-)send the phone request.
    if update.callback_query:
        await update.callback_query.answer()
    await send_phone_request(update.effective_chat.id, context, lang)
    raise ApplicationHandlerStop
