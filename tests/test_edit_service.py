"""EditService: mijoz va qarzni tahrirlash, qoldiqni qayta hisoblash, tarix."""
from __future__ import annotations

from datetime import date

import pytest

from bot.application.services.debt_service import DebtService
from bot.application.services.edit_service import EditService
from bot.domain.entities.client import Client
from bot.domain.entities.debt import DebtProduct, DebtStatus
from bot.domain.entities.payment import PaymentType
from tests.conftest import (
    FakeClientRepository,
    FakeEditLogRepository,
)


@pytest.fixture
def edit_log() -> FakeEditLogRepository:
    return FakeEditLogRepository()


@pytest.fixture
def services(client_repo, debt_repo, payment_repo, edit_log):
    return (
        DebtService(client_repo, debt_repo, payment_repo),
        EditService(client_repo, debt_repo, payment_repo, edit_log),
    )


async def _client(repo: FakeClientRepository, phone: str = "+998901234567") -> int:
    client = await repo.add(Client(full_name="Aliyev Anvar", phone=phone))
    assert client.id is not None
    return client.id


async def test_update_client_logs_changes(client_repo, services, edit_log) -> None:
    _debts, edits = services
    client_id = await _client(client_repo)

    updated = await edits.update_client(
        client_id, "  Aliyev  Anvarjon ", "+998 93 111 22 33", actor_id=7, actor_name="Yusuf"
    )

    assert updated.full_name == "Aliyev Anvarjon"
    assert updated.phone == "+998931112233"
    [record] = await edits.get_edits(client_id)
    assert record.debt_id is None and record.edited_by == 7 and record.edited_by_name == "Yusuf"
    assert [(c.field, c.old, c.new) for c in record.changes] == [
        ("full_name", "Aliyev Anvar", "Aliyev Anvarjon"),
        ("phone", "+998901234567", "+998931112233"),
    ]


async def test_update_client_rejects_phone_of_other_client(client_repo, services) -> None:
    _debts, edits = services
    client_id = await _client(client_repo)
    await _client(client_repo, phone="+998931112233")

    with pytest.raises(ValueError, match="boshqa mijozga"):
        await edits.update_client(client_id, "Aliyev Anvar", "+998931112233")


async def test_update_client_without_changes_is_rejected(client_repo, services, edit_log) -> None:
    _debts, edits = services
    client_id = await _client(client_repo)

    with pytest.raises(ValueError, match="o'zgarmadi"):
        await edits.update_client(client_id, "Aliyev Anvar", "+998901234567")
    assert edit_log.records == []


async def test_update_debt_recalculates_remaining_after_payment(
    client_repo, debt_repo, services
) -> None:
    debts, edits = services
    client_id = await _client(client_repo)
    debt = await debts.create_debt(
        client_id=client_id, debt_date="16.08.2026", product_name="Shina", product_price=1_000_000
    )
    await debts.pay_partial_debt(client_id, 300_000, "17.08.2026")

    saved = await edits.update_debt(
        debt.id, "16.08.2026", [DebtProduct(name="Shina", quantity=2, price_per_unit=600_000)]
    )

    assert saved.original_debt == 1_200_000
    assert saved.remaining_debt == 900_000  # 1 200 000 − to'langan 300 000
    assert saved.status == DebtStatus.ACTIVE
    [record] = await edits.get_edits(client_id)
    assert record.debt_id == debt.id
    assert [c.field for c in record.changes] == ["products", "original_debt"]


async def test_update_debt_below_repaid_amount_is_rejected(
    client_repo, debt_repo, services
) -> None:
    debts, edits = services
    client_id = await _client(client_repo)
    debt = await debts.create_debt(
        client_id=client_id, debt_date="16.08.2026", product_name="Shina", product_price=1_000_000
    )
    await debts.pay_partial_debt(client_id, 800_000, "17.08.2026")

    with pytest.raises(ValueError, match="allaqachon to'langan"):
        await edits.update_debt(
            debt.id, "16.08.2026", [DebtProduct(name="Shina", price_per_unit=500_000)]
        )
    assert (await debt_repo.get_by_id(debt.id)).remaining_debt == 200_000


async def test_update_debt_reopens_paid_debt_and_moves_initial_payment(
    client_repo, debt_repo, payment_repo, services
) -> None:
    debts, edits = services
    client_id = await _client(client_repo)
    debt = await debts.create_debt(
        client_id=client_id,
        debt_date="16.08.2026",
        product_name="Shina",
        product_price=1_000_000,
        given_money=1_000_000,
    )
    assert debt.status == DebtStatus.PAID

    saved = await edits.update_debt(
        debt.id, "20.08.2026", [DebtProduct(name="Shina", price_per_unit=1_500_000)]
    )

    assert saved.remaining_debt == 500_000 and saved.status == DebtStatus.ACTIVE
    [initial] = [
        p for p in await payment_repo.get_by_client_id(client_id)
        if p.payment_type == PaymentType.INITIAL
    ]
    assert initial.payment_date == date(2026, 8, 20)


async def test_trashed_debt_cannot_be_edited(client_repo, debt_repo, services) -> None:
    debts, edits = services
    client_id = await _client(client_repo)
    debt = await debts.create_debt(  # to'liq to'langan — korzinaga faqat yopilgan qarz tushadi
        client_id=client_id,
        debt_date="16.08.2026",
        product_name="Shina",
        product_price=1_000,
        given_money=1_000,
    )
    assert await debt_repo.move_to_trash([debt.id]) == 1

    with pytest.raises(ValueError, match="Korzinadagi"):
        await edits.update_debt(debt.id, "16.08.2026", [DebtProduct(name="X", price_per_unit=5)])


async def test_concurrent_payment_makes_edit_fail(client_repo, debt_repo, services) -> None:
    """Tahrir hisoblangandan keyin qarz o'zgarsa (to'lov tushsa) — yozilmaydi."""
    debts, edits = services
    client_id = await _client(client_repo)
    debt = await debts.create_debt(
        client_id=client_id, debt_date="16.08.2026", product_name="Shina", product_price=1_000
    )
    stale = await debt_repo.get_by_id(debt.id)
    await debts.pay_partial_debt(client_id, 100, "17.08.2026")

    assert await debt_repo.update_details(stale, stale) is None


async def test_bot_report_marks_edited_client_and_debt(client_repo, services) -> None:
    from bot.presentation.handlers.debt_table import _render_report

    debts, edits = services
    client_id = await _client(client_repo)
    debt = await debts.create_debt(
        client_id=client_id, debt_date="16.08.2026", product_name="Shina", product_price=1_000
    )
    report = await debts.get_client_report(client_id)
    assert "tahrirlangan" not in _render_report(report, await edits.get_edits(client_id))

    products = [DebtProduct(name="Shina", price_per_unit=2_000)]
    await edits.update_debt(debt.id, "16.08.2026", products)
    report = await debts.get_client_report(client_id)
    text = _render_report(report, await edits.get_edits(client_id))
    assert text.count("tahrirlangan") == 1
