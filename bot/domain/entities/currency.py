"""Domain entity: Currency.

Qarz va to'lovlarning valyutasi. Summalar hech qachon valyutalarsiz
qo'shib hisoblanmaydi — so'm va dollar alohida saqlanadi.
"""
from __future__ import annotations

from enum import StrEnum


class Currency(StrEnum):
    UZS = "UZS"
    USD = "USD"


SUPPORTED_CURRENCIES: tuple[Currency, ...] = (Currency.UZS, Currency.USD)
