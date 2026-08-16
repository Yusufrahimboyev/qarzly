"""Infrastructure qatlami: aiohttp web server adapteri.

Mini App va health check server'ini ishga tushiradi va to'xtatadi.
Bot polling bilan bir vaqtda, bitta event loop ichida ishlaydi.
"""
from __future__ import annotations

import logging

from aiohttp import web

from bot.infrastructure.web.routes import setup_routes

logger = logging.getLogger(__name__)


class WebServer:
    """aiohttp web server'ining hayot siklini boshqaradi."""

    def __init__(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        self._host = host
        self._port = port
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        """Web server'ni ishga tushiradi."""
        app = web.Application()
        setup_routes(app)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info(
            "🌐 WebApp & Health Check server ishga tushdi: http://%s:%s",
            self._host,
            self._port,
        )

    async def stop(self) -> None:
        """Web server'ni to'xtatadi va resurslarni tozalaydi."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            logger.info("Web server to'xtatildi.")
