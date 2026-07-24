from telegram import Update
from telegram.ext import ApplicationHandlerStop, ContextTypes

from bot.handlers.registration import register_user_profile, send_phone_request
from bot.i18n import language_name, t
from bot.keyboards import language_keyboard, main_reply_keyboard
from bot.language_utils import get_user_language
from db import repository


async def language_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(update)
    await update.message.reply_text(t("interface_language.prompt", lang), reply_markup=language_keyboard(lang))


async def language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    code = query.data.split(":", 1)[1]
    repository.update_language(user_id, code)
    # From here on, every response - starting with this very confirmation -
    # must already be in the newly selected language, not the old one.
    label = language_name(code, code)
    await query.edit_message_text(t("interface_language.selected", code, label=label))

    # A reply keyboard can't ride on an edited message - it needs a fresh one.
    # First-time users still need to give a phone number before the main menu
    # unlocks; returning users (e.g. changing language via /language) already
    # have one on file and go straight back to the main menu.
    if repository.get_phone_number(user_id):
        await context.bot.send_message(
            update.effective_chat.id,
            t("interface_language.main_menu_ready", code),
            reply_markup=main_reply_keyboard(code),
        )
    else:
        await send_phone_request(update.effective_chat.id, context, lang=code)


async def first_contact_language_gate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Registered ahead of every other handler (group=-2). Until a user has
    explicitly picked an interface language, every update from them is
    intercepted here and replaced with the language prompt - nothing else in
    the bot runs for that update.
    """
    if update.callback_query and (update.callback_query.data or "").startswith("lang:"):
        return  # the language pick itself - let language_callback handle it

    user = update.effective_user
    if user is None:
        return
    await register_user_profile(update)
    settings = repository.get_settings(user.id)
    if settings.language_chosen:
        return

    lang = get_user_language(update)
    prompt = t("interface_language.first_contact", lang)
    if update.callback_query:
        await update.callback_query.answer()
        await context.bot.send_message(update.effective_chat.id, prompt, reply_markup=language_keyboard(lang))
    elif update.effective_message:
        await update.effective_message.reply_text(prompt, reply_markup=language_keyboard(lang))
    raise ApplicationHandlerStop
