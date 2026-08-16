"""Presentation qatlami: Qarzlar jadvali va mijozlar hisoboti handler'lari."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import (
    aggregate_remaining,
    format_money,
    format_money_map,
)
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.domain.entities.debt import DebtStatus
from bot.domain.entities.payment import PaymentType
from bot.domain.entities.report import ClientReport
from bot.presentation.keyboards.debt_table_kb import (
    get_client_report_keyboard,
    get_debt_table_keyboard,
)

router = Router()


def _table_header(summaries) -> str:
    """Jadval sarlavhasini (statistikasi) valyutalar bo'yicha shakllantiradi."""
    debtors_count = sum(1 for s in summaries if s.has_debt)
    total_market_debt = aggregate_remaining(summaries)
    return (
        "📋 <b>Qarzlar jadvali (Alifbo bo'yicha):</b>\n\n"
        f"👥 <b>Jami mijozlar:</b> {len(summaries)} ta\n"
        f"🔴 <b>Qarzdorlar:</b> {debtors_count} ta\n"
        f"💳 <b>Jami qoldiq qarz:</b> <b>{format_money_map(total_market_debt)}</b>\n\n"
        "<i>Batafsil hisobotni ko'rish uchun mijoz ustiga bosing:</i>"
    )


@router.message(F.text == "📋 Qarzlar jadvali")
async def show_debt_table_msg(
    message: Message,
    client_service: ClientService,
    state: FSMContext,
) -> None:
    """Qarzlar jadvalini birinchi sahifadan ko'rsatadi."""
    await state.clear()
    summaries = await client_service.get_all_summaries()

    if not summaries:
        await message.answer(
            "📋 <b>Qarzlar jadvali bo'sh.</b>\n\n"
            "Hali hech qanday mijoz yoki qarz kiritilmagan.\n"
            "Yangi qarz qo'shish uchun <b>➕ Yaratish</b> tugmasini bosing."
        )
        return

    await message.answer(
        _table_header(summaries),
        reply_markup=get_debt_table_keyboard(summaries, page=1),
    )


@router.callback_query(F.data.startswith("debt_page:"))
async def cb_debt_page(
    callback: CallbackQuery,
    client_service: ClientService,
) -> None:
    """Jadval sahifasini almashtiradi."""
    if callback.data is None or not isinstance(callback.message, Message):
        return

    page = int(callback.data.split(":")[1])
    summaries = await client_service.get_all_summaries()
    if not summaries:
        await callback.answer("Ro'yxat bo'sh.", show_alert=True)
        return

    await callback.message.edit_text(
        _table_header(summaries),
        reply_markup=get_debt_table_keyboard(summaries, page=page),
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_debt_table")
async def cb_back_to_debt_table(
    callback: CallbackQuery,
    client_service: ClientService,
) -> None:
    """Batafsil hisobotdan orqaga jadvalga qaytish."""
    if not isinstance(callback.message, Message):
        return

    summaries = await client_service.get_all_summaries()
    if not summaries:
        await callback.message.edit_text("📋 Qarzlar jadvali bo'sh.")
        await callback.answer()
        return

    await callback.message.edit_text(
        _table_header(summaries),
        reply_markup=get_debt_table_keyboard(summaries, page=1),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("client_report:"))
async def cb_client_report(
    callback: CallbackQuery,
    debt_service: DebtService,
) -> None:
    """Tanlangan mijozning to'liq qarz va to'lovlar hisobotini ko'rsatadi."""
    if callback.data is None or not isinstance(callback.message, Message):
        return

    client_id = int(callback.data.split(":")[1])
    try:
        report = await debt_service.get_client_report(client_id)
    except ValueError:
        await callback.answer("Mijoz topilmadi.", show_alert=True)
        return

    text = _render_report(report)
    await callback.message.edit_text(
        text,
        reply_markup=get_client_report_keyboard(client_id, has_debt=_has_debt(report)),
    )
    await callback.answer()


def _has_debt(report: ClientReport) -> bool:
    return any(amount > 0 for amount in report.total_remaining_debt.values())


def _render_report(report: ClientReport) -> str:
    """Mijoz hisoboti matnini valyutalar ajratilgan holda shakllantiradi."""
    client = report.client

    lines: list[str] = [
        f"👤 <b>MIJOZ HISOBOTI:</b> <b>{client.full_name}</b>",
        f"📞 <b>Telefon:</b> {client.phone}",
        "━━━━━━━━━━━━━━━━━━━━",
        "<b>📦 QARZLAR TARIXI:</b>",
    ]

    if not report.debts:
        lines.append("<i>Qarzlar mavjud emas.</i>")
    else:
        for idx, d in enumerate(report.debts, start=1):
            status_icon = "🔴" if d.status == DebtStatus.ACTIVE else "🟢"
            status_text = "Qarzdor" if d.status == DebtStatus.ACTIVE else "Yopilgan"

            lines.append(f"\n<b>{idx}. {d.debt_date} — {status_icon} {status_text}</b>")
            lines.append(f"  • Tovar: <b>{d.product_name}</b> — {d.product_quantity} ta")
            lines.append(f"  • Narxi (jami): {format_money(d.product_price, d.currency)}")

            if d.exchange_exists:
                lines.append(
                    f"  • Exchange: <i>{d.exchange_product_name or 'Tovar'}</i> "
                    f"({format_money(d.exchange_product_price, d.currency)})"
                )

            if d.given_money > 0:
                lines.append(f"  • Berilgan pul: {format_money(d.given_money, d.currency)}")

            lines.append(f"  • Asl qarz: {format_money(d.original_debt, d.currency)}")
            lines.append(f"  • Qoldiq: <b>{format_money(d.remaining_debt, d.currency)}</b>")

    # To'lovlar tarixi
    actual_payments = [p for p in report.payments if p.payment_type != PaymentType.INITIAL]
    if actual_payments:
        lines.append("\n━━━━━━━━━━━━━━━━━━━━")
        lines.append("<b>💰 TO'LOVLAR TARIXI:</b>")
        for idx, p in enumerate(actual_payments, start=1):
            p_type_label = "To'liq" if p.payment_type == PaymentType.FULL else "Qisman"
            lines.append(
                f"{idx}. {p.payment_date}: +{format_money(p.amount, p.currency)} ({p_type_label})"
            )

    # Yakuniy umumiy hisob — har bir total valyutalar bo'yicha
    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append("<b>📊 UMUMIY HISOB-KITOB:</b>")
    lines.append(f"• Jami tovarlar: {format_money_map(report.total_product_price)}")
    if any(v > 0 for v in report.total_exchange_price.values()):
        lines.append(f"• Jami exchange: -{format_money_map(report.total_exchange_price)}")
    if any(v > 0 for v in report.total_given_money.values()):
        lines.append(f"• Dastlabki to'langan: -{format_money_map(report.total_given_money)}")
    lines.append(f"• Jami asl qarz: {format_money_map(report.total_original_debt)}")
    if any(v > 0 for v in report.total_paid_after.values()):
        lines.append(f"• Keyin to'langan: -{format_money_map(report.total_paid_after)}")

    lines.append("────────────────────")
    if _has_debt(report):
        lines.append(
            f"💳 <b>HOZIRGI QARZ:</b> <b>🔴 {format_money_map(report.total_remaining_debt)}</b>"
        )
    else:
        lines.append("💳 <b>HOZIRGI QARZ:</b> <b>🟢 0 (Qarz yo'q)</b>")

    return "\n".join(lines)
