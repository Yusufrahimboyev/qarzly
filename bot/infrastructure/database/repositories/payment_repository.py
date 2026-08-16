"""Infrastructure qatlami: PaymentRepository SQLite implementatsiyasi."""
from __future__ import annotations

from datetime import datetime

import aiosqlite

from bot.domain.entities.currency import Currency
from bot.domain.entities.payment import Payment, PaymentType
from bot.domain.repositories.payment_repository import PaymentRepository


class SqlitePaymentRepository(PaymentRepository):
    """PaymentRepository ning aiosqlite orqali amalga oshirilishi."""

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self._connection = connection

    async def add(self, payment: Payment) -> Payment:
        cursor = await self._connection.execute(
            """
            INSERT INTO payments (
                client_id,
                debt_id,
                amount,
                currency,
                payment_type,
                payment_date
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                payment.client_id,
                payment.debt_id,
                payment.amount,
                payment.currency.value
                if isinstance(payment.currency, Currency)
                else str(payment.currency),
                payment.payment_type.value,
                payment.payment_date,
            ),
        )
        await self._connection.commit()
        payment_id = cursor.lastrowid
        if payment_id is None:
            raise RuntimeError("To'lov yozuvini saqlashda ID olinmadi.")
        return await self._get_by_id(payment_id)  # type: ignore[return-value]

    async def _get_by_id(self, payment_id: int) -> Payment | None:
        async with self._connection.execute(
            """
            SELECT id, client_id, debt_id, amount, currency, payment_type, payment_date, created_at
            FROM payments
            WHERE id = ?
            """,
            (payment_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return self._map_row(row)

    async def get_by_client_id(self, client_id: int) -> list[Payment]:
        async with self._connection.execute(
            """
            SELECT id, client_id, debt_id, amount, currency, payment_type, payment_date, created_at
            FROM payments
            WHERE client_id = ?
            ORDER BY payment_date ASC, id ASC
            """,
            (client_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._map_row(row) for row in rows]

    async def get_by_debt_id(self, debt_id: int) -> list[Payment]:
        async with self._connection.execute(
            """
            SELECT id, client_id, debt_id, amount, currency, payment_type, payment_date, created_at
            FROM payments
            WHERE debt_id = ?
            ORDER BY payment_date ASC, id ASC
            """,
            (debt_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._map_row(row) for row in rows]

    @staticmethod
    def _map_row(row: aiosqlite.Row) -> Payment:
        created_at_raw = row["created_at"]
        created_at = None
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(str(created_at_raw))
            except Exception:
                created_at = None

        return Payment(
            id=row["id"],
            client_id=row["client_id"],
            debt_id=row["debt_id"],
            amount=row["amount"],
            currency=Currency(row["currency"]),
            payment_type=PaymentType(row["payment_type"]),
            payment_date=row["payment_date"],
            created_at=created_at,
        )
