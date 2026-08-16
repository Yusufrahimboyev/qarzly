from __future__ import annotations

from aiogram import Dispatcher

from bot.presentation.handlers import start


def register_handlers(dp: Dispatcher) -> None:
    dp.include_router(start.router)
