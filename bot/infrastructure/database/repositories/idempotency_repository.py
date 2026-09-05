"""Idempotency kalitlari uchun PostgreSQL saqlagichi.

Tarmoq retry'i, tugmani ikki marta bosish yoki qayta yuborilgan Telegram
update'i dublikat qarz/to'lov yaratmasligi kerak. Mijoz `Idempotency-Key`
header'ini yuboradi; bir xil kalit bilan kelgan ikkinchi so'rov yangi yozuv
yaratmaydi — birinchi so'rovning javobi qaytariladi.
"""
from __future__ import annotations

import logging

from bot.infrastructure.database.repositories.executor import Executor

logger = logging.getLogger(__name__)

# Juda uzun kalitlar saqlanmaydi (abuse'dan himoya).
MAX_KEY_LENGTH = 200


class IdempotencyStore:
    """`idempotency_keys` jadvali bilan ishlaydi."""

    def __init__(self, executor: Executor) -> None:
        self._db = executor

    async def reserve(self, scope: str, key: str, actor_id: int | None) -> bool:
        """Kalitni band qiladi. Birinchi marta band qilinsa True qaytaradi."""
        row = await self._db.fetchrow(
            """
            INSERT INTO idempotency_keys (scope, idem_key, actor_id)
            VALUES ($1, $2, $3)
            ON CONFLICT (scope, idem_key) DO NOTHING
            RETURNING id
            """,
            scope,
            key[:MAX_KEY_LENGTH],
            actor_id,
        )
        return row is not None

    async def get_response(self, scope: str, key: str) -> str | None:
        """Avval saqlangan javobni qaytaradi (bo'lmasa None)."""
        return await self._db.fetchval(
            """
            SELECT response_json FROM idempotency_keys
            WHERE scope = $1 AND idem_key = $2
            """,
            scope,
            key[:MAX_KEY_LENGTH],
        )

    async def save_response(self, scope: str, key: str, response_json: str) -> None:
        """Muvaffaqiyatli javobni kalitga bog'lab saqlaydi."""
        await self._db.execute(
            """
            UPDATE idempotency_keys
            SET response_json = $3
            WHERE scope = $1 AND idem_key = $2
            """,
            scope,
            key[:MAX_KEY_LENGTH],
            response_json,
        )

    async def release(self, scope: str, key: str) -> None:
        """Bandlikni bekor qiladi (amal xato bilan tugagan holat uchun)."""
        await self._db.execute(
            """
            DELETE FROM idempotency_keys
            WHERE scope = $1 AND idem_key = $2 AND response_json IS NULL
            """,
            scope,
            key[:MAX_KEY_LENGTH],
        )

    async def purge_older_than(self, days: int = 7) -> int:
        """Eski kalitlarni tozalaydi."""
        result = await self._db.execute(
            "DELETE FROM idempotency_keys WHERE created_at < NOW() - $1::interval",
            f"{days} days",
        )
        return int(result.split()[-1]) if result else 0
