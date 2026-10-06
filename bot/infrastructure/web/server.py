"""Infrastructure qatlami: aiohttp web server adapteri.

Mini App, REST API va health check server'ini ishga tushiradi va to'xtatadi.
Bot polling bilan bir vaqtda, bitta event loop ichida ishlaydi. /api/*
route'lari Telegram initData autentifikatsiyasidan o'tadi.
"""
from __future__ import annotations

import logging

from aiohttp import web

from bot.core.config import Settings
from bot.infrastructure.branches import BranchRegistry
from bot.infrastructure.database.repositories.language_repository import LanguageStore
from bot.infrastructure.web.routes import (
    BRANCH_REGISTRY_KEY,
    LANGUAGE_STORE_KEY,
    branch_middleware,
    language_middleware,
    setup_routes,
    static_cache_middleware,
)
from bot.infrastructure.web.telegram_auth import (
    create_auth_middleware,
    security_headers_middleware,
)

logger = logging.getLogger(__name__)


class WebServer:
    """aiohttp web server'ining hayot siklini boshqaradi."""

    def __init__(
        self,
        registry: BranchRegistry,
        settings: Settings,
        language_store: LanguageStore,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        self._registry = registry
        self._language_store = language_store
        self._settings = settings
        self._host = host
        self._port = port
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        """Web server'ni ishga tushiradi."""
        app = web.Application(
            middlewares=[
                security_headers_middleware,
                static_cache_middleware,
                create_auth_middleware(
                    self._settings.token,
                    self._settings.admin_id_list,
                    allow_open_access=self._settings.allow_open_access,
                    rate_limit_per_minute=self._settings.api_rate_limit_per_minute,
                    max_age_seconds=self._settings.init_data_max_age_seconds,
                ),
                branch_middleware,
                language_middleware,
            ]
        )
        app[BRANCH_REGISTRY_KEY] = self._registry
        app[LANGUAGE_STORE_KEY] = self._language_store

        setup_routes(app)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        await site.start()
        logger.info(
            "🌐 WebApp & REST API server ishga tushdi: http://%s:%s",
            self._host,
            self._port,
        )

    async def stop(self) -> None:
        """Web server'ni to'xtatadi va resurslarni tozalaydi."""
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None
            logger.info("Web server to'xtatildi.")
