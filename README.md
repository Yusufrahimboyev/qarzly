# Telegram Bot Starter (Aiogram 3.x + Clean Architecture)

Aiogram 3.x asosidagi Clean Architecture Telegram bot starter shabloni.

## Arxitektura

5 qatlamli Clean Architecture (Dependency Inversion prinsipi asosida):

```
┌──────────────────────────────────────────┐
│  Core (config, logging)                  │
├──────────────────────────────────────────┤
│  Domain (entities, repository interfaces) │
├──────────────────────────────────────────┤
│  Application (use-case services)         │
├──────────────────────────────────────────┤
│  Infrastructure (DB, scheduler, web)     │
├──────────────────────────────────────────┤
│  Presentation (handlers, keyboards,      │
│                middlewares, states)      │
├──────────────────────────────────────────┤
│  Composition Root (app.py — DI wiring)   │
└──────────────────────────────────────────┘
```

## Xususiyatlari

- **Aiogram 3.x** — eng so'nggi asinxron Telegram Bot framework
- **Clean Architecture** — test qilish oson, kengaytiriladigan kod
- **Async SQLite** (aiosqlite) — WAL rejimi bilan, shared ulanish
- **Dependency Injection** — middleware orqali service'lar handler'ga uzatiladi
- **aiohttp WebApp** — Telegram Mini App + health check
- **APScheduler** — rejalashtirilgan vazifalar
- **pydantic-settings** — typed, validatsiyalangan konfiguratsiya
- **pytest** — Fake repository bilan unit testlar

## O'rnatish

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` faylini to'ldiring:

| O'zgaruvchi | Majburiy | Default | Izoh |
|---|---|---|---|
| `BOT_TOKEN` | ✅ | — | BotFather'dan olingan token |
| `PORT` | — | `8080` | Web server porti |
| `DATABASE_PATH` | — | `data/bot.db` | SQLite fayl yo'li |
| `RENDER_EXTERNAL_URL` | — | — | Mini App / keep-alive URL |
| `LOG_LEVEL` | — | `INFO` | Log darajasi |

## Ishga tushirish

```bash
python -m bot
```

## Test

```bash
pytest
```

## Loyiha tuzilishi

```
bot/
├── __main__.py              # entrypoint
├── app.py                   # composition root
├── core/config.py           # sozlamalar
├── domain/entities/         # biznes obyektlari
├── domain/repositories/     # interfeyslar (ABC)
├── application/services/    # use-case'lar
├── infrastructure/database/ # SQLite implementatsiya
├── infrastructure/scheduler/# APScheduler
├── infrastructure/web/      # aiohttp server
└── presentation/
    ├── handlers/            # /start, /help
    ├── keyboards/           # reply/inline klaviaturalar
    ├── middlewares/         # DI + error handling
    └── states/              # FSM state'lar
```

## Deploy (Render.com)

1. Repository'ni Render.com ga ulang
2. Start command: `python -m bot`
3. Health check: `/health`
4. `RENDER_EXTERNAL_URL` ni Render bergan URL ga sozlang
