from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ApplicationHandlerStop

from bot.handlers import access_control
from bot.i18n import t


def _make_message_update(user_id, username=None):
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_message = message
    update.callback_query = None
    update.effective_user = MagicMock(id=user_id, username=username)
    return update, message


def _make_callback_update(user_id):
    query = MagicMock()
    query.answer = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.message = None
    update.effective_message = None
    update.effective_user = MagicMock(id=user_id)
    return update, query


async def test_admin_passes_through_when_maintenance_mode_on():
    update, message = _make_message_update(995082730)

    with patch.object(access_control.config, "MAINTENANCE_MODE", True), patch.object(
        access_control.config, "ADMIN_USER_ID", 995082730
    ):
        await access_control.maintenance_gate(update, MagicMock())  # must not raise

    message.reply_text.assert_not_called()


async def test_non_admin_message_is_blocked_with_maintenance_notice():
    update, message = _make_message_update(111)

    with patch.object(access_control.config, "MAINTENANCE_MODE", True), patch.object(
        access_control.config, "ADMIN_USER_ID", 995082730
    ):
        with pytest.raises(ApplicationHandlerStop):
            await access_control.maintenance_gate(update, MagicMock())

    message.reply_text.assert_awaited_once_with(t("maintenance.text", "uz"))


async def test_non_admin_callback_is_answered_and_blocked():
    update, query = _make_callback_update(111)

    with patch.object(access_control.config, "MAINTENANCE_MODE", True), patch.object(
        access_control.config, "ADMIN_USER_ID", 995082730
    ):
        with pytest.raises(ApplicationHandlerStop):
            await access_control.maintenance_gate(update, MagicMock())

    query.answer.assert_awaited_once()


async def test_everyone_blocked_when_admin_user_id_not_configured():
    update, message = _make_message_update(995082730)

    with patch.object(access_control.config, "MAINTENANCE_MODE", True), patch.object(
        access_control.config, "ADMIN_USER_ID", 0
    ):
        with pytest.raises(ApplicationHandlerStop):
            await access_control.maintenance_gate(update, MagicMock())


async def test_everyone_passes_through_when_maintenance_mode_off():
    update, message = _make_message_update(111)  # not the admin

    with patch.object(access_control.config, "MAINTENANCE_MODE", False), patch.object(
        access_control.config, "ADMIN_USER_ID", 995082730
    ):
        await access_control.maintenance_gate(update, MagicMock())  # must not raise

    message.reply_text.assert_not_called()


async def test_allowed_username_passes_through_maintenance_mode():
    update, message = _make_message_update(111, username="qwertyzaaaa")

    with patch.object(access_control.config, "MAINTENANCE_MODE", True), patch.object(
        access_control.config, "ADMIN_USER_ID", 995082730
    ), patch.object(access_control.config, "ALLOWED_USERNAMES", {"qwertyzaaaa"}):
        await access_control.maintenance_gate(update, MagicMock())  # must not raise

    message.reply_text.assert_not_called()


async def test_allowed_username_check_is_case_insensitive():
    update, message = _make_message_update(111, username="QwertyZaaaa")

    with patch.object(access_control.config, "MAINTENANCE_MODE", True), patch.object(
        access_control.config, "ADMIN_USER_ID", 995082730
    ), patch.object(access_control.config, "ALLOWED_USERNAMES", {"qwertyzaaaa"}):
        await access_control.maintenance_gate(update, MagicMock())  # must not raise

    message.reply_text.assert_not_called()


async def test_username_not_in_allowed_list_is_still_blocked():
    update, message = _make_message_update(111, username="someone_else")

    with patch.object(access_control.config, "MAINTENANCE_MODE", True), patch.object(
        access_control.config, "ADMIN_USER_ID", 995082730
    ), patch.object(access_control.config, "ALLOWED_USERNAMES", {"qwertyzaaaa"}):
        with pytest.raises(ApplicationHandlerStop):
            await access_control.maintenance_gate(update, MagicMock())

    message.reply_text.assert_awaited_once_with(t("maintenance.text", "uz"))
