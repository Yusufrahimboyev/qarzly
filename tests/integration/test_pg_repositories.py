"""Repository, tranzaksiya va pool xulqi uchun integration testlar.

Bu testlar aynan fake repository'lar ushlay olmaydigan xatolarni qamraydi:
atomiklik (C-02), SQL darajasidagi sana saralashi (C-03) va pool
saturation (C-04).
"""
from __future__ import annotations

import asyncio
from datetime import date

import pytest

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.domain.entities.client import Client
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import DebtProduct
from bot.infrastructure.database.connection import Database
from bot.infrastructure.database.repositories.client_repository import (
    PgClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import PgDebtRepository
from bot.infrastructure.database.repositories.payment_repository import (
    PgPaymentRepository,
)
from bot.infrastructure.database.unit_of_work import create_unit_of_work_factory

pytestmark = [pytest.mark.asyncio, pytest.mark.integration]


def _service(database: Database) -> tuple[DebtService, PgDebtRepository, PgClientRepository]:
    pool = database.pool
    clients = PgClientRepository(pool)
    debts = PgDebtRepository(pool)
    payments = PgPaymentRepository(pool)
    service = DebtService(
        clients=clients,
        debts=debts,
        payments=payments,
        uow_factory=create_unit_of_work_factory(pool),
    )
    return service, debts, clients


async def test_schema_uses_real_date_columns(database: Database) -> None:
    """debt_date va payment_date ustunlari DATE bo'lishi kerak."""
    rows = await database.pool.fetch(
        """
        SELECT table_name, column_name, data_type
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND column_name IN ('debt_date', 'payment_date')
        """
    )
    assert rows
    assert all(row["data_type"] == "date" for row in rows)


async def test_fifo_order_comes_from_sql(database: Database) -> None:
    """SQL saralashi sana bo'yicha xronologik bo'lishi kerak (C-03)."""
    service, debts, clients = _service(database)
    client = await clients.add(Client(full_name="FIFO", phone="+998900000001"))
    assert client.id is not None

    for raw_date in ("01.02.2026", "15.12.2025", "31.01.2026"):
        await service.create_debt(
            client.id, raw_date, product_name="Tovar", product_price=100000
        )

    active = await debts.get_active_by_client_id(client.id)
    assert [d.debt_date for d in active] == [
        date(2025, 12, 15),
        date(2026, 1, 31),
        date(2026, 2, 1),
    ]

    # To'lov eng eski qarzga tushadi
    await service.pay_partial_debt(client.id, 100000, "05.02.2026")
    active_after = await debts.get_active_by_client_id(client.id)
    assert [d.debt_date for d in active_after] == [date(2026, 1, 31), date(2026, 2, 1)]


async def test_failed_use_case_rolls_back_everything(database: Database) -> None:
    """Oraliq xatoda qarz ham, to'lov ham saqlanmasligi kerak (C-02)."""
    service, debts, clients = _service(database)
    client = await clients.add(Client(full_name="Rollback", phone="+998900000002"))
    assert client.id is not None

    products = [
        DebtProduct(name="Moy", price_per_unit=500000, currency=Currency.UZS),
        # Ikkinchi guruh xato beradi: USD guruhida 100 $ tovar bor, 500 $ berilgan
        DebtProduct(name="Shina", price_per_unit=100, currency=Currency.USD),
    ]
    with pytest.raises(ValueError):
        await service.create_debts(
            client_id=client.id,
            debt_date="16.08.2026",
            products=products,
            given_money=500,
            given_currency=Currency.USD,
        )

    assert await debts.get_all_by_client_id(client.id) == []
    payments = await PgPaymentRepository(database.pool).get_by_client_id(client.id)
    assert payments == []


async def test_debt_and_initial_payment_are_atomic(database: Database) -> None:
    """Qarz va dastlabki to'lov bitta tranzaksiyada yoziladi (C-02)."""
    service, debts, clients = _service(database)
    client = await clients.add(Client(full_name="Atomik", phone="+998900000003"))
    assert client.id is not None

    debt = await service.create_debt(
        client.id,
        "16.08.2026",
        product_name="Moy",
        product_price=1000000,
        given_money=400000,
    )
    payments = await PgPaymentRepository(database.pool).get_by_client_id(client.id)

    assert debt.remaining_debt == 600000
    assert len(payments) == 1
    assert payments[0].debt_id == debt.id
    assert payments[0].payment_date == date(2026, 8, 16)


async def test_concurrent_partial_payments_do_not_overdraw(database: Database) -> None:
    """Parallel to'lovlar qarzni manfiyga tushirmasligi kerak (C-02, FOR UPDATE)."""
    service, debts, clients = _service(database)
    client = await clients.add(Client(full_name="Parallel", phone="+998900000004"))
    assert client.id is not None

    await service.create_debt(
        client.id, "16.08.2026", product_name="Moy", product_price=100000
    )

    results = await asyncio.gather(
        *[
            service.pay_partial_debt(client.id, 100000, "17.08.2026")
            for _ in range(5)
        ],
        return_exceptions=True,
    )

    succeeded = [r for r in results if not isinstance(r, BaseException)]
    assert len(succeeded) == 1

    remaining = await debts.get_active_by_client_id(client.id)
    assert remaining == []


async def test_concurrent_inserts_do_not_exhaust_pool(database: Database) -> None:
    """Ichma-ich `pool.acquire()` bo'lmasligi kerak (C-04).

    Pool max_size = 5; 20 ta parallel insert deadlock bermasdan tugashi kerak.
    """
    service, debts, clients = _service(database)
    client = await clients.add(Client(full_name="Pool", phone="+998900000005"))
    assert client.id is not None

    client_id = client.id

    async def create(idx: int) -> None:
        await service.create_debt(
            client_id, "16.08.2026", product_name=f"Tovar {idx}", product_price=1000
        )

    await asyncio.wait_for(
        asyncio.gather(*[create(i) for i in range(20)]),
        timeout=30,
    )
    assert len(await debts.get_all_by_client_id(client.id)) == 20


async def test_duplicate_phone_does_not_create_duplicate_client(
    database: Database,
) -> None:
    """Parallel so'rovlar bir xil telefon bilan bitta mijoz yaratadi (M-02)."""
    clients = PgClientRepository(database.pool)
    debts = PgDebtRepository(database.pool)
    service = ClientService(clients, debts)

    results = await asyncio.gather(
        *[service.get_or_create("Bir Mijoz", "+998900000006") for _ in range(10)]
    )
    ids = {client.id for client, _ in results}
    assert len(ids) == 1


async def test_purge_trash_archives_payments(database: Database) -> None:
    """Korzina tozalanganda to'lov tarixi arxivda qolishi kerak (M-08)."""
    service, debts, clients = _service(database)
    client = await clients.add(Client(full_name="Arxiv", phone="+998900000007"))
    assert client.id is not None

    debt = await service.create_debt(
        client.id, "16.08.2026", product_name="Moy", product_price=100000
    )
    await service.pay_full_debt(client.id, "17.08.2026")
    assert debt.id is not None
    await service.move_to_trash([debt.id])

    deleted = await service.purge_trash(actor_id=42)
    assert deleted == 1

    archived = await database.pool.fetchval(
        "SELECT COUNT(*) FROM trash_payments WHERE client_id = $1", client.id
    )
    assert archived == 1
    archived_debt = await database.pool.fetchval(
        "SELECT COUNT(*) FROM trash WHERE original_id = $1", debt.id
    )
    assert archived_debt == 1


async def test_date_range_includes_both_boundaries(database: Database) -> None:
    """BETWEEN chegaralari SQL darajasida ham inklyuziv bo'lishi kerak."""
    service, debts, clients = _service(database)
    client = await clients.add(Client(full_name="Akmal", phone="+998901234567"))
    assert client.id is not None

    for debt_date in (
        date(2025, 12, 31),
        date(2026, 1, 1),
        date(2026, 1, 15),
        date(2026, 1, 31),
        date(2026, 2, 1),
    ):
        await service.create_debt(
            client_id=client.id,
            debt_date=debt_date,
            products=[DebtProduct(name="Moy", price_per_unit=100_000)],
        )

    rows = await debts.get_by_date_range(date(2026, 1, 1), date(2026, 1, 31))

    assert [d.debt_date for d in rows] == [
        date(2026, 1, 1),
        date(2026, 1, 15),
        date(2026, 1, 31),
    ]


async def test_opening_aggregates_exclude_period_itself(database: Database) -> None:
    """Ochilish qoldig'i faqat davrdan OLDINGI yozuvlarni qamrashi kerak."""
    service, debts, clients = _service(database)
    client = await clients.add(Client(full_name="Akmal", phone="+998901234567"))
    assert client.id is not None

    await service.create_debt(
        client_id=client.id,
        debt_date=date(2025, 6, 1),
        products=[DebtProduct(name="Shina", price_per_unit=1_000_000)],
    )
    await service.create_debt(
        client_id=client.id,
        debt_date=date(2026, 1, 5),
        products=[DebtProduct(name="Moy", price_per_unit=400_000)],
    )
    await service.pay_partial_debt(
        client_id=client.id,
        amount=300_000,
        currency=Currency.UZS,
        payment_date=date(2025, 8, 1),
    )

    opening_given = await debts.sum_original_before(date(2026, 1, 1))
    opening_repaid = await PgPaymentRepository(
        database.pool
    ).sum_repayments_before(date(2026, 1, 1))

    assert opening_given == {"UZS": 1_000_000}
    assert opening_repaid == {"UZS": 300_000}


async def test_initial_payments_excluded_from_repayment_sum(
    database: Database,
) -> None:
    """`initial` to'lov qaytarilgan pul yig'indisiga kirmasligi kerak."""
    service, _, clients = _service(database)
    payments = PgPaymentRepository(database.pool)
    client = await clients.add(Client(full_name="Akmal", phone="+998901234567"))
    assert client.id is not None

    # given_money=200 000 -> 'initial' to'lov yoziladi.
    await service.create_debt(
        client_id=client.id,
        debt_date=date(2025, 3, 1),
        products=[DebtProduct(name="Shina", price_per_unit=1_000_000)],
        given_money=200_000,
    )

    assert await payments.sum_repayments_before(date(2026, 1, 1)) == {}

    rows = await payments.get_by_date_range(date(2025, 1, 1), date(2025, 12, 31))
    assert [p.payment_type.value for p in rows] == ["initial"]

