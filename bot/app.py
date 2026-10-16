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

from bot.application.services.admin_service import AdminService
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.edit_service import EditService
from bot.application.services.user_service import UserService
from bot.application.services.voice_debt_service import VoiceDebtService
from bot.core.branches import BRANCH_SCHEMAS, BRANCH_TITLES, oil_code, oil_title
from bot.core.config import Settings, get_settings
from bot.core.logging import setup_logging
from bot.domain.entities.debt import UNIT_LITRES, UNIT_PIECES
from bot.infrastructure.branches import Branch, BranchRegistry
from bot.infrastructure.database.connection import Database
from bot.infrastructure.database.repositories.admin_repository import PgAdminRepository
from bot.infrastructure.database.repositories.client_repository import (
    PgClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import (
    PgDebtRepository,
)
from bot.infrastructure.database.repositories.edit_log_repository import (
    PgEditLogRepository,
)
from bot.infrastructure.database.repositories.idempotency_repository import (
    IdempotencyStore,
)
from bot.infrastructure.database.repositories.language_repository import LanguageStore
from bot.infrastructure.database.repositories.payment_repository import (
    PgPaymentRepository,
)
from bot.infrastructure.database.repositories.user_repository import (
    PgUserRepository,
)
from bot.infrastructure.database.unit_of_work import create_unit_of_work_factory
from bot.infrastructure.layakit.client import LayaKitClient
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


async def _open_branch(
    stack: AsyncExitStack,
    settings: Settings,
    code: str,
    laya: LayaKitClient | None,
    *,
    title: str,
    schema: str | None,
    unit: str = UNIT_PIECES,
) -> Branch:
    """Filial (yoki uning Oil daftari) sxemasini ochadi va servislarini yig'adi."""
    database = Database(
        settings.dsn,
        schema=schema,
        min_size=settings.db_pool_min_size,
        max_size=settings.db_pool_max_size,
        command_timeout=settings.db_command_timeout,
        apply_migrations=settings.apply_migrations,
    )
    await database.connect()
    await stack.enter_async_context(_closing(database, database.disconnect))

    pool = database.pool
    client_repository = PgClientRepository(pool)
    debt_repository = PgDebtRepository(pool)
    payment_repository = PgPaymentRepository(pool)
    uow_factory = create_unit_of_work_factory(pool)
    client_service = ClientService(clients=client_repository, debts=debt_repository)
    debt_service = DebtService(
        clients=client_repository,
        debts=debt_repository,
        payments=payment_repository,
        uow_factory=uow_factory,
        unit=unit,
    )
    return Branch(
        code=code,
        title=title,
        unit=unit,
        client_service=client_service,
        debt_service=debt_service,
        user_service=UserService(PgUserRepository(pool)),
        database=database,
        idempotency_store=IdempotencyStore(pool),
        voice_debt_service=(
            VoiceDebtService(laya=laya, client_service=client_service)
            if laya is not None
            else None
        ),
        edit_service=EditService(
            clients=client_repository,
            debts=debt_repository,
            payments=payment_repository,
            edits=PgEditLogRepository(pool),
            uow_factory=uow_factory,
            unit=unit,
        ),
    )


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
        # --- Infrastructure: shu bot filialining bazasi va servislari ---
        laya = None
        if settings.voice_enabled:
            laya = LayaKitClient(
                base_url=settings.layakit_url,
                token=settings.layakit_token.get_secret_value(),
                timeout_seconds=settings.layakit_timeout_seconds,
            )

        code = settings.branch
        branches = [
            await _open_branch(
                stack, settings, code, laya,
                title=BRANCH_TITLES[code], schema=BRANCH_SCHEMAS[code],
            )
        ]
        if settings.oil_enabled:
            # Moy daftari faqat Mini App'da (bot asosiy daftar bilan ishlaydi).
            branches.append(await _open_branch(
                stack, settings, oil_code(code), None,
                title=oil_title(code), schema=oil_code(code), unit=UNIT_LITRES,
            ))
        registry = BranchRegistry(branches, code)
        logger.info("Filial ulandi: %s", ", ".join(b.code for b in registry))
        language_store = LanguageStore(registry.default.database.pool)
        admin_service = AdminService(
            PgAdminRepository(registry.default.database.pool), settings.admin_id_list
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
            registry=registry,
            settings=settings,
            language_store=language_store,
            admin_service=admin_service,
        )
        register_handlers(dp)

        # --- Infrastructure: scheduler va web server ---
        daily_report_job = None
        if settings.report_channel_id:
            async def daily_report_job() -> None:  # noqa: E306
                # Asosiy daftar va (yoqilgan bo'lsa) Oil daftari — alohida fayllar.
                for branch in registry:
                    await send_daily_report(
                        bot=bot,
                        debt_service=branch.debt_service,
                        channel_id=settings.report_channel_id,
                        start_date=settings.report_start_date,
                        branch_code=branch.code,
                        branch_title=branch.title,
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
            registry=registry,
            settings=settings,
            language_store=language_store,
            admin_service=admin_service,
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
