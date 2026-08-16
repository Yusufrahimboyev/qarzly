"""Presentation qatlami: Qarzlar jadvali inline klaviaturalari."""
from __future__ import annotations

import math

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.application.common.formatters import clip_button_text, format_money_map
from bot.domain.entities.report import ClientDebtSummary


def get_debt_table_keyboard(
    summaries: list[ClientDebtSummary],
    page: int = 1,
    per_page: int = 8,
) -> InlineKeyboardMarkup:
    """Mijozlar ro'yxatini sahifalangan (pagination) inline tugmalar ko'rinishida qaytaradi."""
    keyboard: list[list[InlineKeyboardButton]] = []

    if not summaries:
        return InlineKeyboardMarkup(inline_keyboard=[])

    total_pages = max(1, math.ceil(len(summaries) / per_page))
    current_page = max(1, min(page, total_pages))

    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = summaries[start_idx:end_idx]

    # Har bir mijoz uchun alohida qatorda tugma
    for summary in page_items:
        client = summary.client
        if client.id is None:
            continue

        if summary.has_debt:
            btn_text = (
                f"🔴 {client.full_name} — "
                f"{format_money_map(summary.remaining_by_currency)}"
            )
        else:
            btn_text = f"🟢 {client.full_name} — Qarz yo'q"

        keyboard.append([
            InlineKeyboardButton(
                text=clip_button_text(btn_text),
                callback_data=f"client_report:{client.id}",
            )
        ])

    # Navigatsiya / sahifalash tugmalari
    nav_buttons: list[InlineKeyboardButton] = []
    if current_page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"debt_page:{current_page - 1}",
            )
        )

    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 {current_page}/{total_pages}",
            callback_data="noop",
        )
    )

    if current_page < total_pages:
        nav_buttons.append(
            InlineKeyboardButton(
                text="Keyingi ➡️",
                callback_data=f"debt_page:{current_page + 1}",
            )
        )

    keyboard.append(nav_buttons)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_client_report_keyboard(client_id: int, has_debt: bool) -> InlineKeyboardMarkup:
    """Mijoz hisoboti ekrani uchun inline tugmalar."""
    buttons: list[list[InlineKeyboardButton]] = []

    buttons.append([
        InlineKeyboardButton(
            text="➕ Yana qarz qo'shish",
            callback_data=f"add_debt_for_client:{client_id}",
        )
    ])

    if has_debt:
        buttons.append([
            InlineKeyboardButton(
                text="💰 Qarzni to'lash",
                callback_data=f"select_pay_client:{client_id}",
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔙 Ro'yxatga qaytish",
            callback_data="back_to_debt_table",
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
