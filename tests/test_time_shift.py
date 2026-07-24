import re
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import time_shift
from bot.keyboards import TIME_SHIFT_CANCEL, TIME_SHIFT_DONE
from models.types import LastJob, SubtitleBlock, SubtitleStyle


def _make_message_update():
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_user = MagicMock(id=111)
    return update, message


def _make_callback_update(data: str):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=111)
    update.effective_chat = MagicMock(id=222)
    return update, query


def _make_context():
    context = MagicMock()
    context.user_data = {}
    context.bot.send_document = AsyncMock()
    return context


def _make_job():
    return LastJob(
        user_id=111,
        filename="clip.mp4",
        media_kind="audio",
        duration_seconds=10.0,
        style=SubtitleStyle.WORDS_3,
        blocks=[SubtitleBlock(["salom"], 1.0, 2.0)],
        completed_at="2026-07-23T10:00:00+00:00",
    )


async def test_time_shift_start_without_last_job_tells_user_to_process_one_first():
    update, message = _make_message_update()
    context = _make_context()

    with patch.object(time_shift.repository, "get_last_job", return_value=None):
        await time_shift.time_shift_start_handler(update, context)

    assert "kerak" in message.reply_text.call_args[0][0]
    assert "shift_offset_ms" not in context.user_data


async def test_time_shift_start_with_last_job_initializes_zero_offset():
    update, message = _make_message_update()
    context = _make_context()

    with patch.object(time_shift.repository, "get_last_job", return_value=_make_job()):
        await time_shift.time_shift_start_handler(update, context)

    assert context.user_data["shift_offset_ms"] == 0
    message.reply_text.assert_awaited_once()


async def test_time_shift_callback_accumulates_offset_across_presses():
    update, query = _make_callback_update("tshift:-100")
    context = _make_context()
    context.user_data["shift_offset_ms"] = 0

    await time_shift.time_shift_callback(update, context)
    assert context.user_data["shift_offset_ms"] == -100

    update2, query2 = _make_callback_update("tshift:500")
    await time_shift.time_shift_callback(update2, context)
    assert context.user_data["shift_offset_ms"] == 400


async def test_time_shift_cancel_clears_offset_and_confirms():
    update, query = _make_callback_update(TIME_SHIFT_CANCEL)
    context = _make_context()
    context.user_data["shift_offset_ms"] = 200

    await time_shift.time_shift_callback(update, context)

    assert "shift_offset_ms" not in context.user_data
    assert "Bekor" in query.edit_message_text.call_args[0][0]


async def test_time_shift_done_applies_offset_and_sends_new_srt(tmp_path):
    update, query = _make_callback_update(TIME_SHIFT_DONE)
    context = _make_context()
    context.user_data["shift_offset_ms"] = 500
    job = _make_job()

    with patch.object(time_shift.repository, "get_last_job", return_value=job), patch.object(
        time_shift, "new_session_dir", return_value=tmp_path
    ), patch.object(time_shift, "cleanup_session_dir") as mock_cleanup:
        await time_shift.time_shift_callback(update, context)

    context.bot.send_document.assert_awaited_once()
    kwargs = context.bot.send_document.call_args.kwargs
    assert kwargs["filename"] == "subtitr_tuzatilgan.srt"
    assert "shift_offset_ms" not in context.user_data
    mock_cleanup.assert_called_once_with(tmp_path)


async def test_time_shift_done_clamps_negative_result_to_zero(tmp_path):
    """Regression test for the 'no negative timestamps' requirement: a large
    negative offset must never push a cue below 0s, and the cue must still be
    present in the file that gets sent (not silently dropped)."""
    update, query = _make_callback_update(TIME_SHIFT_DONE)
    context = _make_context()
    context.user_data["shift_offset_ms"] = -5000  # -5s, more than the job's own start time
    job = _make_job()

    with patch.object(time_shift.repository, "get_last_job", return_value=job), patch.object(
        time_shift, "new_session_dir", return_value=tmp_path
    ), patch.object(time_shift, "cleanup_session_dir"):
        await time_shift.time_shift_callback(update, context)

    written = (tmp_path / "subtitr_tuzatilgan.srt").read_text(encoding="utf-8")
    assert "salom" in written  # the cue survived, not silently dropped
    assert not re.search(r"-\d", written.split("\n")[1])  # no negative timestamp (the --> arrow is fine)


async def test_time_shift_done_without_last_job_tells_user_gracefully():
    update, query = _make_callback_update(TIME_SHIFT_DONE)
    context = _make_context()
    context.user_data["shift_offset_ms"] = 100

    with patch.object(time_shift.repository, "get_last_job", return_value=None):
        await time_shift.time_shift_callback(update, context)

    assert "kerak" in query.edit_message_text.call_args[0][0]
    context.bot.send_document.assert_not_awaited()
