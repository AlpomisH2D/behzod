from dataclasses import dataclass
from enum import Enum


@dataclass(frozen=True)
class Word:
    """A single transcribed word with its timing, as returned by the STT provider."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class CharacterTiming:
    """A single character's timing, as returned by providers that support
    character-level precision (e.g. ElevenLabs Scribe). More precise than
    word-level timing - word boundaries are derived from these when available."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class TranscriptionResult:
    """A transcript: word timings plus the real, known length of the audio.

    `characters`, when the provider supports it, holds the raw character-level
    timestamps the word list itself was derived from - kept around for any
    future code that needs finer-than-word precision. None for providers
    (like Groq) that only ever return word-level timing.
    """

    words: list[Word]
    duration: float | None = None
    characters: list[CharacterTiming] | None = None


@dataclass(frozen=True)
class AlignedWord:
    """A word from the (possibly user-supplied) script, timed against Groq's transcript."""

    text: str
    start: float
    end: float


@dataclass(frozen=True)
class SubtitleBlock:
    """One SRT cue: one or more display lines sharing a single time range."""

    lines: list[str]
    start: float
    end: float


class SubtitleStyle(str, Enum):
    WORDS_1 = "words_1"
    WORDS_2 = "words_2"
    WORDS_3 = "words_3"
    WORDS_4 = "words_4"
    WORDS_4_2L = "words_4_2l"
    WORDS_5_2L = "words_5_2l"
    WORDS_5_3L = "words_5_3l"
    WORDS_6_7_2L = "words_6_7_2l"
    WORDS_6_7_3L = "words_6_7_3l"
    WORDS_6_7_4L = "words_6_7_4l"
    AI_CHOICE = "ai_choice"


# Order matters - this is the exact order the style-choice keyboard shows them in.
STYLE_LABELS = {
    SubtitleStyle.WORDS_1: "1 ta so'z",
    SubtitleStyle.WORDS_2: "2 ta so'z",
    SubtitleStyle.WORDS_3: "3 ta so'z",
    SubtitleStyle.WORDS_4: "4 ta so'z",
    SubtitleStyle.WORDS_4_2L: "4 ta so'z (2 qator)",
    SubtitleStyle.WORDS_5_2L: "5 ta so'z (2 qator)",
    SubtitleStyle.WORDS_5_3L: "5 ta so'z (3 qator)",
    SubtitleStyle.WORDS_6_7_2L: "6-7 ta so'z (2 qator)",
    SubtitleStyle.WORDS_6_7_3L: "6-7 ta so'z (3 qator)",
    SubtitleStyle.WORDS_6_7_4L: "6-7 ta so'z (4 qator)",
    SubtitleStyle.AI_CHOICE: "AI ixtiyorida",
}


SUBTITLE_LANGUAGES = {
    "uz": "O'zbek",
    "ru": "Rus",
    "en": "Ingliz",
}

VISUAL_TEMPLATES = {
    "classic": "Klassik",
    "hormozi": "Hormozi",
    "minimal": "Minimal",
}

# Order matters - this is the exact order the format-choice keyboard shows them
# in. Only "srt" and "vtt" and "ass" are actually generated for now - "xml" and
# "mcc_scc_stl" show a "not available yet" notice and fall back to srt.
OUTPUT_FORMATS = {
    "srt": "SRT",
    "vtt": "VTT",
    "ass": "SSA/ASS",
    "xml": "XML",
    "mcc_scc_stl": "MCC/SCC/STL",
}
SUPPORTED_OUTPUT_FORMATS = {"srt", "vtt", "ass"}


@dataclass
class UserSettings:
    user_id: int
    language: str = "uz"
    language_chosen: bool = False
    visual_template: str = "classic"
    # Saved per-job defaults (Settings section) - independent of `language`
    # above, which is the bot's own interface language.
    default_language: str = "uz"
    default_word_style: str = SubtitleStyle.AI_CHOICE.value
    default_format: str = "srt"
    auto_apply_enabled: bool = False
    # The hub menu's word/line-style row pre-selects whichever style the user
    # last explicitly picked there (independent of the Settings-screen saved
    # default_word_style above) - "AI ixtiyorida" until they've ever picked one.
    last_word_style: str = SubtitleStyle.AI_CHOICE.value


@dataclass
class UserProfile:
    """A registered bot user - created on first contact, phone number filled
    in once they complete the onboarding phone-collection step."""

    user_id: int
    username: str | None
    first_name: str
    last_name: str | None
    phone_number: str | None
    joined_at: str  # ISO 8601, UTC


@dataclass
class UsageStats:
    """A user's cumulative usage across every successfully completed job -
    unlike LastJob (which only remembers the single latest one)."""

    user_id: int
    username: str | None
    first_name: str
    last_name: str | None
    total_media_count: int
    total_duration_seconds: float


@dataclass
class LastJob:
    """The most recent completed subtitling job for a user - kept around so
    "last job status" and "adjust timing" work even in a brand new session."""

    user_id: int
    filename: str
    media_kind: str
    duration_seconds: float | None
    style: SubtitleStyle
    blocks: list[SubtitleBlock]
    completed_at: str  # ISO 8601, UTC
