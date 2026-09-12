"""Infrastructure qatlami: davr hisobotini Excel (.xlsx) faylga yozish.

Bu modul yagona joy bo'lib, `openpyxl` ga bog'liq. `PeriodReport` allaqachon
hisoblangan holda keladi — bu yerda hech qanday biznes-mantiq yo'q, faqat
varaqlarga joylashtirish va formatlash.

Summalar Excel'ga MATN emas, SON sifatida yoziladi (o'z number_format'i bilan)
— shunda foydalanuvchi ustunni saralashi, filtrlashi va SUM qilishi mumkin.
"""
from __future__ import annotations

import re
from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.worksheet import Worksheet

from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import DebtStatus
from bot.domain.entities.payment import PaymentType
from bot.domain.entities.period_report import PeriodReport
from bot.domain.entities.report import ClientReport, MoneyMap

UZS = Currency.UZS.value
USD = Currency.USD.value

# So'm butun son sifatida, ming ajratgichi bilan; dollar sentlarsiz.
_UZS_FORMAT = "#,##0"
_USD_FORMAT = '#,##0" $"'
_DATE_FORMAT = "DD.MM.YYYY"

_HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
_HEADER_FONT = Font(bold=True, color="FFFFFF", size=11)
_TITLE_FONT = Font(bold=True, size=14, color="1F4E78")
_SECTION_FONT = Font(bold=True, size=11, color="1F4E78")
_TOTAL_FONT = Font(bold=True)
_DEBTOR_FILL = PatternFill("solid", fgColor="FCE4E4")
_CLOSED_FILL = PatternFill("solid", fgColor="E4F3E4")

_THIN = Side(style="thin", color="BFBFBF")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)

_STATUS_LABELS = {
    DebtStatus.ACTIVE: "Ochiq",
    DebtStatus.PAID: "Yopilgan",
    DebtStatus.TRASHED: "Korzinada",
}

_PAYMENT_LABELS = {
    PaymentType.FULL: "To'liq",
    PaymentType.PARTIAL: "Qisman",
    PaymentType.INITIAL: "Boshlang'ich (berilgan pul)",
}


def build_period_workbook(
    report: PeriodReport,
    *,
    include_day_sheet: bool = False,
) -> bytes:
    """Davr hisobotidan .xlsx fayl baytlarini yasaydi.

    `include_day_sheet` — "Bugun" varag'i faqat kanalga ketadigan kunlik
    hisobotda kerak. Botdan qo'lda eksport qilinganda ixtiyoriy davr
    tanlanadi, u yerda "bugun" tushunchasi ma'nosiz bo'lgani uchun varaq
    qo'shilmaydi.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)

    _write_summary_sheet(workbook.create_sheet("Umumiy natija"), report)
    if include_day_sheet:
        _write_day_sheet(workbook.create_sheet("Bugun"), report)
    _write_monthly_sheet(workbook.create_sheet("Oyma-oy"), report)
    _write_clients_sheet(workbook.create_sheet("Mijozlar kesimida"), report)
    _write_top_sheet(workbook.create_sheet("Eng katta qarzdorlar"), report)
    _write_debts_sheet(workbook.create_sheet("Qarzlar"), report)
    _write_payments_sheet(workbook.create_sheet("To'lovlar"), report)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_client_workbook(report: ClientReport) -> bytes:
    """Bitta mijozning to'liq hisobotidan .xlsx fayl baytlarini yasaydi.

    Botdagi matnli mijoz hisobotining Excel ko'rinishi: jami ko'rsatkichlar,
    qarzlar tarixi va to'lovlar tarixi. Summalar shu yerda ham son sifatida
    yoziladi — SUM va saralash ishlashi uchun.
    """
    workbook = Workbook()
    workbook.remove(workbook.active)

    _write_client_summary_sheet(workbook.create_sheet("Hisobot"), report)
    _write_client_payments_sheet(workbook.create_sheet("To'lovlar"), report)

    buffer = BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def build_client_file_name(client_name: str, today_date: date) -> str:
    """Mijoz hisoboti uchun fayl nomi (ismdagi xavfli belgilar tozalanadi)."""
    slug = re.sub(r"[^\w\-]+", "-", client_name, flags=re.UNICODE).strip("-")
    return f"mijoz-hisobot_{slug or 'mijoz'}_{today_date:%d.%m.%Y}.xlsx"


def build_file_name(date_from: date, date_to: date) -> str:
    """Telegram'ga yuboriladigan fayl nomi."""
    return (
        f"qarz-hisobot_{date_from:%d.%m.%Y}_{date_to:%d.%m.%Y}.xlsx"
    )


# ==========================================
# Yordamchi yozuvchilar
# ==========================================


def _money(amounts: MoneyMap, currency: str) -> int:
    return int(amounts.get(currency, 0))


def _money_format(currency: str) -> str:
    return _USD_FORMAT if currency == USD else _UZS_FORMAT


def _write_title(sheet: Worksheet, row: int, text: str, span: int) -> int:
    """Varaq sarlavhasini yozadi va keyingi qator raqamini qaytaradi."""
    cell = sheet.cell(row=row, column=1, value=text)
    cell.font = _TITLE_FONT
    if span > 1:
        sheet.merge_cells(
            start_row=row, start_column=1, end_row=row, end_column=span
        )
    return row + 2


def _write_section(sheet: Worksheet, row: int, text: str) -> int:
    cell = sheet.cell(row=row, column=1, value=text)
    cell.font = _SECTION_FONT
    return row + 1


def _write_header(sheet: Worksheet, row: int, headers: list[str]) -> int:
    """Jadval sarlavha qatorini yozadi va avtofiltr/muzlatishni sozlaydi."""
    for index, title in enumerate(headers, start=1):
        cell = sheet.cell(row=row, column=index, value=title)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = _BORDER
    sheet.row_dimensions[row].height = 30
    sheet.freeze_panes = sheet.cell(row=row + 1, column=1)
    return row + 1


def _write_money_pair(sheet: Worksheet, row: int, column: int, amounts: MoneyMap) -> int:
    """So'm va dollar ustunlarini yonma-yon yozadi; keyingi ustunni qaytaradi."""
    for currency in (UZS, USD):
        cell = sheet.cell(row=row, column=column, value=_money(amounts, currency))
        cell.number_format = _money_format(currency)
        cell.border = _BORDER
        column += 1
    return column


def _autosize(sheet: Worksheet, widths: list[int]) -> None:
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width


def _label_value_row(
    sheet: Worksheet,
    row: int,
    label: str,
    amounts: MoneyMap,
    *,
    bold: bool = False,
) -> int:
    """"Ko'rsatkich | so'm | $" ko'rinishidagi qator."""
    cell = sheet.cell(row=row, column=1, value=label)
    cell.border = _BORDER
    if bold:
        cell.font = _TOTAL_FONT
    column = _write_money_pair(sheet, row, 2, amounts)
    if bold:
        for col in range(2, column):
            sheet.cell(row=row, column=col).font = _TOTAL_FONT
    return row + 1


def _count_row(sheet: Worksheet, row: int, label: str, value: int) -> int:
    label_cell = sheet.cell(row=row, column=1, value=label)
    label_cell.border = _BORDER
    value_cell = sheet.cell(row=row, column=2, value=value)
    value_cell.border = _BORDER
    sheet.merge_cells(start_row=row, start_column=2, end_row=row, end_column=3)
    return row + 1


# ==========================================
# 1. Umumiy natija (+ valyuta kesimi, + yakuniy xulosa)
# ==========================================


def _write_summary_sheet(sheet: Worksheet, report: PeriodReport) -> None:
    period = f"{report.date_from:%d.%m.%Y} — {report.date_to:%d.%m.%Y}"
    row = _write_title(sheet, 1, f"QARZ HISOBOTI: {period}", span=3)

    row = _write_section(sheet, row, "1. UMUMIY NATIJA")
    row = _write_header(sheet, row, ["Ko'rsatkich", "So'm", "Dollar"])

    row = _label_value_row(sheet, row, "Davr boshidagi qarz", report.opening_debt)
    row = _label_value_row(sheet, row, "Davrda berilgan jami qarz", report.given_total)
    row = _label_value_row(
        sheet, row, "Davrda qaytarilgan jami pul", report.returned_total
    )
    row = _label_value_row(
        sheet,
        row,
        "Davr oxiridagi qarzdorlik",
        report.closing_debt,
        bold=True,
    )
    row += 1

    row = _count_row(sheet, row, "Jami mijozlar (bazada)", report.clients_total)
    row = _count_row(sheet, row, "Jami qarzdorlar (hozirgi holat)", report.debtors_total)
    row = _count_row(sheet, row, "Davrda faol mijozlar", report.period_clients_total)
    row = _count_row(sheet, row, "Yopilgan qarzlar soni", report.closed_debts_count)
    row = _count_row(sheet, row, "Ochiq qarzlar soni", report.open_debts_count)
    row = _count_row(sheet, row, "Korzinadagi qarzlar soni", report.trashed_debts_count)
    row += 1

    # --- 2. Valyuta bo'yicha ---
    row = _write_section(sheet, row, "2. VALYUTA BO'YICHA")
    row = _write_header(sheet, row, ["Ko'rsatkich", "So'm", "Dollar"])
    row = _label_value_row(sheet, row, "Berilgan qarzlar", report.given_total)
    row = _label_value_row(sheet, row, "Qaytarilgan pul", report.returned_total)
    row = _label_value_row(sheet, row, "Qolgan qarzdorlik", report.closing_debt)
    row = _label_value_row(
        sheet,
        row,
        "Boshlang'ich to'lovlar (ma'lumot uchun)",
        report.initial_total,
    )
    row += 1

    note = sheet.cell(
        row=row,
        column=1,
        value=(
            "Izoh 1: \"Boshlang'ich to'lov\" — qarz yaratilganda darhol berilgan pul. "
            "U \"Berilgan jami qarz\" dan allaqachon ayrilgan, shuning uchun "
            "\"Qaytarilgan pul\" ga qo'shilmaydi (aks holda ikki marta hisoblanardi).\n"
            "Izoh 2: Korzinadagi qarzlar hisobotga kiradi, ammo korzina BUTUNLAY "
            "tozalangan (o'chirilgan) yozuvlar kirmaydi. Ular to'liq to'langan "
            "bo'lgani uchun qarz qoldig'i raqamlariga ta'sir qilmaydi, faqat "
            "\"berilgan\" va \"qaytarilgan\" aylanmasi o'shancha kam ko'rinadi.\n"
            "Izoh 3: Barcha summalar DAVR OXIRIDAGI holat bo'yicha — qarz sanasi "
            "(debt_date) va to'lov sanasi bo'yicha qayta qurilgan. Bot ekranidagi "
            "\"jami qoldiq qarz\" esa HOZIRGI holatni ko'rsatadi, shuning uchun "
            "o'tgan davr uchun hisobot bilan farq qilishi normal."
        ),
    )
    note.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.merge_cells(start_row=row, start_column=1, end_row=row + 5, end_column=3)
    row += 7

    # --- 6. Yakuniy xulosa ---
    row = _write_section(sheet, row, "6. YAKUNIY XULOSA")
    summary = sheet.cell(row=row, column=1, value=_summary_text(report))
    summary.alignment = Alignment(wrap_text=True, vertical="top")
    summary.font = Font(size=11)
    sheet.merge_cells(start_row=row, start_column=1, end_row=row + 5, end_column=3)
    sheet.row_dimensions[row].height = 20

    _autosize(sheet, [42, 20, 16])


def _grouped(amount: int) -> str:
    """Summani "1 500 000" ko'rinishida yozadi (matnli xulosa uchun)."""
    return f"{amount:,}".replace(",", "\u00a0")


def _summary_text(report: PeriodReport) -> str:
    """"Qancha qarz berildi, qancha qaytdi, hozir qancha turibdi" xulosasi."""
    period = f"{report.date_from:%d.%m.%Y} — {report.date_to:%d.%m.%Y}"
    lines = [f"{period} davri uchun:", ""]

    for currency, name in ((UZS, "so'm"), (USD, "dollar")):
        opening = _money(report.opening_debt, currency)
        given = _money(report.given_total, currency)
        returned = _money(report.returned_total, currency)
        closing = _money(report.closing_debt, currency)
        if not any((opening, given, returned, closing)):
            continue
        lines.append(
            f"• {name.capitalize()}da: davr boshida {_grouped(opening)} qarz bor edi, "
            f"davr davomida {_grouped(given)} qarz berildi va "
            f"{_grouped(returned)} qaytdi. "
            f"Hozirda {_grouped(closing)} {name} qarzda turibdi."
        )

    if len(lines) == 2:
        lines.append("• Bu davrda hech qanday harakat bo'lmagan.")

    lines.append("")
    lines.append(
        f"Hozirda {report.debtors_total} nafar mijozda ochiq qarz bor "
        f"(jami {report.clients_total} mijozdan)."
    )
    return "\n".join(lines)


# ==========================================
# Bitta mijoz hisoboti
# ==========================================


def _write_client_summary_sheet(sheet: Worksheet, report: ClientReport) -> None:
    """Mijoz ma'lumoti, jami ko'rsatkichlar va qarzlar tarixi."""
    client = report.client
    row = _write_title(sheet, 1, f"MIJOZ HISOBOTI: {client.full_name}", span=8)

    phone = sheet.cell(row=row, column=1, value=f"📞 Telefon: {client.phone}")
    phone.font = Font(size=11)
    row += 2

    row = _write_section(sheet, row, "JAMI KO'RSATKICHLAR")
    row = _write_header(sheet, row, ["Ko'rsatkich", "So'm", "Dollar"])
    row = _label_value_row(sheet, row, "Tovarlar jami narxi", report.total_product_price)
    row = _label_value_row(sheet, row, "Exchange", report.total_exchange_price)
    row = _label_value_row(sheet, row, "Berilgan pul", report.total_given_money)
    row = _label_value_row(sheet, row, "Asl qarz", report.total_original_debt)
    row = _label_value_row(sheet, row, "To'langan", report.total_paid_after)
    row = _label_value_row(
        sheet, row, "Qoldiq qarz", report.total_remaining_debt, bold=True
    )
    row += 2

    row = _write_section(sheet, row, "QARZLAR TARIXI")
    _write_client_debts(sheet, row, report)

    _autosize(sheet, [30, 34, 8, 16, 14, 14, 16, 16, 10, 12])


def _write_client_debts(sheet: Worksheet, row: int, report: ClientReport) -> int:
    headers = [
        "Sana",
        "Tovar(lar)",
        "Soni",
        "Tovar narxi",
        "Exchange",
        "Berilgan pul",
        "Asl qarz",
        "Qoldiq",
        "Valyuta",
        "Holati",
    ]
    header_row = row
    for index, title in enumerate(headers, start=1):
        cell = sheet.cell(row=row, column=index, value=title)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = _BORDER
    row += 1

    if not report.debts:
        return _empty_row(sheet, row, "Qarzlar mavjud emas", span=len(headers))

    for debt in report.debts:
        currency = str(debt.currency)
        money_format = _money_format(currency)
        values = [
            debt.debt_date,
            debt.product_name,
            debt.product_quantity,
            debt.product_price,
            debt.exchange_product_price,
            debt.given_money,
            debt.original_debt,
            debt.remaining_debt,
            currency,
            _STATUS_LABELS.get(debt.status, str(debt.status)),
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            cell.border = _BORDER
            if index == 1:
                cell.number_format = _DATE_FORMAT
            elif 4 <= index <= 8:
                cell.number_format = money_format

        status_cell = sheet.cell(row=row, column=len(headers))
        status_cell.fill = (
            _DEBTOR_FILL if debt.remaining_debt > 0 else _CLOSED_FILL
        )
        row += 1

    sheet.auto_filter.ref = (
        f"A{header_row}:{get_column_letter(len(headers))}{row - 1}"
    )
    return row


def _write_client_payments_sheet(sheet: Worksheet, report: ClientReport) -> None:
    """Mijozning to'lovlar tarixi."""
    row = _write_title(
        sheet, 1, f"TO'LOVLAR TARIXI: {report.client.full_name}", span=4
    )
    header_row = row
    row = _write_header(sheet, row, ["Sana", "Summa", "Valyuta", "To'lov turi"])

    if not report.payments:
        _empty_row(sheet, row, "To'lovlar mavjud emas", span=4)
        _autosize(sheet, [14, 18, 10, 26])
        return

    for payment in report.payments:
        currency = str(payment.currency)
        values = [
            payment.payment_date,
            payment.amount,
            currency,
            _PAYMENT_LABELS.get(payment.payment_type, str(payment.payment_type)),
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            cell.border = _BORDER
            if index == 1:
                cell.number_format = _DATE_FORMAT
            elif index == 2:
                cell.number_format = _money_format(currency)
        row += 1

    sheet.auto_filter.ref = f"A{header_row}:D{row - 1}"
    _autosize(sheet, [14, 18, 10, 26])


# ==========================================
# Bugun (hisobot kuni) — berilgan va yopilgan
# ==========================================


def _write_day_sheet(sheet: Worksheet, report: PeriodReport) -> None:
    """Hisobot kunida (date_to) berilgan va yopilgan qarzlar."""
    day = report.date_to
    row = _write_title(sheet, 1, f"BUGUN: {day:%d.%m.%Y}", span=6)

    row = _write_header(sheet, row, ["Ko'rsatkich", "So'm", "Dollar"])
    row = _label_value_row(sheet, row, "Bugun berilgan qarz", report.day_given)
    row = _label_value_row(sheet, row, "Bugun tushgan pul", report.day_returned)
    row = _count_row(sheet, row, "Bugun ochilgan qarzlar soni", report.day_new_debts)
    row = _count_row(sheet, row, "Bugun yopilgan qarzlar soni", report.day_closed_debts)
    row += 2

    row = _write_section(sheet, row, "BUGUN BERILGAN QARZLAR")
    row = _write_day_debts(sheet, row, report, day)
    row += 2

    row = _write_section(sheet, row, "BUGUN YOPILGAN QARZLAR")
    _write_day_closed(sheet, row, report, day)

    _autosize(sheet, [30, 24, 34, 16, 16, 12])


def _write_day_debts(
    sheet: Worksheet,
    row: int,
    report: PeriodReport,
    day: date,
) -> int:
    """Hisobot kunida ochilgan qarzlar ro'yxati."""
    headers = ["Mijoz", "Tovar(lar)", "Tovar narxi", "Berilgan pul", "Qarz", "Valyuta"]
    for index, title in enumerate(headers, start=1):
        cell = sheet.cell(row=row, column=index, value=title)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = _BORDER
    row += 1

    debts = [d for d in report.debts if d.debt_date == day]
    if not debts:
        return _empty_row(sheet, row, "Bugun yangi qarz berilmagan", span=6)

    for debt in debts:
        currency = str(debt.currency)
        values = [
            report.client_names.get(debt.client_id, f"ID {debt.client_id}"),
            debt.product_name,
            debt.product_price,
            debt.given_money,
            debt.original_debt,
            currency,
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            cell.border = _BORDER
            if 3 <= index <= 5:
                cell.number_format = _money_format(currency)
        row += 1

    return row


def _write_day_closed(
    sheet: Worksheet,
    row: int,
    report: PeriodReport,
    day: date,
) -> int:
    """Hisobot kunida to'liq yopilgan qarzlar.

    `full` turidagi to'lov aynan "shu to'lov qarzni yopdi" degani — shuning
    uchun yopilganlar to'lovlar ro'yxatidan aniqlanadi.
    """
    headers = ["Mijoz", "Tovar(lar)", "Yopilgan summa", "Valyuta"]
    for index, title in enumerate(headers, start=1):
        cell = sheet.cell(row=row, column=index, value=title)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center", wrap_text=True)
        cell.border = _BORDER
    row += 1

    debt_names: dict[int, str] = {
        d.id: d.product_name for d in report.debts if d.id is not None
    }
    closed = [
        p
        for p in report.payments
        if p.payment_date == day and p.payment_type == PaymentType.FULL
    ]
    if not closed:
        return _empty_row(sheet, row, "Bugun yopilgan qarz yo'q", span=4)

    for payment in closed:
        currency = str(payment.currency)
        values = [
            report.client_names.get(payment.client_id, f"ID {payment.client_id}"),
            debt_names.get(payment.debt_id or 0, ""),
            payment.amount,
            currency,
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            cell.border = _BORDER
            if index == 3:
                cell.number_format = _money_format(currency)
        row += 1

    return row


def _empty_row(sheet: Worksheet, row: int, text: str, span: int) -> int:
    cell = sheet.cell(row=row, column=1, value=text)
    cell.border = _BORDER
    sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=span)
    return row + 1


# ==========================================
# 3. Oyma-oy hisobot
# ==========================================


def _write_monthly_sheet(sheet: Worksheet, report: PeriodReport) -> None:
    row = _write_title(sheet, 1, "3. OYMA-OY HISOBOT", span=7)
    row = _write_header(
        sheet,
        row,
        [
            "Oy",
            "Berilgan qarz (so'm)",
            "Berilgan qarz ($)",
            "Qaytgan pul (so'm)",
            "Qaytgan pul ($)",
            "Oy oxiridagi qarz (so'm)",
            "Oy oxiridagi qarz ($)",
        ],
    )

    for month in report.months:
        label = sheet.cell(row=row, column=1, value=month.label)
        label.border = _BORDER
        column = _write_money_pair(sheet, row, 2, month.given)
        column = _write_money_pair(sheet, row, column, month.returned)
        _write_money_pair(sheet, row, column, month.closing)
        row += 1

    total = sheet.cell(row=row, column=1, value="JAMI")
    total.font = _TOTAL_FONT
    total.border = _BORDER
    column = _write_money_pair(sheet, row, 2, report.given_total)
    column = _write_money_pair(sheet, row, column, report.returned_total)
    _write_money_pair(sheet, row, column, report.closing_debt)
    for col in range(2, 8):
        sheet.cell(row=row, column=col).font = _TOTAL_FONT

    _autosize(sheet, [16, 20, 16, 20, 16, 22, 18])


# ==========================================
# 4. Mijozlar kesimida
# ==========================================


def _write_clients_sheet(sheet: Worksheet, report: PeriodReport) -> None:
    row = _write_title(sheet, 1, "4. MIJOZLAR KESIMIDA", span=12)
    header_row = row
    row = _write_header(
        sheet,
        row,
        [
            "Mijoz (F.I.Sh.)",
            "Telefon",
            "Qarzdorlik sanasi",
            "Berilgan (so'm)",
            "Berilgan ($)",
            "To'langan (so'm)",
            "To'langan ($)",
            "Qolgan (so'm)",
            "Qolgan ($)",
            "Davrda tushgan pul (so'm)",
            "Davrda tushgan pul ($)",
            "Holati",
        ],
    )

    for client_row in report.client_rows:
        name = sheet.cell(row=row, column=1, value=client_row.full_name)
        name.border = _BORDER
        phone = sheet.cell(row=row, column=2, value=client_row.phone)
        phone.border = _BORDER

        date_cell = sheet.cell(row=row, column=3, value=client_row.debt_date)
        date_cell.number_format = _DATE_FORMAT
        date_cell.alignment = Alignment(horizontal="center")
        date_cell.border = _BORDER

        column = _write_money_pair(sheet, row, 4, client_row.given)
        column = _write_money_pair(sheet, row, column, client_row.paid)
        column = _write_money_pair(sheet, row, column, client_row.remaining)
        column = _write_money_pair(sheet, row, column, client_row.cash_paid)

        status = sheet.cell(row=row, column=column, value=client_row.status_label)
        status.alignment = Alignment(horizontal="center")
        status.border = _BORDER
        status.fill = _CLOSED_FILL if client_row.is_closed else _DEBTOR_FILL
        row += 1

    if report.client_rows:
        sheet.auto_filter.ref = f"A{header_row}:L{row - 1}"

    _autosize(sheet, [26, 16, 17, 17, 13, 17, 13, 16, 13, 22, 18, 12])


# ==========================================
# 5. Eng katta qarzdorlar
# ==========================================


def _write_top_sheet(sheet: Worksheet, report: PeriodReport) -> None:
    row = _write_title(sheet, 1, "5. ENG KATTA QARZDORLAR (Top-10)", span=4)

    note = sheet.cell(
        row=row,
        column=1,
        value=(
            "Bu ro'yxat davr chegarasiga bog'liq emas — mijozning HOZIRGI "
            "ochiq qarzini ko'rsatadi. Kurs noma'lum bo'lgani uchun so'm va "
            "dollar alohida ro'yxatlarda."
        ),
    )
    note.alignment = Alignment(wrap_text=True, vertical="top")
    sheet.merge_cells(start_row=row, start_column=1, end_row=row + 1, end_column=4)
    row += 3

    row = _write_section(sheet, row, "So'm bo'yicha")
    row = _write_top_table(sheet, row, report.top_by_uzs, UZS, "Qarz (so'm)")
    row += 1

    row = _write_section(sheet, row, "Dollar bo'yicha")
    _write_top_table(sheet, row, report.top_by_usd, USD, "Qarz ($)")

    _autosize(sheet, [8, 28, 18, 18])


def _write_top_table(
    sheet: Worksheet,
    row: int,
    rows,
    currency: str,
    amount_header: str,
) -> int:
    for index, title in enumerate(["#", "Mijoz", "Telefon", amount_header], start=1):
        cell = sheet.cell(row=row, column=index, value=title)
        cell.fill = _HEADER_FILL
        cell.font = _HEADER_FONT
        cell.alignment = Alignment(horizontal="center")
        cell.border = _BORDER
    row += 1

    if not rows:
        empty = sheet.cell(row=row, column=1, value="Qarzdor yo'q")
        empty.border = _BORDER
        sheet.merge_cells(start_row=row, start_column=1, end_row=row, end_column=4)
        return row + 1

    for rank, debtor in enumerate(rows, start=1):
        rank_cell = sheet.cell(row=row, column=1, value=rank)
        rank_cell.alignment = Alignment(horizontal="center")
        rank_cell.border = _BORDER
        name = sheet.cell(row=row, column=2, value=debtor.full_name)
        name.border = _BORDER
        phone = sheet.cell(row=row, column=3, value=debtor.phone)
        phone.border = _BORDER
        amount = sheet.cell(row=row, column=4, value=_money(debtor.remaining, currency))
        amount.number_format = _money_format(currency)
        amount.border = _BORDER
        row += 1

    return row


# ==========================================
# Tafsilot: qarzlar va to'lovlar
# ==========================================


def _write_debts_sheet(sheet: Worksheet, report: PeriodReport) -> None:
    row = _write_title(sheet, 1, "QARZLAR (davr ichidagi barcha yozuvlar)", span=11)
    header_row = row
    row = _write_header(
        sheet,
        row,
        [
            "ID",
            "Sana",
            "Mijoz",
            "Tovar(lar)",
            "Soni",
            "Tovar narxi",
            "Exchange",
            "Berilgan pul",
            "Asl qarz",
            "Qoldiq (davr oxiriga)",
            "Valyuta",
            "Holati (hozirgi)",
        ],
    )

    for debt in report.debts:
        currency = str(debt.currency)
        money_format = _money_format(currency)
        values = [
            debt.id,
            debt.debt_date,
            report.client_names.get(debt.client_id, f"ID {debt.client_id}"),
            debt.product_name,
            debt.product_quantity,
            debt.product_price,
            debt.exchange_product_price,
            debt.given_money,
            debt.original_debt,
            report.remaining_as_of.get(debt.id or 0, debt.remaining_debt),
            currency,
            _STATUS_LABELS.get(debt.status, str(debt.status)),
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            cell.border = _BORDER
            if index == 2:
                cell.number_format = _DATE_FORMAT
            elif 6 <= index <= 10:
                cell.number_format = money_format
        row += 1

    if report.debts:
        sheet.auto_filter.ref = f"A{header_row}:L{row - 1}"

    _autosize(sheet, [8, 13, 24, 34, 8, 16, 14, 14, 16, 16, 10, 12])


def _write_payments_sheet(sheet: Worksheet, report: PeriodReport) -> None:
    row = _write_title(sheet, 1, "TO'LOVLAR (davr ichidagi barcha yozuvlar)", span=6)
    header_row = row
    row = _write_header(
        sheet,
        row,
        ["ID", "Sana", "Mijoz", "Qarz ID", "Summa", "Valyuta", "To'lov turi"],
    )

    for payment in report.payments:
        currency = str(payment.currency)
        values = [
            payment.id,
            payment.payment_date,
            report.client_names.get(payment.client_id, f"ID {payment.client_id}"),
            payment.debt_id,
            payment.amount,
            currency,
            _PAYMENT_LABELS.get(payment.payment_type, str(payment.payment_type)),
        ]
        for index, value in enumerate(values, start=1):
            cell = sheet.cell(row=row, column=index, value=value)
            cell.border = _BORDER
            if index == 2:
                cell.number_format = _DATE_FORMAT
            elif index == 5:
                cell.number_format = _money_format(currency)
        row += 1

    if report.payments:
        sheet.auto_filter.ref = f"A{header_row}:G{row - 1}"

    _autosize(sheet, [8, 13, 24, 10, 16, 10, 26])
