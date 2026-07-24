import os

from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# Telegram @username (without the leading "@") - display only (e.g. the
# contact link in the help menu). Not used for authorization - see
# ADMIN_USER_ID below, which is what access-control checks actually use
# (usernames can change; numeric user_id cannot).
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "")

# Numeric Telegram user_id of the bot owner - resolved once from a real
# /start update (see db table `users`) and pinned here so authorization never
# depends on a username that could change. 0 means "unset".
ADMIN_USER_ID = int(os.environ.get("ADMIN_USER_ID", "0") or "0")

# While true, the entire bot is restricted to ADMIN_USER_ID only - everyone
# else gets a maintenance message instead of the normal flow. Flip to false
# in .env to reopen the bot to everyone without touching code.
MAINTENANCE_MODE = os.environ.get("MAINTENANCE_MODE", "false").strip().lower() == "true"

# Extra usernames (comma-separated, with or without a leading "@") allowed
# through the maintenance gate as regular clients alongside ADMIN_USER_ID -
# for beta testers/specific people to use the bot while it's otherwise
# closed. Checked by username (not a numeric ID) since these people haven't
# necessarily ever /start'ed the bot yet, so no user_id is on file for them.
ALLOWED_USERNAMES = {
    u.strip().lstrip("@").lower()
    for u in os.environ.get("ALLOWED_USERNAMES", "").split(",")
    if u.strip()
}

GROQ_TRANSCRIBE_MODEL = "whisper-large-v3-turbo"
ELEVENLABS_STT_MODEL = "scribe_v2"
CLAUDE_SPLIT_MODEL = "claude-haiku-4-5"

DB_PATH = os.environ.get("DB_PATH", "yozar_ai.db")

# Groq free-tier audio upload limit.
MAX_AUDIO_FILE_SIZE_MB = 25

# Hard ceilings on the slow, network-bound steps so a stalled request errors
# out instead of leaving the conversation hanging forever. Each one below is a
# *minimum* - the caller scales it up for large files / long audio / long
# transcripts (see FILE_DOWNLOAD_SECONDS_PER_MB etc. below), since a flat
# timeout sized for a short clip silently kills longer ones (~2min+ audio).
FILE_DOWNLOAD_TIMEOUT_SECONDS = 40
GROQ_REQUEST_TIMEOUT_SECONDS = 40  # per chunk - chunks are a fixed short length, so this stays flat
ELEVENLABS_REQUEST_TIMEOUT_SECONDS = 60  # ElevenLabs transcribes the whole clip in one call, not chunked
CLAUDE_REQUEST_TIMEOUT_SECONDS = 30

# Scaling factors applied on top of the minimums above.
FILE_DOWNLOAD_SECONDS_PER_MB = 5
ELEVENLABS_TIMEOUT_SECONDS_PER_AUDIO_SECOND = 2
CLAUDE_TIMEOUT_SECONDS_PER_WORD = 0.15

# ffmpeg/ffprobe are run as blocking subprocesses - without a timeout, a
# malformed or unusually large input can hang the call (and, since some
# callers invoke them directly on the event loop, the whole bot) forever.
FFMPEG_SUBPROCESS_TIMEOUT_SECONDS = 180

# Whisper's word-level timestamps drift on longer audio (they're estimated
# from attention weights, not computed natively). Audio longer than the
# threshold is split into chunks before transcription to bound the drift.
GROQ_CHUNK_THRESHOLD_SECONDS = 20.0
GROQ_CHUNK_DURATION_SECONDS = 12.0

# Chunks are transcribed in parallel (not sequentially) - capped so a long
# clip's burst of requests doesn't trip Groq's own rate limiting.
GROQ_MAX_CONCURRENT_CHUNKS = 4

STYLE_WORD_LIMITS = {
    # style: (min_total_words_per_block, max_total_words_per_block, lines_per_block)
    # The word-count numbers are a ceiling on the WHOLE block, never a
    # per-line count - lines_per_block only controls how that same total is
    # visually wrapped across lines (see services/fallback_splitter.py:
    # regroup_into_blocks). Multiplying max_total * lines_per_block would be
    # the "8 words instead of 4" bug this shape exists to prevent.
    "words_1": (1, 1, 1),
    "words_2": (2, 2, 1),
    "words_3": (3, 3, 1),
    "words_4": (4, 4, 1),
    "words_4_2l": (4, 4, 2),
    "words_5_2l": (5, 5, 2),
    "words_5_3l": (5, 5, 3),
    "words_6_7_2l": (6, 7, 2),
    "words_6_7_3l": (6, 7, 3),
    "words_6_7_4l": (6, 7, 4),
    # "AI ixtiyorida" - no fixed constraint is communicated to Claude; this is
    # only a generous ceiling for the rule-based fallback's safety net.
    "ai_choice": (1, 12, 1),
}

UZBEK_CONJUNCTIONS = {
    "va", "ham", "lekin", "ammo", "biroq", "yoki", "chunki",
    "shuning", "shuningdek", "hamda", "yo", "yoxud", "balki",
}


def require_bot_tokens() -> None:
    missing = [
        name
        for name, value in (
            ("TELEGRAM_BOT_TOKEN", TELEGRAM_BOT_TOKEN),
            ("GROQ_API_KEY", GROQ_API_KEY),
            ("ANTHROPIC_API_KEY", ANTHROPIC_API_KEY),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f".env faylida quyidagi kalitlar yo'q: {', '.join(missing)}"
        )
