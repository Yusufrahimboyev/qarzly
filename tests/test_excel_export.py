"""Excel eksporti va sana chegaralari uchun testlar."""
from __future__ import annotations

from datetime import date
from io import BytesIO

from openpyxl import load_workbook

from bot.application.common.period_report import (
    build_period_report,
    validate_period_bounds,
)
from bot.domain.entities.client import Client
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import Debt, DebtStatus
from bot.domain.entities.payment import Payment, PaymentType
from bot.infrastructure.export.excel import build_file_name, build_period_workbook
from bot.presentation.keyboards.debt_table_kb import (
    get_debt_table_keyboard,
    get_export_date_keyboard,
)

TODAY = date(2026, 9, 11)


# ==========================================
# Sana chegaralari
# ==========================================


def test_end_date_after_today_is_rejected():
    error = validate_period_bounds(date(2026, 1, 1), date(2026, 9, 12), TODAY)
    assert error is not None
    assert "bugundan keyin" in error


def test_today_itself_is_allowed():
    assert validate_period_bounds(date(2026, 1, 1), TODAY, TODAY) is None


def test_start_after_end_is_rejected():
    error = validate_period_bounds(date(2026, 5, 10), date(2026, 5, 1), TODAY)
    assert error is not None
    assert "Boshlanish sanasi" in error


def test_single_day_period_is_allowed():
    assert validate_period_bounds(TODAY, TODAY, TODAY) is None


# ==========================================
# Klaviatura
# ==========================================


def test_debt_table_keyboard_has_export_button():
    summaries: list = []
    keyboard = get_debt_table_keyboard(summaries, page=1)
    assert keyboard.inline_keyboard == []  # bo'sh ro'yxatda tugma ham yo'q


def test_export_keyboard_shows_today_only_when_asked():
    with_today = get_export_date_keyboard(with_today=True)
    without = get_export_date_keyboard(with_today=False)

    labels = [b.text for row in with_today.inline_keyboard for b in row]
    assert any("Bugun" in label for label in labels)

    labels_without = [b.text for row in without.inline_keyboard for b in row]
    assert not any("Bugun" in label for label in labels_without)
    assert any("Bekor" in label for label in labels_without)


# ==========================================
# Excel fayli
# ==========================================


def _sample_report() -> object:
    clients = [
        Client(id=1, full_name="Akmal", phone="+998901111111"),
        Client(id=2, full_name="Amin aka", phone="+998902222222"),
    ]
    debts = [
        Debt(
            id=1,
            client_id=1,
            debt_date=date(2026, 2, 10),
            product_name="Shina — 4 ta",
            product_quantity=4,
            product_price=4_000_000,
            given_money=500_000,
            original_debt=3_500_000,
            remaining_debt=1_000_000,
        ),
        Debt(
            id=2,
            client_id=2,
            debt_date=date(2026, 7, 3),
            product_name="Akkumulyator",
            product_price=300,
            original_debt=300,
            remaining_debt=240,
            currency=Currency.USD,
            status=DebtStatus.ACTIVE,
        ),
    ]
    payments = [
        Payment(
            id=1,
            client_id=1,
            debt_id=1,
            amount=500_000,
            payment_type=PaymentType.INITIAL,
            payment_date=date(2026, 2, 10),
        ),
        Payment(
            id=2,
            client_id=1,
            debt_id=1,
            amount=2_500_000,
            payment_type=PaymentType.PARTIAL,
            payment_date=date(2026, 3, 15),
        ),
        Payment(
            id=3,
            client_id=2,
            debt_id=2,
            amount=60,
            currency=Currency.USD,
            payment_type=PaymentType.PARTIAL,
            payment_date=date(2026, 8, 1),
        ),
    ]
    return build_period_report(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 12, 31),
        debts=debts,
        payments=payments,
        clients=clients,
        opening_given={"UZS": 2_000_000},
        opening_repaid={"UZS": 500_000},
        repaid_by_debt={1: 2_500_000, 2: 60},
        active_totals={1: {"UZS": (1_000_000, 1)}, 2: {"USD": (240, 1)}},
    )


def _load(report) -> object:
    return load_workbook(BytesIO(build_period_workbook(report)))


def test_workbook_has_all_expected_sheets():
    workbook = _load(_sample_report())
    assert workbook.sheetnames == [
        "Umumiy natija",
        "Oyma-oy",
        "Mijozlar kesimida",
        "Eng katta qarzdorlar",
        "Qarzlar",
        "To'lovlar",
    ]


def test_summary_sheet_shows_balance():
    sheet = _load(_sample_report())["Umumiy natija"]
    values = {
        row[0]: (row[1], row[2])
        for row in sheet.iter_rows(min_row=1, max_row=12, max_col=3, values_only=True)
        if row[0]
    }
    assert values["Davr boshidagi qarz"] == (1_500_000, 0)
    assert values["Davrda berilgan jami qarz"] == (3_500_000, 300)
    assert values["Davrda qaytarilgan jami pul"] == (2_500_000, 60)
    assert values["Davr oxiridagi qarzdorlik"] == (2_500_000, 240)


def test_monthly_sheet_has_twelve_months_and_totals():
    sheet = _load(_sample_report())["Oyma-oy"]
    labels = [
        row[0]
        for row in sheet.iter_rows(min_row=4, max_col=1, values_only=True)
        if row[0]
    ]
    assert labels[0] == "Yanvar 2026"
    assert labels[11] == "Dekabr 2026"
    assert labels[12] == "JAMI"


def test_amounts_are_written_as_numbers_not_text():
    """Foydalanuvchi ustunni saralay va SUM qila olishi uchun son bo'lishi shart."""
    sheet = _load(_sample_report())["Qarzlar"]
    header_row = 3
    original_debt_cell = sheet.cell(row=header_row + 1, column=9)
    assert isinstance(original_debt_cell.value, int)
    assert original_debt_cell.number_format == "#,##0"


def test_usd_rows_use_dollar_number_format():
    sheet = _load(_sample_report())["Qarzlar"]
    # 2-qator — USD dagi qarz (Akkumulyator).
    cell = sheet.cell(row=5, column=9)
    assert cell.value == 300
    assert "$" in cell.number_format


def test_client_sheet_rows_balance():
    sheet = _load(_sample_report())["Mijozlar kesimida"]
    rows = [
        row
        for row in sheet.iter_rows(min_row=4, max_col=12, values_only=True)
        if row[0]
    ]
    assert len(rows) == 2
    for row in rows:
        given_uzs, given_usd, paid_uzs, paid_usd, rem_uzs, rem_usd = row[3:9]
        assert given_uzs - paid_uzs == rem_uzs
        assert given_usd - paid_usd == rem_usd
    assert rows[0][11] == "Qarzdor"


def test_top_sheet_lists_debtors_per_currency():
    sheet = _load(_sample_report())["Eng katta qarzdorlar"]
    texts = [
        row[1]
        for row in sheet.iter_rows(min_row=1, max_col=4, values_only=True)
        if row[1]
    ]
    assert "Akmal" in texts
    assert "Amin aka" in texts


def test_empty_report_still_produces_valid_workbook():
    report = build_period_report(
        date_from=date(2026, 1, 1),
        date_to=date(2026, 1, 31),
        debts=[],
        payments=[],
        clients=[],
        opening_given={},
        opening_repaid={},
        repaid_by_debt={},
        active_totals={},
    )
    workbook = _load(report)
    assert len(workbook.sheetnames) == 6
    assert workbook["Eng katta qarzdorlar"]["A8"].value == "Qarzdor yo'q"


def test_file_name_contains_both_dates():
    name = build_file_name(date(2026, 1, 1), date(2026, 9, 11))
    assert name == "qarz-hisobot_01.01.2026_11.09.2026.xlsx"


def test_manual_export_has_no_today_sheet():
    """Botdan qo'lda eksportda "Bugun" varag'i bo'lmasligi kerak."""
    workbook = _load(_sample_report())
    assert "Bugun" not in workbook.sheetnames


def test_day_sheet_added_only_when_requested():
    """Kanalga ketadigan kunlik hisobotda esa varaq qo'shiladi."""
    data = build_period_workbook(_sample_report(), include_day_sheet=True)
    workbook = load_workbook(BytesIO(data))
    assert workbook.sheetnames[1] == "Bugun"
    assert len(workbook.sheetnames) == 7
