# Qarz Daftar — Telegram qarz hisob boti

**Qarz Daftar** — do'konlar va yakka tadbirkorlar uchun mijozlar qarzlarini
hisobga olish, kuzatish va boshqarish Telegram boti. Aiogram 3.x va Clean
Architecture asosida qurilgan bo'lib, Telegram Mini App (Web UI) va REST API
orqali veb-interfeys ham taqdim etadi.

## Imkoniyatlari

- **📋 Qarzlar jadvali** — barcha mijozlar va qarzdorlar ro'yxati, sahifalash
  (pagination) bilan; har bir mijoz uchun batafsil qarz va to'lovlar hisoboti.
- **➕ Yangi qarz yaratish** — bosqichma-bosqich (wizard) interfeys: sana, mijoz
  ismi va telefoni, tovar nomi va narxi, **ayirboshlash (exchange)** tovari,
  **berilgan pul** (dastlabki to'lov) va avtomatik hisob-kitob.
- **💰 Qarz to'lovi** — mijoz qarzini **to'liq** yoki **qisman** yopish.
- **🚀 Mini App (Web UI)** — `RENDER_EXTERNAL_URL` sozlanganida Telegram
  ichidan ochiladigan veb-ilova va uning REST API'lari.
- **Hisobotlar** — mijoz bo'yicha to'liq qarz tarixi, exchange, to'lovlar va
  umumiy hisob-kitob (jami qoldiq qarz, qarzdorlar soni va h.k.).
- **Health check** — `/health` endpoint orqali xizmat holatini kuzatish.

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

Asosiy biznes obyektlari (`bot/domain/entities/`):

- `Client` — qarz oluvchi mijoz (ism, telefon)
- `Debt` — qarz yozuvi (tovar, narx, exchange, berilgan pul, qoldiq qarz, holat)
- `Payment` — to'lov tranzaksiyasi (to'liq / qisman / dastlabki)
- `ClientDebtSummary` / `ClientReport` — umumiy va batafsil hisobot modellari

## Texnologiyalar

- **Aiogram 3.x** — eng so'nggi asinxron Telegram Bot framework
- **Clean Architecture** — test qilish oson, kengaytiriladigan kod
- **Async SQLite** (aiosqlite) — bitta ulanish ustida repositories
- **Dependency Injection** — middleware orqali service'lar handler'ga uzatiladi
- **aiohttp WebApp** — Telegram Mini App + REST API + health check
- **APScheduler** — rejalashtirilgan vazifalar (namuna job mavjud)
- **pydantic-settings** — typed, validatsiyalangan konfiguratsiya
- **pytest** — Fake repository bilan unit va API testlari

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
| `ADMIN_IDS` | — | — | Admin Telegram ID lari (vergul bilan ajratilgan) |
| `PORT` | — | `8080` | Web server porti |
| `DATABASE_PATH` | — | `data/bot.db` | SQLite fayl yo'li |
| `RENDER_EXTERNAL_URL` | — | — | Mini App / keep-alive URL |
| `LOG_LEVEL` | — | `INFO` | Log darajasi |

## Ishga tushirish

```bash
python -m bot
```

Bot ishga tushgach, asosiy menyudan foydalanish mumkin:

- `/start` — ro'yxatdan o'tish va asosiy menyu
- `/help` — yordam

## Web API

`RENDER_EXTERNAL_URL` sozlanganida quyidagi endpoint'lar mavjud:

| Method | Yo'l | Izoh |
|---|---|---|
| `GET` | `/health` | Xizmat holati (monitoring / keep-alive) |
| `GET` | `/` | Mini App bosh sahifasi (index.html) |
| `GET` | `/api/stats` | Umumiy statistika (jami qarz, qarzdorlar, mijozlar) |
| `GET` | `/api/summaries` | Barcha mijozlar qarz ma'lumotlari (alifbo bo'yicha) |
| `GET` | `/api/debtors` | Faqat faol qarzdorlar |
| `GET` | `/api/clients/{id}/report` | Mijozning to'liq hisoboti |
| `POST` | `/api/debts` | Yangi qarz yaratish |
| `POST` | `/api/payments` | To'lov qilish (to'liq yoki qisman) |

## Test

```bash
pytest
```

## Loyiha tuzilishi

```
bot/
├── __main__.py              # entrypoint
├── app.py                   # composition root (DI wiring)
├── core/
│   ├── config.py            # sozlamalar (pydantic-settings)
│   └── logging.py           # log sozlamalari
├── domain/
│   ├── entities/            # Client, Debt, Payment, Report
│   └── repositories/        # interfeyslar (ABC)
├── application/
│   ├── services/            # ClientService, DebtService, UserService
│   └── common/formatters.py # pul/sana formatlash yordamchilari
├── infrastructure/
│   ├── database/            # SQLite (connection, schema, repositories)
│   ├── scheduler/           # APScheduler
│   └── web/                 # aiohttp server + REST API
└── presentation/
    ├── handlers/            # /start, qarzlar jadvali, yaratish, to'lov
    ├── keyboards/           # reply/inline klaviaturalar
    ├── middlewares/         # DI + admin + error handling
    └── states/             # FSM state'lar

web/
├── templates/index.html     # Mini App bosh sahifasi
└── static/                  # Mini App CSS/JS

tests/                       # pytest testlari
```

## Deploy (Render.com)

`render.yaml` konfiguratsiyasi fayli mavjud (web xizmat, bepul reja):

1. Repository'ni Render.com ga ulang
2. Start command: `python -m bot`
3. Health check: `/health`
4. `RENDER_EXTERNAL_URL` ni Render bergan URL ga sozlang (Mini App uchun)
5. `BOT_TOKEN` va `ADMIN_IDS` ni Render panelidan Secrets sifatida kiriting
