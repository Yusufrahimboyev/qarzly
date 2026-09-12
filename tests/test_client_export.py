"""Bitta mijoz Excel hisoboti uchun testlar."""
from __future__ import annotations

from datetime import date, datetime
from io import BytesIO

from openpyxl import load_workbook

from bot.application.services.debt_service import DebtService
from bot.domain.entities.client import Client
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import DebtProduct
from bot.infrastructure.export.excel import (
    build_client_file_name,
    build_client_workbook,
)
from bot.presentation.handlers.report_export import cb_client_excel
from bot.presentation.keyboards.debt_table_kb import get_client_report_keyboard
from tests.test_report_export_handler import StubCallback, StubMessage


async def _report_with_history(client_repo, debt_repo, payment_repo):
    """Bitta mijoz: ikkita qarz (biri yopilgan), bir nechta to'lov."""
    service = DebtService(client_repo, debt_repo, payment_repo)
    client = await client_repo.add(Client(full_name="Akmal", phone="+998901234567"))
    assert client.id is not None

    await service.create_debt(
        client_id=client.id,
        debt_date=date(2026, 3, 1),
        products=[DebtProduct(name="Shina", quantity=4, price_per_unit=500_000)],
        given_money=200_000,
    )
    await service.create_debt(
        client_id=client.id,
        debt_date=date(2026, 5, 10),
        products=[DebtProduct(name="Akkumulyator", price_per_unit=300, currency=Currency.USD)],
        currency=Currency.USD,
    )
    await service.pay_partial_debt(
        client_id=client.id,
        amount=800_000,
        currency=Currency.UZS,
        payment_date=date(2026, 6, 1),
    )
    return service, client


# ==========================================
# Tugma
# ==========================================


def test_client_report_keyboard_has_excel_button():
    keyboard = get_client_report_keyboard(7, has_debt=True)
    pairs = [
        (b.text, b.callback_data)
        for row in keyboard.inline_keyboard
        for b in row
    ]
    assert ("📊 Excel hisobot", "client_excel:7") in pairs


def test_excel_button_shown_even_without_debt():
    """Qarzi yopilgan mijozning tarixini ham chiqarib olish kerak."""
    keyboard = get_client_report_keyboard(9, has_debt=False)
    data = [b.callback_data for row in keyboard.inline_keyboard for b in row]
    assert "client_excel:9" in data


# ==========================================
# Fayl mazmuni
# ==========================================


async def test_workbook_has_two_sheets(client_repo, debt_repo, payment_repo):
    service, client = await _report_with_history(client_repo, debt_repo, payment_repo)
    report = await service.get_client_report(client.id)

    workbook = load_workbook(BytesIO(build_client_workbook(report)))
    assert workbook.sheetnames == ["Hisobot", "To'lovlar"]


async def test_summary_totals_are_written(client_repo, debt_repo, payment_repo):
    service, client = await _report_with_history(client_repo, debt_repo, payment_repo)
    report = await service.get_client_report(client.id)

    sheet = load_workbook(BytesIO(build_client_workbook(report)))["Hisobot"]
    values = {
        row[0]: (row[1], row[2])
        for row in sheet.iter_rows(min_row=1, max_row=14, max_col=3, values_only=True)
        if row[0]
    }

    # 4 × 500 000 = 2 000 000 tovar, 200 000 berilgan pul -> 1 800 000 asl qarz
    assert values["Tovarlar jami narxi"] == (2_000_000, 300)
    assert values["Berilgan pul"] == (200_000, 0)
    assert values["Asl qarz"] == (1_800_000, 300)
    assert values["To'langan"] == (800_000, 0)
    assert values["Qoldiq qarz"] == (1_000_000, 300)


async def test_debt_rows_listed_with_dates(client_repo, debt_repo, payment_repo):
    service, client = await _report_with_history(client_repo, debt_repo, payment_repo)
    report = await service.get_client_report(client.id)

    sheet = load_workbook(BytesIO(build_client_workbook(report)))["Hisobot"]
    rows = [
        row
        for row in sheet.iter_rows(values_only=True)
        if isinstance(row[0], datetime)
    ]
    assert len(rows) == 2
    assert {r[0].date() for r in rows} == {date(2026, 3, 1), date(2026, 5, 10)}
    assert {r[8] for r in rows} == {"UZS", "USD"}


async def test_payments_sheet_lists_history(client_repo, debt_repo, payment_repo):
    service, client = await _report_with_history(client_repo, debt_repo, payment_repo)
    report = await service.get_client_report(client.id)

    sheet = load_workbook(BytesIO(build_client_workbook(report)))["To'lovlar"]
    rows = [
        row
        for row in sheet.iter_rows(values_only=True)
        if isinstance(row[0], datetime)
    ]
    amounts = sorted(r[1] for r in rows)
    # 200 000 boshlang'ich (berilgan pul) + 800 000 qisman
    assert amounts == [200_000, 800_000]


async def test_client_without_debts_still_builds(client_repo, debt_repo, payment_repo):
    service = DebtService(client_repo, debt_repo, payment_repo)
    client = await client_repo.add(Client(full_name="Bobur", phone="+998900000000"))
    assert client.id is not None

    report = await service.get_client_report(client.id)
    sheet = load_workbook(BytesIO(build_client_workbook(report)))["Hisobot"]
    text = [c for row in sheet.iter_rows(values_only=True) for c in row if isinstance(c, str)]
    assert "Qarzlar mavjud emas" in text


# ==========================================
# Fayl nomi
# ==========================================


def test_file_name_uses_client_name():
    name = build_client_file_name("Akmal", date(2026, 9, 12))
    assert name == "mijoz-hisobot_Akmal_12.09.2026.xlsx"


def test_file_name_sanitizes_unsafe_characters():
    name = build_client_file_name("Амин ака / кушни", date(2026, 9, 12))
    assert "/" not in name
    assert name.endswith(".xlsx")


def test_file_name_falls_back_when_name_is_unusable():
    assert build_client_file_name("///", date(2026, 9, 12)).startswith("mijoz-hisobot_mijoz")


# ==========================================
# Handler
# ==========================================


async def test_handler_sends_document(client_repo, debt_repo, payment_repo):
    service, client = await _report_with_history(client_repo, debt_repo, payment_repo)
    callback = StubCallback(
        message=StubMessage.build(), data=f"client_excel:{client.id}"
    )

    await cb_client_excel(callback, service)

    (document,) = callback.message.documents
    assert document.filename.startswith("mijoz-hisobot_Akmal_")
    assert document.content[:2] == b"PK"
    assert "Akmal" in document.caption
    assert "Qoldiq:" in document.caption


async def test_handler_reports_missing_client(client_repo, debt_repo, payment_repo):
    service = DebtService(client_repo, debt_repo, payment_repo)
    callback = StubCallback(message=StubMessage.build(), data="client_excel:999")

    await cb_client_excel(callback, service)

    assert not callback.message.documents
    assert callback.alert == "Mijoz topilmadi."
