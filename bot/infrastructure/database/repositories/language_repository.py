"""Foydalanuvchi tanlagan interfeys tilini saqlash (PostgreSQL).

Til bot va Mini App uchun umumiy. Har bir update'da o'qilgani uchun
xotirada keshlanadi; o'zgartirilganda kesh yangilanadi.
"""
from __future__ import annotations

from bot.infrastructure.database.repositories.executor import Executor


class LanguageStore:
    """`user_settings` jadvalidagi `language` ustuni bilan ishlaydi."""

    def __init__(self, executor: Executor) -> None:
        self._db = executor
        self._cache: dict[int, str | None] = {}

    async def get(self, telegram_id: int) -> str | None:
        if telegram_id not in self._cache:
            self._cache[telegram_id] = await self._db.fetchval(
                "SELECT language FROM user_settings WHERE telegram_id = $1", telegram_id
            )
        return self._cache[telegram_id]

    async def set(self, telegram_id: int, language: str) -> None:
        await self._db.execute(
            """
            INSERT INTO user_settings (telegram_id, language)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id)
            DO UPDATE SET language = EXCLUDED.language, updated_at = NOW()
            """,
            telegram_id, language,
        )
        self._cache[telegram_id] = language
