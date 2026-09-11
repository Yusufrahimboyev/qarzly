"""Composition root: barcha qatlamlarni ulaydi va bot hayot siklini boshqaradi.

Bu — dasturning yagona joyi bo'lib, konkret implementatsiyalarni (PostgreSQL repo,
scheduler, web server) yaratadi va bir-biriga bog'laydi (dependency injection).
Boshqa hech bir qatlam bu ulanishlar haqida bilmaydi.

Resurslar `AsyncExitStack` orqali ochiladi: qaysi bosqichda xato bo'lishidan
qat'i nazar, undan oldin ochilgan hamma narsa teskari tartibda va bir-birini
bloklamasdan yopiladi.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.user_service import UserService
from bot.core.config import get_settings
from bot.core.logging import setup_logging
from bot.infrastructure.database.connection import Database
from bot.infrastructure.database.repositories.client_repository import (
    PgClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import (
    PgDebtRepository,
)
from bot.infrastructure.database.repositories.idempotency_repository import (
    IdempotencyStore,
)
from bot.infrastructure.database.repositories.payment_repository import (
    PgPaymentRepository,
)
from bot.infrastructure.database.repositories.user_repository import (
    PgUserRepository,
)
from bot.infrastructure.database.unit_of_work import create_unit_of_work_factory
from bot.infrastructure.scheduler.daily_report import send_daily_report
from bot.infrastructure.scheduler.scheduler import create_scheduler
from bot.infrastructure.telegram.retry_middleware import RetryAfterMiddleware
from bot.infrastructure.web.server import WebServer
from bot.presentation.handlers import register_handlers
from bot.presentation.middlewares import register_middlewares

logger = logging.getLogger(__name__)


@asynccontextmanager
async def _closing(resource, close) -> AsyncIterator[object]:
    """Resursni beradi va chiqishda uni xatolarga chidamli yopadi."""
    try:
        yield resource
    finally:
        try:
            result = close()
            if asyncio.iscoroutine(result):
                await result
        except Exception:
            logger.exception("Resursni yopishda xatolik (davom etilmoqda)")


async def run() -> None:
    """Botni sozlaydi, ishga tushiradi va to'xtaganda resurslarni tozalaydi."""
    settings = get_settings()
    setup_logging(settings.log_level, json_format=settings.log_json)

    if settings.allow_open_access and not settings.admin_id_list:
        logger.warning(
            "⚠️ ALLOW_OPEN_ACCESS=true va ADMIN_IDS bo'sh — bot OCHIQ rejimda "
            "ishlaydi: botni topgan HAR QANDAY Telegram foydalanuvchisi barcha "
            "mijozlar ma'lumotlarini ko'ra va o'zgartira oladi. Bu rejim faqat "
            "development uchun!"
        )

    async with AsyncExitStack() as stack:
        # --- Infrastructure: ma'lumotlar bazasi (Supabase PostgreSQL) ---
        database = Database(
            settings.dsn,
            min_size=settings.db_pool_min_size,
            max_size=settings.db_pool_max_size,
            command_timeout=settings.db_command_timeout,
            apply_migrations=settings.apply_migrations,
        )
        await database.connect()
        await stack.enter_async_context(_closing(database, database.disconnect))

        # --- Repositories ---
        pool = database.pool
        user_repository = PgUserRepository(pool)
        client_repository = PgClientRepository(pool)
        debt_repository = PgDebtRepository(pool)
        payment_repository = PgPaymentRepository(pool)
        idempotency_store = IdempotencyStore(pool)
        uow_factory = create_unit_of_work_factory(pool)

        # --- Application Services ---
        user_service = UserService(user_repository)
        client_service = ClientService(
            clients=client_repository,
            debts=debt_repository,
        )
        debt_service = DebtService(
            clients=client_repository,
            debts=debt_repository,
            payments=payment_repository,
            uow_factory=uow_factory,
        )

        # --- Aiogram: Bot va Dispatcher ---
        bot = Bot(
            token=settings.token,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML),
        )
        # Telegram 429 va tarmoq xatolarida retry_after'ni hurmat qiladi.
        bot.session.middleware(RetryAfterMiddleware())
        await stack.enter_async_context(_closing(bot, bot.session.close))
        dp = Dispatcher(storage=MemoryStorage())

        # --- Middlewares & Handlers ---
        register_middlewares(
            dp=dp,
            user_service=user_service,
            client_service=client_service,
            debt_service=debt_service,
            settings=settings,
        )
        register_handlers(dp)

        # --- Infrastructure: scheduler va web server ---
        daily_report_job = None
        if settings.report_channel_id:
            async def daily_report_job() -> None:  # noqa: E306
                await send_daily_report(
                    bot=bot,
                    debt_service=debt_service,
                    channel_id=settings.report_channel_id,
                    start_date=settings.report_start_date,
                )

        scheduler = create_scheduler(
            settings.render_external_url,
            daily_report_job=daily_report_job,
            report_hour=settings.report_send_hour,
            report_minute=settings.report_send_minute,
        )
        await stack.enter_async_context(
            _closing(scheduler, lambda: scheduler.shutdown(wait=False))
        )

        web_server = WebServer(
            client_service=client_service,
            debt_service=debt_service,
            settings=settings,
            database=database,
            idempotency_store=idempotency_store,
            host="0.0.0.0",
            port=settings.port,
        )
        await web_server.start()
        await stack.enter_async_context(_closing(web_server, web_server.stop))

        logger.info("🤖 Qarz Daftar boti ishga tushdi. Polling boshlandi.")
        try:
            await dp.start_polling(bot)
        finally:
            logger.info("Bot to'xtatilmoqda, resurslar tozalanmoqda...")


def main() -> None:
    """Sinxron kirish nuqtasi (asyncio event loop'ni ishga tushiradi)."""
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot foydalanuvchi tomonidan to'xtatildi.")
