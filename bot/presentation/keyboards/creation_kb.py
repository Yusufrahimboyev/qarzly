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


def get_product_currency_keyboard() -> InlineKeyboardMarkup:
    """Tovar valyutasi tanlash klaviaturasi (har tovar alohida)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 So'm", callback_data="prodcur_uzs"),
                InlineKeyboardButton(text="$ Dollar", callback_data="prodcur_usd"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_exchange_currency_keyboard() -> InlineKeyboardMarkup:
    """Exchange tovari valyutasi tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 So'm", callback_data="excur_uzs"),
                InlineKeyboardButton(text="$ Dollar", callback_data="excur_usd"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_given_currency_keyboard() -> InlineKeyboardMarkup:
    """Berilgan pul valyutasi tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 So'm", callback_data="gcur_uzs"),
                InlineKeyboardButton(text="$ Dollar", callback_data="gcur_usd"),
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


def get_more_products_keyboard() -> InlineKeyboardMarkup:
    """'Yana tovar qo'shasizmi?' klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Yana tovar qo'shish",
                    callback_data="more_products_yes",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Shu enough, keyingi",
                    callback_data="more_products_no",
                ),
            ],
            [
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
