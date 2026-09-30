"""Supabase PostgreSQL ulanishini boshqaruvchi Database klassi.

asyncpg pool orqali PostgreSQL (Supabase) ga ulanadi.
Transaction mode pooler (port 6543) va direct mode (port 5432) uchun optimallashgan.
"""
from __future__ import annotations

import logging

import asyncpg

from bot.infrastructure.database.migrations import run_migrations
from bot.infrastructure.database.schema import SCHEMA

logger = logging.getLogger(__name__)


class Database:
    """asyncpg pool hayot siklini boshqaradi."""

    def __init__(
        self,
        dsn: str,
        *,
        min_size: int = 2,
        max_size: int = 10,
        command_timeout: int = 60,
        apply_migrations: bool = True,
        schema: str | None = None,
    ) -> None:
        self._dsn = dsn
        self._schema = schema
        self._pool: asyncpg.Pool | None = None
        self._min_size = min_size
        self._max_size = max_size
        self._command_timeout = command_timeout
        self._apply_migrations = apply_migrations

    @property
    def pool(self) -> asyncpg.Pool:
        """Ochiq ulanishlar hovuzini qaytaradi."""
        if self._pool is None:
            raise RuntimeError("Database ulanmagan. Avval connect() chaqiring.")
        return self._pool

    async def connect(self) -> None:
        """PostgreSQL ulanish hovuzini ochadi va sxemani ishga tushiradi.

        Migratsiya xatosi jimgina yutilmaydi — ilova ishga tushmaydi, chunki
        noto'g'ri sxema bilan ishlagan bot moliyaviy yozuvlarni buzishi mumkin.
        """
        server_settings = None
        if self._schema:
            await self._ensure_schema()
            # Faqat shu sxema: boshqa filial yoki public jadvallariga
            # tasodifan tushib qolish imkoni yo'q.
            server_settings = {"search_path": self._schema}
        self._pool = await asyncpg.create_pool(
            dsn=self._dsn,
            server_settings=server_settings,
            min_size=self._min_size,
            max_size=self._max_size,
            statement_cache_size=0,
            command_timeout=self._command_timeout,
        )
        await self._init_schema()
        if self._apply_migrations:
            await run_migrations(self.pool)
        else:
            logger.info("Migratsiyalar o'tkazib yuborildi (APPLY_MIGRATIONS=false).")
        logger.info("Supabase PostgreSQL bazasiga muvaffaqiyatli ulandi.")

    async def _ensure_schema(self) -> None:
        """Filial sxemasini yaratadi (mavjud bo'lsa tegmaydi)."""
        conn = await asyncpg.connect(
            dsn=self._dsn,
            statement_cache_size=0,
            timeout=self._command_timeout,
        )
        try:
            # Sxema nomi faqat BRANCH_SCHEMAS dan keladi; baribir qo'shtirnoqlanadi.
            quoted = '"' + self._schema.replace('"', '""') + '"'  # type: ignore[union-attr]
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {quoted}")
        finally:
            await conn.close()

    async def _init_schema(self) -> None:
        """Jadvallar va indekslarni yaratadi (faqat mavjud bo'lmaganlarini)."""
        async with self.pool.acquire() as conn:
            for ddl in SCHEMA:
                await conn.execute(ddl)

    async def ping(self) -> bool:
        """Baza bilan aloqani tekshiradi (health check uchun)."""
        if self._pool is None:
            return False
        try:
            res = await self._pool.fetchval("SELECT 1")
            return bool(res == 1)
        except Exception as exc:
            logger.warning("Database ping xatosi: %s", exc)
            return False

    async def disconnect(self) -> None:
        """Ulanishlar hovuzini toza yopadi."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None
            logger.info("PostgreSQL ulanishi yopildi.")
