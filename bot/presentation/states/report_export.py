"""Presentation qatlami: Excel hisobot eksporti FSM holatlari."""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class ReportExportStates(StatesGroup):
    """Hisobot sanalarini kiritish bosqichlari."""

    waiting_start_date = State()
    waiting_end_date = State()
