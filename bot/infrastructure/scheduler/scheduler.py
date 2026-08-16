"""Infrastructure qatlami: APScheduler adapteri.

Rejalashtirilgan (davriy) vazifalarni sozlaydi. Bu yerda faqat namuna
vazifa bor — o'z vazifalaringizni shu yerga qo'shing.
"""
from __future__ import annotations

import logging

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)


async def _example_job(bot: Bot) -> None:
    """Namuna davriy vazifa (har soatda bir marta chaqiriladi)."""
    logger.info("⏰ APScheduler davriy vazifa bajarilmoqda...")


def create_scheduler(bot: Bot) -> AsyncIOScheduler:
    """Scheduler'ni yaratadi, vazifalarni ro'yxatga oladi va ishga tushiradi."""
    scheduler = AsyncIOScheduler()
    scheduler.add_job(_example_job, "interval", hours=1, args=[bot])
    scheduler.start()
    logger.info("Scheduler ishga tushdi.")
    return scheduler
