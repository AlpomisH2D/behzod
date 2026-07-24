from bot.handlers.help_menu import help_menu_handler
from bot.handlers.language import language_command
from bot.handlers.last_job import last_job_status_handler
from bot.handlers.settings_menu import settings_menu_handler
from bot.handlers.time_shift import time_shift_start_handler
from bot.i18n import SUPPORTED_LANGUAGES, t

# Maps each persistent reply-keyboard button label - in every supported
# interface language, since the label a user's button actually sends depends
# on their own language setting - to the handler it triggers. Registered
# ahead of the conversation handler so these work at any point in the
# conversation without disturbing whatever state it's currently in.
MENU_DISPATCH = {}
for _lang in SUPPORTED_LANGUAGES:
    MENU_DISPATCH[t("menu.language", _lang)] = language_command
    MENU_DISPATCH[t("menu.help", _lang)] = help_menu_handler
    MENU_DISPATCH[t("menu.last_job", _lang)] = last_job_status_handler
    MENU_DISPATCH[t("menu.time_shift", _lang)] = time_shift_start_handler
    MENU_DISPATCH[t("menu.settings", _lang)] = settings_menu_handler
del _lang
