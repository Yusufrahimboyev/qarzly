"""Presentation qatlami: barcha handler router'larini ro'yxatga olish."""
from __future__ import annotations

from aiogram import Dispatcher

from bot.presentation.handlers import (
    debt_creation,
    debt_payment,
    debt_table,
    start,
)


def register_handlers(dp: Dispatcher) -> None:
    """Barcha router'larni Dispatcher'ga ulaydi."""
    dp.include_router(start.router)
    dp.include_router(debt_table.router)
    dp.include_router(debt_creation.router)
    dp.include_router(debt_payment.router)
