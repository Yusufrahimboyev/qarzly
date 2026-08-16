"""Domain entity: Report & Summary.

Mijozning umumiy qarz holati va to'liq hisoboti uchun kompozit modellar.
"""
from __future__ import annotations

from dataclasses import dataclass

from bot.domain.entities.client import Client
from bot.domain.entities.debt import Debt
from bot.domain.entities.payment import Payment


@dataclass(frozen=True, slots=True)
class ClientDebtSummary:
    """Mijozning qisqa qarz holati (jadval va ro'yxat uchun)."""

    client: Client
    total_remaining_debt: int
    active_debts_count: int

    @property
    def has_debt(self) -> bool:
        return self.total_remaining_debt > 0


@dataclass(frozen=True, slots=True)
class ClientReport:
    """Mijozning barcha qarz va to'lovlari bo'yicha to'liq hisoboti."""

    client: Client
    debts: list[Debt]
    payments: list[Payment]
    total_product_price: int
    total_exchange_price: int
    total_given_money: int
    total_original_debt: int
    total_paid_after: int
    total_remaining_debt: int
