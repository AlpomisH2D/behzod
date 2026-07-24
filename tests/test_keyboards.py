from bot.keyboards import (
    FEEDBACK_DISLIKE,
    FEEDBACK_LIKE,
    HUB_DONE,
    HUB_FORMAT,
    HUB_STYLE,
    HUB_SUBLANG,
    MAIN_MENU_BUTTONS,
    NAV_BACK,
    NAV_CANCEL,
    SCRIPT_SOURCE_AUTO,
    SCRIPT_SOURCE_MANUAL,
    TIME_SHIFT_CANCEL,
    TIME_SHIFT_DONE,
    feedback_keyboard,
    format_choice_keyboard,
    help_menu_keyboard,
    hub_menu_keyboard,
    language_keyboard,
    main_reply_keyboard,
    script_source_keyboard,
    style_choice_keyboard,
    subtitle_language_keyboard,
    time_shift_keyboard,
)
from models.types import OUTPUT_FORMATS, STYLE_LABELS, SubtitleStyle


def _flat_callback_data(markup):
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def _row_lengths(markup):
    return [len(row) for row in markup.inline_keyboard]


def test_style_choice_keyboard_lists_all_11_options_in_order_vertical_back_to_hub():
    markup = style_choice_keyboard()

    assert all(length == 1 for length in _row_lengths(markup))
    expected = [f"style:{style.value}" for style in STYLE_LABELS]
    body = [b.callback_data for row in markup.inline_keyboard[:-1] for b in row]
    assert body == expected
    nav_row = markup.inline_keyboard[-1]
    assert [b.callback_data for b in nav_row] == [NAV_BACK]  # only Back - Cancel lives on the hub


def test_format_choice_keyboard_lists_all_formats_vertical_back_to_hub():
    markup = format_choice_keyboard()

    expected = [f"format:{code}" for code in OUTPUT_FORMATS]
    body = [b.callback_data for row in markup.inline_keyboard[:-1] for b in row]
    assert body == expected
    nav_row = markup.inline_keyboard[-1]
    assert [b.callback_data for b in nav_row] == [NAV_BACK]


def test_subtitle_language_keyboard_covers_all_languages_back_to_hub():
    markup = subtitle_language_keyboard()

    body = [b.callback_data for row in markup.inline_keyboard[:-1] for b in row]
    assert body == ["sublang:uz", "sublang:ru", "sublang:en"]
    nav_row = markup.inline_keyboard[-1]
    assert [b.callback_data for b in nav_row] == [NAV_BACK]


def test_hub_menu_keyboard_shows_defaults_with_icons_when_untouched():
    markup = hub_menu_keyboard(SubtitleStyle.AI_CHOICE, "uz", "srt", touched=set())

    texts = [b.text for row in markup.inline_keyboard for b in row]
    assert texts[0] == "📝 So'zlar/qator uslubi: AI ixtiyorida"
    assert texts[1] == "🌐 Subtitr tili: O'zbek"
    assert texts[2] == "📄 Fayl formati: SRT"
    assert texts[3] == "✅ Tayyor"

    callbacks = _flat_callback_data(markup)
    assert callbacks == [HUB_STYLE, HUB_SUBLANG, HUB_FORMAT, HUB_DONE, NAV_CANCEL]


def test_hub_menu_keyboard_shows_checkmark_for_touched_rows():
    markup = hub_menu_keyboard(SubtitleStyle.WORDS_3, "ru", "srt", touched={"style", "sublang"})

    texts = [b.text for row in markup.inline_keyboard for b in row]
    assert texts[0] == "✅ So'zlar/qator uslubi: 3 ta so'z"
    assert texts[1] == "✅ Subtitr tili: Rus"
    assert texts[2] == "📄 Fayl formati: SRT"  # untouched - keeps its icon, no checkmark


def test_script_source_keyboard_has_auto_and_manual_with_back_and_cancel():
    markup = script_source_keyboard()

    assert _flat_callback_data(markup) == [SCRIPT_SOURCE_AUTO, SCRIPT_SOURCE_MANUAL, NAV_BACK, NAV_CANCEL]


def test_language_keyboard_is_vertical_and_covers_all_languages():
    markup = language_keyboard()

    assert all(length == 1 for length in _row_lengths(markup))
    assert _flat_callback_data(markup) == ["lang:uz", "lang:ru", "lang:en"]


def test_main_reply_keyboard_is_a_2x2_grid_plus_settings_row():
    markup = main_reply_keyboard()

    rows = [[button.text for button in row] for row in markup.keyboard]
    assert rows == MAIN_MENU_BUTTONS
    assert [len(row) for row in rows] == [2, 2, 1]
    assert sum(len(row) for row in rows) == 5
    assert markup.resize_keyboard is True


def test_time_shift_keyboard_has_four_deltas_then_done_then_cancel():
    markup = time_shift_keyboard()

    delta_row = markup.inline_keyboard[0]
    assert [b.callback_data for b in delta_row] == ["tshift:-500", "tshift:-100", "tshift:100", "tshift:500"]
    assert [b.text for b in delta_row] == ["-500ms", "-100ms", "+100ms", "+500ms"]
    assert markup.inline_keyboard[1][0].callback_data == TIME_SHIFT_DONE
    assert markup.inline_keyboard[2][0].callback_data == TIME_SHIFT_CANCEL


def test_feedback_keyboard_embeds_job_identifier_in_callback_data():
    markup = feedback_keyboard("2026-07-24T10:00:00+00:00")

    assert _flat_callback_data(markup) == [
        f"{FEEDBACK_LIKE}:2026-07-24T10:00:00+00:00",
        f"{FEEDBACK_DISLIKE}:2026-07-24T10:00:00+00:00",
    ]


def test_help_menu_keyboard_has_three_vertical_options():
    markup = help_menu_keyboard()

    assert all(length == 1 for length in _row_lengths(markup))
    assert len(_flat_callback_data(markup)) == 3


def test_main_reply_keyboard_follows_interface_language():
    assert main_reply_keyboard("ru").keyboard[0][0].text == "\U0001F310 Язык"
    assert main_reply_keyboard("en").keyboard[0][0].text == "\U0001F310 Language"
    assert main_reply_keyboard("uz").keyboard[0][0].text == "\U0001F310 Til"


def test_hub_menu_keyboard_follows_interface_language():
    markup = hub_menu_keyboard(SubtitleStyle.AI_CHOICE, "uz", "srt", touched=set(), lang="en")
    texts = [b.text for row in markup.inline_keyboard for b in row]
    assert texts[0] == "📝 Word/line style: AI's choice"
    assert texts[3] == "✅ Done"
    assert texts[4] == "✖️ Cancel"


def test_help_menu_keyboard_follows_interface_language():
    markup = help_menu_keyboard("ru")
    texts = [b.text for row in markup.inline_keyboard for b in row]
    assert texts == [
        "\U0001F41E Сообщить об ошибке",
        "\U0001F4A1 Оставить предложение",
        "\U0001F4AC Связаться с администратором",
    ]


def test_language_keyboard_names_follow_interface_language():
    markup = language_keyboard("en")
    texts = [b.text for row in markup.inline_keyboard for b in row]
    assert texts == ["Uzbek", "Russian", "English"]
