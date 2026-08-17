"""Infrastructure qatlami: DebtRepository PostgreSQL implementatsiyasi."""
from __future__ import annotations

from datetime import datetime

import asyncpg

from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import (
    Debt,
    DebtStatus,
    parse_products_json,
    serialize_products_json,
)
from bot.domain.repositories.debt_repository import DebtRepository

_SELECT_COLS = """
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
    products_json,
    status,
    created_at,
    updated_at
"""


class PgDebtRepository(DebtRepository):
    """DebtRepository ning asyncpg orqali amalga oshirilishi."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, debt: Debt) -> Debt:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
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
                    products_json,
                    status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
                RETURNING id
                """,
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
                serialize_products_json(list(debt.products)),
                debt.status.value if isinstance(debt.status, DebtStatus) else str(debt.status),
            )
            debt_id = row["id"] if row else None
            if debt_id is None:
                raise RuntimeError("Qarz yozuvini saqlashda ID olinmadi.")
            return await self.get_by_id(debt_id)  # type: ignore[return-value]

    async def get_by_id(self, debt_id: int) -> Debt | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                f"SELECT{_SELECT_COLS} FROM debts WHERE id = $1",
                debt_id,
            )

        if row is None:
            return None
        return self._map_row(row)

    async def get_all_by_client_id(self, client_id: int) -> list[Debt]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT{_SELECT_COLS} FROM debts"
                " WHERE client_id = $1 ORDER BY debt_date ASC, id ASC",
                client_id,
            )

        return [self._map_row(row) for row in rows]

    async def get_active_by_client_id(self, client_id: int) -> list[Debt]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT{_SELECT_COLS} FROM debts"
                " WHERE client_id = $1 AND remaining_debt > 0"
                " AND status = 'active' ORDER BY debt_date ASC, id ASC",
                client_id,
            )

        return [self._map_row(row) for row in rows]

    async def get_all_active(self) -> list[Debt]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT{_SELECT_COLS} FROM debts"
                " WHERE remaining_debt > 0 AND status = 'active'"
                " ORDER BY id ASC"
            )

        return [self._map_row(row) for row in rows]

    async def get_active_totals(self) -> dict[int, dict[str, tuple[int, int]]]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT client_id, currency,
                       COALESCE(SUM(remaining_debt), 0), COUNT(*)
                FROM debts
                WHERE remaining_debt > 0 AND status = 'active'
                GROUP BY client_id, currency
                """
            )

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
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE debts
                SET remaining_debt = $1, status = $2,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $3
                """,
                remaining_debt,
                status.value if isinstance(status, DebtStatus) else str(status),
                debt_id,
            )

    @staticmethod
    def _map_row(row: asyncpg.Record) -> Debt:
        products = parse_products_json(row["products_json"])

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
            products=tuple(products),
            status=DebtStatus(row["status"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
