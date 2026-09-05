"""Infrastructure qatlami: aiohttp web server adapteri.

Mini App, REST API va health check server'ini ishga tushiradi va to'xtatadi.
Bot polling bilan bir vaqtda, bitta event loop ichida ishlaydi. /api/*
route'lari Telegram initData autentifikatsiyasidan o'tadi.
"""
from __future__ import annotations

import logging

from aiohttp import web

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.infrastructure.database.connection import Database
from bot.infrastructure.database.repositories.idempotency_repository import (
    IdempotencyStore,
)
from bot.infrastructure.web.routes import (
    CLIENT_SERVICE_KEY,
    DATABASE_KEY,
    DEBT_SERVICE_KEY,
    IDEMPOTENCY_KEY,
    setup_routes,
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
        client_service: ClientService,
        debt_service: DebtService,
        settings: Settings,
        database: Database | None = None,
        idempotency_store: IdempotencyStore | None = None,
        host: str = "0.0.0.0",
        port: int = 8080,
    ) -> None:
        self._client_service = client_service
        self._debt_service = debt_service
        self._settings = settings
        self._database = database
        self._idempotency_store = idempotency_store
        self._host = host
        self._port = port
        self._runner: web.AppRunner | None = None

    async def start(self) -> None:
        """Web server'ni ishga tushiradi."""
        app = web.Application(
            middlewares=[
                security_headers_middleware,
                create_auth_middleware(
                    self._settings.token,
                    self._settings.admin_id_list,
                    allow_open_access=self._settings.allow_open_access,
                    rate_limit_per_minute=self._settings.api_rate_limit_per_minute,
                    max_age_seconds=self._settings.init_data_max_age_seconds,
                ),
            ]
        )
        app[CLIENT_SERVICE_KEY] = self._client_service
        app[DEBT_SERVICE_KEY] = self._debt_service
        if self._database is not None:
            app[DATABASE_KEY] = self._database
        if self._idempotency_store is not None:
            app[IDEMPOTENCY_KEY] = self._idempotency_store

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
