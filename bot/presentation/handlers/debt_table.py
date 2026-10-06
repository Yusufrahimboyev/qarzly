"""Presentation qatlami: Qarzlar jadvali va mijozlar hisoboti handler'lari."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import (
    aggregate_remaining,
    esc_html,
    format_date,
    format_money,
    format_money_map,
)
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import DebtStatus
from bot.domain.entities.payment import PaymentType
from bot.domain.entities.report import ClientReport
from bot.i18n import _, all_variants
from bot.infrastructure.branches import Branch
from bot.presentation.common.messaging import split_message
from bot.presentation.keyboards.debt_table_kb import (
    get_client_report_keyboard,
    get_debt_table_keyboard,
)
from bot.presentation.keyboards.main_menu_kb import TABLE_BUTTON_TEXT

router = Router()


def _table_header(summaries) -> str:
    """Jadval sarlavhasini (statistikasi) valyutalar bo'yicha shakllantiradi."""
    debtors_count = sum(1 for s in summaries if s.has_debt)
    total_market_debt = aggregate_remaining(summaries)
    return (
        _(
            "👥 <b>Jami mijozlar:</b> {clients} ta\n"
            "🔴 <b>Qarzdorlar:</b> {debtors} ta\n"
            "💳 <b>Jami qoldiq qarz:</b> <b>{total}</b>",
            clients=len(summaries),
            debtors=debtors_count,
            total=format_money_map(total_market_debt),
        )
    )


@router.message(F.text.in_(all_variants(TABLE_BUTTON_TEXT)))
async def show_debt_table_msg(
    message: Message,
    client_service: ClientService,
    state: FSMContext,
    branch: Branch,
) -> None:
    """Qarzlar jadvalini birinchi sahifadan ko'rsatadi."""
    await state.clear()
    summaries = await client_service.get_all_summaries()

    if not summaries:
        await message.answer(_(
            "📋 <b>Qarzlar jadvali bo'sh.</b>\n\n"
            "Hali hech qanday mijoz yoki qarz kiritilmagan.\n"
            "Yangi qarz qo'shish uchun <b>➕ Yaratish</b> tugmasini bosing."
        ))
        return

    await message.answer(
        _("🏢 <b>Filial:</b> {branch}", branch=esc_html(branch.title)) + "\n"
        + _table_header(summaries),
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
        await callback.answer(_("Ro'yxat bo'sh."), show_alert=True)
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
    state: FSMContext,
) -> None:
    """Batafsil hisobotdan orqaga jadvalga qaytish.

    Jadvalga qaytish boshlangan har qanday jarayonni (masalan Excel hisobot
    sanalarini kiritish) yakunlaydi — aks holda FSM holati osilib qolar va
    keyingi oddiy xabar o'sha jarayonga tushib ketardi.
    """
    await state.clear()

    if not isinstance(callback.message, Message):
        return

    summaries = await client_service.get_all_summaries()
    if not summaries:
        await callback.message.edit_text(_("📋 Qarzlar jadvali bo'sh."))
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
        await callback.answer(_("Mijoz topilmadi."), show_alert=True)
        return

    text = _render_report(report)
    keyboard = get_client_report_keyboard(client_id, has_debt=_has_debt(report))
    chunks = split_message(text)

    # Uzun tarixli mijozda hisobot Telegram chegarasidan (4096 belgi) oshadi —
    # bunda xabar bo'laklarga bo'linadi, tugmalar oxirgi bo'lakda bo'ladi.
    await callback.message.edit_text(chunks[0], reply_markup=None if len(chunks) > 1 else keyboard)
    for idx, chunk in enumerate(chunks[1:], start=1):
        await callback.message.answer(
            chunk,
            reply_markup=keyboard if idx == len(chunks) - 1 else None,
        )
    await callback.answer()


def _has_debt(report: ClientReport) -> bool:
    return any(amount > 0 for amount in report.total_remaining_debt.values())


def _render_report(report: ClientReport) -> str:
    """Mijoz hisoboti matnini valyutalar ajratilgan holda shakllantiradi."""
    client = report.client

    lines: list[str] = [
        _("👤 <b>MIJOZ HISOBOTI:</b> <b>{name}</b>", name=esc_html(client.full_name)),
        _("📞 <b>Telefon:</b> {phone}", phone=esc_html(client.phone)),
        "━━━━━━━━━━━━━━━━━━━━",
        _("<b>📦 QARZLAR TARIXI:</b>"),
    ]

    if not report.debts:
        lines.append(_("<i>Qarzlar mavjud emas.</i>"))
    else:
        for idx, d in enumerate(report.debts, start=1):
            status_icon = "🔴" if d.status == DebtStatus.ACTIVE else "🟢"
            status_text = _("Qarzdor") if d.status == DebtStatus.ACTIVE else _("Yopilgan")

            lines.append(
                f"\n<b>{idx}. {format_date(d.debt_date)} — "
                f"{status_icon} {status_text}</b>"
            )

            # Ko'p tovarli bo'lsa har bir tovarni alohida ko'rsatamiz
            if len(d.products) > 1:
                for p_idx, p in enumerate(d.products, start=1):
                    p_cur = Currency(p.currency)
                    if p.quantity > 1:
                        lines.append(
                            f"  • {p_idx}) <b>{esc_html(p.name)}</b> — {p.quantity} × "
                            f"{format_money(p.price_per_unit, p_cur)} = "
                            f"{format_money(p.total_price, p_cur)}"
                        )
                    else:
                        lines.append(
                            f"  • {p_idx}) <b>{esc_html(p.name)}</b> — "
                            f"{format_money(p.price_per_unit, p_cur)}"
                        )
            else:
                lines.append(_(
                    "  • Tovar: <b>{name}</b> — {quantity} ta",
                    name=esc_html(d.product_name),
                    quantity=d.product_quantity,
                ))
            lines.append(_(
                "  • Narxi (jami): {amount}", amount=format_money(d.product_price, d.currency)
            ))

            if d.exchange_exists:
                lines.append(_(
                    "  • Exchange: <i>{name}</i> ({amount})",
                    name=esc_html(d.exchange_product_name or _("Tovar")),
                    amount=format_money(d.exchange_product_price, d.currency),
                ))

            if d.given_money > 0:
                lines.append(_(
                    "  • Berilgan pul: {amount}", amount=format_money(d.given_money, d.currency)
                ))

            lines.append(_(
                "  • Asl qarz: {amount}", amount=format_money(d.original_debt, d.currency)
            ))
            lines.append(_(
                "  • Qoldiq: <b>{amount}</b>", amount=format_money(d.remaining_debt, d.currency)
            ))

    # To'lovlar tarixi
    actual_payments = [p for p in report.payments if p.payment_type != PaymentType.INITIAL]
    if actual_payments:
        lines.append("\n━━━━━━━━━━━━━━━━━━━━")
        lines.append(_("<b>💰 TO'LOVLAR TARIXI:</b>"))
        for idx, pay in enumerate(actual_payments, start=1):
            p_type_label = _("To'liq") if pay.payment_type == PaymentType.FULL else _("Qisman")
            pay_str = format_money(pay.amount, pay.currency)
            lines.append(
                f"{idx}. {format_date(pay.payment_date)}: +{pay_str} ({p_type_label})"
            )

    # Yakuniy umumiy hisob — har bir total valyutalar bo'yicha
    lines.append("\n━━━━━━━━━━━━━━━━━━━━")
    lines.append(_("<b>📊 UMUMIY HISOB-KITOB:</b>"))
    lines.append(_(
        "• Jami tovarlar: {amount}", amount=format_money_map(report.total_product_price)
    ))
    if any(v > 0 for v in report.total_exchange_price.values()):
        lines.append(_(
            "• Jami exchange: -{amount}", amount=format_money_map(report.total_exchange_price)
        ))
    if any(v > 0 for v in report.total_given_money.values()):
        lines.append(_(
            "• Dastlabki to'langan: -{amount}",
            amount=format_money_map(report.total_given_money),
        ))
    lines.append(_(
        "• Jami asl qarz: {amount}", amount=format_money_map(report.total_original_debt)
    ))
    if any(v > 0 for v in report.total_paid_after.values()):
        lines.append(_(
            "• Keyin to'langan: -{amount}", amount=format_money_map(report.total_paid_after)
        ))

    lines.append("────────────────────")
    if _has_debt(report):
        lines.append(_(
            "💳 <b>HOZIRGI QARZ:</b> <b>🔴 {amount}</b>",
            amount=format_money_map(report.total_remaining_debt),
        ))
    else:
        lines.append(_("💳 <b>HOZIRGI QARZ:</b> <b>🟢 0 (Qarz yo'q)</b>"))

    return "\n".join(lines)
