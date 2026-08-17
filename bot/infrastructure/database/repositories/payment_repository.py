"""Infrastructure qatlami: PaymentRepository PostgreSQL implementatsiyasi."""
from __future__ import annotations

import asyncpg

from bot.domain.entities.currency import Currency
from bot.domain.entities.payment import Payment, PaymentType
from bot.domain.repositories.payment_repository import PaymentRepository

_SELECT_PAYMENT_COLS = """
    id, client_id, debt_id, amount, currency, payment_type, payment_date, created_at
"""


class PgPaymentRepository(PaymentRepository):
    """PaymentRepository ning asyncpg orqali amalga oshirilishi."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, payment: Payment) -> Payment:
        currency_val = (
            payment.currency.value
            if isinstance(payment.currency, Currency)
            else str(payment.currency)
        )
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO payments (
                    client_id,
                    debt_id,
                    amount,
                    currency,
                    payment_type,
                    payment_date
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING id
                """,
                payment.client_id,
                payment.debt_id,
                payment.amount,
                currency_val,
                payment.payment_type.value,
                payment.payment_date,
            )
            payment_id = row["id"] if row else None
            if payment_id is None:
                raise RuntimeError("To'lov yozuvini saqlashda ID olinmadi.")
            return await self._get_by_id(payment_id)  # type: ignore[return-value]

    async def _get_by_id(self, payment_id: int) -> Payment | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                SELECT {_SELECT_PAYMENT_COLS}
                FROM payments
                WHERE id = $1
                """,
                payment_id,
            )

        if row is None:
            return None
        return self._map_row(row)

    async def get_by_client_id(self, client_id: int) -> list[Payment]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
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
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT {_SELECT_PAYMENT_COLS}
                FROM payments
                WHERE debt_id = $1
                ORDER BY payment_date ASC, id ASC
                """,
                debt_id,
            )

        return [self._map_row(row) for row in rows]

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
