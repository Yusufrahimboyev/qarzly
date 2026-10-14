"""Presentation qatlami: admin qo'shish FSM holati."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    waiting_id = State()
