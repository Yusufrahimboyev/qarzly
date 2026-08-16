"""Testlar uchun fixture'lar."""
from __future__ import annotations

import aiosqlite
import pytest

from bot.domain.entities.user import User
from bot.domain.repositories.user_repository import UserRepository
from bot.infrastructure.database.repositories.client_repository import (
    SqliteClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import (
    SqliteDebtRepository,
)
from bot.infrastructure.database.repositories.payment_repository import (
    SqlitePaymentRepository,
)
from bot.infrastructure.database.schema import SCHEMA


class FakeUserRepository(UserRepository):
    def __init__(self) -> None:
        self._store: dict[int, User] = {}

    async def add(self, user: User) -> None:
        self._store.setdefault(user.telegram_id, user)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self._store.get(telegram_id)


@pytest.fixture
def fake_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
async def in_memory_db():
    """In-memory SQLite ulanishi va jadvallarni yaratadi."""
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.execute("PRAGMA foreign_keys=ON;")

    for ddl in SCHEMA:
        await conn.executescript(ddl)
    await conn.commit()

    yield conn

    await conn.close()


@pytest.fixture
def client_repo(in_memory_db: aiosqlite.Connection) -> SqliteClientRepository:
    return SqliteClientRepository(in_memory_db)


@pytest.fixture
def debt_repo(in_memory_db: aiosqlite.Connection) -> SqliteDebtRepository:
    return SqliteDebtRepository(in_memory_db)


@pytest.fixture
def payment_repo(in_memory_db: aiosqlite.Connection) -> SqlitePaymentRepository:
    return SqlitePaymentRepository(in_memory_db)
