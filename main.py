import logging
import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from telegram import BotCommand, MenuButtonCommands
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, MessageHandler, filters

import config
from bot.handlers.access_control import maintenance_gate
from bot.handlers.admin import reply_command, statistika_command, users_command
from bot.handlers.feedback import feedback_callback
from bot.handlers.help_menu import help_menu_callback
from bot.handlers.language import first_contact_language_gate, language_callback, language_command
from bot.handlers.main_menu import MENU_DISPATCH
from bot.handlers.registration import phone_number_gate
from bot.handlers.settings_menu import (
    settings_back_callback,
    settings_format_choice_callback,
    settings_row_callback,
    settings_style_choice_callback,
    settings_sublang_choice_callback,
    settings_toggle_autoapply_callback,
)
from bot.handlers.start import start
from bot.handlers.subtitle_flow import build_conversation_handler, unexpected_text_fallback
from bot.handlers.support import admin_message_capture_gate
from bot.handlers.time_shift import time_shift_callback
from bot.i18n import BOT_DESCRIPTION, SUPPORTED_LANGUAGES, t
from bot.language_utils import get_user_language
from db.database import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

_REPO_ROOT = Path(__file__).resolve().parent


def _code_version() -> str:
    """A marker that changes whenever the source actually changes, logged on
    every startup - so a restart can be visually confirmed (from the log,
    not just inferred from behavior) to have picked up the latest edits
    instead of silently still running old in-memory code. Prefers the git
    commit hash; falls back to the newest .py file's mtime (this project
    isn't a git repo)."""
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=_REPO_ROOT, capture_output=True, text=True, timeout=5,
        )
        if commit.returncode == 0 and commit.stdout.strip():
            return f"git:{commit.stdout.strip()}"
    except Exception:  # noqa: BLE001 - version marker must never block startup
        pass

    newest_mtime = max(
        (p.stat().st_mtime for p in _REPO_ROOT.rglob("*.py") if "venv" not in p.parts),
        default=0,
    )
    stamp = datetime.fromtimestamp(newest_mtime, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"mtime:{stamp}"


def _bot_commands(lang: str) -> list[BotCommand]:
    return [
        BotCommand("start", t("command.start_description", lang)),
        BotCommand("language", t("command.language_description", lang)),
    ]


# Telegram's hard limits: 512 chars for the full description, 120 for the
# short one - the given description text is only short enough for the former.
_SHORT_DESCRIPTION_LIMIT = 120


def _as_short_description(text: str) -> str:
    if len(text) <= _SHORT_DESCRIPTION_LIMIT:
        return text
    return text[: _SHORT_DESCRIPTION_LIMIT - 1].rstrip() + "…"


async def _try(coro, description: str) -> None:
    """Runs one startup API call in isolation - a single flaky network
    request (Telegram's own API has occasional timeouts) must never crash the
    entire bot on startup and take every user down with it. Logged and
    skipped instead; these are cosmetic profile/menu settings, not required
    for the bot to actually serve users."""
    try:
        await coro
    except Exception:  # noqa: BLE001 - startup must proceed regardless of which cosmetic call failed
        logging.getLogger(__name__).exception("Bot ishga tushishida '%s' bajarilmadi", description)


async def _post_init(application: Application) -> None:
    """Makes the command menu button always visible next to the message box,
    and sets the bot's profile description shown before the user ever
    presses Start, localized per language (section B)."""
    # Fallback for clients whose language isn't uz/ru/en.
    await _try(application.bot.set_my_commands(_bot_commands("uz")), "set_my_commands (fallback)")
    await _try(application.bot.set_chat_menu_button(menu_button=MenuButtonCommands()), "set_chat_menu_button")

    for language_code in SUPPORTED_LANGUAGES:
        await _try(
            application.bot.set_my_commands(_bot_commands(language_code), language_code=language_code),
            f"set_my_commands ({language_code})",
        )

    for language_code, text in BOT_DESCRIPTION.items():
        await _try(
            application.bot.set_my_description(text, language_code=language_code),
            f"set_my_description ({language_code})",
        )
        await _try(
            application.bot.set_my_short_description(_as_short_description(text), language_code=language_code),
            f"set_my_short_description ({language_code})",
        )
    await _try(application.bot.set_my_description(BOT_DESCRIPTION["uz"]), "set_my_description (fallback)")
    await _try(
        application.bot.set_my_short_description(_as_short_description(BOT_DESCRIPTION["uz"])),
        "set_my_short_description (fallback)",
    )


async def _stale_callback_fallback(update, context) -> None:
    """Catches inline-button clicks left over from a conversation that has
    already ended (e.g. after conversation_timeout, or a fresh bot restart).
    Registered in a higher group so it only runs when nothing else handled
    the update - otherwise a stale click would just spin its loading icon
    forever with no reply, which looks like the bot hanging.
    """
    await update.callback_query.answer(
        t("stale_callback.expired", get_user_language(update)), show_alert=False
    )


def build_application() -> Application:
    config.require_bot_tokens()
    init_db()

    application = Application.builder().token(config.TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    # While config.MAINTENANCE_MODE is on, the bot is restricted to
    # config.ADMIN_USER_ID only - checked before anything else, including the
    # onboarding gates below.
    application.add_handler(MessageHandler(filters.ALL, maintenance_gate), group=-4)
    application.add_handler(CallbackQueryHandler(maintenance_gate), group=-4)

    # Sequential onboarding gates, each in its own group so all of them always
    # get a turn: language first (-3), then a phone number on file (-2), then
    # (if the Yordam menu put this chat in that state) the next message gets
    # forwarded to the admin instead of processed normally (-1) - all before
    # anything else in the bot (group 0 onward) ever sees the update.
    application.add_handler(MessageHandler(filters.ALL, first_contact_language_gate), group=-3)
    application.add_handler(CallbackQueryHandler(first_contact_language_gate), group=-3)
    application.add_handler(MessageHandler(filters.ALL, phone_number_gate), group=-2)
    application.add_handler(CallbackQueryHandler(phone_number_gate), group=-2)
    application.add_handler(MessageHandler(filters.ALL, admin_message_capture_gate), group=-1)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("language", language_command))
    # Admin-only, intentionally left out of _BOT_COMMANDS / the visible menu.
    application.add_handler(CommandHandler("users", users_command))
    application.add_handler(CommandHandler("reply", reply_command))
    application.add_handler(CommandHandler("statistika", statistika_command))
    application.add_handler(CallbackQueryHandler(language_callback, pattern=r"^lang:"))
    application.add_handler(CallbackQueryHandler(time_shift_callback, pattern=r"^tshift:"))
    application.add_handler(CallbackQueryHandler(help_menu_callback, pattern=r"^help:"))
    application.add_handler(CallbackQueryHandler(feedback_callback, pattern=r"^feedback:"))

    # Settings screen (saved per-job defaults + auto-apply toggle) - a
    # standalone screen outside the per-job ConversationHandler, same pattern
    # as help_menu above.
    application.add_handler(CallbackQueryHandler(settings_row_callback, pattern=r"^settings:(style|sublang|format)$"))
    application.add_handler(CallbackQueryHandler(settings_toggle_autoapply_callback, pattern=r"^settings:toggle_auto$"))
    application.add_handler(CallbackQueryHandler(settings_back_callback, pattern=r"^settings:back$"))
    application.add_handler(CallbackQueryHandler(settings_style_choice_callback, pattern=r"^setdefault_style:"))
    application.add_handler(CallbackQueryHandler(settings_sublang_choice_callback, pattern=r"^setdefault_sublang:"))
    application.add_handler(CallbackQueryHandler(settings_format_choice_callback, pattern=r"^setdefault_format:"))

    # Persistent reply-keyboard buttons - registered ahead of the conversation
    # handler (same group) so they're picked up regardless of which step of
    # the video-processing wizard is currently active.
    for label, handler_fn in MENU_DISPATCH.items():
        application.add_handler(MessageHandler(filters.Text([label]), handler_fn))

    application.add_handler(build_conversation_handler())
    # Section D: any non-command, non-media text outside any active
    # conversation (e.g. right after a job, or before ever starting one)
    # still gets the "send me audio/video" reply instead of being ignored.
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unexpected_text_fallback))
    application.add_handler(CallbackQueryHandler(_stale_callback_fallback), group=1)

    return application


def main() -> None:
    logging.getLogger(__name__).info(
        "Bot ishga tushdi - kod versiyasi: %s, PID: %s", _code_version(), os.getpid()
    )
    # Phase 1: local polling. Phase 2 swaps run_polling() for a webhook without
    # touching any handler code above.
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
