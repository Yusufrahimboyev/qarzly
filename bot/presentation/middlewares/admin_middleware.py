"""Presentation qatlami: Admin autentifikatsiya va ruxsat tekshiruvi middleware'i.

Agar ADMIN_IDS sozlangan bo'lsa, faqat ro'yxatdagi Telegram ID egalariga
botdan foydalanishga ruxsat beriladi.
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
        # Agar admin_ids bo'sh bo'lsa, barcha foydalanuvchilarga ruxsat beriladi (dastlabki sozlash uchun)
        if not self._settings.admin_ids:
            return await handler(event, data)

        user_id: int | None = None
        if isinstance(event, Message) and event.from_user is not None:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user is not None:
            user_id = event.from_user.id

        if user_id is not None and user_id not in self._settings.admin_ids:
            logger.warning("Ruxsatsiz kirishga urinish: user_id=%s", user_id)
            if isinstance(event, Message):
                await event.answer(
                    "⛔️ <b>Kechirasiz, sizda ushbu botdan foydalanish huquqi mavjud emas.</b>\n\n"
                    f"Sizning Telegram ID: <code>{user_id}</code>\n"
                    "Admin bilan bog'laning.",
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔️ Ruxsat berilmagan.", show_alert=True)
            return None

        return await handler(event, data)
