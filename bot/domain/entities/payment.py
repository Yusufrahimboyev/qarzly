"""Domain entity: Payment.

To'lovlar (to'liq, qisman yoki dastlabki berilgan pul) yozuvi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class PaymentType(StrEnum):
    FULL = "full"
    PARTIAL = "partial"
    INITIAL = "initial"


@dataclass(frozen=True, slots=True)
class Payment:
    """To'lov tranzaksiyasi entity'si."""

    client_id: int
    amount: int
    payment_type: PaymentType
    payment_date: str
    debt_id: int | None = None
    id: int | None = None
    created_at: datetime | None = None
