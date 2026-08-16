"""Presentation qatlami: Qarz to'lovi FSM holatlari."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class DebtPaymentStates(StatesGroup):
    """Qarz to'lash bosqichlari."""

    selecting_client = State()
    selecting_payment_type = State()
    waiting_partial_amount = State()
    waiting_confirm = State()
