"""Telegram API chaqiruvlari uchun flood-control va retry siyosati.

Telegram ko'p xabar yuborilganda 429 (`TelegramRetryAfter`) qaytaradi va
qancha kutish kerakligini aytadi. Bu qiymat hisobga olinmasa, bot xabarni
yo'qotadi yoki limitga qayta-qayta urilib qoladi. Tarmoq/server xatolarida
esa qisqa eksponensial backoff bilan qayta uriniladi.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiogram import Bot
from aiogram.client.session.middlewares.base import (
    BaseRequestMiddleware,
    NextRequestMiddlewareType,
)
from aiogram.exceptions import (
    RestartingTelegram,
    TelegramNetworkError,
    TelegramRetryAfter,
    TelegramServerError,
)
from aiogram.methods.base import TelegramMethod

logger = logging.getLogger(__name__)

MAX_RETRY_ATTEMPTS = 3
MAX_RETRY_AFTER_SECONDS = 60
BACKOFF_BASE_SECONDS = 1.0


class RetryAfterMiddleware(BaseRequestMiddleware):
    """`retry_after` qiymatini hurmat qiladigan va qayta uriniladigan middleware."""

    def __init__(
        self,
        max_attempts: int = MAX_RETRY_ATTEMPTS,
        max_retry_after: int = MAX_RETRY_AFTER_SECONDS,
    ) -> None:
        self._max_attempts = max_attempts
        self._max_retry_after = max_retry_after

    async def __call__(
        self,
        make_request: NextRequestMiddlewareType[Any],
        bot: Bot,
        method: TelegramMethod[Any],
    ) -> Any:
        last_error: Exception | None = None

        for attempt in range(1, self._max_attempts + 1):
            try:
                return await make_request(bot, method)
            except TelegramRetryAfter as exc:
                last_error = exc
                delay = min(exc.retry_after, self._max_retry_after)
                logger.warning(
                    "Telegram flood control: method=%s retry_after=%ss urinish=%s/%s",
                    type(method).__name__,
                    delay,
                    attempt,
                    self._max_attempts,
                )
                if attempt == self._max_attempts:
                    break
                await asyncio.sleep(delay)
            except (TelegramNetworkError, TelegramServerError, RestartingTelegram) as exc:
                last_error = exc
                delay = BACKOFF_BASE_SECONDS * (2 ** (attempt - 1))
                logger.warning(
                    "Telegram vaqtinchalik xatosi: method=%s xato=%s urinish=%s/%s",
                    type(method).__name__,
                    exc.__class__.__name__,
                    attempt,
                    self._max_attempts,
                )
                if attempt == self._max_attempts:
                    break
                await asyncio.sleep(delay)

        assert last_error is not None
        raise last_error
