from bot.i18n import BOT_DESCRIPTION, START_TEXT, SUPPORTED_LANGUAGES, STYLE_LABEL_TEXT, TEXT, resolve_language, t


def test_start_text_and_description_cover_all_three_languages():
    assert set(START_TEXT.keys()) == {"uz", "ru", "en"}
    assert set(BOT_DESCRIPTION.keys()) == {"uz", "ru", "en"}


def test_resolve_language_prefers_saved_setting():
    assert resolve_language("ru", "en") == "ru"


def test_resolve_language_falls_back_to_telegram_client_language():
    assert resolve_language(None, "en-US") == "en"


def test_resolve_language_defaults_to_uzbek_when_nothing_matches():
    assert resolve_language(None, "fr") == "uz"
    assert resolve_language(None, None) == "uz"


def test_resolve_language_ignores_unsupported_saved_language():
    assert resolve_language("fr", "ru") == "ru"


def test_every_translation_key_covers_all_three_languages():
    for key, entry in TEXT.items():
        assert set(entry.keys()) == SUPPORTED_LANGUAGES, f"{key} is missing a language"
        for lang, value in entry.items():
            assert value, f"{key}[{lang}] is empty"


def test_every_style_label_covers_all_three_languages():
    for style_value, entry in STYLE_LABEL_TEXT.items():
        assert set(entry.keys()) == SUPPORTED_LANGUAGES, f"{style_value} is missing a language"


def test_t_formats_placeholders():
    assert t("job.transcription_error", "en", error="boom") == "Transcription error: boom"
    assert t("job.transcription_error", "ru", error="boom") == "Ошибка транскрипции: boom"


def test_t_raises_on_unknown_key():
    import pytest

    with pytest.raises(KeyError):
        t("does.not.exist", "uz")
