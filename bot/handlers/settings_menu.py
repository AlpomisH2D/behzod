from telegram import Update
from telegram.ext import ContextTypes

from bot.i18n import t
from bot.keyboards import (
    settings_format_keyboard,
    settings_menu_keyboard,
    settings_style_keyboard,
    settings_sublang_keyboard,
)
from bot.language_utils import get_user_language
from db import repository
from models.types import UserSettings


def _keyboard(settings: UserSettings, lang: str):
    return settings_menu_keyboard(
        settings.default_word_style, settings.default_language, settings.default_format,
        settings.auto_apply_enabled, lang,
    )


async def settings_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """The '⚙️ Sozlamalar' persistent-menu button - saved per-job defaults,
    entirely separate from the '🌐 Til' interface-language screen."""
    lang = get_user_language(update)
    settings = repository.get_settings(update.effective_user.id)
    await update.message.reply_text(t("settings.intro", lang), reply_markup=_keyboard(settings, lang))


async def _show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lang = get_user_language(update)
    settings = repository.get_settings(update.effective_user.id)
    await update.callback_query.edit_message_text(t("settings.intro", lang), reply_markup=_keyboard(settings, lang))


async def settings_row_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    lang = get_user_language(update)
    target = query.data.split(":", 1)[1]
    if target == "style":
        await query.edit_message_text(t("hub.style_prompt", lang), reply_markup=settings_style_keyboard(lang))
    elif target == "sublang":
        await query.edit_message_text(t("hub.sublang_prompt", lang), reply_markup=settings_sublang_keyboard(lang))
    else:
        await query.edit_message_text(t("hub.format_prompt", lang), reply_markup=settings_format_keyboard(lang))


async def settings_style_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    style_value = query.data.split(":", 1)[1]
    repository.update_default_word_style(update.effective_user.id, style_value)
    await _show_settings(update, context)


async def settings_sublang_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    sublang = query.data.split(":", 1)[1]
    repository.update_default_language(update.effective_user.id, sublang)
    await _show_settings(update, context)


async def settings_format_choice_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    fmt = query.data.split(":", 1)[1]
    repository.update_default_format(update.effective_user.id, fmt)
    await _show_settings(update, context)


async def settings_toggle_autoapply_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    settings = repository.get_settings(update.effective_user.id)
    repository.update_auto_apply_enabled(update.effective_user.id, not settings.auto_apply_enabled)
    await _show_settings(update, context)


async def settings_back_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    await _show_settings(update, context)
