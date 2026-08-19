"""Domain entity: Report & Summary.

Mijozning umumiy qarz holati va to'liq hisoboti uchun kompozit modellar.
Barcha pul summalari valyuta bo'yicha ajratilgan holda saqlanadi
(masalan: {"UZS": 1500000, "USD": 200}) — so'm va dollar hech qachon
qo'shib yuborilmaydi.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from bot.domain.entities.client import Client
from bot.domain.entities.debt import Debt
from bot.domain.entities.payment import Payment

MoneyMap = dict[str, int]


def empty_money() -> MoneyMap:
    return {}


@dataclass(frozen=True, slots=True)
class ClientDebtSummary:
    """Mijozning qisqa qarz holati (jadval va ro'yxat uchun)."""

    client: Client
    remaining_by_currency: MoneyMap = field(default_factory=empty_money)
    active_debts_count: int = 0
    latest_debt_date: str = ""

    @property
    def has_debt(self) -> bool:
        return any(amount > 0 for amount in self.remaining_by_currency.values())

    def remaining_in(self, currency: str) -> int:
        return self.remaining_by_currency.get(currency, 0)


@dataclass(frozen=True, slots=True)
class ClientReport:
    """Mijozning barcha qarz va to'lovlari bo'yicha to'liq hisoboti.

    Har bir total — valyutadan summaga xarita: {"UZS": n, "USD": n}.
    """

    client: Client
    debts: list[Debt]
    payments: list[Payment]
    total_product_price: MoneyMap = field(default_factory=empty_money)
    total_exchange_price: MoneyMap = field(default_factory=empty_money)
    total_given_money: MoneyMap = field(default_factory=empty_money)
    total_original_debt: MoneyMap = field(default_factory=empty_money)
    total_paid_after: MoneyMap = field(default_factory=empty_money)
    total_remaining_debt: MoneyMap = field(default_factory=empty_money)
