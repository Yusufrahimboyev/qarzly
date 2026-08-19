"""Infrastructure qatlami: DebtRepository PostgreSQL implementatsiyasi."""
from __future__ import annotations

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
        currency_val = (
            debt.currency.value
            if isinstance(debt.currency, Currency)
            else str(debt.currency)
        )
        status_val = (
            debt.status.value
            if isinstance(debt.status, DebtStatus)
            else str(debt.status)
        )
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
                currency_val,
                1 if debt.exchange_exists else 0,
                debt.exchange_product_name,
                debt.exchange_product_price,
                debt.given_money,
                debt.original_debt,
                debt.remaining_debt,
                serialize_products_json(list(debt.products)),
                status_val,
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
                " WHERE client_id = $1 AND status != 'trashed' ORDER BY debt_date ASC, id ASC",
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
            client_id = int(row[0])
            currency_code = str(row[1])
            rem_amount = int(row[2])
            count = int(row[3])
            totals.setdefault(client_id, {})[currency_code] = (rem_amount, count)
        return totals

    async def get_client_latest_dates(self) -> dict[int, str]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT client_id, MAX(debt_date)
                FROM debts
                WHERE status != 'trashed'
                GROUP BY client_id
                """
            )
        return {int(row[0]): str(row[1]) for row in rows if row[1]}

    async def update_remaining_debt(
        self,
        debt_id: int,
        remaining_debt: int,
        status: DebtStatus,
    ) -> None:
        status_val = (
            status.value if isinstance(status, DebtStatus) else str(status)
        )
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE debts
                SET remaining_debt = $1, status = $2,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = $3
                """,
                remaining_debt,
                status_val,
                debt_id,
            )

    # ------------------------------------------------------------------
    # Korzina (Trash) operatsiyalari
    # ------------------------------------------------------------------

    async def get_all_paid(self) -> list[Debt]:
        """Barcha yopilgan (paid) qarzlarni qaytaradi."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT{_SELECT_COLS} FROM debts"
                " WHERE status = 'paid'"
                " ORDER BY updated_at DESC, id DESC"
            )
        return [self._map_row(row) for row in rows]

    async def get_paid_by_client_id(self, client_id: int) -> list[Debt]:
        """Berilgan mijozning yopilgan qarzlarini qaytaradi."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT{_SELECT_COLS} FROM debts"
                " WHERE client_id = $1 AND status = 'paid'"
                " ORDER BY updated_at DESC, id DESC",
                client_id,
            )
        return [self._map_row(row) for row in rows]

    async def move_to_trash(self, debt_ids: list[int]) -> int:
        """Ko'rsatilgan IDlardagi yopilgan qarzlarni 'trashed' ga o'tkazadi.

        Faqat status='paid' bo'lgan qarzlar o'tkaziladi (active qarzlarga tegmaydi).
        """
        if not debt_ids:
            return 0
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE debts
                SET status = 'trashed', updated_at = CURRENT_TIMESTAMP
                WHERE id = ANY($1::BIGINT[]) AND status = 'paid'
                """,
                debt_ids,
            )
        # asyncpg "UPDATE N" formatida qaytaradi
        count_str = result.split()[-1] if result else "0"
        return int(count_str)

    async def restore_from_trash(self, debt_ids: list[int]) -> int:
        """Ko'rsatilgan IDlardagi trashed qarzlarni 'paid' statusiga qaytaradi."""
        if not debt_ids:
            return 0
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE debts
                SET status = 'paid', updated_at = CURRENT_TIMESTAMP
                WHERE id = ANY($1::BIGINT[]) AND status = 'trashed'
                """,
                debt_ids,
            )
        count_str = result.split()[-1] if result else "0"
        return int(count_str)

    async def get_all_trashed(self) -> list[Debt]:
        """Barcha korzinaga yuborilgan (trashed) qarzlarni qaytaradi."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"SELECT{_SELECT_COLS} FROM debts"
                " WHERE status = 'trashed'"
                " ORDER BY updated_at DESC, id DESC"
            )
        return [self._map_row(row) for row in rows]

    async def purge_trash(self) -> int:
        """Korzinani butunlay tozalaydi (atomik tranzaksiya).

        1. Trashed qarzlar uchun payments o'chiriladi.
        2. Trashed qarzlar trash arxiv jadvaliga ko'chiriladi (mijoz nomi bilan).
        3. debts jadvalidan o'chiriladi.

        Qaytaradi: o'chirilgan debt yozuvlar soni.
        """
        async with self._pool.acquire() as conn:
            async with conn.transaction():
                # 1. Trashed qarzlarga tegishli payments o'chiriladi
                await conn.execute(
                    """
                    DELETE FROM payments
                    WHERE debt_id IN (
                        SELECT id FROM debts WHERE status = 'trashed'
                    )
                    """
                )

                # 2. Trashed qarzlarni trash arxiviga ko'chirish (clients bilan JOIN)
                await conn.execute(
                    """
                    INSERT INTO trash (
                        original_id, client_id, client_name,
                        product_name, product_price,
                        original_debt, remaining_debt,
                        currency, debt_date, status_before, products_json
                    )
                    SELECT
                        d.id, d.client_id, c.full_name,
                        d.product_name, d.product_price,
                        d.original_debt, d.remaining_debt,
                        d.currency, d.debt_date, d.status, d.products_json
                    FROM debts d
                    JOIN clients c ON c.id = d.client_id
                    WHERE d.status = 'trashed'
                    """
                )

                # 3. debts jadvalidan o'chirish
                result = await conn.execute(
                    "DELETE FROM debts WHERE status = 'trashed'"
                )

                # 4. Qarzi qolmagan (debts jadvalida yo'q) mijozlarni tozalash
                await conn.execute(
                    """
                    DELETE FROM clients
                    WHERE id NOT IN (SELECT DISTINCT client_id FROM debts)
                    """
                )

        count_str = result.split()[-1] if result else "0"
        return int(count_str)


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

