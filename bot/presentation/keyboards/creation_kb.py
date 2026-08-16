"""Presentation qatlami: Qarz yaratish klaviaturalari."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.application.common.formatters import today_str


def get_date_picker_keyboard() -> InlineKeyboardMarkup:
    """Sana kiritish uchun tezkor inline klaviatura."""
    today = today_str()
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📅 Bugun ({today})",
                    callback_data="create_date_today",
                )
            ],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="cancel_creation",
                )
            ],
        ]
    )


def get_back_cancel_keyboard(show_back: bool = True) -> InlineKeyboardMarkup:
    """Ortga va Bekor qilish tugmalari."""
    buttons: list[InlineKeyboardButton] = []
    if show_back:
        buttons.append(
            InlineKeyboardButton(
                text="🔙 Ortga",
                callback_data="create_back",
            )
        )
    buttons.append(
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_creation",
        )
    )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def get_currency_choice_keyboard() -> InlineKeyboardMarkup:
    """Valyuta tanlash klaviaturasi (so'm / dollar)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 So'm", callback_data="currency_uzs"),
                InlineKeyboardButton(text="$ Dollar", callback_data="currency_usd"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_exchange_choice_keyboard() -> InlineKeyboardMarkup:
    """Ayirboshlash (exchange) bor/yo'qligini tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data="exchange_yes"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="exchange_no"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_given_money_choice_keyboard() -> InlineKeyboardMarkup:
    """Dastlabki berilgan pul bor/yo'qligini tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 Pul berdi", callback_data="given_money_yes"),
                InlineKeyboardButton(text="❌ Pul bermadi", callback_data="given_money_no"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_creation_confirm_keyboard() -> InlineKeyboardMarkup:
    """Qarzni yakuniy tasdiqlash va saqlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash / Yaratish",
                    callback_data="confirm_create_debt",
                )
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )
