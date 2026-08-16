"""SQLite ulanishini boshqaruvchi Database klassi.

Bitta umumiy (shared) aiosqlite ulanishi ochiladi va butun bot hayoti
davomida qayta ishlatiladi — har bir update uchun yangi ulanish ochish
o'rniga. WAL rejimi bir vaqtda o'qish/yozishni yaxshilaydi.
"""
from __future__ import annotations

import logging
from pathlib import Path

import aiosqlite

from bot.infrastructure.database.schema import SCHEMA

logger = logging.getLogger(__name__)


class Database:
    """Umumiy aiosqlite ulanishining hayot siklini boshqaradi."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._connection: aiosqlite.Connection | None = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Ochiq ulanishni qaytaradi (connect() chaqirilgan bo'lishi shart)."""
        if self._connection is None:
            raise RuntimeError("Database ulanmagan. Avval connect() chaqiring.")
        return self._connection

    async def connect(self) -> None:
        """Ulanishni ochadi, PRAGMA'larni sozlaydi va sxemani qo'llaydi."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self._path)
        self._connection.row_factory = aiosqlite.Row

        await self._connection.execute("PRAGMA journal_mode=WAL;")
        await self._connection.execute("PRAGMA foreign_keys=ON;")
        await self._init_schema()
        logger.info("Ma'lumotlar bazasi ulandi: %s", self._path)

    async def _init_schema(self) -> None:
        for ddl in SCHEMA:
            await self.connection.execute(ddl)
        await self.connection.commit()

    async def disconnect(self) -> None:
        """Ulanishni yopadi."""
        if self._connection is not None:
            await self._connection.close()
            self._connection = None
            logger.info("Ma'lumotlar bazasi ulanishi yopildi.")
