"""Supabase PostgreSQL ulanishini boshqaruvchi Database klassi.

asyncpg pool orqali PostgreSQL (Supabase) ga ulanadi.
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
        if self._pool is None:
            raise RuntimeError("Database ulanmagan. Avval connect() chaqiring.")
        return self._pool

    async def connect(self) -> None:
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=2,
            max_size=10,
            statement_cache_size=0,
        )
        await self._init_schema()
        logger.info("Supabase PostgreSQL bazasiga ulandi.")

    async def _init_schema(self) -> None:
        async with self.pool.acquire() as conn:
            for ddl in SCHEMA:
                await conn.execute(ddl)

    async def disconnect(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL ulanishi yopildi.")
