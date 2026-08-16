"""Composition root: barcha qatlamlarni ulaydi va bot hayot siklini boshqaradi.

Bu — dasturning yagona joyi bo'lib, konkret implementatsiyalarni (SQLite repo,
scheduler, web server) yaratadi va bir-biriga bog'laydi (dependency injection).
Boshqa hech bir qatlam bu ulanishlar haqida bilmaydi.
"""
from __future__ import annotations

import asyncio
import logging
import os

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
    SqliteClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import (
    SqliteDebtRepository,
)
from bot.infrastructure.database.repositories.payment_repository import (
    SqlitePaymentRepository,
)
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

    if not settings.admin_ids:
        logger.warning(
            "⚠️ ADMIN_IDS bo'sh — bot OCHIQ rejimda ishlaydi: botni topgan HAR QANDAY "
            "Telegram foydalanuvchisi barcha mijozlar ma'lumotlarini ko'ra va "
            "o'zgartira oladi. .env faylida ADMIN_IDS ni sozlang!"
        )

    # --- Infrastructure: ma'lumotlar bazasi ---
    database = Database(settings.database_path)
    await database.connect()

    if os.environ.get("RENDER") == "true":
        logger.warning(
            "⚠️ Render'da ishlayapsiz. Free tarifda disk EPHEMERAL — har "
            "deploy/restartda SQLite fayli yo'qolishi mumkin. Persistent disk "
            "uling yoki tashqi baza ishlating (README → 'Deploy' bo'limi)."
        )

    # --- Repositories ---
    user_repository = SqliteUserRepository(database.connection)
    client_repository = SqliteClientRepository(database.connection)
    debt_repository = SqliteDebtRepository(database.connection)
    payment_repository = SqlitePaymentRepository(database.connection)

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
    )

    # --- Aiogram: Bot va Dispatcher ---
    bot = Bot(
        token=settings.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
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
    scheduler = create_scheduler(settings.render_external_url)
    web_server = WebServer(
        client_service=client_service,
        debt_service=debt_service,
        settings=settings,
        host="0.0.0.0",
        port=settings.port,
    )
    await web_server.start()

    logger.info("🤖 Qarz Daftar boti ishga tushdi. Polling boshlandi.")
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
