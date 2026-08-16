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
    settings = get_settings()
    setup_logging(settings.log_level)

    database = Database(settings.database_path)
    await database.connect()

    user_repository = SqliteUserRepository(database.connection)
    user_service = UserService(user_repository)

    bot = Bot(
        token=settings.token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    register_middlewares(dp, user_service)
    register_handlers(dp)

    scheduler = create_scheduler(bot)
    web_server = WebServer(host="0.0.0.0", port=settings.port)
    await web_server.start()

    logger.info("Bot ishga tushdi. Polling boshlandi.")
    try:
        await dp.start_polling(bot)
    finally:
        logger.info("Bot to'xtatilmoqda, resurslar tozalanmoqda...")
        scheduler.shutdown(wait=False)
        await web_server.stop()
        await database.disconnect()
        await bot.session.close()


def main() -> None:
    try:
        asyncio.run(run())
    except (KeyboardInterrupt, SystemExit):
        logging.getLogger(__name__).info("Bot foydalanuvchi tomonidan to'xtatildi.")
