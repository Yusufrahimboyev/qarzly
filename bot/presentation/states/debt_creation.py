"""Presentation qatlami: Qarz yaratish FSM holatlari."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class DebtCreationStates(StatesGroup):
    """Qarz yaratish bosqichlari."""

    waiting_date = State()
    waiting_client_name = State()
    waiting_client_phone = State()
    waiting_product_name = State()
    waiting_product_price = State()
    waiting_exchange_choice = State()
    waiting_exchange_name = State()
    waiting_exchange_price = State()
    waiting_given_money_choice = State()
    waiting_given_money_amount = State()
    waiting_confirm = State()
