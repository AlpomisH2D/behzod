"""Central translation table for every user-facing string in the bot.

Two languages settings exist and must never be conflated:
  - interface language (this file): controls all UI text - buttons, prompts,
    confirmations, errors, help text. Saved per-user as `UserSettings.language`
    (the "🌐 Til / Language" persistent-menu button), default "uz".
  - subtitle output language (models.types.SUBTITLE_LANGUAGES): controls only
    the language of a specific job's generated subtitle file content, chosen
    per-job in the hub menu. Independent of the interface language.

Usage: `t("key.name", lang)` or, for strings with placeholders,
`t("key.name", lang, value=123)`.
"""

SUPPORTED_LANGUAGES = {"uz", "ru", "en"}


def resolve_language(settings_language: str | None, telegram_language_code: str | None) -> str:
    """Preference order: the user's saved interface-language setting, then
    Telegram client's own language_code, then Uzbek as the default."""
    if settings_language in SUPPORTED_LANGUAGES:
        return settings_language
    short = (telegram_language_code or "")[:2].lower()
    if short in SUPPORTED_LANGUAGES:
        return short
    return "uz"


# The name of each of the 3 supported languages, written in each of the 3
# supported languages - used for both the interface-language keyboard and the
# per-job subtitle-language keyboard (they show the same 3 language names).
LANGUAGE_NAMES = {
    "uz": {"uz": "O'zbek", "ru": "Узбекский", "en": "Uzbek"},
    "ru": {"uz": "Rus", "ru": "Русский", "en": "Russian"},
    "en": {"uz": "Ingliz", "ru": "Английский", "en": "English"},
}


def language_name(code: str, lang: str) -> str:
    return LANGUAGE_NAMES.get(code, {}).get(lang, code)


MEDIA_KIND_NAMES = {
    "video": {"uz": "video", "ru": "видео", "en": "video"},
    "audio": {"uz": "audio", "ru": "аудио", "en": "audio"},
    "voice": {"uz": "ovozli xabar", "ru": "голосовое сообщение", "en": "voice message"},
    "document": {"uz": "fayl", "ru": "файл", "en": "file"},
}


def media_kind_name(kind: str, lang: str) -> str:
    return MEDIA_KIND_NAMES.get(kind, {}).get(lang, kind)


STYLE_LABEL_TEXT = {
    "words_1": {"uz": "1 ta so'z", "ru": "1 слово", "en": "1 word"},
    "words_2": {"uz": "2 ta so'z", "ru": "2 слова", "en": "2 words"},
    "words_3": {"uz": "3 ta so'z", "ru": "3 слова", "en": "3 words"},
    "words_4": {"uz": "4 ta so'z", "ru": "4 слова", "en": "4 words"},
    "words_4_2l": {"uz": "4 ta so'z (2 qator)", "ru": "4 слова (2 строки)", "en": "4 words (2 lines)"},
    "words_5_2l": {"uz": "5 ta so'z (2 qator)", "ru": "5 слов (2 строки)", "en": "5 words (2 lines)"},
    "words_5_3l": {"uz": "5 ta so'z (3 qator)", "ru": "5 слов (3 строки)", "en": "5 words (3 lines)"},
    "words_6_7_2l": {"uz": "6-7 ta so'z (2 qator)", "ru": "6-7 слов (2 строки)", "en": "6-7 words (2 lines)"},
    "words_6_7_3l": {"uz": "6-7 ta so'z (3 qator)", "ru": "6-7 слов (3 строки)", "en": "6-7 words (3 lines)"},
    "words_6_7_4l": {"uz": "6-7 ta so'z (4 qator)", "ru": "6-7 слов (4 строки)", "en": "6-7 words (4 lines)"},
    "ai_choice": {"uz": "AI ixtiyorida", "ru": "На усмотрение ИИ", "en": "AI's choice"},
}


def style_label(style_value: str, lang: str) -> str:
    return STYLE_LABEL_TEXT.get(style_value, {}).get(lang, style_value)


TEXT: dict[str, dict[str, str]] = {
    "start.greeting": {
        "uz": (
            "Assalomu alaykum! \U0001F44B\n\n"
            "Men video yoki audio fayllaringizga avtomatik subtitr (matn) tayyorlab beraman.\n\n"
            "Boshlash uchun menga audio yoki video yuboring."
        ),
        "ru": (
            "Здравствуйте! \U0001F44B\n\n"
            "Я автоматически создаю субтитры для ваших видео или аудио файлов.\n\n"
            "Чтобы начать, отправьте мне аудио или видео."
        ),
        "en": (
            "Hello! \U0001F44B\n\n"
            "I automatically generate subtitles for your video or audio files.\n\n"
            "To get started, send me an audio or video file."
        ),
    },
    "bot.description": {
        "uz": (
            "Men video yoki audio fayllaringizga o'zbek tilida subtitr (matn) tayyorlab beraman "
            "— tez, aniq va bepul sinab ko'rish imkoniyati bilan."
        ),
        "ru": "Я подготовлю субтитры для вашего видео или аудио — быстро, точно и с возможностью бесплатно протестировать.",
        "en": "I generate subtitles for your video or audio — fast, accurate, and free to try.",
    },
    "fallback.send_media": {
        "uz": "Menga audio yoki video yuboring, men sizga uni subtitr qilib beraman.",
        "ru": "Отправьте мне аудио или видео, и я сделаю для него субтитры.",
        "en": "Send me an audio or video file and I'll turn it into subtitles.",
    },
    "maintenance.text": {
        "uz": "Botda hozir sozlash ishlari olib borilmoqda. Birozdan so'ng ishga tushadi.",
        "ru": "Сейчас на боте ведутся технические работы. Он снова заработает в ближайшее время.",
        "en": "The bot is currently undergoing maintenance. It will be back shortly.",
    },
    # --- persistent menu ---
    "menu.language": {"uz": "\U0001F310 Til", "ru": "\U0001F310 Язык", "en": "\U0001F310 Language"},
    "menu.help": {"uz": "❓ Yordam", "ru": "❓ Помощь", "en": "❓ Help"},
    "menu.last_job": {
        "uz": "\U0001F4CA Oxirgi ish holati",
        "ru": "\U0001F4CA Статус последней работы",
        "en": "\U0001F4CA Last job status",
    },
    "menu.time_shift": {
        "uz": "⏱ Vaqtni sozlash",
        "ru": "⏱ Настройка времени",
        "en": "⏱ Adjust timing",
    },
    "menu.settings": {
        "uz": "⚙️ Sozlamalar",
        "ru": "⚙️ Настройки",
        "en": "⚙️ Settings",
    },
    # --- nav ---
    "nav.back": {"uz": "◀️ Orqaga", "ru": "◀️ Назад", "en": "◀️ Back"},
    "nav.cancel": {"uz": "✖️ Bekor qilish", "ru": "✖️ Отмена", "en": "✖️ Cancel"},
    # --- hub menu ---
    "hub.intro": {
        "uz": "Fayl qabul qilindi! Sozlamalarni tanlang (yoki standart holicha qoldiring):",
        "ru": "Файл получен! Выберите настройки (или оставьте их по умолчанию):",
        "en": "File received! Choose your settings (or leave them at the default):",
    },
    "hub.style_row_label": {
        "uz": "So'zlar/qator uslubi",
        "ru": "Стиль слов/строк",
        "en": "Word/line style",
    },
    "hub.sublang_row_label": {"uz": "Subtitr tili", "ru": "Язык субтитров", "en": "Subtitle language"},
    "hub.format_row_label": {"uz": "Fayl formati", "ru": "Формат файла", "en": "File format"},
    "hub.done_button": {"uz": "✅ Tayyor", "ru": "✅ Готово", "en": "✅ Done"},
    "hub.style_prompt": {
        "uz": "So'zlar/qator uslubini tanlang:",
        "ru": "Выберите стиль слов/строк:",
        "en": "Choose a word/line style:",
    },
    "hub.sublang_prompt": {
        "uz": "Subtitr tilini tanlang:",
        "ru": "Выберите язык субтитров:",
        "en": "Choose the subtitle language:",
    },
    "hub.format_prompt": {
        "uz": "Fayl formatini tanlang:",
        "ru": "Выберите формат файла:",
        "en": "Choose the file format:",
    },
    # --- script source step ---
    "script_source.prompt": {
        "uz": "Skript avtomatik yozilsinmi yoki o'zingiz tayyor skript berasizmi?",
        "ru": "Расшифровать текст автоматически или вы дадите готовый текст сами?",
        "en": "Should the transcript be generated automatically, or will you provide your own script?",
    },
    "script_source.auto_button": {
        "uz": "Avtomatik transkripsiya",
        "ru": "Автоматическая транскрипция",
        "en": "Automatic transcription",
    },
    "script_source.manual_button": {
        "uz": "Men skript beraman",
        "ru": "Я дам готовый текст",
        "en": "I'll provide the script",
    },
    "script_source.manual_prompt": {
        "uz": "Skriptni matn ko'rinishida yuboring.",
        "ru": "Отправьте текст скрипта сообщением.",
        "en": "Send the script as a text message.",
    },
    "script_source.auto_starting": {
        "uz": "Avtomatik transkripsiya boshlanmoqda...",
        "ru": "Начинается автоматическая транскрипция...",
        "en": "Starting automatic transcription...",
    },
    # --- media intake ---
    "media.unsupported": {
        "uz": "Bu fayl formati qo'llab-quvvatlanmaydi. Iltimos video yoki audio fayl yuboring.",
        "ru": "Этот формат файла не поддерживается. Пожалуйста, отправьте видео или аудио файл.",
        "en": "This file format isn't supported. Please send a video or audio file.",
    },
    "media.download_timeout": {
        "uz": "Faylni yuklab olish juda uzoq davom etdi. Internet aloqasini tekshirib, qayta urinib ko'ring.",
        "ru": "Загрузка файла заняла слишком много времени. Проверьте интернет-соединение и попробуйте снова.",
        "en": "Downloading the file took too long. Check your internet connection and try again.",
    },
    "media.ffmpeg_error": {
        "uz": "Audioni videodan ajratishda xatolik yuz berdi. Boshqa fayl bilan qayta urinib ko'ring.",
        "ru": "Не удалось извлечь аудио из видео. Попробуйте другой файл.",
        "en": "Failed to extract audio from the video. Try a different file.",
    },
    "media.too_large": {
        "uz": "Fayl juda katta ({size} MB). {limit} MB dan kichikroq fayl yuboring.",
        "ru": "Файл слишком большой ({size} МБ). Отправьте файл меньше {limit} МБ.",
        "en": "The file is too large ({size} MB). Please send a file under {limit} MB.",
    },
    # --- job pipeline ---
    "job.done": {"uz": "✅ Tayyor bo'ldi!", "ru": "✅ Готово!", "en": "✅ Done!"},
    "job.feedback_prompt": {"uz": "Natija yoqdimi?", "ru": "Вам понравился результат?", "en": "Did you like the result?"},
    "job.transcription_error": {
        "uz": "Transkripsiya qilishda xatolik: {error}",
        "ru": "Ошибка транскрипции: {error}",
        "en": "Transcription error: {error}",
    },
    "job.split_error": {
        "uz": "SRT yaratishda kutilmagan xatolik yuz berdi.",
        "ru": "Произошла непредвиденная ошибка при создании SRT.",
        "en": "An unexpected error occurred while generating the subtitle file.",
    },
    "job.unexpected_error": {
        "uz": "Kutilmagan xatolik yuz berdi.",
        "ru": "Произошла непредвиденная ошибка.",
        "en": "An unexpected error occurred.",
    },
    "job.format_notice": {
        "uz": "{requested} formati hozircha mavjud emas, shuning uchun SRT formatida yuborildi.",
        "ru": "Формат {requested} пока недоступен, поэтому файл отправлен в формате SRT.",
        "en": "The {requested} format isn't available yet, so the file was sent as SRT instead.",
    },
    # --- real chunk-progress (replaces the generic animation once the total
    # chunk count is known) ---
    "job.chunk_progress": {
        "uz": "{done}/{total} qism qayta ishlanmoqda...",
        "ru": "Обрабатывается часть {done}/{total}...",
        "en": "Processing part {done}/{total}...",
    },
    # --- transcript confirmation (Section B) ---
    "transcript.confirm_prompt": {
        "uz": "Quyidagi matn to'g'rimi?\n\n{text}",
        "ru": "Этот текст верен?\n\n{text}",
        "en": "Is the following text correct?\n\n{text}",
    },
    "transcript.truncated_note": {
        "uz": "\n\n(matn juda uzun, qisqartirildi)",
        "ru": "\n\n(текст слишком длинный, сокращён)",
        "en": "\n\n(text was too long, shortened)",
    },
    "transcript.confirm_button": {"uz": "✅ Tasdiqlash", "ru": "✅ Подтвердить", "en": "✅ Confirm"},
    "transcript.edit_button": {"uz": "✏️ Tuzatish", "ru": "✏️ Исправить", "en": "✏️ Edit"},
    "transcript.edit_prompt": {
        "uz": "Tuzatilgan matnni yuboring:",
        "ru": "Отправьте исправленный текст:",
        "en": "Send the corrected text:",
    },
    # --- animation ---
    "job.animation_1": {"uz": "Tayyorlanmoqda.", "ru": "Готовится.", "en": "Preparing."},
    "job.animation_2": {"uz": "Tayyorlanmoqda..", "ru": "Готовится..", "en": "Preparing.."},
    "job.animation_3": {"uz": "Tayyorlanmoqda...", "ru": "Готовится...", "en": "Preparing..."},
    # --- cancel / restart ---
    "cancel.done": {"uz": "Bekor qilindi.", "ru": "Отменено.", "en": "Cancelled."},
    "cancel.process_cancelled": {
        "uz": "Jarayon bekor qilindi.",
        "ru": "Процесс отменён.",
        "en": "The process was cancelled.",
    },
    "restart.new_media": {
        "uz": "Avvalgi jarayon bekor qilindi, yangi fayl qabul qilinmoqda...",
        "ru": "Предыдущий процесс отменён, принимается новый файл...",
        "en": "The previous process was cancelled, accepting the new file...",
    },
    # --- feedback ---
    "feedback.thanks": {"uz": "Rahmat, fikringiz uchun!", "ru": "Спасибо за ваш отзыв!", "en": "Thanks for your feedback!"},
    # --- last job status ---
    "last_job.none": {"uz": "Hali ishlaringiz yo'q.", "ru": "У вас пока нет выполненных работ.", "en": "You don't have any jobs yet."},
    "last_job.summary": {
        "uz": "Oxirgi ish: {duration} {kind}, '{style}' uslub, {relative} bajarildi.",
        "ru": "Последняя работа: {duration} {kind}, стиль «{style}», выполнено {relative}.",
        "en": "Last job: {duration} {kind}, '{style}' style, completed {relative}.",
    },
    "last_job.duration_unknown": {
        "uz": "noma'lum davomiylik",
        "ru": "неизвестная длительность",
        "en": "unknown duration",
    },
    "last_job.relative_now": {"uz": "hozirgina", "ru": "только что", "en": "just now"},
    "last_job.relative_minutes": {"uz": "{n} daqiqa oldin", "ru": "{n} мин. назад", "en": "{n} minutes ago"},
    "last_job.relative_hours": {"uz": "{n} soat oldin", "ru": "{n} ч. назад", "en": "{n} hours ago"},
    "last_job.relative_days": {"uz": "{n} kun oldin", "ru": "{n} дн. назад", "en": "{n} days ago"},
    # --- time shift ---
    "time_shift.no_last_job": {
        "uz": "Avval kamida bitta subtitr faylini tayyorlashingiz kerak.",
        "ru": "Сначала нужно подготовить хотя бы один файл субтитров.",
        "en": "You need to generate at least one subtitle file first.",
    },
    "time_shift.offset_text": {
        "uz": "Joriy siljish: {offset}ms\n\nQiymatni tanlang yoki \"Tayyor\"ni bosing:",
        "ru": "Текущий сдвиг: {offset}мс\n\nВыберите значение или нажмите «Готово»:",
        "en": "Current shift: {offset}ms\n\nPick a value or press \"Done\":",
    },
    "time_shift.done_button": {
        "uz": "✅ Tayyor, faylni ber",
        "ru": "✅ Готово, отправить файл",
        "en": "✅ Done, send the file",
    },
    "time_shift.result": {
        "uz": "Tayyor! Qo'llanilgan siljish: {offset}ms",
        "ru": "Готово! Применённый сдвиг: {offset}мс",
        "en": "Done! Applied shift: {offset}ms",
    },
    # --- interface language menu ---
    "interface_language.prompt": {
        "uz": "Bot tilini tanlang:",
        "ru": "Выберите язык бота:",
        "en": "Choose the bot language:",
    },
    "interface_language.first_contact": {
        "uz": "Salom! Avval botning tilini tanlang:",
        "ru": "Здравствуйте! Сначала выберите язык бота:",
        "en": "Hello! First, choose the bot's language:",
    },
    "interface_language.selected": {
        "uz": "✅ Til tanlandi: {label}",
        "ru": "✅ Язык выбран: {label}",
        "en": "✅ Language selected: {label}",
    },
    "interface_language.main_menu_ready": {
        "uz": "Asosiy menyu quyida doim ochiq turadi.",
        "ru": "Главное меню всегда доступно ниже.",
        "en": "The main menu is always available below.",
    },
    # --- registration / phone collection ---
    "registration.phone_example": {
        "uz": "Namuna: +998 00 000 00 00\n\nFaqat +998 dan keyingi 9 ta raqamni kiriting, masalan: 00 000 00 00",
        "ru": "Пример: +998 00 000 00 00\n\nВведите только 9 цифр после +998, например: 00 000 00 00",
        "en": "Example: +998 00 000 00 00\n\nEnter only the 9 digits after +998, e.g. 00 000 00 00",
    },
    "registration.phone_prompt": {
        "uz": (
            "\U0001F4F1 Telefon raqamingizni kiriting.\n\n"
            "Pastdagi tugma orqali bir bosishda ulashishingiz yoki qo'lda yozishingiz mumkin.\n\n"
            "{example}"
        ),
        "ru": (
            "\U0001F4F1 Введите ваш номер телефона.\n\n"
            "Вы можете поделиться им одним нажатием на кнопку ниже или ввести вручную.\n\n"
            "{example}"
        ),
        "en": (
            "\U0001F4F1 Enter your phone number.\n\n"
            "You can share it with one tap using the button below, or type it manually.\n\n"
            "{example}"
        ),
    },
    "registration.phone_invalid": {
        "uz": "Raqam formati noto'g'ri.\n\n{example}",
        "ru": "Неверный формат номера.\n\n{example}",
        "en": "Invalid phone number format.\n\n{example}",
    },
    "registration.phone_saved": {
        "uz": "Rahmat! Raqamingiz saqlandi.",
        "ru": "Спасибо! Ваш номер сохранён.",
        "en": "Thanks! Your number has been saved.",
    },
    "registration.wrong_contact": {
        "uz": "Iltimos, faqat o'zingizning raqamingizni ulashing.",
        "ru": "Пожалуйста, поделитесь только своим собственным номером.",
        "en": "Please share only your own phone number.",
    },
    "registration.share_button": {
        "uz": "\U0001F4F1 Raqamni ulashish",
        "ru": "\U0001F4F1 Поделиться номером",
        "en": "\U0001F4F1 Share phone number",
    },
    # --- help menu ---
    "help.intro": {
        "uz": "Yordam kerakmi? Quyidagilardan birini tanlang:",
        "ru": "Нужна помощь? Выберите один из вариантов:",
        "en": "Need help? Choose one of the options below:",
    },
    "help.bug_button": {
        "uz": "\U0001F41E Xatolik haqida xabar berish",
        "ru": "\U0001F41E Сообщить об ошибке",
        "en": "\U0001F41E Report a bug",
    },
    "help.suggestion_button": {
        "uz": "\U0001F4A1 Taklif bildirish",
        "ru": "\U0001F4A1 Оставить предложение",
        "en": "\U0001F4A1 Suggest an idea",
    },
    "help.contact_admin_button": {
        "uz": "\U0001F4AC Administrator bilan bog'lanish",
        "ru": "\U0001F4AC Связаться с администратором",
        "en": "\U0001F4AC Contact the administrator",
    },
    # --- support (forward-to-admin) ---
    "support.route_prompt": {
        "uz": "Xabaringizni shu yerga yozing, adminga yetkazamiz.",
        "ru": "Напишите ваше сообщение здесь, мы передадим его администратору.",
        "en": "Write your message here, and we'll pass it on to the admin.",
    },
    "support.forwarded_confirm": {
        "uz": "Xabaringiz yuborildi, rahmat!",
        "ru": "Ваше сообщение отправлено, спасибо!",
        "en": "Your message has been sent, thank you!",
    },
    "stale_callback.expired": {
        "uz": "Bu tugma eskirgan. Yangi video yoki audio yuboring.",
        "ru": "Эта кнопка устарела. Отправьте новое видео или аудио.",
        "en": "This button has expired. Send a new video or audio file.",
    },
    "support.forward_failed": {
        "uz": "Xabaringizni yuborishda xatolik yuz berdi, birozdan so'ng qayta urinib ko'ring.",
        "ru": "Не удалось отправить сообщение, попробуйте ещё раз чуть позже.",
        "en": "Something went wrong sending your message — please try again shortly.",
    },
    # --- Settings (saved per-job defaults + auto-apply toggle) ---
    "settings.intro": {
        "uz": (
            "Standart sozlamalaringiz. Bu yerda tanlangan qiymatlar har safar "
            "\"Avtomatik qo'llash\" yoqilgan bo'lsa ishlatiladi."
        ),
        "ru": (
            "Ваши настройки по умолчанию. Выбранные здесь значения будут "
            "использоваться каждый раз, когда включено \"Автоматическое применение\"."
        ),
        "en": (
            "Your saved defaults. The values chosen here are used whenever "
            "\"Auto-apply\" is turned on."
        ),
    },
    "settings.auto_apply_row": {
        "uz": "{state} Avtomatik qo'llash",
        "ru": "{state} Автоматическое применение",
        "en": "{state} Auto-apply",
    },
    "settings.auto_apply_on": {"uz": "🔄 Yoqilgan", "ru": "🔄 Включено", "en": "🔄 On"},
    "settings.auto_apply_off": {"uz": "⭕️ O'chirilgan", "ru": "⭕️ Выключено", "en": "⭕️ Off"},

    # --- Telegram's own "/" command-menu descriptions ---
    "command.start_description": {
        "uz": "Botni ishga tushirish",
        "ru": "Запустить бота",
        "en": "Start the bot",
    },
    "command.language_description": {
        "uz": "Tilni tanlash",
        "ru": "Выбрать язык",
        "en": "Choose language",
    },
}


def t(key: str, lang: str, **kwargs) -> str:
    entry = TEXT.get(key)
    if entry is None:
        raise KeyError(f"Unknown translation key: {key!r}")
    text = entry.get(lang) or entry.get("uz")
    return text.format(**kwargs) if kwargs else text


def animation_frames(lang: str) -> list[str]:
    return [t("job.animation_1", lang), t("job.animation_2", lang), t("job.animation_3", lang)]


# --- backwards-compatible aliases (still used by main.py's post_init) ---
START_TEXT = {lang: TEXT["start.greeting"][lang] for lang in SUPPORTED_LANGUAGES}
BOT_DESCRIPTION = {lang: TEXT["bot.description"][lang] for lang in SUPPORTED_LANGUAGES}
FALLBACK_TEXT = TEXT["fallback.send_media"]["uz"]
