"""Infrastructure qatlami: APScheduler adapteri.

Render.com free tarifida trafik kelmasa xizmat 15 daqiqadan keyin
"uyquga" o'tadi — bu bot polling'ini ham to'xtatib qo'yadi. Shuning
uchun tashqi URL sozlangan bo'lsa, o'zining /health endpointini
muntazam ping qiladigan keep-alive vazifasi ishlaydi.
"""
from __future__ import annotations

import logging

import aiohttp
from apscheduler.schedulers.asyncio import AsyncIOScheduler

logger = logging.getLogger(__name__)

KEEP_ALIVE_INTERVAL_MINUTES = 10


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


def create_scheduler(external_url: str = "") -> AsyncIOScheduler:
    """Scheduler'ni yaratadi, keep-alive vazifasini ro'yxatga oladi va ishga tushiradi."""
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

    scheduler.start()
    return scheduler
