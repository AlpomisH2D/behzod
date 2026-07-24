from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import admin
from models.types import UsageStats, UserProfile

_ADMIN_ID = 995082730


def _make_update(user_id: int | None):
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_user = MagicMock(id=user_id) if user_id is not None else None
    return update, message


def _profile(user_id, username="johndoe", first_name="John", last_name=None, phone="+998994253952"):
    return UserProfile(
        user_id=user_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        phone_number=phone,
        joined_at="2026-07-24T10:00:00+00:00",
    )


def _stats(user_id, username="johndoe", first_name="John", last_name=None, count=1, seconds=60.0):
    return UsageStats(
        user_id=user_id, username=username, first_name=first_name, last_name=last_name,
        total_media_count=count, total_duration_seconds=seconds,
    )


async def test_users_command_lists_profiles_with_count_header_for_admin():
    update, message = _make_update(_ADMIN_ID)
    context = MagicMock()
    profiles = [_profile(111), _profile(222, username=None, last_name="Doe", phone=None)]

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID), patch.object(
        admin.repository, "list_user_profiles", return_value=profiles
    ):
        await admin.users_command(update, context)

    message.reply_text.assert_awaited_once()
    text = message.reply_text.call_args[0][0]
    assert "Jami foydalanuvchilar soni: 2" in text
    assert "@johndoe" in text
    assert "John" in text
    assert "111" in text
    assert "+998994253952" in text
    assert "username yo'q" in text  # second profile has no username
    assert "kiritilmagan" in text  # second profile has no phone


async def test_users_command_silently_ignores_non_admin():
    update, message = _make_update(111)
    context = MagicMock()

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID), patch.object(
        admin.repository, "list_user_profiles"
    ) as mock_list:
        await admin.users_command(update, context)

    message.reply_text.assert_not_called()
    mock_list.assert_not_called()


async def test_users_command_ignores_update_with_no_user():
    update, message = _make_update(None)
    context = MagicMock()

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID):
        await admin.users_command(update, context)

    message.reply_text.assert_not_called()


async def test_users_command_ignores_everyone_when_admin_user_id_not_configured():
    update, message = _make_update(_ADMIN_ID)
    context = MagicMock()

    with patch.object(admin.config, "ADMIN_USER_ID", 0):
        await admin.users_command(update, context)

    message.reply_text.assert_not_called()


async def test_users_command_reports_no_users_message_when_empty():
    update, message = _make_update(_ADMIN_ID)
    context = MagicMock()

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID), patch.object(
        admin.repository, "list_user_profiles", return_value=[]
    ):
        await admin.users_command(update, context)

    message.reply_text.assert_awaited_once_with(admin._NO_USERS_TEXT)


async def test_users_command_splits_long_lists_into_multiple_messages():
    update, message = _make_update(_ADMIN_ID)
    context = MagicMock()
    # Enough profiles to exceed a small artificial limit and force pagination.
    profiles = [_profile(i, username=f"user{i}") for i in range(50)]

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID), patch.object(
        admin.repository, "list_user_profiles", return_value=profiles
    ), patch.object(admin, "_MESSAGE_CHAR_LIMIT", 300):
        await admin.users_command(update, context)

    assert message.reply_text.await_count > 1
    all_text = "\n".join(call.args[0] for call in message.reply_text.call_args_list)
    for i in range(50):
        assert f"user{i}" in all_text
    # only the first message carries the summary header
    header_occurrences = sum(
        1 for call in message.reply_text.call_args_list if "Jami foydalanuvchilar" in call.args[0]
    )
    assert header_occurrences == 1


def test_format_profile_combines_first_and_last_name():
    text = admin._format_profile(_profile(111, last_name="Doe"))
    assert "John Doe" in text


def test_paginate_messages_never_exceeds_limit():
    blocks = ["x" * 100 for _ in range(10)]
    messages = admin._paginate_messages("HEADER", blocks, limit=250)

    assert all(len(m) <= 250 for m in messages)
    assert sum(m.count("x" * 100) for m in messages) == 10


# --- /reply ---


def _make_reply_update(user_id, args):
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_user = MagicMock(id=user_id) if user_id is not None else None
    context = MagicMock()
    context.args = args
    context.bot.send_message = AsyncMock()
    return update, message, context


async def test_reply_command_sends_message_to_target_user():
    update, message, context = _make_reply_update(_ADMIN_ID, ["111", "Salom,", "yordam", "beraman"])

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID):
        await admin.reply_command(update, context)

    context.bot.send_message.assert_awaited_once_with(111, "Salom, yordam beraman")
    message.reply_text.assert_awaited_once_with(admin._REPLY_SENT_TEXT)


async def test_reply_command_silently_ignores_non_admin():
    update, message, context = _make_reply_update(111, ["222", "salom"])

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID):
        await admin.reply_command(update, context)

    context.bot.send_message.assert_not_called()
    message.reply_text.assert_not_called()


async def test_reply_command_shows_usage_when_missing_args():
    update, message, context = _make_reply_update(_ADMIN_ID, ["111"])

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID):
        await admin.reply_command(update, context)

    message.reply_text.assert_awaited_once_with(admin._REPLY_USAGE_TEXT)
    context.bot.send_message.assert_not_called()


async def test_reply_command_rejects_non_numeric_user_id():
    update, message, context = _make_reply_update(_ADMIN_ID, ["not-a-number", "salom"])

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID):
        await admin.reply_command(update, context)

    message.reply_text.assert_awaited_once_with(admin._REPLY_BAD_USER_ID_TEXT)
    context.bot.send_message.assert_not_called()


async def test_reply_command_handles_send_failure_gracefully():
    update, message, context = _make_reply_update(_ADMIN_ID, ["111", "salom"])
    context.bot.send_message.side_effect = RuntimeError("blocked")

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID):
        await admin.reply_command(update, context)

    message.reply_text.assert_awaited_once_with(admin._REPLY_FAILED_TEXT)


# --- /statistika ---


async def test_statistika_command_lists_stats_sorted_with_totals_for_admin():
    update, message = _make_update(_ADMIN_ID)
    context = MagicMock()
    stats = [
        _stats(111, username="alice", first_name="Alice", count=12, seconds=34.5 * 60),
        _stats(222, username="bob", first_name="Bob", count=5, seconds=8.2 * 60),
    ]

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID), patch.object(
        admin.repository, "list_usage_stats", return_value=stats
    ):
        await admin.statistika_command(update, context)

    message.reply_text.assert_awaited_once()
    text = message.reply_text.call_args[0][0]
    assert "Alice" in text
    assert "@alice" in text
    assert "111" in text
    assert "12 ta fayl" in text
    assert "34.5 daqiqa" in text
    assert "Bob" in text
    assert "Umumiy: 2 foydalanuvchi, 17 ta fayl" in text
    assert "42.7 daqiqa" in text


async def test_statistika_command_silently_ignores_non_admin():
    update, message = _make_update(111)
    context = MagicMock()

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID), patch.object(
        admin.repository, "list_usage_stats"
    ) as mock_list:
        await admin.statistika_command(update, context)

    message.reply_text.assert_not_called()
    mock_list.assert_not_called()


async def test_statistika_command_ignores_update_with_no_user():
    update, message = _make_update(None)
    context = MagicMock()

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID):
        await admin.statistika_command(update, context)

    message.reply_text.assert_not_called()


async def test_statistika_command_reports_no_stats_message_when_empty():
    update, message = _make_update(_ADMIN_ID)
    context = MagicMock()

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID), patch.object(
        admin.repository, "list_usage_stats", return_value=[]
    ):
        await admin.statistika_command(update, context)

    message.reply_text.assert_awaited_once_with(admin._NO_STATS_TEXT)


async def test_statistika_command_splits_long_lists_into_multiple_messages():
    update, message = _make_update(_ADMIN_ID)
    context = MagicMock()
    stats = [_stats(i, username=f"user{i}") for i in range(50)]

    with patch.object(admin.config, "ADMIN_USER_ID", _ADMIN_ID), patch.object(
        admin.repository, "list_usage_stats", return_value=stats
    ), patch.object(admin, "_MESSAGE_CHAR_LIMIT", 300):
        await admin.statistika_command(update, context)

    assert message.reply_text.await_count > 1
    all_text = "\n".join(call.args[0] for call in message.reply_text.call_args_list)
    for i in range(50):
        assert f"user{i}" in all_text


def test_format_stats_entry_combines_first_and_last_name():
    text = admin._format_stats_entry(1, _stats(111, first_name="John", last_name="Doe"))
    assert "John Doe" in text
    assert text.startswith("1.")
