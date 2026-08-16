"""Infrastructure qatlami: DebtRepository SQLite implementatsiyasi."""
from __future__ import annotations

from datetime import datetime

import aiosqlite

from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import Debt, DebtStatus
from bot.domain.repositories.debt_repository import DebtRepository


class SqliteDebtRepository(DebtRepository):
    """DebtRepository ning aiosqlite orqali amalga oshirilishi."""

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self._connection = connection

    async def add(self, debt: Debt) -> Debt:
        cursor = await self._connection.execute(
            """
            INSERT INTO debts (
                client_id,
                debt_date,
                product_name,
                product_quantity,
                product_price,
                currency,
                exchange_exists,
                exchange_product_name,
                exchange_product_price,
                given_money,
                original_debt,
                remaining_debt,
                status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                debt.client_id,
                debt.debt_date,
                debt.product_name,
                debt.product_quantity,
                debt.product_price,
                debt.currency.value if isinstance(debt.currency, Currency) else str(debt.currency),
                1 if debt.exchange_exists else 0,
                debt.exchange_product_name,
                debt.exchange_product_price,
                debt.given_money,
                debt.original_debt,
                debt.remaining_debt,
                debt.status.value if isinstance(debt.status, DebtStatus) else str(debt.status),
            ),
        )
        await self._connection.commit()
        debt_id = cursor.lastrowid
        if debt_id is None:
            raise RuntimeError("Qarz yozuvini saqlashda ID olinmadi.")
        return await self.get_by_id(debt_id)  # type: ignore[return-value]

    async def get_by_id(self, debt_id: int) -> Debt | None:
        async with self._connection.execute(
            """
            SELECT
                id,
                client_id,
                debt_date,
                product_name,
                product_quantity,
                product_price,
                currency,
                exchange_exists,
                exchange_product_name,
                exchange_product_price,
                given_money,
                original_debt,
                remaining_debt,
                status,
                created_at,
                updated_at
            FROM debts
            WHERE id = ?
            """,
            (debt_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return self._map_row(row)

    async def get_all_by_client_id(self, client_id: int) -> list[Debt]:
        async with self._connection.execute(
            """
            SELECT
                id,
                client_id,
                debt_date,
                product_name,
                product_quantity,
                product_price,
                currency,
                exchange_exists,
                exchange_product_name,
                exchange_product_price,
                given_money,
                original_debt,
                remaining_debt,
                status,
                created_at,
                updated_at
            FROM debts
            WHERE client_id = ?
            ORDER BY debt_date ASC, id ASC
            """,
            (client_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._map_row(row) for row in rows]

    async def get_active_by_client_id(self, client_id: int) -> list[Debt]:
        async with self._connection.execute(
            """
            SELECT
                id,
                client_id,
                debt_date,
                product_name,
                product_quantity,
                product_price,
                currency,
                exchange_exists,
                exchange_product_name,
                exchange_product_price,
                given_money,
                original_debt,
                remaining_debt,
                status,
                created_at,
                updated_at
            FROM debts
            WHERE client_id = ? AND remaining_debt > 0 AND status = 'active'
            ORDER BY debt_date ASC, id ASC
            """,
            (client_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._map_row(row) for row in rows]

    async def get_all_active(self) -> list[Debt]:
        async with self._connection.execute(
            """
            SELECT
                id,
                client_id,
                debt_date,
                product_name,
                product_quantity,
                product_price,
                currency,
                exchange_exists,
                exchange_product_name,
                exchange_product_price,
                given_money,
                original_debt,
                remaining_debt,
                status,
                created_at,
                updated_at
            FROM debts
            WHERE remaining_debt > 0 AND status = 'active'
            ORDER BY id ASC
            """
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._map_row(row) for row in rows]

    async def get_active_totals(self) -> dict[int, dict[str, tuple[int, int]]]:
        async with self._connection.execute(
            """
            SELECT client_id, currency, COALESCE(SUM(remaining_debt), 0), COUNT(*)
            FROM debts
            WHERE remaining_debt > 0 AND status = 'active'
            GROUP BY client_id, currency
            """
        ) as cursor:
            rows = await cursor.fetchall()

        totals: dict[int, dict[str, tuple[int, int]]] = {}
        for row in rows:
            totals.setdefault(row[0], {})[row[1]] = (row[2], row[3])
        return totals

    async def update_remaining_debt(
        self,
        debt_id: int,
        remaining_debt: int,
        status: DebtStatus,
    ) -> None:
        await self._connection.execute(
            """
            UPDATE debts
            SET remaining_debt = ?, status = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                remaining_debt,
                status.value if isinstance(status, DebtStatus) else str(status),
                debt_id,
            ),
        )
        await self._connection.commit()

    @staticmethod
    def _map_row(row: aiosqlite.Row) -> Debt:
        created_at_raw = row["created_at"]
        updated_at_raw = row["updated_at"]

        created_at = None
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(str(created_at_raw))
            except Exception:
                created_at = None

        updated_at = None
        if updated_at_raw:
            try:
                updated_at = datetime.fromisoformat(str(updated_at_raw))
            except Exception:
                updated_at = None

        return Debt(
            id=row["id"],
            client_id=row["client_id"],
            debt_date=row["debt_date"],
            product_name=row["product_name"],
            product_quantity=row["product_quantity"],
            product_price=row["product_price"],
            currency=Currency(row["currency"]),
            exchange_exists=bool(row["exchange_exists"]),
            exchange_product_name=row["exchange_product_name"],
            exchange_product_price=row["exchange_product_price"],
            given_money=row["given_money"],
            original_debt=row["original_debt"],
            remaining_debt=row["remaining_debt"],
            status=DebtStatus(row["status"]),
            created_at=created_at,
            updated_at=updated_at,
        )
