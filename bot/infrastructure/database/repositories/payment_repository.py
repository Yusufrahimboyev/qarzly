"""Infrastructure qatlami: PaymentRepository PostgreSQL implementatsiyasi."""
from __future__ import annotations

from datetime import date

import asyncpg

from bot.domain.entities.currency import Currency
from bot.domain.entities.payment import Payment, PaymentType
from bot.domain.repositories.payment_repository import PaymentRepository
from bot.infrastructure.database.repositories.executor import Executor

_SELECT_PAYMENT_COLS = """
    id, client_id, debt_id, amount, currency, payment_type, payment_date, created_at
"""


class PgPaymentRepository(PaymentRepository):
    """PaymentRepository ning asyncpg orqali amalga oshirilishi."""

    def __init__(self, executor: Executor) -> None:
        self._db = executor

    async def add(self, payment: Payment) -> Payment:
        currency_val = (
            payment.currency.value
            if isinstance(payment.currency, Currency)
            else str(payment.currency)
        )
        row = await self._db.fetchrow(
            f"""
            INSERT INTO payments (
                client_id,
                debt_id,
                amount,
                currency,
                payment_type,
                payment_date
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING {_SELECT_PAYMENT_COLS}
            """,
            payment.client_id,
            payment.debt_id,
            payment.amount,
            currency_val,
            payment.payment_type.value,
            payment.payment_date,
        )
        if row is None:
            raise RuntimeError("To'lov yozuvi saqlanmadi.")
        return self._map_row(row)

    async def get_by_client_id(self, client_id: int) -> list[Payment]:
        rows = await self._db.fetch(
            f"""
            SELECT {_SELECT_PAYMENT_COLS}
            FROM payments
            WHERE client_id = $1
            ORDER BY payment_date ASC, id ASC
            """,
            client_id,
        )
        return [self._map_row(row) for row in rows]

    async def get_by_debt_id(self, debt_id: int) -> list[Payment]:
        rows = await self._db.fetch(
            f"""
            SELECT {_SELECT_PAYMENT_COLS}
            FROM payments
            WHERE debt_id = $1
            ORDER BY payment_date ASC, id ASC
            """,
            debt_id,
        )
        return [self._map_row(row) for row in rows]

    async def get_by_date_range(self, date_from: date, date_to: date) -> list[Payment]:
        rows = await self._db.fetch(
            f"""
            SELECT {_SELECT_PAYMENT_COLS}
            FROM payments
            WHERE payment_date BETWEEN $1 AND $2
            ORDER BY payment_date ASC, id ASC
            """,
            date_from,
            date_to,
        )
        return [self._map_row(row) for row in rows]

    async def sum_repayments_before(self, before: date) -> dict[str, int]:
        rows = await self._db.fetch(
            """
            SELECT currency, COALESCE(SUM(amount), 0)
            FROM payments
            WHERE payment_date < $1 AND payment_type IN ('full', 'partial')
            GROUP BY currency
            """,
            before,
        )
        return {str(row[0]): int(row[1]) for row in rows}

    @staticmethod
    def _map_row(row: asyncpg.Record) -> Payment:
        return Payment(
            id=row["id"],
            client_id=row["client_id"],
            debt_id=row["debt_id"],
            amount=row["amount"],
            currency=Currency(row["currency"]),
            payment_type=PaymentType(row["payment_type"]),
            payment_date=row["payment_date"],
            created_at=row["created_at"],
        )
