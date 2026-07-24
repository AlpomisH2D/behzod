from db import repository
from models.types import SubtitleBlock, SubtitleStyle


def test_get_settings_creates_default_row_with_language_not_chosen(tmp_path):
    db_path = str(tmp_path / "test.db")

    settings = repository.get_settings(111, db_path=db_path)

    assert settings.language == "uz"
    assert settings.language_chosen is False


def test_update_language_sets_value_and_marks_chosen(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.get_settings(111, db_path=db_path)

    repository.update_language(111, "ru", db_path=db_path)
    settings = repository.get_settings(111, db_path=db_path)

    assert settings.language == "ru"
    assert settings.language_chosen is True


def test_update_language_does_not_affect_other_users(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.get_settings(111, db_path=db_path)
    repository.get_settings(222, db_path=db_path)

    repository.update_language(111, "en", db_path=db_path)

    assert repository.get_settings(111, db_path=db_path).language_chosen is True
    assert repository.get_settings(222, db_path=db_path).language_chosen is False


def test_update_visual_template_persists(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.get_settings(111, db_path=db_path)

    repository.update_visual_template(111, "hormozi", db_path=db_path)

    assert repository.get_settings(111, db_path=db_path).visual_template == "hormozi"


def test_get_settings_defaults_visual_template_to_classic(tmp_path):
    db_path = str(tmp_path / "test.db")

    assert repository.get_settings(111, db_path=db_path).visual_template == "classic"


def test_get_last_job_returns_none_when_no_job_recorded(tmp_path):
    db_path = str(tmp_path / "test.db")

    assert repository.get_last_job(111, db_path=db_path) is None


def test_save_and_get_last_job_round_trip(tmp_path):
    db_path = str(tmp_path / "test.db")
    blocks = [SubtitleBlock(["salom", "dunyo"], 0.0, 1.5)]

    repository.save_last_job(
        111,
        filename="clip.mp4",
        media_kind="video",
        duration_seconds=49.0,
        style=SubtitleStyle.WORDS_3,
        blocks=blocks,
        completed_at="2026-07-23T10:00:00+00:00",
        db_path=db_path,
    )
    job = repository.get_last_job(111, db_path=db_path)

    assert job.filename == "clip.mp4"
    assert job.media_kind == "video"
    assert job.duration_seconds == 49.0
    assert job.style == SubtitleStyle.WORDS_3
    assert job.blocks == blocks
    assert job.completed_at == "2026-07-23T10:00:00+00:00"


def test_save_last_job_replaces_previous_job_for_same_user(tmp_path):
    db_path = str(tmp_path / "test.db")
    first_blocks = [SubtitleBlock(["birinchi"], 0.0, 1.0)]
    second_blocks = [SubtitleBlock(["ikkinchi"], 0.0, 2.0)]

    repository.save_last_job(
        111, filename="a.mp4", media_kind="video", duration_seconds=10.0,
        style=SubtitleStyle.WORDS_3, blocks=first_blocks, completed_at="t1", db_path=db_path,
    )
    repository.save_last_job(
        111, filename="b.mp4", media_kind="audio", duration_seconds=20.0,
        style=SubtitleStyle.WORDS_4_2L, blocks=second_blocks, completed_at="t2", db_path=db_path,
    )

    job = repository.get_last_job(111, db_path=db_path)
    assert job.filename == "b.mp4"
    assert job.blocks == second_blocks


def test_register_user_creates_profile_row(tmp_path):
    db_path = str(tmp_path / "test.db")

    repository.register_user(111, "johndoe", "John", "Doe", "2026-07-24T10:00:00+00:00", db_path=db_path)
    profiles = repository.list_user_profiles(db_path=db_path)

    assert len(profiles) == 1
    assert profiles[0].user_id == 111
    assert profiles[0].username == "johndoe"
    assert profiles[0].first_name == "John"
    assert profiles[0].last_name == "Doe"
    assert profiles[0].phone_number is None
    assert profiles[0].joined_at == "2026-07-24T10:00:00+00:00"


def test_register_user_is_idempotent_and_never_overwrites(tmp_path):
    """A second registration for the same user_id (e.g. they hit /start again)
    must not clobber their already-saved profile or phone number."""
    db_path = str(tmp_path / "test.db")
    repository.register_user(111, "johndoe", "John", "Doe", "2026-07-24T10:00:00+00:00", db_path=db_path)
    repository.save_phone_number(111, "+998994253952", db_path=db_path)

    repository.register_user(111, "changed_username", "Changed", None, "2026-07-25T00:00:00+00:00", db_path=db_path)

    profiles = repository.list_user_profiles(db_path=db_path)
    assert len(profiles) == 1
    assert profiles[0].username == "johndoe"
    assert profiles[0].phone_number == "+998994253952"


def test_get_phone_number_returns_none_when_not_saved(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.register_user(111, "johndoe", "John", None, "2026-07-24T10:00:00+00:00", db_path=db_path)

    assert repository.get_phone_number(111, db_path=db_path) is None


def test_get_phone_number_returns_none_for_unregistered_user(tmp_path):
    db_path = str(tmp_path / "test.db")

    assert repository.get_phone_number(999, db_path=db_path) is None


def test_save_phone_number_then_get_phone_number_round_trip(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.register_user(111, "johndoe", "John", None, "2026-07-24T10:00:00+00:00", db_path=db_path)

    repository.save_phone_number(111, "+998994253952", db_path=db_path)

    assert repository.get_phone_number(111, db_path=db_path) == "+998994253952"


def test_list_user_profiles_returns_all_users_ordered_by_joined_at(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.register_user(222, "second", "Second", None, "2026-07-24T12:00:00+00:00", db_path=db_path)
    repository.register_user(111, "first", "First", None, "2026-07-24T10:00:00+00:00", db_path=db_path)

    profiles = repository.list_user_profiles(db_path=db_path)

    assert [p.user_id for p in profiles] == [111, 222]


def test_list_user_profiles_empty_database_returns_empty_list(tmp_path):
    db_path = str(tmp_path / "test.db")

    assert repository.list_user_profiles(db_path=db_path) == []


# --- Remembered last-used word style (hub menu default) ---


def test_get_settings_defaults_last_word_style_to_ai_choice(tmp_path):
    db_path = str(tmp_path / "test.db")

    assert repository.get_settings(111, db_path=db_path).last_word_style == "ai_choice"


def test_update_last_word_style_persists(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.get_settings(111, db_path=db_path)

    repository.update_last_word_style(111, "words_3", db_path=db_path)

    assert repository.get_settings(111, db_path=db_path).last_word_style == "words_3"


def test_update_last_word_style_does_not_affect_other_users(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.get_settings(111, db_path=db_path)
    repository.get_settings(222, db_path=db_path)

    repository.update_last_word_style(111, "words_6_7_3l", db_path=db_path)

    assert repository.get_settings(111, db_path=db_path).last_word_style == "words_6_7_3l"
    assert repository.get_settings(222, db_path=db_path).last_word_style == "ai_choice"


def test_update_last_word_style_is_independent_of_settings_screen_default(tmp_path):
    """last_word_style (hub memory) and default_word_style (Settings-screen
    saved default for auto-apply) must never clobber each other."""
    db_path = str(tmp_path / "test.db")
    repository.get_settings(111, db_path=db_path)
    repository.update_default_word_style(111, "words_4", db_path=db_path)

    repository.update_last_word_style(111, "words_2", db_path=db_path)

    settings = repository.get_settings(111, db_path=db_path)
    assert settings.default_word_style == "words_4"
    assert settings.last_word_style == "words_2"


# --- Usage statistics (admin-only) ---


def test_list_usage_stats_empty_database_returns_empty_list(tmp_path):
    db_path = str(tmp_path / "test.db")

    assert repository.list_usage_stats(db_path=db_path) == []


def test_record_usage_creates_a_row_on_first_call(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.register_user(111, "johndoe", "John", None, "2026-07-24T10:00:00+00:00", db_path=db_path)

    repository.record_usage(111, 90.0, db_path=db_path)

    stats = repository.list_usage_stats(db_path=db_path)
    assert len(stats) == 1
    assert stats[0].user_id == 111
    assert stats[0].total_media_count == 1
    assert stats[0].total_duration_seconds == 90.0


def test_record_usage_accumulates_across_multiple_calls(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.register_user(111, "johndoe", "John", None, "2026-07-24T10:00:00+00:00", db_path=db_path)

    repository.record_usage(111, 60.0, db_path=db_path)
    repository.record_usage(111, 30.0, db_path=db_path)
    repository.record_usage(111, 90.0, db_path=db_path)

    stats = repository.list_usage_stats(db_path=db_path)
    assert stats[0].total_media_count == 3
    assert stats[0].total_duration_seconds == 180.0


def test_record_usage_treats_missing_duration_as_zero(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.register_user(111, "johndoe", "John", None, "2026-07-24T10:00:00+00:00", db_path=db_path)

    repository.record_usage(111, None, db_path=db_path)

    stats = repository.list_usage_stats(db_path=db_path)
    assert stats[0].total_media_count == 1
    assert stats[0].total_duration_seconds == 0


def test_record_usage_keeps_separate_totals_per_user(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.register_user(111, "first", "First", None, "2026-07-24T10:00:00+00:00", db_path=db_path)
    repository.register_user(222, "second", "Second", None, "2026-07-24T10:00:00+00:00", db_path=db_path)

    repository.record_usage(111, 60.0, db_path=db_path)
    repository.record_usage(222, 600.0, db_path=db_path)
    repository.record_usage(222, 600.0, db_path=db_path)

    stats = {s.user_id: s for s in repository.list_usage_stats(db_path=db_path)}
    assert stats[111].total_media_count == 1
    assert stats[222].total_media_count == 2
    assert stats[222].total_duration_seconds == 1200.0


def test_list_usage_stats_sorted_by_duration_descending(tmp_path):
    db_path = str(tmp_path / "test.db")
    repository.register_user(111, "low", "Low", None, "2026-07-24T10:00:00+00:00", db_path=db_path)
    repository.register_user(222, "high", "High", None, "2026-07-24T10:00:00+00:00", db_path=db_path)
    repository.record_usage(111, 30.0, db_path=db_path)
    repository.record_usage(222, 3000.0, db_path=db_path)

    stats = repository.list_usage_stats(db_path=db_path)

    assert [s.user_id for s in stats] == [222, 111]


def test_existing_database_without_language_chosen_column_is_migrated(tmp_path):
    """Regression test: databases created before language_chosen existed must
    not break init_db - the column is added in place instead of crashing."""
    import sqlite3

    db_path = str(tmp_path / "legacy.db")
    conn = sqlite3.connect(db_path)
    conn.execute(
        "CREATE TABLE user_settings ("
        "user_id INTEGER PRIMARY KEY, "
        "default_style TEXT NOT NULL DEFAULT 'ask_each_time', "
        "language TEXT NOT NULL DEFAULT 'uz', "
        "diarization_enabled INTEGER NOT NULL DEFAULT 0)"
    )
    conn.execute("INSERT INTO user_settings (user_id, language) VALUES (333, 'uz')")
    conn.commit()
    conn.close()

    settings = repository.get_settings(333, db_path=db_path)

    assert settings.language == "uz"
    assert settings.language_chosen is False
