"""Supabase PostgreSQL ulanishini boshqaruvchi Database klassi.

asyncpg pool orqali PostgreSQL (Supabase) ga ulanadi.
Transaction mode pooler (port 6543) va direct mode (port 5432) uchun optimallashgan.
"""
from __future__ import annotations

import logging

import asyncpg

from bot.infrastructure.database.schema import SCHEMA

logger = logging.getLogger(__name__)


class Database:
    """asyncpg pool hayot siklini boshqaradi."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: asyncpg.Pool | None = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Ochiq ulanishlar hovuzini qaytaradi."""
        if self._pool is None:
            raise RuntimeError("Database ulanmagan. Avval connect() chaqiring.")
        return self._pool

    async def connect(self) -> None:
        """PostgreSQL ulanish hovuzini ochadi va sxemani ishga tushiradi."""
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=2,
            max_size=10,
            statement_cache_size=0,
            command_timeout=60,
        )
        await self._init_schema()
        await self._migrate_columns()
        logger.info("Supabase PostgreSQL bazasiga muvaffaqiyatli ulandi.")

    async def _init_schema(self) -> None:
        """Jadvallar va indekslarni yaratadi."""
        async with self.pool.acquire() as conn:
            for ddl in SCHEMA:
                await conn.execute(ddl)

    async def _migrate_columns(self) -> None:
        """Eski INTEGER ustunlarni BIGINT ga o'tkazish migratsiyasi."""
        alter_statements = [
            "ALTER TABLE debts ALTER COLUMN product_quantity TYPE BIGINT;",
            "ALTER TABLE debts ALTER COLUMN product_price TYPE BIGINT;",
            "ALTER TABLE debts ALTER COLUMN exchange_product_price TYPE BIGINT;",
            "ALTER TABLE debts ALTER COLUMN given_money TYPE BIGINT;",
            "ALTER TABLE debts ALTER COLUMN original_debt TYPE BIGINT;",
            "ALTER TABLE debts ALTER COLUMN remaining_debt TYPE BIGINT;",
            "ALTER TABLE payments ALTER COLUMN amount TYPE BIGINT;",
        ]
        async with self.pool.acquire() as conn:
            for stmt in alter_statements:
                try:
                    await conn.execute(stmt)
                except Exception:
                    # Agar allaqachon BIGINT bo'lsa yoki jadval endi yaratilgan bo'lsa
                    pass

    async def ping(self) -> bool:
        """Baza bilan aloqani tekshiradi (health check uchun)."""
        if self._pool is None:
            return False
        try:
            async with self.pool.acquire() as conn:
                res = await conn.fetchval("SELECT 1")
                return res == 1
        except Exception as exc:
            logger.warning("Database ping xatosi: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Ulanishlar hovuzini toza yopadi."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL ulanishi yopildi.")
