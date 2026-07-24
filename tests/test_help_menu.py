from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import help_menu


def _make_message_update():
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_user = MagicMock(id=111, language_code="uz")
    return update, message


def _make_callback_update(action: str):
    query = MagicMock()
    query.data = f"help:{action}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=111, language_code="uz")
    return update, query


async def test_help_menu_handler_sends_keyboard():
    update, message = _make_message_update()
    context = MagicMock()

    await help_menu.help_menu_handler(update, context)

    message.reply_text.assert_awaited_once()
    kwargs = message.reply_text.call_args.kwargs
    assert kwargs["reply_markup"] is not None


async def test_help_menu_callback_routes_every_option_to_admin_message_flow():
    """All three options (bug/suggestion/contact_admin) are just different
    labels for the same underlying flow - none of them ever reveal the
    admin's identity to the user."""
    for action in ("bug", "suggestion", "contact_admin"):
        update, query = _make_callback_update(action)
        context = MagicMock()
        context.user_data = {}

        with patch.object(help_menu, "start_awaiting_admin_message", new=AsyncMock()) as mock_start:
            await help_menu.help_menu_callback(update, context)

        mock_start.assert_awaited_once_with(update, context)
