"""Presentation qatlami: DI (dependency injection) middleware.

Har bir handler chaqiruvi uchun kerakli servislarni `data` lug'atiga qo'shadi.
Servislar shu bot xizmat qiladigan filialga tegishli.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from bot.core.config import Settings
from bot.infrastructure.branches import BranchRegistry


class DependencyMiddleware(BaseMiddleware):
    """Servislarni handler'lar uchun `data` ga joylaydi."""

    def __init__(
        self,
        registry: BranchRegistry,
        settings: Settings,
    ) -> None:
        self._registry = registry
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        branch = self._registry.default
        data["branch"] = branch
        data["branch_registry"] = self._registry
        data["user_service"] = branch.user_service
        data["client_service"] = branch.client_service
        data["debt_service"] = branch.debt_service
        data["settings"] = self._settings
        data["voice_debt_service"] = branch.voice_debt_service
        return await handler(event, data)
