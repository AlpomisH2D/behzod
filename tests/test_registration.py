from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ApplicationHandlerStop

from bot.handlers import registration
from models.types import UserSettings


def _make_update(
    user_id=111,
    username="johndoe",
    first_name="John",
    last_name="Doe",
    text=None,
    contact=None,
    is_command=False,
    callback_data=None,
):
    message = None
    if text is not None or contact is not None:
        message = MagicMock()
        message.text = text
        message.contact = contact
        message.reply_text = AsyncMock()

    query = None
    if callback_data is not None:
        query = MagicMock()
        query.data = callback_data
        query.answer = AsyncMock()

    update = MagicMock()
    update.message = message
    update.effective_message = message
    update.callback_query = query
    update.effective_user = MagicMock(id=user_id, username=username, first_name=first_name, last_name=last_name)
    update.effective_chat = MagicMock(id=user_id)
    return update, message, query


def _make_context():
    context = MagicMock()
    context.bot.send_message = AsyncMock()
    return context


def _contact(phone_number, user_id, has_plus=True):
    contact = MagicMock()
    contact.phone_number = phone_number
    contact.user_id = user_id
    return contact


# --- normalize_phone_number ---


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("994253952", "+998994253952"),  # bare 9 digits - the expected case
        ("99 425 39 52", "+998994253952"),
        ("99   425 3952", "+998994253952"),
        ("+998994253952", "+998994253952"),  # user typed +998 anyway - tolerated
        ("+998 99 425 39 52", "+998994253952"),
    ],
)
def test_normalize_phone_number_accepts_valid_formats(raw, expected):
    assert registration.normalize_phone_number(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "99425395",  # too short (8 digits)
        "9942539522",  # too long (10 digits)
        "+99799425395",  # wrong country code left in front of 9 digits
        "not a number",
    ],
)
def test_normalize_phone_number_rejects_invalid_formats(raw):
    assert registration.normalize_phone_number(raw) is None


# --- register_user_profile ---


async def test_register_user_profile_saves_id_username_and_names():
    update, _, _ = _make_update()

    with patch.object(registration.repository, "register_user") as mock_register:
        await registration.register_user_profile(update)

    args, kwargs = mock_register.call_args
    assert args[0] == 111
    assert args[1] == "johndoe"
    assert args[2] == "John"
    assert args[3] == "Doe"


# --- phone_number_gate ---


async def test_phone_gate_does_nothing_before_language_is_chosen():
    update, message, _ = _make_update(text="salom")
    context = _make_context()
    unset = UserSettings(user_id=111, language_chosen=False)

    with patch.object(registration.repository, "get_settings", return_value=unset), patch.object(
        registration.repository, "register_user"
    ) as mock_register:
        await registration.phone_number_gate(update, context)  # must not raise

    mock_register.assert_not_called()


async def test_phone_gate_lets_language_pick_callback_through():
    update, _, query = _make_update(callback_data="lang:uz")
    context = _make_context()

    with patch.object(registration.repository, "get_settings") as mock_get_settings:
        await registration.phone_number_gate(update, context)  # must not raise

    mock_get_settings.assert_not_called()


async def test_phone_gate_passes_through_when_phone_already_saved():
    update, message, _ = _make_update(text="/anything")
    context = _make_context()
    chosen = UserSettings(user_id=111, language_chosen=True)

    with patch.object(registration.repository, "get_settings", return_value=chosen), patch.object(
        registration.repository, "register_user"
    ), patch.object(registration.repository, "get_phone_number", return_value="+998994253952"):
        await registration.phone_number_gate(update, context)  # must not raise

    context.bot.send_message.assert_not_called()


async def test_phone_gate_saves_contact_share_and_reveals_main_menu():
    contact = _contact("998994253952", user_id=111)
    update, message, _ = _make_update(contact=contact)
    context = _make_context()
    chosen = UserSettings(user_id=111, language_chosen=True)

    with patch.object(registration.repository, "get_settings", return_value=chosen), patch.object(
        registration.repository, "register_user"
    ), patch.object(registration.repository, "get_phone_number", return_value=None), patch.object(
        registration.repository, "save_phone_number"
    ) as mock_save:
        with pytest.raises(ApplicationHandlerStop):
            await registration.phone_number_gate(update, context)

    mock_save.assert_called_once_with(111, "+998994253952")  # '+' prepended since Telegram omitted it
    message.reply_text.assert_awaited_once()
    context.bot.send_message.assert_awaited_once()


async def test_phone_gate_rejects_someone_elses_shared_contact():
    contact = _contact("+998994253952", user_id=999)  # not the sender's own contact
    update, message, _ = _make_update(contact=contact, user_id=111)
    context = _make_context()
    chosen = UserSettings(user_id=111, language_chosen=True)

    with patch.object(registration.repository, "get_settings", return_value=chosen), patch.object(
        registration.repository, "register_user"
    ), patch.object(registration.repository, "get_phone_number", return_value=None), patch.object(
        registration.repository, "save_phone_number"
    ) as mock_save:
        with pytest.raises(ApplicationHandlerStop):
            await registration.phone_number_gate(update, context)

    mock_save.assert_not_called()
    message.reply_text.assert_awaited_once()


async def test_phone_gate_saves_bare_9_digit_manual_text_and_reveals_main_menu():
    """The primary expected path per spec: user types only the 9 digits, no
    country code."""
    update, message, _ = _make_update(text="99 425 39 52")
    context = _make_context()
    chosen = UserSettings(user_id=111, language_chosen=True)

    with patch.object(registration.repository, "get_settings", return_value=chosen), patch.object(
        registration.repository, "register_user"
    ), patch.object(registration.repository, "get_phone_number", return_value=None), patch.object(
        registration.repository, "save_phone_number"
    ) as mock_save:
        with pytest.raises(ApplicationHandlerStop):
            await registration.phone_number_gate(update, context)

    mock_save.assert_called_once_with(111, "+998994253952")
    message.reply_text.assert_awaited_once()
    context.bot.send_message.assert_awaited_once()


async def test_phone_gate_saves_valid_manual_text_and_reveals_main_menu():
    update, message, _ = _make_update(text="+998 99 425 39 52")
    context = _make_context()
    chosen = UserSettings(user_id=111, language_chosen=True)

    with patch.object(registration.repository, "get_settings", return_value=chosen), patch.object(
        registration.repository, "register_user"
    ), patch.object(registration.repository, "get_phone_number", return_value=None), patch.object(
        registration.repository, "save_phone_number"
    ) as mock_save:
        with pytest.raises(ApplicationHandlerStop):
            await registration.phone_number_gate(update, context)

    mock_save.assert_called_once_with(111, "+998994253952")
    message.reply_text.assert_awaited_once()
    context.bot.send_message.assert_awaited_once()


async def test_phone_gate_rejects_invalid_manual_text_and_reprompts():
    update, message, _ = _make_update(text="not a phone number")
    context = _make_context()
    chosen = UserSettings(user_id=111, language_chosen=True)

    with patch.object(registration.repository, "get_settings", return_value=chosen), patch.object(
        registration.repository, "register_user"
    ), patch.object(registration.repository, "get_phone_number", return_value=None), patch.object(
        registration.repository, "save_phone_number"
    ) as mock_save:
        with pytest.raises(ApplicationHandlerStop):
            await registration.phone_number_gate(update, context)

    mock_save.assert_not_called()
    message.reply_text.assert_awaited_once()
    assert "noto'g'ri" in message.reply_text.call_args[0][0]


async def test_phone_gate_intercepts_media_with_phone_request():
    update, message, _ = _make_update(text=None)  # no text/contact - e.g. a photo
    update.message = MagicMock()  # media-bearing message with no .text/.contact useful
    update.message.text = None
    update.message.contact = None
    context = _make_context()
    chosen = UserSettings(user_id=111, language_chosen=True)

    with patch.object(registration.repository, "get_settings", return_value=chosen), patch.object(
        registration.repository, "register_user"
    ), patch.object(registration.repository, "get_phone_number", return_value=None):
        with pytest.raises(ApplicationHandlerStop):
            await registration.phone_number_gate(update, context)

    context.bot.send_message.assert_awaited_once()
    kwargs = context.bot.send_message.call_args.kwargs
    assert kwargs["reply_markup"] is not None
