"""Presentation qatlami: Asosiy menyu klaviaturasi."""
from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)

BRANCH_BUTTON_TEXT = "🏢 Filial"


def get_main_menu_keyboard(web_app_url: str = "") -> ReplyKeyboardMarkup:
    """Asosiy menyu tugmalari:
    1. 📋 Qarzlar jadvali
    2. ➕ Yaratish
    3. 💰 Qarz to'lovi
    4. 🏢 Filial (almashtirish)
    5. 🚀 Mini App (agar URL sozlangan bo'lsa)
    """
    rows: list[list[KeyboardButton]] = [
        [
            KeyboardButton(text="📋 Qarzlar jadvali"),
        ],
        [
            KeyboardButton(text="➕ Yaratish"),
            KeyboardButton(text="💰 Qarz to'lovi"),
        ],
        [
            KeyboardButton(text=BRANCH_BUTTON_TEXT),
        ],
    ]

    if web_app_url:
        rows.append([
            KeyboardButton(
                text="🚀 Mini App (Web UI)",
                web_app=WebAppInfo(url=web_app_url),
            )
        ])

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
    )


def get_web_app_inline_keyboard(web_app_url: str) -> InlineKeyboardMarkup:
    """Mini App'ni ochuvchi inline klaviatura."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Qarz Daftar Mini App",
                    web_app=WebAppInfo(url=web_app_url),
                )
            ]
        ]
    )


def get_branch_keyboard(
    branches: list[tuple[str, str]], current: str
) -> InlineKeyboardMarkup:
    """Filial tanlash inline klaviaturasi: [(kod, nom)], joriysi ✅ bilan."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"✅ {title}" if code == current else title,
                    callback_data=f"branch:{code}",
                )
                for code, title in branches
            ]
        ]
    )
