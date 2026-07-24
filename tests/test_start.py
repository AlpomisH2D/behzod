from unittest.mock import AsyncMock, MagicMock, patch

from bot import language_utils
from bot.handlers import start
from bot.i18n import START_TEXT
from models.types import UserSettings


def _make_update(language_code="uz"):
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_user = MagicMock(
        id=111, username="johndoe", first_name="John", last_name=None, language_code=language_code
    )
    return update, message


async def test_start_registers_profile_and_shows_main_menu():
    update, message = _make_update()
    context = MagicMock()
    settings = UserSettings(user_id=111, language="uz", language_chosen=True)

    with patch.object(start, "register_user_profile", new=AsyncMock()) as mock_register, patch.object(
        language_utils.repository, "get_settings", return_value=settings
    ):
        await start.start(update, context)

    mock_register.assert_awaited_once_with(update)
    message.reply_text.assert_awaited_once()
    args, kwargs = message.reply_text.call_args
    assert args[0] == START_TEXT["uz"]
    assert kwargs["reply_markup"] is not None


async def test_start_uses_saved_language_when_chosen():
    update, message = _make_update(language_code="en")
    context = MagicMock()
    settings = UserSettings(user_id=111, language="ru", language_chosen=True)

    with patch.object(start, "register_user_profile", new=AsyncMock()), patch.object(
        language_utils.repository, "get_settings", return_value=settings
    ):
        await start.start(update, context)

    assert message.reply_text.call_args[0][0] == START_TEXT["ru"]


async def test_start_falls_back_to_telegram_language_when_not_chosen():
    update, message = _make_update(language_code="en")
    context = MagicMock()
    settings = UserSettings(user_id=111, language="uz", language_chosen=False)

    with patch.object(start, "register_user_profile", new=AsyncMock()), patch.object(
        language_utils.repository, "get_settings", return_value=settings
    ):
        await start.start(update, context)

    assert message.reply_text.call_args[0][0] == START_TEXT["en"]
