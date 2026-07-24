from bot.handlers.help_menu import help_menu_handler
from bot.handlers.language import language_command
from bot.handlers.last_job import last_job_status_handler
from bot.handlers.main_menu import MENU_DISPATCH
from bot.handlers.time_shift import time_shift_start_handler
from bot.i18n import SUPPORTED_LANGUAGES, t
from bot.keyboards import MAIN_MENU_BUTTONS, MENU_HELP, MENU_LANGUAGE, MENU_LAST_JOB, MENU_TIME_SHIFT


def test_every_main_menu_button_has_a_dispatch_entry():
    grid_labels = {label for row in MAIN_MENU_BUTTONS for label in row}
    assert grid_labels <= set(MENU_DISPATCH.keys())


def test_every_language_variant_of_every_button_has_a_dispatch_entry():
    for lang in SUPPORTED_LANGUAGES:
        assert t("menu.language", lang) in MENU_DISPATCH
        assert t("menu.help", lang) in MENU_DISPATCH
        assert t("menu.last_job", lang) in MENU_DISPATCH
        assert t("menu.time_shift", lang) in MENU_DISPATCH


def test_dispatch_routes_each_button_to_the_correct_handler():
    assert MENU_DISPATCH[MENU_LANGUAGE] is language_command
    assert MENU_DISPATCH[MENU_HELP] is help_menu_handler
    assert MENU_DISPATCH[MENU_LAST_JOB] is last_job_status_handler
    assert MENU_DISPATCH[MENU_TIME_SHIFT] is time_shift_start_handler
