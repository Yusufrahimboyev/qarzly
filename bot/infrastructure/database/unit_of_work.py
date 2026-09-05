"""Infrastructure qatlami: PostgreSQL Unit of Work.

Bitta connection oladi, `BEGIN` qiladi va shu connection'ga bog'langan
repository'larni beradi. Shu tufayli use-case ichidagi barcha yozuvlar
bitta tranzaksiyada bajariladi va xatoda to'liq rollback bo'ladi.
"""
from __future__ import annotations

import asyncpg
from asyncpg.transaction import Transaction

from bot.domain.repositories.unit_of_work import UnitOfWork
from bot.infrastructure.database.repositories.client_repository import (
    PgClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import PgDebtRepository
from bot.infrastructure.database.repositories.payment_repository import (
    PgPaymentRepository,
)


class PgUnitOfWork(UnitOfWork):
    """asyncpg tranzaksiyasi asosidagi Unit of Work."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._conn: asyncpg.Connection | None = None
        self._transaction: Transaction | None = None
        self._finished = False

    async def begin(self) -> None:
        conn: asyncpg.Connection = await self._pool.acquire()
        self._conn = conn
        transaction = conn.transaction()
        self._transaction = transaction
        await transaction.start()
        self.clients = PgClientRepository(conn)
        self.debts = PgDebtRepository(conn)
        self.payments = PgPaymentRepository(conn)

    async def commit(self) -> None:
        if self._transaction is not None and not self._finished:
            await self._transaction.commit()
            self._finished = True

    async def rollback(self) -> None:
        if self._transaction is not None and not self._finished:
            await self._transaction.rollback()
            self._finished = True

    async def release(self) -> None:
        if self._conn is not None:
            await self._pool.release(self._conn)
            self._conn = None
            self._transaction = None


def create_unit_of_work_factory(pool: asyncpg.Pool):
    """Har chaqiruvda yangi `PgUnitOfWork` qaytaruvchi fabrika."""

    def factory() -> PgUnitOfWork:
        return PgUnitOfWork(pool)

    return factory
