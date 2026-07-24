import json
import sqlite3

from db.database import get_connection, init_db
from models.types import LastJob, SubtitleBlock, SubtitleStyle, UsageStats, UserProfile, UserSettings


def get_settings(user_id: int, db_path: str | None = None) -> UserSettings:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT language, language_chosen, visual_template, default_language, "
            "default_word_style, default_format, auto_apply_enabled, last_word_style "
            "FROM user_settings WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            settings = UserSettings(user_id=user_id)
            _insert_default(conn, settings)
            return settings
        (
            language, language_chosen, visual_template,
            default_language, default_word_style, default_format, auto_apply_enabled, last_word_style,
        ) = row
        return UserSettings(
            user_id=user_id,
            language=language,
            language_chosen=bool(language_chosen),
            visual_template=visual_template,
            default_language=default_language,
            default_word_style=default_word_style,
            default_format=default_format,
            auto_apply_enabled=bool(auto_apply_enabled),
            last_word_style=last_word_style,
        )
    finally:
        conn.close()


def update_default_language(user_id: int, language: str, db_path: str | None = None) -> None:
    _upsert_field(user_id, "default_language", language, db_path)


def update_default_word_style(user_id: int, style: str, db_path: str | None = None) -> None:
    _upsert_field(user_id, "default_word_style", style, db_path)


def update_last_word_style(user_id: int, style: str, db_path: str | None = None) -> None:
    """Remembers the word/line style the user most recently picked in the hub
    menu, so it's pre-selected as that row's default on their next job -
    independent of the Settings-screen saved default_word_style."""
    _upsert_field(user_id, "last_word_style", style, db_path)


def update_default_format(user_id: int, output_format: str, db_path: str | None = None) -> None:
    _upsert_field(user_id, "default_format", output_format, db_path)


def update_auto_apply_enabled(user_id: int, enabled: bool, db_path: str | None = None) -> None:
    _upsert_field(user_id, "auto_apply_enabled", int(enabled), db_path)


def update_language(user_id: int, language: str, db_path: str | None = None) -> None:
    """Sets the subtitle language and marks it as explicitly chosen by the user."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        get_settings(user_id, db_path)  # ensures a row exists
        conn.execute(
            "UPDATE user_settings SET language = ?, language_chosen = 1 WHERE user_id = ?",
            (language, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def update_visual_template(user_id: int, template: str, db_path: str | None = None) -> None:
    _upsert_field(user_id, "visual_template", template, db_path)


def register_user(
    user_id: int,
    username: str | None,
    first_name: str,
    last_name: str | None,
    joined_at: str,
    db_path: str | None = None,
) -> None:
    """Records a user's profile the first time they're seen. A no-op if this
    user already has a row - never overwrites an existing profile (or a
    phone number already on file)."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name, last_name, joined_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, first_name, last_name, joined_at),
        )
        conn.commit()
    finally:
        conn.close()


def get_phone_number(user_id: int, db_path: str | None = None) -> str | None:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT phone_number FROM users WHERE user_id = ?", (user_id,)).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def save_phone_number(user_id: int, phone_number: str, db_path: str | None = None) -> None:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE users SET phone_number = ? WHERE user_id = ?", (phone_number, user_id))
        conn.commit()
    finally:
        conn.close()


def list_user_profiles(db_path: str | None = None) -> list[UserProfile]:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT user_id, username, first_name, last_name, phone_number, joined_at "
            "FROM users ORDER BY joined_at"
        ).fetchall()
        return [
            UserProfile(
                user_id=r[0], username=r[1], first_name=r[2], last_name=r[3],
                phone_number=r[4], joined_at=r[5],
            )
            for r in rows
        ]
    finally:
        conn.close()


def save_last_job(
    user_id: int,
    filename: str,
    media_kind: str,
    duration_seconds: float | None,
    style: SubtitleStyle,
    blocks: list[SubtitleBlock],
    completed_at: str,
    db_path: str | None = None,
) -> None:
    """Records the most recently completed job for a user, replacing whatever
    was recorded before - only the single latest job is kept."""
    init_db(db_path)
    blocks_json = json.dumps([{"lines": b.lines, "start": b.start, "end": b.end} for b in blocks])
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO job_history "
            "(user_id, filename, media_kind, duration_seconds, style, blocks_json, completed_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "filename=excluded.filename, media_kind=excluded.media_kind, "
            "duration_seconds=excluded.duration_seconds, style=excluded.style, "
            "blocks_json=excluded.blocks_json, completed_at=excluded.completed_at",
            (user_id, filename, media_kind, duration_seconds, style.value, blocks_json, completed_at),
        )
        conn.commit()
    finally:
        conn.close()


def save_feedback(
    user_id: int,
    username: str | None,
    job_identifier: str,
    choice: str,
    created_at: str,
    db_path: str | None = None,
) -> None:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO feedback (user_id, username, job_identifier, choice, created_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, username, job_identifier, choice, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def record_usage(user_id: int, duration_seconds: float | None, db_path: str | None = None) -> None:
    """Increments a user's running totals by one completed job - called once
    a subtitle file has actually been delivered, never on a failed job."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO usage_stats (user_id, total_media_count, total_duration_seconds) "
            "VALUES (?, 1, ?) "
            "ON CONFLICT(user_id) DO UPDATE SET "
            "total_media_count = total_media_count + 1, "
            "total_duration_seconds = total_duration_seconds + excluded.total_duration_seconds",
            (user_id, duration_seconds or 0),
        )
        conn.commit()
    finally:
        conn.close()


def list_usage_stats(db_path: str | None = None) -> list[UsageStats]:
    """Every user with at least one completed job, sorted by total duration
    descending (most active users first)."""
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT u.user_id, u.username, u.first_name, u.last_name, "
            "s.total_media_count, s.total_duration_seconds "
            "FROM usage_stats s JOIN users u ON u.user_id = s.user_id "
            "ORDER BY s.total_duration_seconds DESC"
        ).fetchall()
        return [
            UsageStats(
                user_id=r[0], username=r[1], first_name=r[2], last_name=r[3],
                total_media_count=r[4], total_duration_seconds=r[5],
            )
            for r in rows
        ]
    finally:
        conn.close()


def get_last_job(user_id: int, db_path: str | None = None) -> LastJob | None:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT filename, media_kind, duration_seconds, style, blocks_json, completed_at "
            "FROM job_history WHERE user_id = ?",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        filename, media_kind, duration_seconds, style, blocks_json, completed_at = row
        blocks = [SubtitleBlock(b["lines"], b["start"], b["end"]) for b in json.loads(blocks_json)]
        return LastJob(
            user_id=user_id,
            filename=filename,
            media_kind=media_kind,
            duration_seconds=duration_seconds,
            style=SubtitleStyle(style),
            blocks=blocks,
            completed_at=completed_at,
        )
    finally:
        conn.close()


def _insert_default(conn: sqlite3.Connection, settings: UserSettings) -> None:
    conn.execute(
        "INSERT INTO user_settings "
        "(user_id, language, language_chosen, visual_template, "
        "default_language, default_word_style, default_format, auto_apply_enabled, last_word_style) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            settings.user_id,
            settings.language,
            int(settings.language_chosen),
            settings.visual_template,
            settings.default_language,
            settings.default_word_style,
            settings.default_format,
            int(settings.auto_apply_enabled),
            settings.last_word_style,
        ),
    )
    conn.commit()


def _upsert_field(user_id: int, field: str, value, db_path: str | None) -> None:
    init_db(db_path)
    conn = get_connection(db_path)
    try:
        get_settings(user_id, db_path)  # ensures a row exists
        conn.execute(
            f"UPDATE user_settings SET {field} = ? WHERE user_id = ?",
            (value, user_id),
        )
        conn.commit()
    finally:
        conn.close()
