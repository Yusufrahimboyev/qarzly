"""Presentation qatlami: DI (dependency injection) middleware.

Har bir handler chaqiruvi uchun kerakli servislarni `data` lug'atiga qo'shadi.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.user_service import UserService
from bot.core.config import Settings


class DependencyMiddleware(BaseMiddleware):
    """Servislarni handler'lar uchun `data` ga joylaydi."""

    def __init__(
        self,
        user_service: UserService,
        client_service: ClientService,
        debt_service: DebtService,
        settings: Settings,
    ) -> None:
        self._user_service = user_service
        self._client_service = client_service
        self._debt_service = debt_service
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["user_service"] = self._user_service
        data["client_service"] = self._client_service
        data["debt_service"] = self._debt_service
        data["settings"] = self._settings
        return await handler(event, data)
