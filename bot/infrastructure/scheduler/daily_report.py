"""Infrastructure qatlami: kunlik Excel hisobotni kanalga yuborish.

Har kuni belgilangan vaqtda (odatda 23:59, Toshkent) `REPORT_START_DATE` dan
o'sha kungacha bo'lgan hisobot yig'iladi va kanalga fayl sifatida yuboriladi.

Davr boshlanishi qotirilgan — fayl kundan-kunga kengayib boradi; oxirgi kun
harakati esa "Bugun" varag'ida alohida ko'rinadi.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date

from aiogram import Bot
from aiogram.types import BufferedInputFile

from bot.application.common.formatters import esc_html, format_date, format_money_map, today
from bot.application.services.debt_service import DebtService
from bot.domain.entities.period_report import PeriodReport
from bot.infrastructure.export.excel import build_file_name, build_period_workbook

logger = logging.getLogger(__name__)


async def send_daily_report(
    *,
    bot: Bot,
    debt_service: DebtService,
    channel_id: int,
    start_date: date,
    report_date: date | None = None,
    branch_code: str = "",
    branch_title: str = "",
) -> bool:
    """Kunlik hisobotni yig'ib kanalga yuboradi.

    Qaytaradi: yuborilgan bo'lsa True. Xatolik botni to'xtatmaydi — vazifa
    log'ga yozadi va keyingi kuni qaytadan urinadi.
    """
    day = report_date or today()

    if day < start_date:
        logger.warning(
            "Kunlik hisobot o'tkazib yuborildi: %s hali %s dan oldin.",
            day.isoformat(),
            start_date.isoformat(),
        )
        return False

    try:
        report = await debt_service.get_period_report(start_date, day)
        content = await asyncio.to_thread(
            build_period_workbook, report, include_day_sheet=True
        )
        file_name = build_file_name(start_date, day)
        if branch_code:
            file_name = f"{branch_code}_{file_name}"
        await bot.send_document(
            chat_id=channel_id,
            document=BufferedInputFile(content, filename=file_name),
            caption=build_caption(report, branch_title),
        )
    except Exception:
        logger.exception(
            "Kunlik hisobot yuborilmadi (filial=%s, kanal=%s, sana=%s)",
            branch_code or "-",
            channel_id,
            day.isoformat(),
        )
        return False

    logger.info(
        "Kunlik hisobot yuborildi: kanal=%s davr=%s..%s",
        channel_id,
        start_date.isoformat(),
        day.isoformat(),
    )
    return True


def build_caption(report: PeriodReport, branch_title: str = "") -> str:
    """Kanalga yuboriladigan fayl ostidagi kunlik xulosa."""
    branch_line = f"🏢 <b>Filial: {esc_html(branch_title)}</b>\n" if branch_title else ""
    return (
        f"{branch_line}"
        f"📊 <b>KUNLIK HISOBOT — {format_date(report.date_to)}</b>\n\n"
        "🆕 <b>Bugun:</b>\n"
        f"   ➕ Berilgan: {format_money_map(report.day_given)} "
        f"({report.day_new_debts} ta)\n"
        f"   ✅ Tushgan pul: {format_money_map(report.day_returned)} "
        f"({report.day_closed_debts} ta qarz yopildi)\n\n"
        f"📅 <b>Davr:</b> {format_date(report.date_from)} — "
        f"{format_date(report.date_to)}\n"
        f"   📥 Berilgan qarz: {format_money_map(report.given_total)}\n"
        f"   📤 Qaytarilgan pul: {format_money_map(report.returned_total)}\n\n"
        f"💳 <b>Jami qarzdorlik:</b> <b>{format_money_map(report.closing_debt)}</b>\n"
        f"👥 <b>Qarzdorlar:</b> {report.debtors_total} nafar"
    )
