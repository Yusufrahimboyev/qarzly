"""Presentation qatlami: Qarz to'lovi klaviaturalari."""
from __future__ import annotations

import math

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.application.common.formatters import format_money
from bot.domain.entities.report import ClientDebtSummary


def get_debtors_list_keyboard(
    debtors: list[ClientDebtSummary],
    page: int = 1,
    per_page: int = 8,
) -> InlineKeyboardMarkup:
    """To'lov qilish uchun faqat qarzi bor mijozlar ro'yxati."""
    keyboard: list[list[InlineKeyboardButton]] = []

    if not debtors:
        return InlineKeyboardMarkup(inline_keyboard=[])

    total_pages = max(1, math.ceil(len(debtors) / per_page))
    current_page = max(1, min(page, total_pages))

    start_idx = (current_page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = debtors[start_idx:end_idx]

    for summary in page_items:
        client = summary.client
        if client.id is None:
            continue

        btn_text = f"🔴 {client.full_name} — {format_money(summary.total_remaining_debt)}"
        keyboard.append([
            InlineKeyboardButton(
                text=btn_text,
                callback_data=f"select_pay_client:{client.id}",
            )
        ])

    nav_buttons: list[InlineKeyboardButton] = []
    if current_page > 1:
        nav_buttons.append(
            InlineKeyboardButton(
                text="⬅️ Oldingi",
                callback_data=f"pay_page:{current_page - 1}",
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
                callback_data=f"pay_page:{current_page + 1}",
            )
        )

    keyboard.append(nav_buttons)
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_payment_type_keyboard(client_id: int, total_remaining: int) -> InlineKeyboardMarkup:
    """Qarzni to'liq yoki qisman to'lash tanlovi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"🟢 Qarzini to'liq yopish ({format_money(total_remaining)})",
                    callback_data=f"pay_mode_full:{client_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🟡 Ma'lum miqdorini to'lash",
                    callback_data=f"pay_mode_partial:{client_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔙 Ortga",
                    callback_data="back_to_pay_debtors",
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="cancel_payment",
                ),
            ],
        ]
    )


def get_payment_back_cancel_keyboard(client_id: int) -> InlineKeyboardMarkup:
    """To'lov kiritishdagi Ortga va Bekor qilish tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔙 Ortga",
                    callback_data=f"select_pay_client:{client_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="cancel_payment",
                ),
            ]
        ]
    )
