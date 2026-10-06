"""Presentation qatlami: har bir update uchun foydalanuvchi tilini o'rnatadi.

Eng tashqi middleware — admin rad javobi va xatolik xabarlari ham
foydalanuvchi tilida chiqishi uchun.
"""
from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, InlineQuery, Message, TelegramObject

from bot.i18n import set_language
from bot.infrastructure.database.repositories.language_repository import LanguageStore


class LanguageMiddleware(BaseMiddleware):
    def __init__(self, store: LanguageStore) -> None:
        self._store = store

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = (
            event.from_user
            if isinstance(event, (Message, CallbackQuery, InlineQuery))
            else None
        )
        set_language(await self._store.get(user.id) if user is not None else None)
        data["language_store"] = self._store
        return await handler(event, data)
