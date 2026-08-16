"""Domain entity: Debt.

Har bir qarz yozuvi (operatsiyasi) ning biznes modeli.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class DebtStatus(StrEnum):
    ACTIVE = "active"
    PAID = "paid"


@dataclass(frozen=True, slots=True)
class Debt:
    """Qarz operatsiyasi entity'si."""

    client_id: int
    debt_date: str
    product_name: str
    product_price: int
    original_debt: int
    remaining_debt: int
    exchange_exists: bool = False
    exchange_product_name: str | None = None
    exchange_product_price: int = 0
    given_money: int = 0
    status: DebtStatus = DebtStatus.ACTIVE
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_paid(self) -> bool:
        return self.remaining_debt <= 0 or self.status == DebtStatus.PAID
