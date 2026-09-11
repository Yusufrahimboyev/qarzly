"""Presentation qatlami: Excel hisobot eksporti handler'lari.

Foydalanuvchi "📊 Excel hisobot" tugmasini bosadi, ikkita sana kiritadi
(boshlanish va tugash), natijada shu oraliq — ikkala chegara ham kiradi —
bo'yicha .xlsx fayl yuboriladi.

Fayl diskka yozilmaydi: `build_period_workbook` baytlarni qaytaradi va ular
to'g'ridan-to'g'ri `BufferedInputFile` orqali Telegram'ga uzatiladi.
"""
from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from bot.application.common.formatters import (
    format_date,
    format_money_map,
    parse_date,
    today,
    today_str,
)
from bot.application.common.period_report import validate_period_bounds
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.domain.entities.period_report import PeriodReport
from bot.infrastructure.export.excel import build_file_name, build_period_workbook
from bot.presentation.keyboards.debt_table_kb import get_export_date_keyboard
from bot.presentation.keyboards.main_menu_kb import get_main_menu_keyboard
from bot.presentation.states.report_export import ReportExportStates

logger = logging.getLogger(__name__)

router = Router()

_START_PROMPT = (
    "📊 <b>EXCEL HISOBOT</b>\n\n"
    "📅 <b>Boshlanish sanasini kiriting:</b>\n\n"
    "<i>Masalan: 01.01.2026</i>"
)

_DATE_HELP = (
    "\n\n<i>Qo'llab-quvvatlanadigan formatlar: 01.01.2026, 01/01/2026, "
    "2026-01-01</i>"
)


# ==========================================
# 0. Boshlash va bekor qilish
# ==========================================


@router.callback_query(F.data == "export_start")
async def cb_export_start(callback: CallbackQuery, state: FSMContext) -> None:
    """Hisobot sanalarini so'rashni boshlaydi."""
    await state.set_state(ReportExportStates.waiting_start_date)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _START_PROMPT,
            reply_markup=get_export_date_keyboard(with_today=False),
        )
    await callback.answer()


@router.callback_query(F.data == "cancel_export")
async def cb_cancel_export(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    """Hisobot jarayonini bekor qiladi."""
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("❌ <b>Hisobot bekor qilindi.</b>")
        await callback.message.answer(
            "Asosiy menyu:",
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )
    await callback.answer()


# ==========================================
# 1. Boshlanish sanasi
# ==========================================


@router.message(ReportExportStates.waiting_start_date)
async def process_start_date(message: Message, state: FSMContext) -> None:
    """Boshlanish sanasini qabul qiladi."""
    parsed = parse_date(message.text or "")

    if parsed is None:
        await message.answer(
            "❌ <b>Sana formati noto'g'ri.</b>" + _DATE_HELP,
            reply_markup=get_export_date_keyboard(with_today=False),
        )
        return

    if parsed > today():
        await message.answer(
            "❌ <b>Boshlanish sanasi bugundan keyin bo'lishi mumkin emas.</b>\n"
            f"Eng kech sana: <b>{today_str()}</b>",
            reply_markup=get_export_date_keyboard(with_today=False),
        )
        return

    await state.update_data(date_from=parsed.isoformat())
    await state.set_state(ReportExportStates.waiting_end_date)

    await message.answer(
        f"✅ <b>Boshlanish sanasi:</b> {format_date(parsed)}\n\n"
        "📅 <b>Tugash sanasini kiriting:</b>\n\n"
        f"<i>Bugundan keyingi sana kiritib bo'lmaydi (eng kech: {today_str()})</i>",
        reply_markup=get_export_date_keyboard(with_today=True),
    )


# ==========================================
# 2. Tugash sanasi va faylni yuborish
# ==========================================


@router.callback_query(
    F.data == "export_date_today",
    ReportExportStates.waiting_end_date,
)
async def cb_export_date_today(
    callback: CallbackQuery,
    state: FSMContext,
    debt_service: DebtService,
) -> None:
    """"Bugun" tugmasi orqali tugash sanasini belgilaydi."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    await callback.answer()
    await _finish(
        message=callback.message,
        state=state,
        debt_service=debt_service,
        raw_date=today_str(),
        edit_source=callback.message,
    )


@router.message(ReportExportStates.waiting_end_date)
async def process_end_date(
    message: Message,
    state: FSMContext,
    debt_service: DebtService,
) -> None:
    """Tugash sanasini qabul qiladi va hisobotni yuboradi."""
    await _finish(
        message=message,
        state=state,
        debt_service=debt_service,
        raw_date=message.text or "",
    )


async def _finish(
    *,
    message: Message,
    state: FSMContext,
    debt_service: DebtService,
    raw_date: str,
    edit_source: Message | None = None,
) -> None:
    """Tugash sanasini tekshiradi, hisobotni yig'adi va faylni yuboradi."""
    parsed = parse_date(raw_date)

    if parsed is None:
        await message.answer(
            "❌ <b>Sana formati noto'g'ri.</b>" + _DATE_HELP,
            reply_markup=get_export_date_keyboard(with_today=True),
        )
        return

    data = await state.get_data()
    raw_from = data.get("date_from")
    if not raw_from:
        # FSM ma'lumoti yo'qolgan (bot qayta ishga tushgan) — boshidan.
        await state.clear()
        await message.answer(
            "⚠️ <b>Sessiya eskirgan.</b> Hisobotni qaytadan boshlang: "
            "<b>📋 Qarzlar jadvali</b> → <b>📊 Excel hisobot</b>."
        )
        return

    date_from = parse_date(raw_from)
    assert date_from is not None  # ISO formatda o'zimiz yozganmiz

    error = validate_period_bounds(date_from, parsed, today())
    if error is not None:
        await message.answer(
            f"❌ <b>{error}</b>",
            reply_markup=get_export_date_keyboard(with_today=True),
        )
        return

    await state.clear()

    if edit_source is not None:
        await edit_source.edit_text(
            f"⏳ <b>Hisobot tayyorlanmoqda...</b>\n\n"
            f"📅 {format_date(date_from)} — {format_date(parsed)}"
        )
        status: Message | None = None
    else:
        status = await message.answer(
            f"⏳ <b>Hisobot tayyorlanmoqda...</b>\n\n"
            f"📅 {format_date(date_from)} — {format_date(parsed)}"
        )

    try:
        report = await debt_service.get_period_report(date_from, parsed)
        # openpyxl sinxron ishlaydi va katta davrda sekin bo'lishi mumkin —
        # event loop'ni bloklamaslik uchun alohida thread'da bajariladi.
        content = await asyncio.to_thread(build_period_workbook, report)
    except Exception:
        logger.exception(
            "Excel hisobot tayyorlanmadi: %s — %s",
            date_from.isoformat(),
            parsed.isoformat(),
        )
        await message.answer(
            "❌ <b>Hisobotni tayyorlashda xatolik yuz berdi.</b>\n"
            "Birozdan so'ng qayta urinib ko'ring."
        )
        return

    await message.answer_document(
        BufferedInputFile(content, filename=build_file_name(date_from, parsed)),
        caption=_caption(report),
    )

    if status is not None:
        await status.delete()


def _caption(report: PeriodReport) -> str:
    """Fayl ostidagi qisqacha xulosa."""
    return (
        "📊 <b>QARZ HISOBOTI</b>\n\n"
        f"📅 <b>Davr:</b> {format_date(report.date_from)} — "
        f"{format_date(report.date_to)}\n\n"
        f"📥 <b>Berilgan qarz:</b> {format_money_map(report.given_total)}\n"
        f"📤 <b>Qaytarilgan pul:</b> {format_money_map(report.returned_total)}\n"
        f"💳 <b>Davr oxiridagi qarzdorlik:</b> "
        f"<b>{format_money_map(report.closing_debt)}</b>\n\n"
        f"👥 <b>Qarzdorlar:</b> {report.debtors_total} nafar\n"
        f"🧾 <b>Qarz yozuvlari:</b> {len(report.debts)} ta"
    )
