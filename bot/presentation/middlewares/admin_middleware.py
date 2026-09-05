"""Presentation qatlami: Admin autentifikatsiya va ruxsat tekshiruvi middleware'i.

Faqat ADMIN_IDS ro'yxatidagi Telegram ID egalari botdan foydalana oladi.

Ro'yxat bo'sh bo'lsa, kirish ochiq emas — taqiqlanadi. Yagona istisno:
`ALLOW_OPEN_ACCESS=true` bilan ongli ravishda yoqilgan development rejimi.
Ilgari bo'sh ro'yxat "hammaga ruxsat" degani edi va bitta unutilgan
environment variable barcha mijozlar ma'lumotlarini ochib qo'yardi.
"""
from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from bot.core.config import Settings

logger = logging.getLogger(__name__)


class AdminMiddleware(BaseMiddleware):
    """Foydalanuvchi admin ekanligini tekshiruvchi middleware."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        allowed_ids = self._settings.admin_id_list

        user_id: int | None = None
        if isinstance(event, Message) and event.from_user is not None:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user is not None:
            user_id = event.from_user.id

        if not allowed_ids:
            if self._settings.allow_open_access:
                # Development rejimi — ochiq kirish ongli yoqilgan.
                return await handler(event, data)
            logger.error(
                "ADMIN_IDS sozlanmagan — kirish rad etildi: user_id=%s", user_id
            )
            await self._deny(event, user_id)
            return None

        if user_id is None or user_id not in allowed_ids:
            logger.warning("Ruxsatsiz kirishga urinish: user_id=%s", user_id)
            await self._deny(event, user_id)
            return None

        return await handler(event, data)

    @staticmethod
    async def _deny(event: TelegramObject, user_id: int | None) -> None:
        """Foydalanuvchiga ruxsat yo'qligini bildiradi."""
        if isinstance(event, Message):
            await event.answer(
                "⛔️ <b>Kechirasiz, sizda ushbu botdan foydalanish huquqi mavjud emas.</b>\n\n"
                f"Sizning Telegram ID: <code>{user_id}</code>\n"
                "Admin bilan bog'laning.",
            )
        elif isinstance(event, CallbackQuery):
            await event.answer("⛔️ Ruxsat berilmagan.", show_alert=True)
