"""Infrastructure qatlami: APScheduler adapteri.

Render.com free tarifida trafik kelmasa xizmat 15 daqiqadan keyin
"uyquga" o'tadi — bu bot polling'ini ham to'xtatib qo'yadi. Shuning
uchun tashqi URL sozlangan bo'lsa, o'zining /health endpointini
muntazam ping qiladigan keep-alive vazifasi ishlaydi.
"""
from __future__ import annotations

import logging
from collections.abc import Callable, Coroutine
from typing import Any

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

KEEP_ALIVE_INTERVAL_MINUTES = 10

# Kunlik hisobot har doim O'zbekiston vaqti bo'yicha yuboriladi — server
# UTC da ishlasa ham 23:59 Toshkent vaqtida bo'lishi kerak.
REPORT_TIMEZONE = "Asia/Tashkent"


async def _keep_alive_job(health_url: str) -> None:
    """O'z /health endpointini ping qiladi (Render spin-down oldini oladi)."""
    try:
        timeout = aiohttp.ClientTimeout(total=15)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(health_url) as resp:
                if resp.status == 200:
                    logger.debug("Keep-alive OK: %s", health_url)
                else:
                    logger.warning("Keep-alive status %s: %s", resp.status, health_url)
    except Exception:
        # Tarmoq muammosi bot ishlashini to'xtatmasligi kerak
        logger.warning("Keep-alive ping yuborilmadi: %s", health_url, exc_info=True)


def create_scheduler(
    external_url: str = "",
    daily_report_job: Callable[[], Coroutine[Any, Any, object]] | None = None,
    report_hour: int = 23,
    report_minute: int = 59,
) -> AsyncIOScheduler:
    """Scheduler'ni yaratadi, vazifalarni ro'yxatga oladi va ishga tushiradi."""
    scheduler = AsyncIOScheduler()

    if external_url:
        health_url = external_url.rstrip("/") + "/health"
        scheduler.add_job(
            _keep_alive_job,
            "interval",
            minutes=KEEP_ALIVE_INTERVAL_MINUTES,
            kwargs={"health_url": health_url},
            id="keep_alive",
            max_instances=1,
        )
        logger.info("Keep-alive vazifasi sozlandi: %s", health_url)
    else:
        logger.info(
            "RENDER_EXTERNAL_URL sozlanmagan — keep-alive vazifasi o'chirildi."
        )

    if daily_report_job is not None:
        scheduler.add_job(
            daily_report_job,
            CronTrigger(
                hour=report_hour,
                minute=report_minute,
                timezone=REPORT_TIMEZONE,
            ),
            id="daily_report",
            max_instances=1,
            # Bot qayta ishga tushayotganda vaqt o'tib ketgan bo'lsa, 10
            # daqiqagacha kechikish bilan baribir yuboriladi.
            misfire_grace_time=600,
        )
        logger.info(
            "Kunlik hisobot vazifasi sozlandi: har kuni %02d:%02d (%s)",
            report_hour,
            report_minute,
            REPORT_TIMEZONE,
        )
    else:
        logger.info(
            "REPORT_CHANNEL_ID sozlanmagan — kunlik hisobot yuborilmaydi."
        )

    scheduler.start()
    return scheduler
