from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ApplicationHandlerStop

from bot.handlers import support
from bot.i18n import t


def _make_callback_update():
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=111, language_code="uz")
    return update, query


def _make_message_update(user_id=111, username="johndoe", first_name="John"):
    message = MagicMock()
    message.message_id = 555
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_user = MagicMock(id=user_id, username=username, first_name=first_name)
    update.effective_chat = MagicMock(id=user_id)
    return update, message


def _make_context():
    context = MagicMock()
    context.user_data = {}
    context.bot.send_message = AsyncMock()
    context.bot.forward_message = AsyncMock()
    return context


async def test_start_awaiting_admin_message_sets_flag_and_prompts():
    update, query = _make_callback_update()
    context = MagicMock()
    context.user_data = {}

    await support.start_awaiting_admin_message(update, context)

    assert context.user_data[support._AWAITING_KEY] is True
    query.edit_message_text.assert_awaited_once_with(t("support.route_prompt", "uz"))


async def test_capture_gate_does_nothing_when_not_awaiting():
    update, message = _make_message_update()
    context = _make_context()  # awaiting flag not set

    await support.admin_message_capture_gate(update, context)  # must not raise

    context.bot.forward_message.assert_not_called()


async def test_capture_gate_forwards_message_to_admin_and_confirms():
    update, message = _make_message_update(user_id=111, username="johndoe", first_name="John")
    context = _make_context()
    context.user_data[support._AWAITING_KEY] = True

    with patch.object(support.config, "ADMIN_USER_ID", 995082730):
        with pytest.raises(ApplicationHandlerStop):
            await support.admin_message_capture_gate(update, context)

    # header with sender info sent first, then the original message forwarded
    header_call = context.bot.send_message.call_args
    assert header_call.args[0] == 995082730
    assert "John" in header_call.args[1]
    assert "@johndoe" in header_call.args[1]
    assert "111" in header_call.args[1]

    context.bot.forward_message.assert_awaited_once_with(
        chat_id=995082730, from_chat_id=111, message_id=555
    )
    message.reply_text.assert_awaited_once_with(t("support.forwarded_confirm", "uz"))
    assert support._AWAITING_KEY not in context.user_data


async def test_capture_gate_shows_no_username_placeholder():
    update, message = _make_message_update(username=None)
    context = _make_context()
    context.user_data[support._AWAITING_KEY] = True

    with patch.object(support.config, "ADMIN_USER_ID", 995082730):
        with pytest.raises(ApplicationHandlerStop):
            await support.admin_message_capture_gate(update, context)

    header_text = context.bot.send_message.call_args.args[1]
    assert "username yo'q" in header_text


async def test_capture_gate_handles_forward_failure_gracefully():
    update, message = _make_message_update()
    context = _make_context()
    context.user_data[support._AWAITING_KEY] = True
    context.bot.forward_message.side_effect = RuntimeError("boom")

    with patch.object(support.config, "ADMIN_USER_ID", 995082730):
        with pytest.raises(ApplicationHandlerStop):
            await support.admin_message_capture_gate(update, context)

    message.reply_text.assert_awaited_once_with(t("support.forward_failed", "uz"))


async def test_capture_gate_handles_unconfigured_admin_gracefully():
    update, message = _make_message_update()
    context = _make_context()
    context.user_data[support._AWAITING_KEY] = True

    with patch.object(support.config, "ADMIN_USER_ID", 0):
        with pytest.raises(ApplicationHandlerStop):
            await support.admin_message_capture_gate(update, context)

    context.bot.forward_message.assert_not_called()
    message.reply_text.assert_awaited_once_with(t("support.forward_failed", "uz"))
