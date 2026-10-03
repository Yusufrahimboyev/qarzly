"""Presentation qatlami: Qarz yaratish FSM holatlari.

Bir qarzda bir nechta tovar bo'lishi mumkin — tovarlar ketma-ketlikda
kiritiladi va har bir tovar o'z valyutasida (so'm/dollar) bo'ladi.
Har bir tovardan keyin "Yana tovar?" savoli beriladi.
"""
from __future__ import annotations

from aiogram.fsm.state import State, StatesGroup


class DebtCreationStates(StatesGroup):
    """Qarz yaratish bosqichlari."""

    waiting_date = State()
    waiting_date_month = State()
    waiting_date_year = State()
    waiting_client_name = State()
    waiting_client_phone = State()
    waiting_product_type = State()
    waiting_product_brand = State()
    waiting_product_size = State()
    waiting_product_quantity = State()
    waiting_product_currency = State()
    waiting_product_price = State()
    waiting_more_products = State()
    waiting_exchange_choice = State()
    waiting_exchange_currency = State()
    waiting_exchange_name = State()
    waiting_exchange_price = State()
    waiting_given_money_choice = State()
    waiting_given_currency = State()
    waiting_given_money_amount = State()
    waiting_confirm = State()
