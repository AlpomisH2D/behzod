import sqlite3
from contextlib import contextmanager

import config

_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_settings (
    user_id INTEGER PRIMARY KEY,
    language TEXT NOT NULL DEFAULT 'uz',
    language_chosen INTEGER NOT NULL DEFAULT 0,
    visual_template TEXT NOT NULL DEFAULT 'classic',
    default_language TEXT NOT NULL DEFAULT 'uz',
    default_word_style TEXT NOT NULL DEFAULT 'ai_choice',
    default_format TEXT NOT NULL DEFAULT 'srt',
    auto_apply_enabled INTEGER NOT NULL DEFAULT 0,
    last_word_style TEXT NOT NULL DEFAULT 'ai_choice'
);

CREATE TABLE IF NOT EXISTS job_history (
    user_id INTEGER PRIMARY KEY,
    filename TEXT NOT NULL,
    media_kind TEXT NOT NULL,
    duration_seconds REAL,
    style TEXT NOT NULL,
    blocks_json TEXT NOT NULL,
    completed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    first_name TEXT NOT NULL,
    last_name TEXT,
    phone_number TEXT,
    joined_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    username TEXT,
    job_identifier TEXT NOT NULL,
    choice TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- Running per-user totals across every successfully completed job. Kept
-- separate from job_history (which only ever remembers the single latest
-- job, overwritten each time) since admin statistics need the cumulative
-- count/duration across ALL of a user's jobs, not just their most recent one.
CREATE TABLE IF NOT EXISTS usage_stats (
    user_id INTEGER PRIMARY KEY,
    total_media_count INTEGER NOT NULL DEFAULT 0,
    total_duration_seconds REAL NOT NULL DEFAULT 0
);
"""

# Columns added after the initial release - existing databases are migrated
# in place with ALTER TABLE (no-op if the column is already there).
_MIGRATIONS = [
    ("user_settings", "ALTER TABLE user_settings ADD COLUMN language_chosen INTEGER NOT NULL DEFAULT 0"),
    ("user_settings", "ALTER TABLE user_settings ADD COLUMN visual_template TEXT NOT NULL DEFAULT 'classic'"),
    ("user_settings", "ALTER TABLE user_settings ADD COLUMN default_language TEXT NOT NULL DEFAULT 'uz'"),
    ("user_settings", "ALTER TABLE user_settings ADD COLUMN default_word_style TEXT NOT NULL DEFAULT 'ai_choice'"),
    ("user_settings", "ALTER TABLE user_settings ADD COLUMN default_format TEXT NOT NULL DEFAULT 'srt'"),
    ("user_settings", "ALTER TABLE user_settings ADD COLUMN auto_apply_enabled INTEGER NOT NULL DEFAULT 0"),
    ("user_settings", "ALTER TABLE user_settings ADD COLUMN last_word_style TEXT NOT NULL DEFAULT 'ai_choice'"),
]


def init_db(db_path: str | None = None) -> None:
    with _connect(db_path) as conn:
        conn.executescript(_SCHEMA)
        for table, migration in _MIGRATIONS:
            existing_columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            column_name = migration.split("ADD COLUMN ")[1].split(" ")[0]
            if column_name not in existing_columns:
                conn.execute(migration)
        conn.commit()


@contextmanager
def _connect(db_path: str | None = None):
    conn = sqlite3.connect(db_path or config.DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    return sqlite3.connect(db_path or config.DB_PATH)
