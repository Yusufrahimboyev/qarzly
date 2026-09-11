"""Davr hisoboti (Excel eksporti) hisob-kitoblari uchun unit testlar.

Asosiy invariant — balans tenglamasi:
    davr boshidagi qarz + berilgan - qaytarilgan == davr oxiridagi qarz
"""
from __future__ import annotations

from datetime import date

import pytest

from bot.application.common.period_report import build_period_report
from bot.application.services.debt_service import DebtService
from bot.domain.entities.client import Client
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import Debt, DebtProduct, DebtStatus
from bot.domain.entities.payment import Payment, PaymentType


def _client(cid: int, name: str, phone: str = "+998901112233") -> Client:
    return Client(id=cid, full_name=name, phone=phone)


def _debt(
    *,
    debt_id: int,
    client_id: int,
    debt_date: date,
    original: int,
    remaining: int,
    currency: Currency = Currency.UZS,
    status: DebtStatus = DebtStatus.ACTIVE,
) -> Debt:
    return Debt(
        id=debt_id,
        client_id=client_id,
        debt_date=debt_date,
        product_name="Tovar",
        product_price=original,
        original_debt=original,
        remaining_debt=remaining,
        currency=currency,
        status=status,
    )


def _payment(
    *,
    client_id: int,
    amount: int,
    payment_date: date,
    payment_type: PaymentType = PaymentType.PARTIAL,
    currency: Currency = Currency.UZS,
) -> Payment:
    return Payment(
        client_id=client_id,
        amount=amount,
        currency=currency,
        payment_type=payment_type,
        payment_date=payment_date,
    )


def _build(**overrides):
    """Standart argumentlar bilan hisobot yig'adi."""
    kwargs = {
        "date_from": date(2026, 1, 1),
        "date_to": date(2026, 12, 31),
        "debts": [],
        "payments": [],
        "clients": [],
        "opening_given": {},
        "opening_repaid": {},
        "repaid_by_debt": {},
        "active_totals": {},
    }
    kwargs.update(overrides)
    return build_period_report(**kwargs)


# ==========================================
# 1. Umumiy natija va balans
# ==========================================


def test_opening_debt_is_given_minus_repaid_before_period():
    report = _build(
        opening_given={"UZS": 5_000_000, "USD": 300},
        opening_repaid={"UZS": 2_000_000},
    )
    assert report.opening_debt == {"UZS": 3_000_000, "USD": 300}


def test_balance_equation_holds_per_currency():
    report = _build(
        opening_given={"UZS": 1_000_000},
        opening_repaid={"UZS": 400_000},
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 3, 10),
                original=2_000_000,
                remaining=1_500_000,
            )
        ],
        payments=[_payment(client_id=1, amount=500_000, payment_date=date(2026, 4, 1))],
    )

    # 600 000 (ochilish) + 2 000 000 (berilgan) - 500 000 (qaytgan)
    assert report.opening_debt["UZS"] == 600_000
    assert report.given_total["UZS"] == 2_000_000
    assert report.returned_total["UZS"] == 500_000
    assert report.closing_debt["UZS"] == 2_100_000


def test_initial_payments_are_excluded_from_returned_total():
    """`initial` to'lov `original_debt` dan allaqachon ayrilgan — ikki marta
    hisoblanmasligi kerak."""
    report = _build(
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 5, 1),
                original=700_000,  # 1 000 000 tovar - 300 000 berilgan pul
                remaining=700_000,
            )
        ],
        payments=[
            _payment(
                client_id=1,
                amount=300_000,
                payment_date=date(2026, 5, 1),
                payment_type=PaymentType.INITIAL,
            )
        ],
    )

    assert report.returned_total == {}
    assert report.initial_total == {"UZS": 300_000}
    assert report.closing_debt["UZS"] == 700_000


def test_debt_counts_by_status():
    report = _build(
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 2, 1),
                original=100,
                remaining=100,
            ),
            _debt(
                debt_id=2,
                client_id=1,
                debt_date=date(2026, 2, 2),
                original=100,
                remaining=0,
                status=DebtStatus.PAID,
            ),
            _debt(
                debt_id=3,
                client_id=2,
                debt_date=date(2026, 2, 3),
                original=100,
                remaining=0,
                status=DebtStatus.TRASHED,
            ),
        ],
        repaid_by_debt={2: 100, 3: 100},
    )
    assert (report.open_debts_count, report.closed_debts_count) == (1, 1)
    assert report.trashed_debts_count == 1


def test_debtors_total_counts_clients_with_positive_remaining():
    report = _build(
        active_totals={
            1: {"UZS": (500_000, 1)},
            2: {"USD": (40, 1)},
            3: {"UZS": (0, 0)},
        },
    )
    assert report.debtors_total == 2


# ==========================================
# 2. Valyutalar aralashmaydi
# ==========================================


def test_currencies_are_kept_separate():
    report = _build(
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 6, 1),
                original=1_000_000,
                remaining=1_000_000,
            ),
            _debt(
                debt_id=2,
                client_id=1,
                debt_date=date(2026, 6, 2),
                original=250,
                remaining=250,
                currency=Currency.USD,
            ),
        ],
    )
    assert report.given_total == {"UZS": 1_000_000, "USD": 250}


# ==========================================
# 3. Oyma-oy hisobot
# ==========================================


def test_months_cover_whole_period_even_when_empty():
    report = _build(date_from=date(2026, 1, 15), date_to=date(2026, 4, 5))
    assert [(m.year, m.month) for m in report.months] == [
        (2026, 1),
        (2026, 2),
        (2026, 3),
        (2026, 4),
    ]
    assert report.months[0].label == "Yanvar 2026"


def test_months_span_year_boundary():
    report = _build(date_from=date(2025, 11, 1), date_to=date(2026, 2, 28))
    assert [(m.year, m.month) for m in report.months] == [
        (2025, 11),
        (2025, 12),
        (2026, 1),
        (2026, 2),
    ]


def test_monthly_closing_is_cumulative():
    report = _build(
        opening_given={"UZS": 1_000_000},
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 1, 10),
                original=500_000,
                remaining=500_000,
            ),
            _debt(
                debt_id=2,
                client_id=1,
                debt_date=date(2026, 2, 10),
                original=300_000,
                remaining=300_000,
            ),
        ],
        payments=[_payment(client_id=1, amount=200_000, payment_date=date(2026, 2, 20))],
        date_from=date(2026, 1, 1),
        date_to=date(2026, 3, 31),
    )
    closings = [m.closing.get("UZS", 0) for m in report.months]
    assert closings == [1_500_000, 1_600_000, 1_600_000]

    # Oxirgi oy qoldig'i davr oxiridagi qarzdorlikka teng bo'lishi shart.
    assert closings[-1] == report.closing_debt["UZS"]


# ==========================================
# 4. Mijozlar kesimi
# ==========================================


def test_client_row_given_minus_paid_equals_remaining():
    report = _build(
        clients=[_client(1, "Akmal", "+998901234567")],
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 3, 1),
                original=1_000_000,
                remaining=400_000,
            )
        ],
        repaid_by_debt={1: 600_000},
    )
    (row,) = report.client_rows
    assert row.full_name == "Akmal"
    assert row.phone == "+998901234567"
    assert row.given["UZS"] - row.paid["UZS"] == row.remaining["UZS"]
    assert row.status_label == "Qarzdor"


def test_client_row_is_closed_when_nothing_remains():
    report = _build(
        clients=[_client(1, "Akmal")],
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 3, 1),
                original=500_000,
                remaining=0,
                status=DebtStatus.PAID,
            )
        ],
        repaid_by_debt={1: 500_000},
    )
    (row,) = report.client_rows
    assert row.is_closed
    assert row.status_label == "Yopilgan"


def test_client_row_debt_date_is_latest_in_period():
    report = _build(
        clients=[_client(1, "Akmal")],
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 3, 1),
                original=100,
                remaining=100,
            ),
            _debt(
                debt_id=2,
                client_id=1,
                debt_date=date(2026, 7, 20),
                original=100,
                remaining=100,
            ),
        ],
    )
    (row,) = report.client_rows
    assert row.debt_date == date(2026, 7, 20)


def test_client_with_only_payments_appears_with_cash_paid():
    """Davrda yangi qarz olmagan, faqat eski qarzini to'lagan mijoz ham
    kesimda ko'rinishi kerak."""
    report = _build(
        clients=[_client(1, "Amin aka")],
        payments=[_payment(client_id=1, amount=250_000, payment_date=date(2026, 5, 5))],
    )
    (row,) = report.client_rows
    assert row.given == {}
    assert row.cash_paid == {"UZS": 250_000}
    assert row.debt_date is None


def test_client_rows_sorted_alphabetically():
    report = _build(
        clients=[_client(1, "Zafar"), _client(2, "akmal"), _client(3, "Bobur")],
        debts=[
            _debt(
                debt_id=i,
                client_id=i,
                debt_date=date(2026, 3, 1),
                original=100,
                remaining=100,
            )
            for i in (1, 2, 3)
        ],
    )
    assert [r.full_name for r in report.client_rows] == ["akmal", "Bobur", "Zafar"]


# ==========================================
# 5. Eng katta qarzdorlar
# ==========================================


def test_top_debtors_sorted_desc_and_split_by_currency():
    report = _build(
        clients=[_client(1, "Akmal"), _client(2, "Amin aka"), _client(3, "Akbar")],
        active_totals={
            1: {"USD": (240, 1)},
            2: {"UZS": (25_600_000, 3)},
            3: {"UZS": (100_000, 1)},
        },
    )
    assert [r.full_name for r in report.top_by_uzs] == ["Amin aka", "Akbar"]
    assert [r.full_name for r in report.top_by_usd] == ["Akmal"]
    assert report.top_by_uzs[0].remaining == {"UZS": 25_600_000}


def test_top_debtors_limited_to_ten():
    report = _build(
        clients=[_client(i, f"Mijoz {i}") for i in range(1, 16)],
        active_totals={i: {"UZS": (i * 1000, 1)} for i in range(1, 16)},
    )
    assert len(report.top_by_uzs) == 10
    assert report.top_by_uzs[0].full_name == "Mijoz 15"


# ==========================================
# 6. Service chegarasi
# ==========================================


async def test_service_rejects_reversed_range(client_repo, debt_repo, payment_repo):
    service = DebtService(client_repo, debt_repo, payment_repo)
    with pytest.raises(ValueError, match="Boshlanish sanasi"):
        await service.get_period_report(date(2026, 5, 10), date(2026, 5, 1))


async def test_service_builds_report_from_repositories(
    client_repo,
    debt_repo,
    payment_repo,
):
    service = DebtService(client_repo, debt_repo, payment_repo)
    client = await client_repo.add(Client(full_name="Akmal", phone="+998901234567"))
    assert client.id is not None
    await service.create_debt(
        client_id=client.id,
        debt_date=date(2026, 4, 10),
        products=[DebtProduct(name="Shina", quantity=2, price_per_unit=500_000)],
    )

    report = await service.get_period_report(date(2026, 1, 1), date(2026, 12, 31))

    assert report.given_total == {"UZS": 1_000_000}
    assert report.clients_total == 1
    assert report.debtors_total == 1
    assert len(report.debts) == 1
    assert report.client_names[client.id] == "Akmal"


async def test_service_excludes_debts_outside_range(
    client_repo,
    debt_repo,
    payment_repo,
):
    service = DebtService(client_repo, debt_repo, payment_repo)
    client = await client_repo.add(Client(full_name="Akmal", phone="+998901234567"))
    assert client.id is not None
    for debt_date in (date(2025, 12, 31), date(2026, 1, 1), date(2026, 1, 31)):
        await service.create_debt(
            client_id=client.id,
            debt_date=debt_date,
            products=[DebtProduct(name="Moy", price_per_unit=100_000)],
        )

    report = await service.get_period_report(date(2026, 1, 1), date(2026, 1, 31))

    # Chegara sanalari oraliqqa KIRADI, undan oldingisi ochilish qoldig'iga.
    assert len(report.debts) == 2
    assert report.given_total == {"UZS": 200_000}
    assert report.opening_debt == {"UZS": 100_000}
    assert report.closing_debt == {"UZS": 300_000}


# ==========================================
# 7. Davr oxiridagi holat (regressiya: varaqlar mos kelishi)
# ==========================================


def test_client_rows_use_period_end_not_today():
    """Davrdan KEYIN tushgan to'lov davr oxiridagi qoldiqni kamaytirmasligi kerak.

    Real hodisa: 01.01-19.08 hisoboti chiqarilganda "Mijozlar kesimida"
    ustuni bugungi `remaining_debt` ni olardi va "Umumiy natija" dagi davr
    oxiridagi qarzdorlikdan kam chiqardi.
    """
    report = _build(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 8, 19),
        clients=[_client(1, "Akmal")],
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 3, 1),
                original=1_000_000,
                remaining=0,  # bugun to'liq yopilgan
                status=DebtStatus.PAID,
            )
        ],
        # ...ammo to'lov 19-avgustdan KEYIN tushgan, shuning uchun bu yerda yo'q.
        repaid_by_debt={},
    )

    (row,) = report.client_rows
    assert row.remaining["UZS"] == 1_000_000
    assert row.paid.get("UZS", 0) == 0
    assert row.status_label == "Qarzdor"
    assert report.open_debts_count == 1
    assert report.closed_debts_count == 0


def test_client_remaining_total_matches_closing_debt():
    """Ikki varaqning jamilari bir-biriga to'g'ri kelishi shart."""
    report = _build(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 8, 19),
        clients=[_client(1, "Akmal"), _client(2, "Bobur")],
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 3, 1),
                original=1_000_000,
                remaining=0,
            ),
            _debt(
                debt_id=2,
                client_id=2,
                debt_date=date(2026, 4, 1),
                original=500_000,
                remaining=200_000,
            ),
        ],
        payments=[_payment(client_id=2, amount=300_000, payment_date=date(2026, 5, 1))],
        repaid_by_debt={2: 300_000},
    )

    rows_total = sum(row.remaining.get("UZS", 0) for row in report.client_rows)
    assert rows_total == report.closing_debt["UZS"] == 1_200_000


def test_repaid_before_period_end_counts_as_paid():
    report = _build(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 8, 19),
        clients=[_client(1, "Akmal")],
        debts=[
            _debt(
                debt_id=1,
                client_id=1,
                debt_date=date(2026, 3, 1),
                original=1_000_000,
                remaining=1_000_000,
            )
        ],
        repaid_by_debt={1: 400_000},
    )

    (row,) = report.client_rows
    assert row.paid["UZS"] == 400_000
    assert row.remaining["UZS"] == 600_000

