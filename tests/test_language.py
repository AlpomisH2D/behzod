from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ApplicationHandlerStop

from bot.handlers import language
from models.types import UserSettings


def _make_message_update(user_id: int = 111):
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.callback_query = None
    update.effective_message = message
    update.effective_user = MagicMock(id=user_id)
    update.effective_chat = MagicMock(id=user_id)
    return update, message


def _make_callback_update(data: str, user_id: int = 111):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.message = None
    update.effective_message = None
    update.effective_user = MagicMock(id=user_id)
    update.effective_chat = MagicMock(id=user_id)
    return update, query


def _make_context():
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


async def test_language_command_sends_language_keyboard():
    update, message = _make_message_update()
    context = _make_context()

    await language.language_command(update, context)

    message.reply_text.assert_awaited_once()
    _, kwargs = message.reply_text.call_args
    assert kwargs["reply_markup"] is not None


async def test_language_callback_sends_phone_request_for_first_time_user():
    update, query = _make_callback_update("lang:ru")
    context = _make_context()

    with patch.object(language.repository, "update_language") as mock_update, patch.object(
        language.repository, "get_phone_number", return_value=None
    ), patch.object(language, "send_phone_request") as mock_send_phone:
        await language.language_callback(update, context)

    mock_update.assert_called_once_with(111, "ru")
    query.edit_message_text.assert_awaited_once()
    # The confirmation itself must already be in the newly selected language.
    assert "Русский" in query.edit_message_text.call_args[0][0]
    mock_send_phone.assert_awaited_once()


async def test_language_callback_shows_main_menu_for_user_with_phone_on_file():
    update, query = _make_callback_update("lang:ru")
    context = _make_context()

    with patch.object(language.repository, "update_language"), patch.object(
        language.repository, "get_phone_number", return_value="+998994253952"
    ), patch.object(language, "send_phone_request") as mock_send_phone:
        await language.language_callback(update, context)

    mock_send_phone.assert_not_called()
    context.bot.send_message.assert_awaited_once()


async def test_first_contact_gate_blocks_and_prompts_when_language_not_chosen():
    update, message = _make_message_update()
    context = _make_context()
    unset = UserSettings(user_id=111, language_chosen=False)

    with patch.object(language.repository, "get_settings", return_value=unset), patch.object(
        language, "register_user_profile", new=AsyncMock()
    ):
        with pytest.raises(ApplicationHandlerStop):
            await language.first_contact_language_gate(update, context)

    message.reply_text.assert_awaited_once()


async def test_first_contact_gate_passes_through_once_language_chosen():
    update, message = _make_message_update()
    context = _make_context()
    chosen = UserSettings(user_id=111, language_chosen=True)

    with patch.object(language.repository, "get_settings", return_value=chosen), patch.object(
        language, "register_user_profile", new=AsyncMock()
    ):
        await language.first_contact_language_gate(update, context)  # must not raise

    message.reply_text.assert_not_called()


async def test_first_contact_gate_lets_the_language_pick_itself_through():
    update, query = _make_callback_update("lang:en")
    context = _make_context()

    with patch.object(language.repository, "get_settings") as mock_get_settings:
        await language.first_contact_language_gate(update, context)  # must not raise

    mock_get_settings.assert_not_called()
