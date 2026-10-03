"""Presentation qatlami: DI (dependency injection) middleware.

Har bir handler chaqiruvi uchun kerakli servislarni `data` lug'atiga qo'shadi.
Servislar foydalanuvchi tanlagan filialga tegishli (har filial — alohida baza).
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineQuery, Message, TelegramObject

from bot.core.config import Settings
from bot.infrastructure.branches import Branch, BranchRegistry
from bot.infrastructure.database.repositories.branch_preference_repository import (
    BranchPreferenceStore,
)


class DependencyMiddleware(BaseMiddleware):
    """Servislarni handler'lar uchun `data` ga joylaydi."""

    def __init__(
        self,
        registry: BranchRegistry,
        preferences: BranchPreferenceStore,
        settings: Settings,
    ) -> None:
        self._registry = registry
        self._preferences = preferences
        self._settings = settings

    async def _resolve_branch(self, event: TelegramObject) -> Branch:
        """Foydalanuvchi tanlagan filial (tanlanmagan/o'chirilgan bo'lsa — asosiy)."""
        user = None
        if isinstance(event, (Message, CallbackQuery, InlineQuery)):
            user = event.from_user
        if user is not None:
            branch = self._registry.get(await self._preferences.get(user.id))
            if branch is not None:
                return branch
        return self._registry.default

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        branch = await self._resolve_branch(event)
        data["branch"] = branch
        data["branch_registry"] = self._registry
        data["branch_preferences"] = self._preferences
        data["user_service"] = branch.user_service
        data["client_service"] = branch.client_service
        data["debt_service"] = branch.debt_service
        data["settings"] = self._settings
        data["voice_debt_service"] = branch.voice_debt_service
        return await handler(event, data)
