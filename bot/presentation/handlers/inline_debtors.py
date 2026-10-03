"""Presentation qatlami: inline rejimda qarzdorlar ro'yxati.

Istalgan chatda `@bot_username Aziz` deb yozilsa, tanlangan filialdagi
qarzdorlar (ism yoki telefon bo'yicha) chiqadi; tanlanganda chatga mijozning
qisqa qarz kartasi yuboriladi. Faqat adminlar uchun (AdminMiddleware).
"""
from __future__ import annotations

from aiogram import Router
from aiogram.types import InlineQuery, InlineQueryResultArticle, InputTextMessageContent

from bot.application.common.formatters import esc_html, format_date, format_money_map
from bot.application.services.client_service import ClientService
from bot.domain.entities.report import ClientDebtSummary
from bot.infrastructure.branches import Branch

router = Router()

# Telegram bitta javobda ko'pi bilan 50 ta natija qabul qiladi.
PAGE_SIZE = 50


@router.inline_query()
async def inline_debtors(
    query: InlineQuery,
    client_service: ClientService,
    branch: Branch,
) -> None:
    """Qarzdorlarni qidiradi va sahifalab qaytaradi."""
    needle = query.query.strip().lower()
    debtors = await client_service.get_debtor_summaries()
    if needle:
        debtors = [
            s for s in debtors
            if needle in s.client.full_name.lower() or needle in s.client.phone
        ]

    offset = int(query.offset) if query.offset.isdigit() else 0
    page = debtors[offset:offset + PAGE_SIZE]
    next_offset = str(offset + PAGE_SIZE) if offset + PAGE_SIZE < len(debtors) else ""

    # is_personal + cache_time=0: Telegram natijani boshqa foydalanuvchilarga
    # keshdan ko'rsatib yubormasligi uchun.
    await query.answer(
        [_result(s, branch) for s in page if s.client.id is not None],
        cache_time=0,
        is_personal=True,
        next_offset=next_offset,
    )


def _result(summary: ClientDebtSummary, branch: Branch) -> InlineQueryResultArticle:
    client = summary.client
    remaining = format_money_map(summary.remaining_by_currency)
    return InlineQueryResultArticle(
        id=str(client.id),
        title=f"🔴 {client.full_name} — {remaining}",
        description=client.phone or "Telefon yo'q",
        input_message_content=InputTextMessageContent(message_text=_card(summary, branch)),
    )


def _card(summary: ClientDebtSummary, branch: Branch) -> str:
    """Chatga yuboriladigan qisqa qarz kartasi."""
    client = summary.client
    lines = [
        f"👤 <b>{esc_html(client.full_name)}</b>",
        f"🏢 <b>Filial:</b> {esc_html(branch.title)}",
    ]
    if client.phone:
        lines.append(f"📞 <b>Telefon:</b> {esc_html(client.phone)}")
    lines.append(
        f"💳 <b>Qoldiq qarz:</b> <b>{format_money_map(summary.remaining_by_currency)}</b>"
    )
    if summary.latest_debt_date is not None:
        lines.append(f"📅 <b>Oxirgi qarz:</b> {format_date(summary.latest_debt_date)}")
    return "\n".join(lines)
