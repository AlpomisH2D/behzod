import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram.ext import ConversationHandler

import bot.handlers.subtitle_flow as flow
from bot.i18n import t
from bot.keyboards import HUB_DONE, HUB_FORMAT, HUB_STYLE, HUB_SUBLANG
from bot.states import State
from models.types import AlignedWord, SubtitleBlock, SubtitleStyle, TranscriptionResult, UserSettings, Word
from services.ffmpeg_service import FfmpegError, UnsupportedFormatError
from services.groq_service import TranscriptionError


@pytest.fixture(autouse=True)
def mock_record_usage():
    """Every _finish_job success path calls repository.record_usage() (admin
    usage stats) - auto-patched here so tests never hit the real sqlite file,
    while still letting individual tests assert on it by name if they care."""
    with patch.object(flow.repository, "record_usage") as mock:
        yield mock


@pytest.fixture(autouse=True)
def mock_update_last_word_style():
    """Every explicit hub style pick calls repository.update_last_word_style()
    - auto-patched for the same reason as mock_record_usage above."""
    with patch.object(flow.repository, "update_last_word_style") as mock:
        yield mock


def _make_callback_update(data: str, user_id: int = 222):
    query = MagicMock()
    query.data = data
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    update = MagicMock()
    update.callback_query = query
    update.message = None
    update.effective_chat = MagicMock(id=111)
    update.effective_user = MagicMock(id=user_id)
    return update, query


def _make_message(kind: str | None):
    message = MagicMock()
    message.video = message.audio = message.voice = message.document = None
    message.reply_text = AsyncMock()

    if kind in (None,):
        return message

    tg_file = MagicMock()
    tg_file.download_to_drive = AsyncMock()
    media_obj = MagicMock()
    media_obj.get_file = AsyncMock(return_value=tg_file)
    media_obj.file_unique_id = "abc123"
    media_obj.file_size = 1024 * 1024  # 1 MB - a real int so timeout math doesn't choke on a MagicMock

    if kind == "video":
        media_obj.file_name = "clip.mp4"
        message.video = media_obj
    elif kind == "audio":
        media_obj.file_name = "clip.mp3"
        message.audio = media_obj
    elif kind == "voice":
        message.voice = media_obj
    elif kind == "document_video":
        media_obj.file_name = "clip.mov"
        message.document = media_obj
    return message


def _make_update(message):
    update = MagicMock()
    update.message = message
    update.effective_chat = MagicMock(id=111)
    update.effective_user = MagicMock(id=222)
    return update


def _make_context():
    context = MagicMock()
    context.user_data = {}
    context.bot.send_message = AsyncMock()
    context.bot.send_document = AsyncMock()
    context.bot.edit_message_text = AsyncMock()

    async def _fake_send_message(*args, **kwargs):
        return MagicMock(message_id=999)

    context.bot.send_message.side_effect = _fake_send_message
    return context


def _uz_settings(user_id: int = 222):
    return UserSettings(user_id=user_id, language="uz", language_chosen=True)


# --- receive_media (entry point, unchanged behavior through download/extract) ---


async def test_receive_media_rejects_message_without_supported_media():
    message = _make_message(None)
    update = _make_update(message)
    context = _make_context()

    result = await flow.receive_media(update, context)

    assert result == ConversationHandler.END
    message.reply_text.assert_awaited_once()
    assert "qo'llab-quvvatlanmaydi" in message.reply_text.call_args[0][0]


async def test_receive_media_downloads_video_and_shows_hub_menu(tmp_path):
    message = _make_message("video")
    update = _make_update(message)
    context = _make_context()

    extracted = tmp_path / "clip.mp3"
    extracted.write_bytes(b"x" * 1024)

    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.ffmpeg_service, "ensure_audio", return_value=extracted
    ) as mock_ensure:
        result = await flow.receive_media(update, context)

    mock_ensure.assert_called_once()
    assert result == State.WAITING_HUB_MENU
    assert context.user_data["audio_path"] == extracted
    message.reply_text.assert_awaited_once()
    kwargs = message.reply_text.call_args.kwargs
    assert kwargs["reply_markup"] is not None


async def test_receive_media_handles_unsupported_format_from_ffmpeg_service(tmp_path):
    message = _make_message("document_video")
    update = _make_update(message)
    context = _make_context()

    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.ffmpeg_service, "ensure_audio", side_effect=UnsupportedFormatError("bad format")
    ), patch.object(flow, "cleanup_session_dir") as mock_cleanup:
        result = await flow.receive_media(update, context)

    assert result == ConversationHandler.END
    assert "qo'llab-quvvatlanmaydi" in message.reply_text.call_args[0][0]
    mock_cleanup.assert_called_once_with(tmp_path)


async def test_receive_media_handles_ffmpeg_failure(tmp_path):
    message = _make_message("video")
    update = _make_update(message)
    context = _make_context()

    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.ffmpeg_service, "ensure_audio", side_effect=FfmpegError("boom")
    ), patch.object(flow, "cleanup_session_dir") as mock_cleanup:
        result = await flow.receive_media(update, context)

    assert result == ConversationHandler.END
    assert "xatolik" in message.reply_text.call_args[0][0]
    mock_cleanup.assert_called_once_with(tmp_path)


async def test_receive_media_rejects_oversized_audio(tmp_path):
    message = _make_message("audio")
    update = _make_update(message)
    context = _make_context()

    extracted = tmp_path / "clip.mp3"
    extracted.write_bytes(b"x" * 1024)

    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.ffmpeg_service, "ensure_audio", return_value=extracted
    ), patch.object(flow.config, "MAX_AUDIO_FILE_SIZE_MB", 0), patch.object(
        flow, "cleanup_session_dir"
    ) as mock_cleanup:
        result = await flow.receive_media(update, context)

    assert result == ConversationHandler.END
    assert "katta" in message.reply_text.call_args[0][0]
    mock_cleanup.assert_called_once()


async def test_receive_media_download_timeout_reports_error_and_cleans_up(tmp_path):
    message = _make_message("video")

    async def _slow_get_file(*args, **kwargs):
        await asyncio.sleep(0.2)
        return MagicMock()

    message.video.get_file = AsyncMock(side_effect=_slow_get_file)
    update = _make_update(message)
    context = _make_context()

    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.config, "FILE_DOWNLOAD_TIMEOUT_SECONDS", 0.05
    ), patch.object(flow, "cleanup_session_dir") as mock_cleanup:
        result = await flow.receive_media(update, context)

    assert result == ConversationHandler.END
    assert "uzoq" in message.reply_text.call_args[0][0]
    mock_cleanup.assert_called_once_with(tmp_path)
    assert context.user_data == {}


async def test_receive_media_skips_hub_and_goes_to_script_source_when_auto_apply_enabled(tmp_path):
    """Section D: with auto-apply on, the hub is skipped entirely and the
    saved defaults are used - straight to the transcription-source question."""
    message = _make_message("audio")
    update = _make_update(message)
    context = _make_context()

    extracted = tmp_path / "clip.mp3"
    extracted.write_bytes(b"x" * 1024)

    auto_settings = UserSettings(
        user_id=222, language="uz", language_chosen=True,
        default_language="ru", default_word_style="words_3", default_format="vtt",
        auto_apply_enabled=True,
    )
    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.ffmpeg_service, "ensure_audio", return_value=extracted
    ), patch.object(flow.repository, "get_settings", return_value=auto_settings):
        result = await flow.receive_media(update, context)

    assert result == State.WAITING_SCRIPT_SOURCE_CHOICE
    assert context.user_data["style"] == SubtitleStyle.WORDS_3
    assert context.user_data["subtitle_language"] == "ru"
    assert context.user_data["output_format"] == "vtt"


async def test_receive_media_shows_hub_when_auto_apply_disabled(tmp_path):
    message = _make_message("audio")
    update = _make_update(message)
    context = _make_context()

    extracted = tmp_path / "clip.mp3"
    extracted.write_bytes(b"x" * 1024)

    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.ffmpeg_service, "ensure_audio", return_value=extracted
    ), patch.object(flow.repository, "get_settings", return_value=_uz_settings()):
        result = await flow.receive_media(update, context)

    assert result == State.WAITING_HUB_MENU
    # Pre-selected from the user's remembered last-used style, but not
    # "touched" this session - so no checkmark shows for it in the hub.
    assert context.user_data["style"] == SubtitleStyle.AI_CHOICE
    assert "style" not in context.user_data.get("hub_touched", set())


# --- Settings hub: 3 sub-menus (style / subtitle language / format) + Tayyor ---


async def test_hub_row_style_opens_style_submenu():
    update, query = _make_callback_update(HUB_STYLE)
    context = _make_context()

    result = await flow.hub_row_callback(update, context)

    assert result == State.WAITING_STYLE_CHOICE
    query.edit_message_text.assert_awaited_once()


async def test_hub_row_sublang_opens_sublang_submenu():
    update, query = _make_callback_update(HUB_SUBLANG)
    context = _make_context()

    result = await flow.hub_row_callback(update, context)

    assert result == State.WAITING_SUBLANG_CHOICE


async def test_hub_row_format_opens_format_submenu():
    update, query = _make_callback_update(HUB_FORMAT)
    context = _make_context()

    result = await flow.hub_row_callback(update, context)

    assert result == State.WAITING_FORMAT_CHOICE


async def test_hub_done_asks_script_source():
    update, query = _make_callback_update(HUB_DONE)
    context = _make_context()

    result = await flow.hub_done_callback(update, context)

    assert result == State.WAITING_SCRIPT_SOURCE_CHOICE
    assert "Skript" in query.edit_message_text.call_args[0][0]


async def test_hub_cancel_ends_conversation():
    update, query = _make_callback_update(flow.NAV_CANCEL)
    context = _make_context()

    with patch.object(flow, "cleanup_session_dir"):
        result = await flow.hub_cancel_callback(update, context)

    assert result == ConversationHandler.END


async def test_style_submenu_choice_saves_style_marks_touched_and_returns_to_hub():
    update, query = _make_callback_update("style:words_3")
    context = _make_context()

    result = await flow.style_choice_callback(update, context)

    assert result == State.WAITING_HUB_MENU
    assert context.user_data["style"] == SubtitleStyle.WORDS_3
    assert "style" in context.user_data["hub_touched"]
    query.edit_message_text.assert_awaited_once()


async def test_style_submenu_choice_remembers_it_as_the_users_last_word_style(
    mock_update_last_word_style,
):
    update, query = _make_callback_update("style:words_3", user_id=222)
    context = _make_context()

    await flow.style_choice_callback(update, context)

    mock_update_last_word_style.assert_called_once_with(222, "words_3")


async def test_receive_media_preselects_the_users_remembered_last_word_style(tmp_path):
    message = _make_message("audio")
    update = _make_update(message)
    context = _make_context()

    extracted = tmp_path / "clip.mp3"
    extracted.write_bytes(b"x" * 1024)

    remembered_settings = UserSettings(user_id=222, language="uz", language_chosen=True, last_word_style="words_5_2l")
    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.ffmpeg_service, "ensure_audio", return_value=extracted
    ), patch.object(flow.repository, "get_settings", return_value=remembered_settings):
        result = await flow.receive_media(update, context)

    assert result == State.WAITING_HUB_MENU
    assert context.user_data["style"] == SubtitleStyle.WORDS_5_2L
    assert "style" not in context.user_data.get("hub_touched", set())  # pre-filled, not "explicitly chosen"


async def test_receive_media_defaults_to_ai_choice_for_a_user_who_never_picked_a_style(tmp_path):
    """First-ever job for this user - no remembered style yet, so the hub
    falls back to "AI ixtiyorida" exactly like before this feature existed."""
    message = _make_message("audio")
    update = _make_update(message)
    context = _make_context()

    extracted = tmp_path / "clip.mp3"
    extracted.write_bytes(b"x" * 1024)

    with patch.object(flow, "new_session_dir", return_value=tmp_path), patch.object(
        flow.ffmpeg_service, "ensure_audio", return_value=extracted
    ), patch.object(flow.repository, "get_settings", return_value=_uz_settings()):
        result = await flow.receive_media(update, context)

    assert result == State.WAITING_HUB_MENU
    assert context.user_data["style"] == SubtitleStyle.AI_CHOICE


async def test_format_submenu_choice_saves_format_marks_touched_and_returns_to_hub():
    update, query = _make_callback_update("format:vtt")
    context = _make_context()

    result = await flow.format_choice_callback(update, context)

    assert result == State.WAITING_HUB_MENU
    assert context.user_data["output_format"] == "vtt"
    assert "format" in context.user_data["hub_touched"]


async def test_sublang_submenu_choice_saves_language_marks_touched_and_returns_to_hub():
    update, query = _make_callback_update("sublang:ru")
    context = _make_context()

    result = await flow.sublang_choice_callback(update, context)

    assert result == State.WAITING_HUB_MENU
    assert context.user_data["subtitle_language"] == "ru"
    assert "sublang" in context.user_data["hub_touched"]


async def test_visiting_one_submenu_does_not_reset_a_previous_selection():
    """Core regression test for the hub redesign: making a choice in the
    format sub-menu, then opening the style sub-menu, must not wipe out the
    format choice already made."""
    update, query = _make_callback_update("format:vtt")
    context = _make_context()
    await flow.format_choice_callback(update, context)

    update2, query2 = _make_callback_update(HUB_STYLE)
    await flow.hub_row_callback(update2, context)

    assert context.user_data["output_format"] == "vtt"
    assert "format" in context.user_data["hub_touched"]


async def test_hub_submenu_back_returns_to_hub_without_changing_anything():
    update, query = _make_callback_update(flow.NAV_BACK)
    context = _make_context()
    context.user_data["style"] = SubtitleStyle.WORDS_5_2L
    context.user_data["hub_touched"] = {"style"}

    result = await flow.hub_submenu_back_callback(update, context)

    assert result == State.WAITING_HUB_MENU
    assert context.user_data["style"] == SubtitleStyle.WORDS_5_2L  # untouched by Back


async def test_script_source_manual_asks_for_script_text():
    update, query = _make_callback_update("scriptsrc:manual")
    context = _make_context()

    result = await flow.script_source_callback(update, context)

    assert result == State.WAITING_SCRIPT_TEXT
    assert "Skriptni" in query.edit_message_text.call_args[0][0]


async def test_script_source_auto_runs_the_transcription_phase():
    update, query = _make_callback_update("scriptsrc:auto")
    context = _make_context()
    context.user_data["audio_path"] = "/tmp/fake.mp3"

    with patch.object(
        flow, "_run_transcription_phase", new=AsyncMock(return_value=ConversationHandler.END)
    ) as mock_phase:
        result = await flow.script_source_callback(update, context)

    mock_phase.assert_awaited_once_with(update, context, original_text=None)
    assert result == ConversationHandler.END


async def test_receive_script_text_runs_the_transcription_phase_with_the_given_text():
    message = _make_message(None)
    message.text = "Mening skriptim"
    update = _make_update(message)
    context = _make_context()

    with patch.object(
        flow, "_run_transcription_phase", new=AsyncMock(return_value=ConversationHandler.END)
    ) as mock_phase:
        result = await flow.receive_script_text(update, context)

    mock_phase.assert_awaited_once_with(update, context, original_text="Mening skriptim")
    assert result == ConversationHandler.END


# --- Back / Cancel navigation from step 4 back to the hub ---


async def test_script_source_nav_back_returns_to_hub():
    update, query = _make_callback_update(flow.NAV_BACK)
    context = _make_context()

    result = await flow.script_source_nav_callback(update, context)

    assert result == State.WAITING_HUB_MENU


async def test_script_source_nav_cancel_ends_conversation():
    update, query = _make_callback_update(flow.NAV_CANCEL)
    context = _make_context()

    with patch.object(flow, "cleanup_session_dir"):
        result = await flow.script_source_nav_callback(update, context)

    assert result == ConversationHandler.END


# --- _run_transcription_phase -> transcript confirmation -> _finish_job ---
# (transcribe/align -> confirm/edit -> split -> translate -> format -> deliver)


def _patch_transcription_success(words=None, duration=0.5):
    return patch.object(
        flow.elevenlabs_service,
        "transcribe_with_fallback_async",
        new=AsyncMock(return_value=TranscriptionResult(words=words or [Word("salom", 0.0, 0.5)], duration=duration)),
    )


def _patch_finish_job_success(fake_blocks):
    return (
        patch.object(flow.claude_service, "split_with_fallback", return_value=fake_blocks),
        patch.object(flow.repository, "get_settings", return_value=_uz_settings()),
        patch.object(flow.repository, "save_last_job"),
    )


async def _confirm_transcript(update: "flow.Update", context) -> int:
    """Drives the transcript-confirmation step (Section B) forward, as a real
    user pressing '✅ Tasdiqlash' would - used by tests that exercise the full
    pipeline end-to-end without caring about the confirmation UI itself."""
    confirm_update, confirm_query = _make_callback_update(flow.TRANSCRIPT_CONFIRM, user_id=update.effective_user.id)
    confirm_update.effective_chat = update.effective_chat
    return await flow.transcript_confirm_callback(confirm_update, context)


async def _run_full_pipeline(update, context, original_text=None) -> int:
    result = await flow._run_transcription_phase(update, context, original_text=original_text)
    if result != State.WAITING_TRANSCRIPT_CONFIRMATION:
        return result
    return await _confirm_transcript(update, context)


async def test_transcription_phase_scales_elevenlabs_timeout_with_audio_duration(tmp_path):
    """A ~2min clip must not be handed the same flat timeout sized for a short
    one - see the "bot hangs on longer audio" fix."""
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["audio_path"] = tmp_path / "in.mp3"
    context.user_data["session_dir"] = tmp_path

    with patch.object(flow.ffmpeg_service, "get_duration", return_value=114.0), _patch_transcription_success(
        duration=114.0
    ) as mock_transcribe:
        await flow._run_transcription_phase(update, context, original_text=None)

    _, kwargs = mock_transcribe.call_args
    assert kwargs["timeout"] == 114.0 * flow.config.ELEVENLABS_TIMEOUT_SECONDS_PER_AUDIO_SECOND
    assert kwargs["timeout"] > flow.config.ELEVENLABS_REQUEST_TIMEOUT_SECONDS


async def test_transcription_phase_uses_minimum_elevenlabs_timeout_for_short_audio(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["audio_path"] = tmp_path / "in.mp3"
    context.user_data["session_dir"] = tmp_path

    with patch.object(flow.ffmpeg_service, "get_duration", return_value=5.0), _patch_transcription_success(
        duration=5.0
    ) as mock_transcribe:
        await flow._run_transcription_phase(update, context, original_text=None)

    _, kwargs = mock_transcribe.call_args
    assert kwargs["timeout"] == flow.config.ELEVENLABS_REQUEST_TIMEOUT_SECONDS


async def test_transcription_phase_uses_uzbek_error_message_on_transcription_failure(tmp_path):
    """Every failure must produce a visible reply, never a silent hang."""
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["audio_path"] = tmp_path / "in.mp3"
    context.user_data["session_dir"] = tmp_path

    with patch.object(flow.ffmpeg_service, "get_duration", return_value=5.0), patch.object(
        flow.elevenlabs_service,
        "transcribe_with_fallback_async",
        new=AsyncMock(side_effect=flow.TranscriptionError("wrong api key")),
    ):
        result = await flow._run_transcription_phase(update, context, original_text=None)

    assert result == ConversationHandler.END
    edited_texts = [call.args[0] for call in context.bot.edit_message_text.call_args_list]
    assert any("Transkripsiya qilishda xatolik" in text for text in edited_texts)


async def test_transcription_phase_shows_confirmation_prompt_with_transcript_text(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["audio_path"] = tmp_path / "in.mp3"
    context.user_data["session_dir"] = tmp_path

    words = [Word("Salom", 0.0, 0.3), Word("dunyo", 0.3, 0.6)]
    with _patch_transcription_success(words=words):
        result = await flow._run_transcription_phase(update, context, original_text=None)

    assert result == State.WAITING_TRANSCRIPT_CONFIRMATION
    edit_call = context.bot.edit_message_text.call_args
    assert "Salom dunyo" in edit_call.args[0]
    assert edit_call.kwargs["reply_markup"] is not None
    assert context.user_data["transcript_text"] == "Salom dunyo"


async def test_transcript_confirm_callback_proceeds_to_finish_job():
    update, query = _make_callback_update(flow.TRANSCRIPT_CONFIRM)
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = "/tmp/session"

    with patch.object(flow, "_finish_job", new=AsyncMock(return_value=ConversationHandler.END)) as mock_finish:
        result = await flow.transcript_confirm_callback(update, context)

    mock_finish.assert_awaited_once_with(update, context)
    assert result == ConversationHandler.END


async def test_transcript_edit_callback_prompts_for_corrected_text():
    update, query = _make_callback_update(flow.TRANSCRIPT_EDIT)
    context = _make_context()

    result = await flow.transcript_edit_callback(update, context)

    assert result == State.WAITING_TRANSCRIPT_CORRECTION
    query.edit_message_text.assert_awaited_once()


async def test_receive_transcript_correction_realigns_and_finishes_job():
    message = _make_message(None)
    message.text = "Tuzatilgan matn"
    update = _make_update(message)
    context = _make_context()
    context.user_data["groq_words"] = [Word("salom", 0.0, 0.5)]
    context.user_data["audio_duration"] = 0.5

    with patch.object(flow, "_finish_job", new=AsyncMock(return_value=ConversationHandler.END)) as mock_finish:
        result = await flow.receive_transcript_correction(update, context)

    assert result == ConversationHandler.END
    mock_finish.assert_awaited_once_with(update, context)
    aligned = context.user_data["aligned_words"]
    assert [w.text for w in aligned] == ["Tuzatilgan", "matn"]


async def test_run_full_pipeline_uses_all_defaults_when_hub_never_touched(tmp_path):
    """Pressing Tayyor without opening any sub-menu must proceed with the
    documented defaults: AI ixtiyorida style, O'zbek language, SRT format."""
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["audio_path"] = tmp_path / "in.mp3"
    context.user_data["session_dir"] = tmp_path
    # deliberately not setting style/output_format/subtitle_language/hub_touched

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    with _patch_transcription_success(), patch.object(
        flow.claude_service, "split_with_fallback", return_value=fake_blocks
    ) as mock_split, patch.object(
        flow.claude_service, "translate_lines"
    ) as mock_translate, patch.object(
        flow.repository, "get_settings", return_value=_uz_settings()
    ), patch.object(flow.repository, "save_last_job"):
        await _run_full_pipeline(update, context)

    assert mock_split.call_args[0][1] == SubtitleStyle.AI_CHOICE
    mock_translate.assert_not_called()  # subtitle language default is "uz" - no translation needed
    kwargs = context.bot.send_document.call_args.kwargs
    assert kwargs["filename"] == "subtitr.srt"


async def test_run_full_pipeline_respects_the_one_changed_setting_and_defaults_the_rest(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["audio_path"] = tmp_path / "in.mp3"
    context.user_data["session_dir"] = tmp_path
    context.user_data["style"] = SubtitleStyle.WORDS_2
    context.user_data["hub_touched"] = {"style"}
    # output_format / subtitle_language left untouched -> should stay default

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    with _patch_transcription_success(), patch.object(
        flow.claude_service, "split_with_fallback", return_value=fake_blocks
    ) as mock_split, patch.object(
        flow.claude_service, "translate_lines"
    ) as mock_translate, patch.object(
        flow.repository, "get_settings", return_value=_uz_settings()
    ), patch.object(flow.repository, "save_last_job"):
        await _run_full_pipeline(update, context)

    assert mock_split.call_args[0][1] == SubtitleStyle.WORDS_2  # the one explicit choice respected
    mock_translate.assert_not_called()  # language default "uz" - untouched
    kwargs = context.bot.send_document.call_args.kwargs
    assert kwargs["filename"] == "subtitr.srt"  # format default - untouched


async def test_run_full_pipeline_sends_document_and_feedback_prompt(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["audio_path"] = tmp_path / "in.mp3"
    context.user_data["session_dir"] = tmp_path

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    p2, p3, p4 = _patch_finish_job_success(fake_blocks)
    with _patch_transcription_success(), p2, p3, p4:
        result = await _run_full_pipeline(update, context)

    assert result == ConversationHandler.END
    context.bot.send_document.assert_awaited_once()
    kwargs = context.bot.send_document.call_args.kwargs
    assert kwargs["filename"] == "subtitr.srt"
    context.bot.edit_message_text.assert_any_call(
        t("job.done", "uz"), chat_id=111, message_id=999
    )
    # feedback prompt with keyboard sent as the final message
    last_send = context.bot.send_message.call_args_list[-1]
    assert last_send.kwargs["reply_markup"] is not None
    assert "session_dir" not in context.user_data


async def test_finish_job_cancels_animation_task_before_finishing():
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = "/tmp/session"

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    with patch.object(flow, "_animate_processing", new=AsyncMock()), patch.object(flow, "cleanup_session_dir"):
        p2, p3, p4 = _patch_finish_job_success(fake_blocks)
        with p2, p3, p4, patch.object(flow.srt_service, "write_subtitle_file"), patch(
            "builtins.open", MagicMock()
        ):
            await flow._finish_job(update, context)

    # No exception means the animation task's cancellation was awaited cleanly.


async def test_run_full_pipeline_reports_error_when_both_transcription_engines_fail(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["audio_path"] = tmp_path / "in.mp3"
    context.user_data["session_dir"] = tmp_path

    with patch.object(
        flow.elevenlabs_service,
        "transcribe_with_fallback_async",
        new=AsyncMock(side_effect=TranscriptionError("balans tugadi")),
    ):
        result = await _run_full_pipeline(update, context)

    assert result == ConversationHandler.END
    error_text = context.bot.edit_message_text.call_args.args[0]
    assert "xatolik" in error_text
    context.bot.send_document.assert_not_awaited()


async def test_finish_job_reports_error_on_unexpected_split_failure(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = tmp_path

    with patch.object(
        flow.claude_service, "split_with_fallback", side_effect=RuntimeError("kutilmagan")
    ), patch.object(flow.repository, "get_settings", return_value=_uz_settings()):
        result = await flow._finish_job(update, context)

    assert result == ConversationHandler.END
    error_text = context.bot.edit_message_text.call_args.args[0]
    assert "xatolik" in error_text
    context.bot.send_document.assert_not_awaited()


async def test_finish_job_passes_visual_template_and_selected_style_to_claude_service():
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = "/tmp/session"
    context.user_data["style"] = SubtitleStyle.WORDS_6_7_3L

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    hormozi_settings = UserSettings(user_id=222, language="uz", language_chosen=True, visual_template="hormozi")

    with patch.object(
        flow.claude_service, "split_with_fallback", return_value=fake_blocks
    ) as mock_split, patch.object(
        flow.repository, "get_settings", return_value=hormozi_settings
    ), patch.object(flow.repository, "save_last_job"):
        await flow._finish_job(update, context)

    args, kwargs = mock_split.call_args
    assert args[1] == SubtitleStyle.WORDS_6_7_3L
    assert kwargs["visual_template"] == "hormozi"


async def test_finish_job_translates_when_subtitle_language_is_not_uzbek(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = tmp_path
    context.user_data["subtitle_language"] = "ru"

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    translated_blocks = [SubtitleBlock(["privet"], 0.0, 0.5)]

    with patch.object(
        flow.claude_service, "split_with_fallback", return_value=fake_blocks
    ), patch.object(
        flow.claude_service, "translate_lines", return_value=translated_blocks
    ) as mock_translate, patch.object(
        flow.repository, "get_settings", return_value=_uz_settings()
    ), patch.object(flow.repository, "save_last_job"):
        result = await flow._finish_job(update, context)

    assert result == ConversationHandler.END
    args, kwargs = mock_translate.call_args
    assert args == (fake_blocks, "ru")
    assert "timeout" in kwargs
    context.bot.send_document.assert_awaited_once()


async def test_finish_job_falls_back_to_original_text_on_translation_error(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = tmp_path
    context.user_data["subtitle_language"] = "en"

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]

    with patch.object(
        flow.claude_service, "split_with_fallback", return_value=fake_blocks
    ), patch.object(
        flow.claude_service, "translate_lines", side_effect=flow.claude_service.TranslationError("xato")
    ), patch.object(
        flow.repository, "get_settings", return_value=_uz_settings()
    ), patch.object(flow.repository, "save_last_job"):
        result = await flow._finish_job(update, context)

    assert result == ConversationHandler.END
    context.bot.send_document.assert_awaited_once()  # translation failing is not fatal


async def test_finish_job_falls_back_to_srt_for_unsupported_format_with_notice(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = tmp_path
    context.user_data["output_format"] = "mcc_scc_stl"

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    p2, p3, p4 = _patch_finish_job_success(fake_blocks)
    with p2, p3, p4:
        await flow._finish_job(update, context)

    kwargs = context.bot.send_document.call_args.kwargs
    assert kwargs["filename"] == "subtitr.srt"
    notice_calls = [
        c.args[1] for c in context.bot.send_message.call_args_list
        if len(c.args) > 1 and isinstance(c.args[1], str) and "mavjud emas" in c.args[1]
    ]
    assert len(notice_calls) == 1


async def test_finish_job_uses_vtt_extension_when_vtt_requested(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = tmp_path
    context.user_data["output_format"] = "vtt"

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    p2, p3, p4 = _patch_finish_job_success(fake_blocks)
    with p2, p3, p4:
        await flow._finish_job(update, context)

    kwargs = context.bot.send_document.call_args.kwargs
    assert kwargs["filename"] == "subtitr.vtt"


async def test_finish_job_saves_last_job_with_correct_metadata(tmp_path):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = tmp_path
    context.user_data["original_filename"] = "clip.mp4"
    context.user_data["media_kind"] = "video"
    context.user_data["audio_duration"] = 49.0
    context.user_data["style"] = SubtitleStyle.WORDS_2

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    with patch.object(
        flow.claude_service, "split_with_fallback", return_value=fake_blocks
    ), patch.object(
        flow.repository, "get_settings", return_value=_uz_settings()
    ), patch.object(flow.repository, "save_last_job") as mock_save:
        await flow._finish_job(update, context)

    kwargs = mock_save.call_args.kwargs
    assert kwargs["filename"] == "clip.mp4"
    assert kwargs["media_kind"] == "video"
    assert kwargs["duration_seconds"] == 49.0
    assert kwargs["style"] == SubtitleStyle.WORDS_2
    assert kwargs["blocks"] == fake_blocks


async def test_finish_job_records_usage_stats_on_successful_delivery(tmp_path, mock_record_usage):
    """Admin usage stats (per-user file count + total minutes) must be
    recorded once a subtitle file has actually been delivered."""
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = tmp_path
    context.user_data["audio_duration"] = 49.0

    fake_blocks = [SubtitleBlock(["salom"], 0.0, 0.5)]
    with patch.object(flow.claude_service, "split_with_fallback", return_value=fake_blocks), patch.object(
        flow.repository, "get_settings", return_value=_uz_settings()
    ), patch.object(flow.repository, "save_last_job"):
        await flow._finish_job(update, context)

    mock_record_usage.assert_called_once_with(222, 49.0)


async def test_finish_job_does_not_record_usage_stats_on_failure(tmp_path, mock_record_usage):
    update = _make_update(_make_message(None))
    context = _make_context()
    context.user_data["aligned_words"] = [AlignedWord("salom", 0.0, 0.5)]
    context.user_data["session_dir"] = tmp_path

    with patch.object(
        flow.claude_service, "split_with_fallback", side_effect=RuntimeError("kutilmagan")
    ), patch.object(flow.repository, "get_settings", return_value=_uz_settings()):
        await flow._finish_job(update, context)

    mock_record_usage.assert_not_called()


# --- Section D: unified fallback text everywhere ---


async def test_unexpected_text_fallback_resets_and_sends_fallback_text():
    message = _make_message(None)
    message.text = "salom, nima uchun javob bermayapsan?"
    update = _make_update(message)
    context = _make_context()
    context.user_data["session_dir"] = "/tmp/stale_session"

    with patch.object(flow, "cleanup_session_dir") as mock_cleanup:
        result = await flow.unexpected_text_fallback(update, context)

    assert result == ConversationHandler.END
    message.reply_text.assert_awaited_once_with(t("fallback.send_media", "uz"))
    mock_cleanup.assert_called_once()
    assert context.user_data == {}


async def test_unexpected_callback_fallback_answers_stale_button_and_resets():
    update, query = _make_callback_update("style:words_3")
    context = _make_context()
    context.user_data["session_dir"] = "/tmp/stale_session"

    with patch.object(flow, "cleanup_session_dir") as mock_cleanup:
        result = await flow.unexpected_callback_fallback(update, context)

    assert result == ConversationHandler.END
    query.answer.assert_awaited_once()  # stops the button's loading spinner
    context.bot.send_message.assert_awaited_once()
    mock_cleanup.assert_called_once()


async def test_unexpected_input_fallback_handles_non_text_non_callback_updates():
    update = _make_update(_make_message(None))
    context = _make_context()

    with patch.object(flow, "cleanup_session_dir") as mock_cleanup:
        result = await flow.unexpected_input_fallback(update, context)

    assert result == ConversationHandler.END
    update.message.reply_text.assert_awaited_once()


async def test_restart_with_new_media_discards_stale_session_and_processes_new_file(tmp_path):
    """Core regression test: media arriving while the conversation is stuck in
    an unrelated state must not be silently dropped - the stale session
    should be discarded and the new file processed as if it were a fresh start.
    """
    stale_session_dir = tmp_path / "stale"
    stale_session_dir.mkdir()
    new_session_dir_path = tmp_path / "new"
    new_session_dir_path.mkdir()

    message = _make_message("video")
    update = _make_update(message)
    context = _make_context()
    context.user_data["session_dir"] = stale_session_dir
    context.user_data["audio_path"] = stale_session_dir / "old.mp3"
    context.user_data["style"] = SubtitleStyle.WORDS_1

    extracted = new_session_dir_path / "clip.mp3"
    extracted.write_bytes(b"x" * 1024)

    with patch.object(flow, "cleanup_session_dir") as mock_cleanup, patch.object(
        flow, "new_session_dir", return_value=new_session_dir_path
    ), patch.object(flow.ffmpeg_service, "ensure_audio", return_value=extracted):
        result = await flow.restart_with_new_media(update, context)

    mock_cleanup.assert_called_once_with(stale_session_dir)  # old session torn down, not leaked
    assert result == State.WAITING_HUB_MENU  # new file processed through the normal path
    assert context.user_data["session_dir"] == new_session_dir_path
    assert context.user_data["audio_path"] == extracted
    # The stale WORDS_1 choice didn't survive the restart - "style" here is
    # freshly re-derived from the user's remembered default, not the old value.
    assert context.user_data["style"] != SubtitleStyle.WORDS_1
    assert "style" not in context.user_data.get("hub_touched", set())


def test_conversation_handler_has_catch_all_fallbacks():
    """Structural regression test for the original bug: fallbacks used to be
    just [CommandHandler("cancel", cancel)], so anything other than /cancel
    sent during an unmatched state was silently dropped. This locks in that
    every major update type (media, callback, text, anything else) now has a
    fallback so the conversation can never again go silent.
    """
    handler = flow.build_conversation_handler()
    fallback_types = [type(h).__name__ for h in handler.fallbacks]

    assert "CommandHandler" in fallback_types
    assert "CallbackQueryHandler" in fallback_types
    assert fallback_types.count("MessageHandler") >= 3


def test_conversation_handler_covers_all_new_states():
    handler = flow.build_conversation_handler()
    assert set(handler.states.keys()) == {
        State.WAITING_HUB_MENU,
        State.WAITING_STYLE_CHOICE,
        State.WAITING_FORMAT_CHOICE,
        State.WAITING_SUBLANG_CHOICE,
        State.WAITING_SCRIPT_SOURCE_CHOICE,
        State.WAITING_SCRIPT_TEXT,
        State.WAITING_TRANSCRIPT_CONFIRMATION,
        State.WAITING_TRANSCRIPT_CORRECTION,
    }
