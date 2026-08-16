"""DebtService biznes mantiqi uchun keng qamrovli testlar."""
from __future__ import annotations

import pytest

from bot.application.services.debt_service import DebtService
from bot.domain.entities.client import Client
from bot.domain.entities.debt import DebtStatus
from bot.domain.entities.payment import PaymentType
from bot.infrastructure.database.repositories.client_repository import (
    SqliteClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import (
    SqliteDebtRepository,
)
from bot.infrastructure.database.repositories.payment_repository import (
    SqlitePaymentRepository,
)


@pytest.mark.asyncio
async def test_create_debt_oddiy(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    client = await client_repo.add(Client(full_name="Aliyev Anvar", phone="+998901234567"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    # 2 500 000 so'mlik Shina (exchange yo'q, berilgan pul yo'q)
    debt = await service.create_debt(
        client_id=client.id,
        debt_date="16.08.2026",
        product_name="Shina",
        product_price=2500000,
    )

    assert debt.original_debt == 2500000
    assert debt.remaining_debt == 2500000
    assert debt.status == DebtStatus.ACTIVE
    assert debt.exchange_exists is False
    assert debt.product_quantity == 1


@pytest.mark.asyncio
async def test_create_debt_with_quantity(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    """Miqdor: jami narx = bitta narx × miqdor."""
    client = await client_repo.add(Client(full_name="Aliyev Anvar", phone="+998901234567"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    # 3 dona × 500 000 = 1 500 000; exchange 200 000; berilgan pul 100 000
    # Qarz: 1 500 000 - 200 000 - 100 000 = 1 200 000
    debt = await service.create_debt(
        client_id=client.id,
        debt_date="16.08.2026",
        product_name="Shina",
        product_price=500000,
        product_quantity=3,
        exchange_exists=True,
        exchange_product_name="Eski shina",
        exchange_product_price=200000,
        given_money=100000,
    )

    assert debt.product_quantity == 3
    assert debt.product_price == 1500000
    assert debt.original_debt == 1200000
    assert debt.remaining_debt == 1200000


@pytest.mark.asyncio
async def test_create_debt_with_exchange_and_given_money(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    client = await client_repo.add(Client(full_name="Aliyev Anvar", phone="+998901234567"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    # Asosiy tovar: 2 500 000
    # Exchange: 800 000
    # Berilgan pul: 200 000
    # Qarz: 2 500 000 - 800 000 - 200 000 = 1 500 000
    debt = await service.create_debt(
        client_id=client.id,
        debt_date="16.08.2026",
        product_name="Shina",
        product_price=2500000,
        exchange_exists=True,
        exchange_product_name="Akkumulyator",
        exchange_product_price=800000,
        given_money=200000,
    )

    assert debt.original_debt == 1500000
    assert debt.remaining_debt == 1500000
    assert debt.status == DebtStatus.ACTIVE
    assert debt.exchange_exists is True

    # Dastlabki to'lov to'lovlar tarixiga yozilgan bo'lishi kerak
    payments = await payment_repo.get_by_client_id(client.id)
    assert len(payments) == 1
    assert payments[0].amount == 200000
    assert payments[0].payment_type == PaymentType.INITIAL


@pytest.mark.asyncio
async def test_create_debt_validation_errors(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    client = await client_repo.add(Client(full_name="Aliyev Anvar", phone="+998901234567"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    # Tovar narxi 0 bo'lsa
    with pytest.raises(ValueError, match="0 dan katta bo'lishi shart"):
        await service.create_debt(
            client_id=client.id,
            debt_date="16.08.2026",
            product_name="Shina",
            product_price=0,
        )

    # Chegirmalar tovar narxidan oshib ketsa
    with pytest.raises(ValueError, match="katta bo'lishi mumkin emas"):
        await service.create_debt(
            client_id=client.id,
            debt_date="16.08.2026",
            product_name="Shina",
            product_price=1000000,
            exchange_exists=True,
            exchange_product_price=800000,
            given_money=300000,  # 800k + 300k = 1.1M > 1M
        )

    # Miqdor 0 bo'lsa
    with pytest.raises(ValueError, match="Miqdor"):
        await service.create_debt(
            client_id=client.id,
            debt_date="16.08.2026",
            product_name="Shina",
            product_price=1000000,
            product_quantity=0,
        )


@pytest.mark.asyncio
async def test_pay_full_debt(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    client = await client_repo.add(Client(full_name="Karimov Bekzod", phone="+998909876543"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    # 2 ta qarz kiritamiz: 1 500 000 va 500 000
    await service.create_debt(
        client_id=client.id,
        debt_date="01.08.2026",
        product_name="Shina",
        product_price=1500000,
    )
    await service.create_debt(
        client_id=client.id,
        debt_date="05.08.2026",
        product_name="Mator moyi",
        product_price=500000,
    )

    # To'liq yopamiz (jami 2 000 000)
    total_paid, summary = await service.pay_full_debt(client.id, "16.08.2026")

    assert total_paid == {"UZS": 2000000}
    assert summary.has_debt is False

    # Bazadagi qarzlarni tekshiramiz
    debts = await debt_repo.get_all_by_client_id(client.id)
    assert all(d.status == DebtStatus.PAID for d in debts)
    assert all(d.remaining_debt == 0 for d in debts)


@pytest.mark.asyncio
async def test_pay_partial_debt_fifo(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    client = await client_repo.add(Client(full_name="Rasulov Sardor", phone="+998901112233"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    # 1-qarz: 1 000 000
    # 2-qarz: 1 500 000
    # Jami qarz: 2 500 000
    d1 = await service.create_debt(
        client_id=client.id,
        debt_date="01.08.2026",
        product_name="Akkumulyator",
        product_price=1000000,
    )
    d2 = await service.create_debt(
        client_id=client.id,
        debt_date="05.08.2026",
        product_name="Shina",
        product_price=1500000,
    )

    # Qisman to'lov: 1 300 000
    # FIFO bo'yicha: 1-qarz (1 000 000) to'liq yopiladi (qoldiq 0), 2-qarzdan 300 000 to'lanadi (qoldiq 1 200 000)
    paid_amount, new_remaining, summary = await service.pay_partial_debt(
        client_id=client.id,
        amount=1300000,
        payment_date="16.08.2026",
    )

    assert paid_amount == 1300000
    assert new_remaining == 1200000
    assert summary.remaining_by_currency == {"UZS": 1200000}

    d1_updated = await debt_repo.get_by_id(d1.id)  # type: ignore[arg-type]
    d2_updated = await debt_repo.get_by_id(d2.id)  # type: ignore[arg-type]

    assert d1_updated is not None and d1_updated.remaining_debt == 0
    assert d1_updated.status == DebtStatus.PAID

    assert d2_updated is not None and d2_updated.remaining_debt == 1200000
    assert d2_updated.status == DebtStatus.ACTIVE


@pytest.mark.asyncio
async def test_pay_partial_debt_overpayment_error(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    client = await client_repo.add(Client(full_name="Eshmat", phone="+998901234500"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)
    await service.create_debt(
        client_id=client.id,
        debt_date="10.08.2026",
        product_name="Moy",
        product_price=500000,
    )

    # 500 000 qarzga 700 000 to'lashga urinsa xatolik chiqishi kerak
    with pytest.raises(ValueError, match="katta bo'lishi mumkin emas"):
        await service.pay_partial_debt(
            client_id=client.id,
            amount=700000,
            payment_date="16.08.2026",
        )


@pytest.mark.asyncio
async def test_get_client_report(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    client = await client_repo.add(Client(full_name="Toshmat", phone="+998901234599"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    # 1-operatsiya: 2 000 000 shina, exchange 500 000, pul berdi 300 000 -> qarz 1 200 000
    await service.create_debt(
        client_id=client.id,
        debt_date="01.08.2026",
        product_name="Shina",
        product_price=2000000,
        exchange_exists=True,
        exchange_product_name="Eski shina",
        exchange_product_price=500000,
        given_money=300000,
    )

    # 2-operatsiya: 1 000 000 akkumulyator -> qarz 1 000 000
    await service.create_debt(
        client_id=client.id,
        debt_date="05.08.2026",
        product_name="Akkumulyator",
        product_price=1000000,
    )

    # Keyin 700 000 to'ladi
    await service.pay_partial_debt(client.id, 700000, "10.08.2026")

    report = await service.get_client_report(client.id)

    assert report.total_product_price == {"UZS": 3000000}
    assert report.total_exchange_price == {"UZS": 500000}
    assert report.total_given_money == {"UZS": 300000}
    assert report.total_original_debt == {"UZS": 2200000}
    assert report.total_paid_after == {"UZS": 700000}
    assert report.total_remaining_debt == {"UZS": 1500000}
    assert len(report.debts) == 2
    assert len(report.payments) == 2  # 1 initial + 1 partial


@pytest.mark.asyncio
async def test_currency_usd_debt_and_per_currency_totals(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    """Dollar qarzi so'm qarzidan alohida saqlanadi va yopiladi."""
    from bot.domain.entities.currency import Currency

    client = await client_repo.add(Client(full_name="Valyuta Mijoz", phone="+998905550011"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    # So'mda: 1 000 000; Dollarda: 2 dona × 100 $ = 200 $
    await service.create_debt(
        client_id=client.id,
        debt_date="01.08.2026",
        product_name="Moy",
        product_price=1000000,
    )
    usd_debt = await service.create_debt(
        client_id=client.id,
        debt_date="02.08.2026",
        product_name="Shina",
        product_price=100,
        product_quantity=2,
        currency=Currency.USD,
    )
    assert usd_debt.currency == Currency.USD
    assert usd_debt.product_price == 200
    assert usd_debt.remaining_debt == 200

    # Dollarda qisman to'lov: 50 $ — faqat dollar qarziga ta'sir qiladi
    paid, new_remaining_usd, summary = await service.pay_partial_debt(
        client_id=client.id,
        amount=50,
        payment_date="10.08.2026",
        currency=Currency.USD,
    )
    assert paid == 50
    assert new_remaining_usd == 150
    assert summary.remaining_by_currency == {"UZS": 1000000, "USD": 150}

    # So'm qarzi o'zgarmagan
    debts = await debt_repo.get_all_by_client_id(client.id)
    uzs_debts = [d for d in debts if d.currency == Currency.UZS]
    assert all(d.remaining_debt == 1000000 for d in uzs_debts)

    # Dollarda yo'q bo'lgan summani oshirib yuborsa xatolik
    with pytest.raises(ValueError, match="katta bo'lishi mumkin emas"):
        await service.pay_partial_debt(
            client_id=client.id,
            amount=151,
            payment_date="10.08.2026",
            currency=Currency.USD,
        )

    # To'liq yopish — ikkala valyutani ham yopadi
    paid_map, summary = await service.pay_full_debt(client.id, "11.08.2026")
    assert paid_map == {"UZS": 1000000, "USD": 150}
    assert summary.has_debt is False

    report = await service.get_client_report(client.id)
    assert report.total_remaining_debt == {}
    assert report.total_product_price == {"UZS": 1000000, "USD": 200}
    assert report.total_paid_after == {"UZS": 1000000, "USD": 200}
