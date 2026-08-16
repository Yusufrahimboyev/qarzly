from __future__ import annotations

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    WebAppInfo,
)


def get_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text="📱 Mini Appni ochish"),
                KeyboardButton(text="ℹ️ Yordam"),
            ]
        ],
        resize_keyboard=True,
    )


def get_web_app_inline_keyboard(web_app_url: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🚀 Mini App (Web UI)",
                    web_app=WebAppInfo(url=web_app_url),
                )
            ]
        ]
    )
