# Qarz Daftar — Telegram qarz hisob boti

**Qarz Daftar** — do'konlar va yakka tadbirkorlar uchun mijozlar qarzlarini
hisobga olish, kuzatish va boshqarish Telegram boti. Aiogram 3.x va Clean
Architecture asosida qurilgan bo'lib, Telegram Mini App (Web UI) va REST API
orqali veb-interfeys ham taqdim etadi.

## Imkoniyatlari

- **📋 Qarzlar jadvali** — barcha mijozlar va qarzdorlar ro'yxati, sahifalash
  (pagination) bilan; har bir mijoz uchun batafsil qarz va to'lovlar hisoboti.
- **➕ Yangi qarz yaratish** — bosqichma-bosqich (wizard) interfeys:
  - sana, mijoz ismi va telefoni;
  - **bir nechta tovar** — har bir tovar uchun nom, miqdor (nechta) va narx,
    "➕ Yana tovar" bilan cheksiz qo'shish;
  - **har bir tovar o'z valyutasida** (so'm yoki dollar) — aralash valyutadagi
    xarid avtomatik alohida qarzlarga bo'linadi;
  - **ayirboshlash (exchange)** tovari va **berilgan pul** (dastlabki to'lov) —
    har biri o'z valyutasidagi qarzdan chegiriladi;
  - avtomatik hisob-kitob va tasdiqlash preview'si.
- **🔁 Mavjud mijozga qarz qo'shish** — jadvaldan (yoki hisobotdan) mijozni
  tanlab, ism/telefonsiz to'g'ridan-to'g'ri yangi qarz kiritish; Mini App'da
  mijozning eski qarzlari ham ko'rinadi (dublikat mijoz yaratilmaydi).
- **💰 Qarz to'lovi** — mijoz qarzini **to'liq** yoki **qisman** yopish
  (valyutalar bo'yicha alohida, FIFO tartibida).
- **🚀 Mini App (Web UI)** — `RENDER_EXTERNAL_URL` sozlanganida Telegram
  ichidan ochiladigan veb-ilova: jadval (qidiruv/filtr), dinamik ko'p tovarli
  yaratish formasi, to'lovlar, mijoz hisoboti modal oynasi.
- **🔒 Telegram initData autentifikatsiyasi** — barcha `/api/*` so'rovlari
  Telegram'ning HMAC imzosi bilan tekshiriladi; begona shaxs URLni bilsa ham
  ma'lumotlarni olib bo'lmaydi.
- **⏰ Keep-alive** — Render free tarifida uyquga ketishning oldini olish
  uchun xizmat o'z `/health` endpointini har 10 daqiqada ping qiladi.
- **🧾 Audit-trail loglari** — qarz yaratish va to'lovlar server logida
  `AUDIT ...` yozuvlari sifatida qoladi.
- **Hisobotlar** — mijoz bo'yicha to'liq qarz tarixi (tovarlar, exchange,
  to'lovlar) va umumiy hisob-kitob valyutalar bo'yicha ajratilgan.
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
| `GET` | `/health` | Xizmat holati (monitoring / keep-alive) — ochiq |
| `GET` | `/` | Mini App bosh sahifasi (index.html) — ochiq |
| `GET` | `/api/stats` | Umumiy statistika (jami qarz, qarzdorlar, mijozlar) |
| `GET` | `/api/summaries` | Barcha mijozlar qarz ma'lumotlari (alifbo bo'yicha) |
| `GET` | `/api/debtors` | Faqat faol qarzdorlar |
| `GET` | `/api/clients/{id}/report` | Mijozning to'liq hisoboti (tovarlar bilan) |
| `POST` | `/api/debts` | Yangi qarz: `products` massivi (har birida `name`, `quantity`, `price_per_unit`, `currency`) yoki eski single-product parametrlari |
| `POST` | `/api/payments` | To'lov qilish (to'liq yoki qisman, valyuta bilan) |

Barcha `/api/*` endpoint'lari **Telegram initData autentifikatsiyasini talab
qiladi**: Mini App har bir so'rovga `X-Telegram-Init-Data` header'ini qo'shadi,
server esa imzoni bot tokeni bilan tekshiradi (HMAC-SHA256, 24 soatlik amal
qilish muddati). `ADMIN_IDS` sozlangan bo'lsa, faqat ro'yxatdagi
foydalanuvchilar API'ga kira oladi; aks holda har qanday haqiqiy Telegram
foydalanuvchisi kira oladi (bot tomonidagi qoida bilan bir xil).

## Xavfsizlik qoidalari

1. **`ADMIN_IDS` ni albatta sozlang** — bo'sh qoldirilsa bot ham, API ham har
   qanday Telegram foydalanuvchisiga ochiq bo'ladi va u barcha mijozlar
   ma'lumotlarini ko'ra oladi. Bot ishga tushganda buning haqida log'da
   ogohlantirish chiqadi.
2. **`.env` hech qachon gitga kiritilmaydi** (`.gitignore` da band qilingan).
3. API 500 xatolarida ichki exception tafsilotlari mijozga yuborilmaydi —
   faqat logga yoziladi.

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
4. `RENDER_EXTERNAL_URL` ni Render bergan URL ga sozlang (Mini App va
   keep-alive uchun; Render odatda bu o'zgaruvchini o'zi beradi)
5. `BOT_TOKEN` va `ADMIN_IDS` ni Render panelidan Secrets sifatida kiriting

### ⚠️ Muhim: Render free tarifi va ma'lumot saqlash

Render **free** tarifida disk **ephemeral** (vaqtinchalik) — har deploy yoki
restartda `data/bot.db` fayli **butunlay o'chib ketadi**. Real foydalanish
uchun quyidagilardan birini qiling:

- **Persistent Disk ulang** (pullik tarif talab qiladi) — `render.yaml` ga
  `disk: { mountPath: data, sizeGB: 1 }` qo'shib, `DATABASE_PATH=data/bot.db`
  qoldiring;
- yoki **tashqi baza** (masalan Supabase/Neon PostgreSQL) ga o'ting;
- yoki kamida muntazam **backup** olib turing (SQLite faylini yuklab olish).

Shuningdek, free tarifda 15 daqiqa trafik kelmasa xizmat uyquga o'tadi — bot
polling'i ham to'xtaydi. Bu loyiha o'z `/health`'ini har 10 daqiqada ping
qilib, uyquga ketishning oldini oladi (`RENDER_EXTERNAL_URL` sozlangan bo'lsa
avtomatik ishlaydi).
