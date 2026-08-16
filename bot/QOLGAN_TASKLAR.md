# Qolgan tasklar — to'liq bajarish yo'riqnomasi

Bu hujjat loyihaning **Clean Architecture** refaktoringidagi qolgan bosqichlarni
(presentation qatlami, composition root, tooling va verifikatsiya) qanday
bajarilishini bosqichma-bosqich tushuntiradi. Har bir fayl uchun to'liq kod,
joylashuv va sabab keltirilgan.

Yakunlangan qatlamlar: `core`, `domain`, `application`, `infrastructure`.
Qolgan qatlamlar: `presentation`, composition root (`app.py` + `__main__.py`),
tooling (requirements, pyproject, tests, README, create.sh) va yakuniy tekshiruv.

---

## 0. Yakuniy maqsad — `template/bot/` papka tuzilmasi

Barcha tasklar bajarilib bo'lgach, `template/bot/` quyidagi ko'rinishda bo'ladi
(eski fayllar o'chiriladi):

```
template/bot/
├── __init__.py
├── __main__.py                      # ← YUPQA entrypoint (faqat app.run() chaqiradi)
├── app.py                           # ← YANGI: composition root (DI wiring + lifecycle)
│
├── core/                            # ✅ tayyor
│   ├── __init__.py
│   ├── config.py                    # pydantic-settings Settings + get_settings()
│   └── logging.py                   # setup_logging()
│
├── domain/                          # ✅ tayyor
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   └── user.py                  # @dataclass(frozen=True) User
│   └── repositories/
│       ├── __init__.py
│       └── user_repository.py       # UserRepository(ABC)
│
├── application/                     # ✅ tayyor
│   ├── __init__.py
│   └── services/
│       ├── __init__.py
│       └── user_service.py          # UserService (use-case'lar)
│
├── infrastructure/                  # ✅ tayyor
│   ├── __init__.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── connection.py            # Database (shared aiosqlite connection)
│   │   ├── schema.py                # CREATE TABLE DDL
│   │   └── repositories/
│   │       ├── __init__.py
│   │       └── user_repository.py   # SqliteUserRepository(UserRepository)
│   ├── scheduler/
│   │   ├── __init__.py
│   │   └── scheduler.py             # create_scheduler(bot)
│   └── web/
│       ├── __init__.py
│       ├── routes.py                # setup_routes(app)
│       └── server.py                # WebServer (lifecycle)
│
└── presentation/                    # ← YANGI: 4-task
    ├── __init__.py
    ├── handlers/
    │   ├── __init__.py               # register_handlers(dp)
    │   └── start.py                  # cmd_start / cmd_help
    ├── keyboards/
    │   ├── __init__.py
    │   └── start_kb.py               # get_main_keyboard / get_web_app_inline_keyboard
    ├── middlewares/
    │   ├── __init__.py               # register_middlewares(dp, service)
    │   ├── dependency_middleware.py  # DI: service'ni handler'ga uzatadi
    │   └── error_middleware.py       # xatolarni ushlaydi
    └── states/
        ├── __init__.py
        └── registration.py          # RegistrationStates
```

**O'chiriladigan eski fayllar/papkalar** (6-taskda):

```
template/bot/config.py
template/bot/web_app.py
template/bot/db/                 (butun papka)
template/bot/handlers/           (butun papka — presentation/handlers ga ko'chadi)
template/bot/keyboards/          (butun papka — presentation/keyboards ga ko'chadi)
template/bot/middlewares/        (butun papka — presentation/middlewares ga ko'chadi)
template/bot/services/           (butun papka — infrastructure/scheduler ga ko'chgan)
template/bot/states/             (butun papka — presentation/states ga ko'chadi)
template/bot/utils/              (bo'sh — o'chiriladi)
```

---

## Muhim qoidalar (barcha fayllar uchun)

1. **Til:** barcha docstring, izoh va foydalanuvchiga ko'rinadigan matnlar
   **o'zbek tilida**.
2. **`parse_mode` — faqat HTML.** Eski `handlers/start.py` da `parse_mode="Markdown"`
   ishlatilgan, lekin bot `DefaultBotProperties(parse_mode=ParseMode.HTML)` bilan
   sozlanadi. Bu nomuvofiqlik. Yangi handler'larda **hech qanday `parse_mode`
   berilmaydi** (default HTML ishlaydi) va matnlar HTML teglari bilan yoziladi
   (`<b>...</b>`, `**...**` emas).
3. **DI (Dependency Injection):** handler'lar `aiosqlite.Connection` ni emas,
   balki `UserService` ni oladi. Ulanish faqat `app.py` da bir marta ochiladi.
4. **Har bir yangi papka `__init__.py` ga ega bo'lishi shart** (package marker).

---

## 4-TASK — Presentation qatlami

Handler'lar, klaviaturalar, middleware'lar va FSM state'lar. Bu qatlam faqat
`application` (UserService) va `core` (config) ga tayanadi — `infrastructure`
yoki `aiosqlite` ni to'g'ridan-to'g'ri bilmaydi.

### 4.1 `presentation/__init__.py`

Bo'sh fayl (package marker).

### 4.2 `presentation/states/registration.py`

Eski `states/registration.py` mazmuni saqlanadi, faqat docstring qo'shiladi.

```python
"""Presentation qatlami: ro'yxatdan o'tish FSM state'lari.

Bu namuna state'lar ko'p bosqichli dialoglar (masalan, ism va telefon so'rash)
uchun asos bo'ladi. O'z state'laringizni shu yerga qo'shing.
"""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    """Foydalanuvchini ro'yxatdan o'tkazish bosqichlari."""

    waiting_for_name = State()
    waiting_for_phone = State()
```

`presentation/states/__init__.py` — bo'sh fayl.

### 4.3 `presentation/keyboards/start_kb.py`

Eski `keyboards/start_kb.py` mantig'i saqlanadi, docstring va izohlar qo'shiladi.

```python
"""Presentation qatlami: asosiy klaviaturalar.

Reply va inline klaviaturalarni yaratuvchi sof funksiyalar. Ular holatga ega
emas (stateless) — kirish argumentiga qarab klaviatura qaytaradi.
"""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Bosh menyu reply-klaviaturasini qaytaradi."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📱 Mini Appni ochish"),
                KeyboardButton(text="ℹ️ Yordam"),
            ]
        ],
        resize_keyboard=True,
    )


def get_web_app_inline_keyboard(web_app_url: str) -> InlineKeyboardMarkup:
    """Mini App'ni ochuvchi inline tugmali klaviaturani qaytaradi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Mini App (Web UI)",
                    web_app={"url": web_app_url},
                )
            ]
        ]
    )
```

`presentation/keyboards/__init__.py` — bo'sh fayl.

### 4.4 `presentation/handlers/start.py`

Eng muhim o'zgarish: handler endi `aiosqlite.Connection` emas, `UserService`
oladi (DI middleware orqali). `parse_mode="Markdown"` olib tashlanadi, matn HTML
formatiga o'tkaziladi.

```python
"""Presentation qatlami: /start va /help buyruqlari handler'lari.

Handler'lar biznes-logikani o'zi bajarmaydi — UserService orqali ishlaydi.
Ma'lumotlar bazasi ulanishi haqida hech narsa bilmaydi (Clean Architecture).
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.application.services.user_service import UserService
from bot.presentation.keyboards.start_kb import get_main_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user_service: UserService) -> None:
    """Foydalanuvchini ro'yxatdan o'tkazadi va salomlashadi."""
    tg_user = message.from_user
    if tg_user is not None:
        await user_service.register(
            telegram_id=tg_user.id,
            full_name=tg_user.full_name,
            username=tg_user.username,
        )

    first_name = tg_user.first_name if tg_user else "Foydalanuvchi"
    await message.answer(
        f"👋 <b>Salom, {first_name}!</b>\n\n"
        "Aiogram 3.x va Async SQLite bilan ishlaydigan botingiz tayyor!",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(message: Message) -> None:
    """Yordam menyusini ko'rsatadi."""
    await message.answer(
        "🛠 <b>Yordam menyusi:</b>\n"
        "• /start — Botni qayta ishga tushirish\n"
        "• /help — Yordam xabari"
    )
```

> Eslatma: `message.reply` o'rniga `message.answer` ishlatildi (odatda bosh
> salomlashuvda reply-quote kerak emas). Bu ixtiyoriy — reply qoldirsangiz ham
> bo'ladi.

### 4.5 `presentation/handlers/__init__.py`

Barcha router'larni bitta joyda `Dispatcher` ga ulaydi. Bu — handler'larni
ro'yxatga olishning yagona kirish nuqtasi.

```python
"""Presentation qatlami: handler'larni ro'yxatga olish.

Barcha router'lar shu yerda Dispatcher'ga ulanadi. Yangi handler moduli
qo'shsangiz, uning router'ini shu yerga import qilib, include_router qiling.
"""
from __future__ import annotations

from aiogram import Dispatcher

from bot.presentation.handlers import start


def register_handlers(dp: Dispatcher) -> None:
    """Barcha router'larni Dispatcher'ga ulaydi."""
    dp.include_router(start.router)
```

### 4.6 `presentation/middlewares/dependency_middleware.py`

Eski `db_middleware.py` **har update uchun yangi ulanish ochardi** — bu sekin va
noto'g'ri. Yangi middleware bir marta yaratilgan `UserService` ni har bir
handler'ga `data` orqali uzatadi (ulanish esa `app.py` da bir marta ochilgan).

```python
"""Presentation qatlami: DI (dependency injection) middleware.

Har bir handler chaqiruvi uchun kerakli servislarni `data` lug'atiga qo'shadi.
Shu tariqa handler'lar konstruktor orqali emas, argument orqali servis oladi
va infrastructure detallaridan (masalan, DB ulanishidan) ajratiladi.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.application.services.user_service import UserService


class DependencyMiddleware(BaseMiddleware):
    """Servislarni handler'lar uchun `data` ga joylaydi."""

    def __init__(self, user_service: UserService) -> None:
        self._user_service = user_service

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        data["user_service"] = self._user_service
        return await handler(event, data)
```

### 4.7 `presentation/middlewares/error_middleware.py`

Handler ichidagi kutilmagan xatolarni ushlab, log qiladi va foydalanuvchiga
xushmuomala xabar beradi — bot butunlay to'xtab qolmaydi.

```python
"""Presentation qatlami: xatolarni ushlovchi middleware.

Handler ichida kutilmagan istisno yuz bersa, uni log qiladi va (imkoni bo'lsa)
foydalanuvchiga qisqa xabar yuboradi. Bot ishlashda davom etadi.
"""
from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

logger = logging.getLogger(__name__)


class ErrorMiddleware(BaseMiddleware):
    """Handler'lardagi kutilmagan xatolarni yumshoq boshqaradi."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:  # noqa: BLE001 - eng yuqori qatlamdagi himoya
            logger.exception("Handler bajarilishida kutilmagan xatolik")
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring."
                )
            return None
```

### 4.8 `presentation/middlewares/__init__.py`

Middleware'larni Dispatcher'ga ulaydigan yagona funksiya. Tartib muhim:
avval xatolarni ushlash (tashqi), keyin DI (ichki).

```python
"""Presentation qatlami: middleware'larni ro'yxatga olish."""
from __future__ import annotations

from aiogram import Dispatcher

from bot.application.services.user_service import UserService
from bot.presentation.middlewares.dependency_middleware import DependencyMiddleware
from bot.presentation.middlewares.error_middleware import ErrorMiddleware


def register_middlewares(dp: Dispatcher, user_service: UserService) -> None:
    """Barcha middleware'larni message va callback_query oqimlariga ulaydi."""
    error_mw = ErrorMiddleware()
    dependency_mw = DependencyMiddleware(user_service)

    for observer in (dp.message, dp.callback_query):
        observer.middleware(error_mw)
        observer.middleware(dependency_mw)
```

---

## 5-TASK — Composition root + entrypoint

Bu Clean Architecture'ning "tashqi halqasi": barcha qatlamlarni bir-biriga
**shu yerda** ulaymiz (dependency wiring). Faqat shu fayl barcha konkret
klasslarni biladi.

### 5.1 `bot/app.py` (YANGI — composition root)

```python
"""Composition root: barcha qatlamlarni ulaydi va bot hayot siklini boshqaradi.

Bu — dasturning yagona joyi bo'lib, konkret implementatsiyalarni (SQLite repo,
scheduler, web server) yaratadi va bir-biriga bog'laydi (dependency injection).
Boshqa hech bir qatlam bu ulanishlar haqida bilmaydi.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.application.services.user_service import UserService
from bot.core.config import get_settings
from bot.core.logging import setup_logging
from bot.infrastructure.database.connection import Database
from bot.infrastructure.database.repositories.user_repository import (
    SqliteUserRepository,
)
from bot.infrastructure.scheduler.scheduler import create_scheduler
from bot.infrastructure.web.server import WebServer
from bot.presentation.handlers import register_handlers
from bot.presentation.middlewares import register_middlewares

logger = logging.getLogger(__name__)


async def run() -> None:
    """Botni sozlaydi, ishga tushiradi va to'xtaganda resurslarni tozalaydi."""
    settings = get_settings()
    setup_logging(settings.log_level)

    # --- Infrastructure: ma'lumotlar bazasi ---
    database = Database(settings.database_path)
    await database.connect()

    # --- Qatlamlarni ulash (dependency injection) ---
    user_repository = SqliteUserRepository(database.connection)
    user_service = UserService(user_repository)

    # --- Aiogram: Bot va Dispatcher ---
    bot = Bot(
        token=settings.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    register_middlewares(dp, user_service)
    register_handlers(dp)

    # --- Infrastructure: scheduler va web server ---
    scheduler = create_scheduler(bot)
    web_server = WebServer(host="0.0.0.0", port=settings.port)
    await web_server.start()

    logger.info("🤖 Bot ishga tushdi. Polling boshlandi.")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Bot to'xtatilmoqda, resurslar tozalanmoqda...")
        scheduler.shutdown(wait=False)
        await web_server.stop()
        await database.disconnect()
        await bot.session.close()


def main() -> None:
    """Sinxron kirish nuqtasi (asyncio event loop'ni ishga tushiradi)."""
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot foydalanuvchi tomonidan to'xtatildi.")
```

> Eslatma: `Settings` majburiy `bot_token` ni validatsiya qiladi. Token bo'lmasa,
> `get_settings()` `pydantic.ValidationError` beradi — eski `sys.exit(1)` bilan
> qo'lda tekshirish endi kerak emas.

### 5.2 `bot/__main__.py` (YUPQA entrypoint)

Butun eski mantiq `app.py` ga ko'chdi. Endi entrypoint faqat `main()` ni
chaqiradi:

```python
"""Bot paketining kirish nuqtasi.

`python -m bot` orqali ishga tushiriladi. Butun sozlash va ulash mantig'i
`bot.app` ichida (composition root).
"""
from __future__ import annotations

from bot.app import main

if __name__ == "__main__":
    main()
```

---

## 6-TASK — Tooling (requirements, pyproject, tests, README, create.sh)

### 6.1 `template/requirements.txt`

`pydantic-settings` va `pydantic` qo'shiladi (config.py shularga tayanadi):

```
aiogram>=3.10.0
aiosqlite>=0.20.0
apscheduler>=3.10.0
aiohttp>=3.9.0
pydantic>=2.7.0
pydantic-settings>=2.3.0
python-dotenv>=1.0.0
```

> `python-dotenv` ni qoldirsa bo'ladi — `pydantic-settings` `.env` ni o'zi o'qiydi,
> lekin `python-dotenv` o'rnatilgan bo'lsa yaxshiroq (pydantic-settings uni
> ishlatadi). Ixtiyoriy.

### 6.2 `template/pyproject.toml` (YANGI)

Loyihaga zamonaviy metama'lumot, tool sozlamalari (ruff, mypy) beradi.

```toml
[project]
name = "telegram-bot-starter"
version = "0.1.0"
description = "Aiogram 3.x Clean Architecture Telegram bot starter"
requires-python = ">=3.11"
dependencies = [
    "aiogram>=3.10.0",
    "aiosqlite>=0.20.0",
    "apscheduler>=3.10.0",
    "aiohttp>=3.9.0",
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "ruff>=0.5.0",
    "mypy>=1.10.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.ruff]
line-length = 100
target-version = "py311"

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B"]

[tool.mypy]
python_version = "3.11"
warn_unused_ignores = true
ignore_missing_imports = true
```

### 6.3 Testlar — `template/tests/`

Clean Architecture'ning asosiy foydasi: `UserService` ni **haqiqiy DB'siz**,
soxta (fake) repository bilan test qilish mumkin.

**`template/tests/__init__.py`** — bo'sh fayl.

**`template/tests/conftest.py`**

```python
"""Test uchun umumiy fixture'lar."""
from __future__ import annotations

import pytest

from bot.domain.entities.user import User
from bot.domain.repositories.user_repository import UserRepository


class FakeUserRepository(UserRepository):
    """Xotira ichidagi soxta repo — testlarda haqiqiy DB o'rniga ishlatiladi."""

    def __init__(self) -> None:
        self._store: dict[int, User] = {}

    async def add(self, user: User) -> None:
        self._store.setdefault(user.telegram_id, user)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self._store.get(telegram_id)


@pytest.fixture
def fake_repo() -> FakeUserRepository:
    return FakeUserRepository()
```

**`template/tests/test_user_service.py`**

```python
"""UserService use-case'lari uchun testlar (DB'siz)."""
from __future__ import annotations

import pytest

from bot.application.services.user_service import UserService
from tests.conftest import FakeUserRepository


@pytest.mark.asyncio
async def test_register_yangi_foydalanuvchi(fake_repo: FakeUserRepository) -> None:
    service = UserService(fake_repo)

    user = await service.register(telegram_id=1, full_name="Ali", username="ali")

    assert user.telegram_id == 1
    assert user.full_name == "Ali"
    assert await fake_repo.get_by_telegram_id(1) is not None


@pytest.mark.asyncio
async def test_register_idempotent(fake_repo: FakeUserRepository) -> None:
    service = UserService(fake_repo)

    first = await service.register(telegram_id=1, full_name="Ali")
    second = await service.register(telegram_id=1, full_name="Boshqa ism")

    # Ikkinchi chaqiruv mavjud foydalanuvchini qaytaradi, yangisini yaratmaydi.
    assert first == second
    assert first.full_name == "Ali"


@pytest.mark.asyncio
async def test_get_mavjud_emas(fake_repo: FakeUserRepository) -> None:
    service = UserService(fake_repo)
    assert await service.get(telegram_id=999) is None
```

> Ixtiyoriy: `SqliteUserRepository` ni `:memory:` bazada test qiluvchi
> integratsion test ham qo'shish mumkin.

### 6.4 `template/README.md` — yangilash

README'ni yangi tuzilma va Clean Architecture bo'yicha yangilash kerak. Asosiy
bo'limlar:

- **Arxitektura:** yuqoridagi qatlamlar diagrammasi (domain → application →
  infrastructure/presentation → composition root) va har qatlamning vazifasi.
- **O'rnatish:**
  ```bash
  python -m venv venv
  source venv/bin/activate        # Windows: venv\Scripts\activate
  pip install -r requirements.txt
  cp .env.example .env            # keyin .env ichini to'ldiring
  ```
- **`.env` o'zgaruvchilari** jadvali:

  | O'zgaruvchi | Majburiy | Default | Izoh |
  |---|---|---|---|
  | `BOT_TOKEN` | ✅ ha | — | BotFather'dan olingan token |
  | `PORT` | yo'q | `8080` | Web server porti |
  | `DATABASE_PATH` | yo'q | `data/bot.db` | SQLite fayl yo'li |
  | `RENDER_EXTERNAL_URL` | yo'q | — | Mini App / keep-alive URL |
  | `LOG_LEVEL` | yo'q | `INFO` | Log darajasi |

- **Ishga tushirish:** `python -m bot`
- **Test:** `pytest`
- **Deploy (Render.com):** health check `/health`, `RENDER_EXTERNAL_URL` ni
  Render bergan URL'ga sozlang.

### 6.5 `create.sh` (root) — sinxronlash

Root'dagi `create.sh` yangi papka tuzilmasini yaratishi kerak. Tekshirish/yangilash:

- Yangi papkalar yaratilsin: `presentation/{handlers,keyboards,middlewares,states}`,
  `infrastructure/{database/repositories,scheduler,web}`, `domain/{entities,repositories}`,
  `application/services`, `core`, `tests`.
- Eski papkalar (`db`, `handlers`, `keyboards`, `middlewares`, `services`,
  `states`, `utils` — bot ildizida) **yaratilmasin**.
- `.env` / `.env.example` generatsiyasi Settings maydonlariga mos bo'lsin:
  `BOT_TOKEN=`, `PORT=8080`, `DATABASE_PATH=data/bot.db`, `RENDER_EXTERNAL_URL=`,
  ixtiyoriy `LOG_LEVEL=INFO`.
- Agar `create.sh` fayllarni `template/` dan nusxalasa (generatsiya qilmasa),
  yangi fayllar ro'yxatga qo'shilganini tekshiring.

### 6.6 Eski fayllarni o'chirish

Yangi qatlamlar tayyor bo'lib, `app.py` ular orqali ishlagach, quyidagilarni
o'chiring:

```bash
rm template/bot/config.py
rm template/bot/web_app.py
rm -r template/bot/db
rm -r template/bot/handlers        # presentation/handlers tayyor bo'lgach
rm -r template/bot/keyboards       # presentation/keyboards tayyor bo'lgach
rm -r template/bot/middlewares     # presentation/middlewares tayyor bo'lgach
rm -r template/bot/services        # infrastructure/scheduler ga ko'chgan
rm -r template/bot/states          # presentation/states tayyor bo'lgach
rm -r template/bot/utils           # bo'sh
```

> Diqqat: o'chirishdan oldin yangi presentation fayllari yaratilgan va
> `app.py` importlari yangi yo'llarga o'tganiga ishonch hosil qiling.

---

## 7-TASK — Verifikatsiya

Barcha o'zgarishlardan so'ng quyidagilarni tekshiring:

1. **Import / kompilyatsiya tekshiruvi** (DB yoki token talab qilmaydi):
   ```bash
   cd template
   python -m compileall bot
   ```
   Xatoliksiz o'tsa — barcha modullar sintaktik to'g'ri.

2. **Testlar:**
   ```bash
   cd template
   pip install -e ".[dev]"     # yoki: pip install pytest pytest-asyncio
   pytest -q
   ```
   Barcha testlar yashil bo'lishi kerak.

3. **Linter / tiplar (ixtiyoriy, lekin tavsiya etiladi):**
   ```bash
   ruff check bot
   mypy bot
   ```

4. **Qo'lda ishga tushirish (real token bilan):**
   ```bash
   cp .env.example .env         # BOT_TOKEN ni to'ldiring
   python -m bot
   ```
   Kutiladigan loglar: "Ma'lumotlar bazasi ulandi", "Scheduler ishga tushdi",
   "WebApp & Health Check server ishga tushdi", "Bot ishga tushdi. Polling
   boshlandi." Telegram'da `/start` yuborilганda salomlashuv + klaviatura kelishi.

5. **Health check:** `curl http://localhost:8080/health` →
   `{"status": "ok", "service": "Telegram Bot & WebApp"}`.

6. **Tozalash:** vaqtincha yaratilgan `data/bot.db`, `data/bot.db-wal`,
   `data/bot.db-shm`, `__pycache__` papkalarini repozitoriyga qo'shmang
   (`.gitignore` da bo'lsin).

---

## Bajarilish tartibi (tavsiya)

1. Presentation qatlamini to'liq yarating (4-task) — eski papkalarni hali
   o'chirmang.
2. `app.py` va yupqa `__main__.py` ni yozing (5-task).
3. `requirements.txt`, `pyproject.toml`, testlarni qo'shing (6-task).
4. `python -m compileall bot` + `pytest` bilan tekshiring (7-task).
5. Hammasi ishlagach, eski fayllarni o'chiring (6.6) va yana bir bor
   `compileall` + `pytest` ni qayta ishga tushiring.
6. README va `create.sh` ni yangilang.
```

