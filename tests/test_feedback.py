from unittest.mock import AsyncMock, MagicMock, patch

from bot.handlers import feedback


def _make_update(data: str):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.effective_user = MagicMock(id=111, username="johndoe")
    return update, query


async def test_feedback_callback_saves_like_choice():
    update, query = _make_update("feedback:like:2026-07-24T10:00:00+00:00")
    context = MagicMock()

    with patch.object(feedback.repository, "save_feedback") as mock_save:
        await feedback.feedback_callback(update, context)

    mock_save.assert_called_once()
    args = mock_save.call_args.args
    assert args[0] == 111
    assert args[1] == "johndoe"
    assert args[2] == "2026-07-24T10:00:00+00:00"
    assert args[3] == "like"
    query.edit_message_text.assert_awaited_once()


async def test_feedback_callback_saves_dislike_choice():
    update, query = _make_update("feedback:dislike:2026-07-24T10:00:00+00:00")
    context = MagicMock()

    with patch.object(feedback.repository, "save_feedback") as mock_save:
        await feedback.feedback_callback(update, context)

    assert mock_save.call_args.args[3] == "dislike"
