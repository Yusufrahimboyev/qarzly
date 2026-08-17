"""DebtService biznes mantiqi uchun keng qamrovli testlar."""
from __future__ import annotations

import pytest

from bot.application.services.debt_service import DebtService
from bot.domain.entities.client import Client
from bot.domain.entities.debt import DebtProduct, DebtStatus
from bot.domain.entities.payment import PaymentType
from tests.conftest import (
    FakeClientRepository,
    FakeDebtRepository,
    FakePaymentRepository,
)


@pytest.mark.asyncio
async def test_create_debt_oddiy(
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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
    # FIFO: 1-qarz (1 000 000) to'liq yopiladi, 2-qarzdan 300 000 (qoldiq 1 200 000)
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
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
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


@pytest.mark.asyncio
async def test_create_debt_with_multiple_products(
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
) -> None:
    """Bir qarzda bir nechta tovar bo'lishi mumkin."""
    from bot.domain.entities.debt import DebtProduct

    client = await client_repo.add(Client(full_name="Multiproduct Mijoz", phone="+998907778899"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    products = [
        DebtProduct(name="Shina", quantity=2, price_per_unit=500000),  # 1 000 000
        DebtProduct(name="Akkumulyator", quantity=1, price_per_unit=800000),  # 800 000
        DebtProduct(name="Mator moyi", quantity=3, price_per_unit=50000),  # 150 000
    ]
    # Jami: 1 950 000; exchange: 150 000; berilgan: 300 000 -> qarz: 1 500 000

    debt = await service.create_debt(
        client_id=client.id,
        debt_date="16.08.2026",
        products=products,
        exchange_exists=True,
        exchange_product_name="Eski shina",
        exchange_product_price=150000,
        given_money=300000,
    )

    assert debt.product_price == 1950000  # jami
    assert debt.original_debt == 1500000
    assert debt.remaining_debt == 1500000
    assert debt.product_name == "Shina — 2 ta, Akkumulyator, Mator moyi — 3 ta"
    assert debt.product_quantity == 6  # 2 + 1 + 3
    assert len(debt.products) == 3
    assert debt.products[0].name == "Shina"
    assert debt.products[0].total_price == 1000000
    assert debt.products[1].name == "Akkumulyator"
    assert debt.products[2].name == "Mator moyi"

    # Bazadan o'qib tekshiramiz
    assert debt.id is not None
    from_db = await debt_repo.get_by_id(debt.id)
    assert from_db is not None
    assert len(from_db.products) == 3
    assert from_db.products[0].to_dict() == {
        "name": "Shina", "quantity": 2, "price_per_unit": 500000, "currency": "UZS",
    }

    # Hisobotda ham ko'rinadi
    report = await service.get_client_report(client.id)
    assert len(report.debts) == 1
    assert report.total_product_price == {"UZS": 1950000}
    assert report.total_remaining_debt == {"UZS": 1500000}


@pytest.mark.asyncio
async def test_create_debt_single_product_via_products_param(
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
) -> None:
    """products parametri bilan bitta tovar yuborish ham ishlaydi."""
    from bot.domain.entities.debt import DebtProduct

    client = await client_repo.add(Client(full_name="SingleProd Mijoz", phone="+998906667788"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    products = [DebtProduct(name="Generator", quantity=1, price_per_unit=3500000)]
    debt = await service.create_debt(
        client_id=client.id,
        debt_date="16.08.2026",
        products=products,
    )

    assert debt.product_price == 3500000
    assert debt.remaining_debt == 3500000
    assert debt.product_name == "Generator"
    assert debt.product_quantity == 1
    assert len(debt.products) == 1


@pytest.mark.asyncio
async def test_create_debts_mixed_currencies(
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
) -> None:
    """1-tovar dollar, 2-tovar so'm — ikkita alohida qarz yaratiladi.

    Exchange va berilgan pul faqat o'z valyutasidagi guruhdan chegiriladi.
    """
    from bot.domain.entities.currency import Currency

    client = await client_repo.add(Client(full_name="Aralash Mijoz", phone="+998904443322"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    products = [
        DebtProduct(name="Shina", quantity=1, price_per_unit=120, currency="USD"),  # 120 $
        DebtProduct(name="Moy", quantity=1, price_per_unit=450000, currency="UZS"),  # 450 000
    ]
    # Exchange 20 $ (dollardan), berilgan pul 50 000 so'm (so'mdan)
    # Dollar qarz: 120 - 20 = 100 $; So'm qarz: 450 000 - 50 000 = 400 000

    debts = await service.create_debts(
        client_id=client.id,
        debt_date="17.08.2026",
        products=products,
        exchange_exists=True,
        exchange_product_name="Eski shina",
        exchange_product_price=20,
        exchange_currency=Currency.USD,
        given_money=50000,
        given_currency=Currency.UZS,
    )

    assert len(debts) == 2

    usd_debt = next(d for d in debts if d.currency == Currency.USD)
    uzs_debt = next(d for d in debts if d.currency == Currency.UZS)

    assert usd_debt.product_price == 120
    assert usd_debt.original_debt == 100
    assert usd_debt.remaining_debt == 100
    assert usd_debt.exchange_exists is True
    assert usd_debt.given_money == 0
    assert usd_debt.products[0].currency == "USD"

    assert uzs_debt.product_price == 450000
    assert uzs_debt.original_debt == 400000
    assert uzs_debt.remaining_debt == 400000
    assert uzs_debt.exchange_exists is False  # exchange dollarda edi
    assert uzs_debt.given_money == 50000
    assert uzs_debt.products[0].currency == "UZS"

    # Summary valyutalar bo'yicha alohida ko'rsatadi
    from bot.application.services.client_service import ClientService
    client_service = ClientService(client_repo, debt_repo)
    summaries = await client_service.get_debtor_summaries()
    s = next(x for x in summaries if x.client.id == client.id)
    assert s.remaining_by_currency == {"UZS": 400000, "USD": 100}

    # Dollar qarzini dollarda yopish so'm qarziga ta'sir qilmaydi
    paid_map, summary = await service.pay_full_debt(client.id, "18.08.2026")
    assert paid_map == {"UZS": 400000, "USD": 100}
    assert summary.has_debt is False


@pytest.mark.asyncio
async def test_create_debts_exchange_bigger_than_group_error(
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
) -> None:
    """Exchange o'z valyutasidagi tovarlar jami narxidan katta bo'lsa xatolik."""
    from bot.domain.entities.currency import Currency

    client = await client_repo.add(Client(full_name="Xato Mijoz", phone="+998904443399"))
    assert client.id is not None

    service = DebtService(client_repo, debt_repo, payment_repo)

    products = [
        DebtProduct(name="Shina", quantity=1, price_per_unit=100, currency="USD"),
        DebtProduct(name="Moy", quantity=1, price_per_unit=1000000, currency="UZS"),
    ]

    # 500 $ exchange — dollar tovarlari jami 100 $ dan katta
    with pytest.raises(ValueError, match="katta bo'lishi mumkin emas"):
        await service.create_debts(
            client_id=client.id,
            debt_date="17.08.2026",
            products=products,
            exchange_exists=True,
            exchange_product_name="Eski shina",
            exchange_product_price=500,
            exchange_currency=Currency.USD,
        )
