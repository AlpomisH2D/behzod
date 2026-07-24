from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import settings_menu
from models.types import UserSettings


def _make_message_update(user_id=111):
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_user = MagicMock(id=user_id, language_code="uz")
    return update, message


def _make_callback_update(data, user_id=111):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=user_id, language_code="uz")
    return update, query


def _settings(**overrides):
    base = dict(
        user_id=111, default_language="uz", default_word_style="ai_choice",
        default_format="srt", auto_apply_enabled=False,
    )
    base.update(overrides)
    return UserSettings(**base)


async def test_settings_menu_handler_shows_current_defaults():
    update, message = _make_message_update()
    context = MagicMock()

    with patch.object(settings_menu.repository, "get_settings", return_value=_settings()):
        await settings_menu.settings_menu_handler(update, context)

    message.reply_text.assert_awaited_once()
    kwargs = message.reply_text.call_args.kwargs
    assert kwargs["reply_markup"] is not None


async def test_settings_row_callback_opens_style_submenu():
    update, query = _make_callback_update("settings:style")
    context = MagicMock()

    await settings_menu.settings_row_callback(update, context)

    query.edit_message_text.assert_awaited_once()
    assert "uslub" in query.edit_message_text.call_args[0][0]


async def test_settings_style_choice_saves_and_returns_to_settings_screen():
    update, query = _make_callback_update("setdefault_style:words_3")
    context = MagicMock()

    with patch.object(settings_menu.repository, "update_default_word_style") as mock_update, patch.object(
        settings_menu.repository, "get_settings", return_value=_settings(default_word_style="words_3")
    ):
        await settings_menu.settings_style_choice_callback(update, context)

    mock_update.assert_called_once_with(111, "words_3")
    query.edit_message_text.assert_awaited_once()


async def test_settings_sublang_choice_saves_default_subtitle_language():
    update, query = _make_callback_update("setdefault_sublang:ru")
    context = MagicMock()

    with patch.object(settings_menu.repository, "update_default_language") as mock_update, patch.object(
        settings_menu.repository, "get_settings", return_value=_settings(default_language="ru")
    ):
        await settings_menu.settings_sublang_choice_callback(update, context)

    mock_update.assert_called_once_with(111, "ru")


async def test_settings_format_choice_saves_default_format():
    update, query = _make_callback_update("setdefault_format:vtt")
    context = MagicMock()

    with patch.object(settings_menu.repository, "update_default_format") as mock_update, patch.object(
        settings_menu.repository, "get_settings", return_value=_settings(default_format="vtt")
    ):
        await settings_menu.settings_format_choice_callback(update, context)

    mock_update.assert_called_once_with(111, "vtt")


async def test_settings_toggle_autoapply_flips_current_value():
    update, query = _make_callback_update("settings:toggle_auto")
    context = MagicMock()

    with patch.object(
        settings_menu.repository, "get_settings", return_value=_settings(auto_apply_enabled=False)
    ), patch.object(settings_menu.repository, "update_auto_apply_enabled") as mock_update:
        await settings_menu.settings_toggle_autoapply_callback(update, context)

    mock_update.assert_called_once_with(111, True)


async def test_settings_back_callback_redraws_settings_screen():
    update, query = _make_callback_update("settings:back")
    context = MagicMock()

    with patch.object(settings_menu.repository, "get_settings", return_value=_settings()):
        await settings_menu.settings_back_callback(update, context)

    query.edit_message_text.assert_awaited_once()
