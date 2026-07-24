# Yozar AI

O'zbek tilidagi video/audio fayllar uchun avtomatik subtitr (SRT) yaratadigan Telegram bot.

## O'rnatish

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
brew install ffmpeg   # agar hali o'rnatilmagan bo'lsa
```

`.env.example` faylini `.env` ga nusxalab, kalitlaringizni kiriting:

```bash
cp .env.example .env
```

- `TELEGRAM_BOT_TOKEN` — @BotFather orqali olinadi
- `GROQ_API_KEY` — https://console.groq.com (zaxira transkripsiya dvigateli)
- `ELEVENLABS_API_KEY` — https://elevenlabs.io (asosiy transkripsiya dvigateli, Scribe v2)
- `ANTHROPIC_API_KEY` — https://console.anthropic.com

## Ishga tushirish

```bash
source venv/bin/activate
python main.py
```

Bot polling rejimida ishga tushadi (hozircha server talab qilinmaydi).

### Diagnostika: Groq'dan kelgan xom vaqt belgilarini ko'rish

Vaqt sinxronligi bilan muammo bo'lsa, DEBUG log darajasini yoqib har bir so'zning
Groq'dan kelgan xom `start`/`end` qiymatlarini ko'rish mumkin:

```bash
python -c "
import logging
logging.basicConfig(level=logging.DEBUG)
import main
main.main()
"
```

`services/groq_service.py` har bir transkripsiyada barcha so'zlarni va audio
`duration`sini DEBUG darajasida log qiladi, shuningdek Groq'ning o'z vaqt
belgilari ketma-ket bo'lmasa (bir so'z tugashidan oldin keyingisi boshlansa)
WARNING log yozadi — bu drift Groq javobining o'zida ekanligini ko'rsatadi.

## Testlarni ishga tushirish

```bash
source venv/bin/activate
pytest -v
```

Barcha testlar tashqi API'larga chiqmasdan, mock orqali ishlaydi.

## Foydalanuvchi oqimi

1. Video yoki audio fayl yuboriladi.
2. Ixtiyoriy ravishda original skript matni yuboriladi (vaqt transkripsiya dvigatelidan, matn skriptdan olinadi).
3. Tayyor matn oldindan ko'rsatiladi — tasdiqlash yoki tuzatish mumkin.
4. Subtitr uslubi tanlanadi: So'zma-so'z, Qisqa, O'rtacha, Erkin (yoki `/settings` orqali standart uslub belgilangan bo'lsa, avtomatik ishlatiladi).
5. Tayyor `.srt` fayl qaytariladi.

## Arxitektura

- `services/` — tashqi xizmatlar bilan ishlash (ffmpeg, ElevenLabs Scribe v2 — asosiy transkripsiya, Groq — zaxira, Claude, difflib-asosli moslashtirish, SRT yasash) va Claude ishlamasa ishga tushadigan qoidaviy fallback bo'luvchi. `elevenlabs_service.transcribe_with_fallback()` ElevenLabs muvaffaqiyatsiz bo'lsa (autentifikatsiya xatosi, timeout, limit va h.k.) avtomatik ravishda `groq_service.transcribe()`ga o'tadi.
- `bot/` — Telegram handler'lar va suhbat oqimi (`ConversationHandler`).
- `db/` — foydalanuvchi sozlamalari uchun SQLite.
- `models/` — umumiy dataclass/enum tiplari.

## Deploy rejasi

- **1-faza (hozir):** lokal, polling rejimida.
- **2-faza:** Docker konteynerida VPS'ga joylanadi, webhook rejimiga o'tkaziladi (`main.py`dagi `run_polling()` ni webhook bilan almashtirish yetarli — handler kodiga tegilmaydi).
