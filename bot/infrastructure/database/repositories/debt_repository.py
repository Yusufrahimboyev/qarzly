"""Infrastructure qatlami: DebtRepository PostgreSQL implementatsiyasi."""
from __future__ import annotations

from datetime import date

import asyncpg

from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import Debt, DebtStatus
from bot.domain.repositories.debt_repository import DebtRepository
from bot.infrastructure.database.mappers.products import (
    parse_products_json,
    serialize_products_json,
)
from bot.infrastructure.database.repositories.executor import Executor, transaction_scope

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
    """DebtRepository ning asyncpg orqali amalga oshirilishi.

    Executor sifatida pool ham, tranzaksiya ichidagi connection ham berilishi
    mumkin — shu sababli repository hech qachon o'zi yangi connection
    "acquire" qilmaydi. Bu pool deadlock'ining oldini oladi va bir nechta
    yozuvni bitta tranzaksiyada bajarish imkonini beradi.
    """

    def __init__(self, executor: Executor) -> None:
        self._db = executor

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
        row = await self._db.fetchrow(
            f"""
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
            RETURNING {_SELECT_COLS}
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
            serialize_products_json(debt.products),
            status_val,
        )
        if row is None:
            raise RuntimeError("Qarz yozuvi saqlanmadi.")
        return self._map_row(row)

    async def get_by_id(self, debt_id: int) -> Debt | None:
        row = await self._db.fetchrow(
            f"SELECT{_SELECT_COLS} FROM debts WHERE id = $1",
            debt_id,
        )
        if row is None:
            return None
        return self._map_row(row)

    async def get_all_by_client_id(self, client_id: int) -> list[Debt]:
        rows = await self._db.fetch(
            f"SELECT{_SELECT_COLS} FROM debts"
            " WHERE client_id = $1 AND status != 'trashed'"
            " ORDER BY debt_date ASC, id ASC",
            client_id,
        )
        return [self._map_row(row) for row in rows]

    async def get_active_by_client_id(
        self,
        client_id: int,
        *,
        for_update: bool = False,
    ) -> list[Debt]:
        # FOR UPDATE — to'lov taqsimoti davomida shu qatorlarni boshqa
        # tranzaksiya o'zgartira olmaydi (lost update va ikki karra to'lovdan himoya).
        lock_clause = " FOR UPDATE" if for_update else ""
        rows = await self._db.fetch(
            f"SELECT{_SELECT_COLS} FROM debts"
            " WHERE client_id = $1 AND remaining_debt > 0"
            " AND status = 'active' ORDER BY debt_date ASC, id ASC"
            f"{lock_clause}",
            client_id,
        )
        return [self._map_row(row) for row in rows]

    async def get_all_active(self) -> list[Debt]:
        rows = await self._db.fetch(
            f"SELECT{_SELECT_COLS} FROM debts"
            " WHERE remaining_debt > 0 AND status = 'active'"
            " ORDER BY id ASC"
        )
        return [self._map_row(row) for row in rows]

    async def get_active_totals(self) -> dict[int, dict[str, tuple[int, int]]]:
        rows = await self._db.fetch(
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

    async def get_by_date_range(self, date_from: date, date_to: date) -> list[Debt]:
        rows = await self._db.fetch(
            f"SELECT{_SELECT_COLS} FROM debts"
            " WHERE debt_date BETWEEN $1 AND $2"
            " ORDER BY debt_date ASC, id ASC",
            date_from,
            date_to,
        )
        return [self._map_row(row) for row in rows]

    async def sum_original_before(self, before: date) -> dict[str, int]:
        rows = await self._db.fetch(
            """
            SELECT currency, COALESCE(SUM(original_debt), 0)
            FROM debts
            WHERE debt_date < $1
            GROUP BY currency
            """,
            before,
        )
        return {str(row[0]): int(row[1]) for row in rows}

    async def get_client_latest_dates(self) -> dict[int, date]:
        rows = await self._db.fetch(
            """
            SELECT client_id, MAX(debt_date)
            FROM debts
            WHERE status != 'trashed'
            GROUP BY client_id
            """
        )
        return {int(row[0]): row[1] for row in rows if row[1] is not None}

    async def get_client_ids_with_paid_debts(self) -> set[int]:
        rows = await self._db.fetch(
            "SELECT DISTINCT client_id FROM debts WHERE status = 'paid'"
        )
        return {int(row[0]) for row in rows}

    async def update_remaining_debt(
        self,
        debt_id: int,
        remaining_debt: int,
        status: DebtStatus,
    ) -> None:
        status_val = (
            status.value if isinstance(status, DebtStatus) else str(status)
        )
        await self._db.execute(
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

    async def get_all_paid(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Debt]:
        """Barcha yopilgan (paid) qarzlarni qaytaradi."""
        rows = await self._db.fetch(
            f"SELECT{_SELECT_COLS} FROM debts"
            " WHERE status = 'paid'"
            " ORDER BY updated_at DESC, id DESC"
            " LIMIT $1 OFFSET $2",
            limit,
            max(offset, 0),
        )
        return [self._map_row(row) for row in rows]

    async def get_paid_by_client_id(self, client_id: int) -> list[Debt]:
        """Berilgan mijozning yopilgan qarzlarini qaytaradi."""
        rows = await self._db.fetch(
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
        result = await self._db.execute(
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
        result = await self._db.execute(
            """
            UPDATE debts
            SET status = 'paid', updated_at = CURRENT_TIMESTAMP
            WHERE id = ANY($1::BIGINT[]) AND status = 'trashed'
            """,
            debt_ids,
        )
        count_str = result.split()[-1] if result else "0"
        return int(count_str)

    async def get_all_trashed(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Debt]:
        """Barcha korzinaga yuborilgan (trashed) qarzlarni qaytaradi."""
        rows = await self._db.fetch(
            f"SELECT{_SELECT_COLS} FROM debts"
            " WHERE status = 'trashed'"
            " ORDER BY updated_at DESC, id DESC"
            " LIMIT $1 OFFSET $2",
            limit,
            max(offset, 0),
        )
        return [self._map_row(row) for row in rows]

    async def purge_trash(self, actor_id: int | None = None) -> int:
        """Korzinani butunlay tozalaydi (atomik tranzaksiya).

        1. Trashed qarzlarning to'lov tarixi `trash_payments` arxiviga ko'chiriladi.
        2. Trashed qarzlar `trash` arxiv jadvaliga ko'chiriladi (mijoz nomi bilan).
        3. debts jadvalidan o'chiriladi.

        Moliyaviy audit trail append-only: payments qatorlari arxivga
        ko'chirilgandan keyingina o'chiriladi.

        Qaytaradi: o'chirilgan debt yozuvlar soni.
        """
        async with self._transaction() as conn:
            # 1. To'lov tarixini arxivlash (audit trail yo'qolmasligi uchun)
            await conn.execute(
                """
                INSERT INTO trash_payments (
                    original_id, original_debt_id, client_id, amount, currency,
                    payment_type, payment_date, paid_created_at, deleted_by
                )
                SELECT p.id, p.debt_id, p.client_id, p.amount, p.currency,
                       p.payment_type, p.payment_date, p.created_at, $1
                FROM payments p
                JOIN debts d ON d.id = p.debt_id
                WHERE d.status = 'trashed'
                """,
                actor_id,
            )

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
                    currency, debt_date, status_before, products_json, deleted_by
                )
                SELECT
                    d.id, d.client_id, c.full_name,
                    d.product_name, d.product_price,
                    d.original_debt, d.remaining_debt,
                    d.currency, d.debt_date, d.status, d.products_json, $1
                FROM debts d
                JOIN clients c ON c.id = d.client_id
                WHERE d.status = 'trashed'
                """,
                actor_id,
            )

            # 3. debts jadvalidan o'chirish
            result = await conn.execute(
                "DELETE FROM debts WHERE status = 'trashed'"
            )

            # 4. Qarzi ham, to'lovi ham qolmagan mijozlarni tozalash
            await conn.execute(
                """
                DELETE FROM clients c
                WHERE NOT EXISTS (SELECT 1 FROM debts d WHERE d.client_id = c.id)
                  AND NOT EXISTS (SELECT 1 FROM payments p WHERE p.client_id = c.id)
                """
            )

        count_str = result.split()[-1] if result else "0"
        return int(count_str)

    def _transaction(self):
        """Purge uchun tranzaksiya konteksti (pool yoki mavjud connection)."""
        return transaction_scope(self._db)

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
