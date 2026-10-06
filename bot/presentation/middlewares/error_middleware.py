from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from bot.i18n import _

logger = logging.getLogger(__name__)


class ErrorMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except Exception:
            logger.exception("Handler bajarilishida kutilmagan xatolik")
            if isinstance(event, Message):
                await event.answer(
                    _("⚠️ Kutilmagan xatolik yuz berdi. Birozdan so'ng qayta urinib ko'ring.")
                )
            return None
