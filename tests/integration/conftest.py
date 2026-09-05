"""Integration testlar uchun haqiqiy PostgreSQL fixture'lari.

Ishga tushirish:

    TEST_DATABASE_URL=postgresql://postgres:postgres@localhost:5432/qarzly_test \
        .venv/bin/python -m pytest tests/integration -q

DIQQAT: fixture har bir testdan oldin jadvallarni TRUNCATE qiladi — faqat
alohida test bazasini ko'rsating, hech qachon productionni emas.
`TEST_DATABASE_URL` berilmasa, barcha integration testlar skip qilinadi.
"""
from __future__ import annotations

import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio

from bot.infrastructure.database.connection import Database

TEST_DSN = os.getenv("TEST_DATABASE_URL", "")

pytestmark = pytest.mark.integration

_TABLES = (
    "trash_payments",
    "trash",
    "idempotency_keys",
    "payments",
    "debts",
    "clients",
    "users",
)


def require_dsn() -> str:
    if not TEST_DSN:
        pytest.skip("TEST_DATABASE_URL sozlanmagan — integration testlar o'tkazib yuborildi")

    # Xavfsizlik to'sig'i: fixture jadvallarni TRUNCATE qiladi. Tasodifan
    # production DSN ko'rsatilib qolmasligi uchun baza nomida "test" bo'lishi
    # shart (yoki ALLOW_DESTRUCTIVE_TESTS=1 bilan ongli ravishda bekor qilinadi).
    if "test" not in TEST_DSN.lower() and os.getenv("ALLOW_DESTRUCTIVE_TESTS") != "1":
        pytest.fail(
            "TEST_DATABASE_URL nomida 'test' yo'q — bu production baza bo'lishi "
            "mumkin. Integration testlar jadvallarni TRUNCATE qiladi! Alohida "
            "test bazasini ko'rsating yoki ALLOW_DESTRUCTIVE_TESTS=1 qo'ying."
        )
    return TEST_DSN


@pytest_asyncio.fixture
async def database() -> AsyncIterator[Database]:
    """Sxema va migratsiyalari qo'llangan toza test bazasi."""
    dsn = require_dsn()
    db = Database(dsn, min_size=1, max_size=5)
    await db.connect()
    async with db.pool.acquire() as conn:
        await conn.execute(
            "TRUNCATE " + ", ".join(_TABLES) + " RESTART IDENTITY CASCADE"
        )
    try:
        yield db
    finally:
        await db.disconnect()
