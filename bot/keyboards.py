from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from bot.i18n import language_name, style_label, t
from models.types import OUTPUT_FORMATS, SUBTITLE_LANGUAGES, STYLE_LABELS

NAV_BACK = "nav:back"
NAV_CANCEL = "nav:cancel"

HUB_STYLE = "hub:style"
HUB_SUBLANG = "hub:sublang"
HUB_FORMAT = "hub:format"
HUB_DONE = "hub:done"

TIME_SHIFT_DELTAS_MS = [-500, -100, 100, 500]
TIME_SHIFT_DONE = "tshift:done"
TIME_SHIFT_CANCEL = "tshift:cancel"

SCRIPT_SOURCE_AUTO = "scriptsrc:auto"
SCRIPT_SOURCE_MANUAL = "scriptsrc:manual"

FEEDBACK_LIKE = "feedback:like"
FEEDBACK_DISLIKE = "feedback:dislike"

HELP_BUG = "help:bug"
HELP_SUGGESTION = "help:suggestion"
HELP_CONTACT_ADMIN = "help:contact_admin"


def main_menu_buttons(lang: str = "uz") -> list[list[str]]:
    """2x2 grid plus a 5th standalone row for Sozlamalar - labels follow the
    user's interface language."""
    return [
        [t("menu.language", lang), t("menu.help", lang)],
        [t("menu.last_job", lang), t("menu.time_shift", lang)],
        [t("menu.settings", lang)],
    ]


# Kept for any code/tests that still want the Uzbek-default labels directly.
MENU_LANGUAGE = t("menu.language", "uz")
MENU_HELP = t("menu.help", "uz")
MENU_LAST_JOB = t("menu.last_job", "uz")
MENU_TIME_SHIFT = t("menu.time_shift", "uz")
MENU_SETTINGS = t("menu.settings", "uz")
MAIN_MENU_BUTTONS = main_menu_buttons("uz")


def main_reply_keyboard(lang: str = "uz") -> ReplyKeyboardMarkup:
    """The persistent 2x2 menu shown next to the message box from the user's
    very first successful interaction onward."""
    return ReplyKeyboardMarkup(main_menu_buttons(lang), resize_keyboard=True)


def _nav_row(lang: str, show_back: bool) -> list[InlineKeyboardButton]:
    """The one exception to the vertical layout: Back and Cancel share a row.

    Back is omitted when the current step is the first one in the wizard.
    """
    row = []
    if show_back:
        row.append(InlineKeyboardButton(t("nav.back", lang), callback_data=NAV_BACK))
    row.append(InlineKeyboardButton(t("nav.cancel", lang), callback_data=NAV_CANCEL))
    return row


def _hub_back_row(lang: str) -> list[InlineKeyboardButton]:
    """Sub-menus reached from the hub only ever go back to the hub - Cancel
    lives on the hub itself, not repeated in every sub-menu."""
    return [InlineKeyboardButton(t("nav.back", lang), callback_data=NAV_BACK)]


def style_choice_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(style_label(style.value, lang), callback_data=f"style:{style.value}")]
        for style in STYLE_LABELS
    ]
    rows.append(_hub_back_row(lang))
    return InlineKeyboardMarkup(rows)


def format_choice_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(label, callback_data=f"format:{code}")] for code, label in OUTPUT_FORMATS.items()]
    rows.append(_hub_back_row(lang))
    return InlineKeyboardMarkup(rows)


def subtitle_language_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """The per-job output subtitle language - independent of the bot's own UI
    language (see `language_keyboard`)."""
    rows = [
        [InlineKeyboardButton(language_name(code, lang), callback_data=f"sublang:{code}")]
        for code in SUBTITLE_LANGUAGES
    ]
    rows.append(_hub_back_row(lang))
    return InlineKeyboardMarkup(rows)


def hub_menu_keyboard(
    style, subtitle_language: str, output_format: str, touched: set, lang: str = "uz"
) -> InlineKeyboardMarkup:
    """The single settings hub shown right after media is received - 3 rows
    (each opens its own sub-menu and shows the current value inline) plus
    Tayyor/Cancel. Replaces the old forced sequential 3-question wizard.
    """

    def _row_text(key: str, icon: str, label: str, value: str) -> str:
        prefix = "✅" if key in touched else icon
        return f"{prefix} {label}: {value}"

    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    _row_text("style", "\U0001F4DD", t("hub.style_row_label", lang), style_label(style.value, lang)),
                    callback_data=HUB_STYLE,
                )
            ],
            [
                InlineKeyboardButton(
                    _row_text(
                        "sublang", "\U0001F310", t("hub.sublang_row_label", lang), language_name(subtitle_language, lang)
                    ),
                    callback_data=HUB_SUBLANG,
                )
            ],
            [
                InlineKeyboardButton(
                    _row_text("format", "\U0001F4C4", t("hub.format_row_label", lang), OUTPUT_FORMATS[output_format]),
                    callback_data=HUB_FORMAT,
                )
            ],
            [InlineKeyboardButton(t("hub.done_button", lang), callback_data=HUB_DONE)],
            [InlineKeyboardButton(t("nav.cancel", lang), callback_data=NAV_CANCEL)],
        ]
    )


def script_source_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("script_source.auto_button", lang), callback_data=SCRIPT_SOURCE_AUTO)],
            [InlineKeyboardButton(t("script_source.manual_button", lang), callback_data=SCRIPT_SOURCE_MANUAL)],
            _nav_row(lang, show_back=True),
        ]
    )


def language_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    """The bot's own interface language (greeting, description, every UI
    string) - see the 🌐 Til persistent-menu button. Independent of the
    per-job subtitle output language (see `subtitle_language_keyboard`)."""
    rows = [
        [InlineKeyboardButton(language_name(code, lang), callback_data=f"lang:{code}")] for code in SUBTITLE_LANGUAGES
    ]
    return InlineKeyboardMarkup(rows)


def time_shift_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    delta_row = [
        InlineKeyboardButton(f"{delta:+d}ms", callback_data=f"tshift:{delta}")
        for delta in TIME_SHIFT_DELTAS_MS
    ]
    return InlineKeyboardMarkup(
        [
            delta_row,
            [InlineKeyboardButton(t("time_shift.done_button", lang), callback_data=TIME_SHIFT_DONE)],
            [InlineKeyboardButton(t("nav.cancel", lang), callback_data=TIME_SHIFT_CANCEL)],
        ]
    )


TRANSCRIPT_CONFIRM = "transcript:confirm"
TRANSCRIPT_EDIT = "transcript:edit"


def transcript_confirm_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("transcript.confirm_button", lang), callback_data=TRANSCRIPT_CONFIRM)],
            [InlineKeyboardButton(t("transcript.edit_button", lang), callback_data=TRANSCRIPT_EDIT)],
        ]
    )


def feedback_keyboard(job_identifier: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("\U0001F44D", callback_data=f"{FEEDBACK_LIKE}:{job_identifier}")],
            [InlineKeyboardButton("\U0001F44E", callback_data=f"{FEEDBACK_DISLIKE}:{job_identifier}")],
        ]
    )


def help_menu_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton(t("help.bug_button", lang), callback_data=HELP_BUG)],
            [InlineKeyboardButton(t("help.suggestion_button", lang), callback_data=HELP_SUGGESTION)],
            [InlineKeyboardButton(t("help.contact_admin_button", lang), callback_data=HELP_CONTACT_ADMIN)],
        ]
    )


# --- Settings (saved per-job defaults + auto-apply toggle) ---
# A standalone screen (reached from the persistent "⚙️ Sozlamalar" button, not
# part of the per-job ConversationHandler) that lets a user pre-set the same
# 3 choices the hub menu offers per-job, plus a toggle to skip the hub
# entirely and auto-apply these saved defaults on every new job.

SETTINGS_ROW_STYLE = "settings:style"
SETTINGS_ROW_SUBLANG = "settings:sublang"
SETTINGS_ROW_FORMAT = "settings:format"
SETTINGS_TOGGLE_AUTOAPPLY = "settings:toggle_auto"
SETTINGS_BACK = "settings:back"

SETTINGS_STYLE_PREFIX = "setdefault_style"
SETTINGS_SUBLANG_PREFIX = "setdefault_sublang"
SETTINGS_FORMAT_PREFIX = "setdefault_format"


def settings_menu_keyboard(
    default_style: str, default_sublang: str, default_format: str, auto_apply_enabled: bool, lang: str = "uz"
) -> InlineKeyboardMarkup:
    toggle_state = t("settings.auto_apply_on" if auto_apply_enabled else "settings.auto_apply_off", lang)
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"\U0001F4DD {t('hub.style_row_label', lang)}: {style_label(default_style, lang)}",
                    callback_data=SETTINGS_ROW_STYLE,
                )
            ],
            [
                InlineKeyboardButton(
                    f"\U0001F310 {t('hub.sublang_row_label', lang)}: {language_name(default_sublang, lang)}",
                    callback_data=SETTINGS_ROW_SUBLANG,
                )
            ],
            [
                InlineKeyboardButton(
                    f"\U0001F4C4 {t('hub.format_row_label', lang)}: {OUTPUT_FORMATS[default_format]}",
                    callback_data=SETTINGS_ROW_FORMAT,
                )
            ],
            [InlineKeyboardButton(toggle_state, callback_data=SETTINGS_TOGGLE_AUTOAPPLY)],
        ]
    )


def settings_style_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(style_label(style.value, lang), callback_data=f"{SETTINGS_STYLE_PREFIX}:{style.value}")]
        for style in STYLE_LABELS
    ]
    rows.append([InlineKeyboardButton(t("nav.back", lang), callback_data=SETTINGS_BACK)])
    return InlineKeyboardMarkup(rows)


def settings_sublang_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(language_name(code, lang), callback_data=f"{SETTINGS_SUBLANG_PREFIX}:{code}")]
        for code in SUBTITLE_LANGUAGES
    ]
    rows.append([InlineKeyboardButton(t("nav.back", lang), callback_data=SETTINGS_BACK)])
    return InlineKeyboardMarkup(rows)


def settings_format_keyboard(lang: str = "uz") -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"{SETTINGS_FORMAT_PREFIX}:{code}")]
        for code, label in OUTPUT_FORMATS.items()
    ]
    rows.append([InlineKeyboardButton(t("nav.back", lang), callback_data=SETTINGS_BACK)])
    return InlineKeyboardMarkup(rows)
