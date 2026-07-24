from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import last_job
from models.types import LastJob, SubtitleBlock, SubtitleStyle


def _make_update():
    message = MagicMock()
    message.reply_text = AsyncMock()
    update = MagicMock()
    update.message = message
    update.effective_user = MagicMock(id=111)
    return update, message


def _make_job(minutes_ago: float, style=SubtitleStyle.WORDS_3, duration=49.0):
    completed_at = (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()
    return LastJob(
        user_id=111,
        filename="clip.mp4",
        media_kind="audio",
        duration_seconds=duration,
        style=style,
        blocks=[SubtitleBlock(["salom"], 0.0, 1.0)],
        completed_at=completed_at,
    )


async def test_last_job_status_reports_no_jobs_message_when_none_recorded():
    update, message = _make_update()
    context = MagicMock()

    with patch.object(last_job.repository, "get_last_job", return_value=None):
        await last_job.last_job_status_handler(update, context)

    assert "yo'q" in message.reply_text.call_args[0][0]


async def test_last_job_status_formats_summary_with_duration_style_and_relative_time():
    update, message = _make_update()
    context = MagicMock()
    job = _make_job(minutes_ago=2)

    with patch.object(last_job.repository, "get_last_job", return_value=job):
        await last_job.last_job_status_handler(update, context)

    text = message.reply_text.call_args[0][0]
    assert "49s" in text
    assert "3 ta so'z" in text
    assert "2 daqiqa oldin" in text


def test_format_relative_time_just_now_for_under_a_minute():
    completed_at = datetime.now(timezone.utc).isoformat()
    assert last_job._format_relative_time(completed_at, "uz") == "hozirgina"


def test_format_relative_time_hours():
    completed_at = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
    assert last_job._format_relative_time(completed_at, "uz") == "3 soat oldin"


def test_format_relative_time_days():
    completed_at = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    assert last_job._format_relative_time(completed_at, "uz") == "2 kun oldin"


def test_format_job_summary_handles_unknown_duration():
    job = _make_job(minutes_ago=5, duration=None)
    assert "noma'lum davomiylik" in last_job._format_job_summary(job, "uz")
