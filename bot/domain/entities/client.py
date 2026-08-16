"""Domain entity: Client.

Mijoz tushunchasi (sof biznes obyekti).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Client:
    """Qarz oluvchi mijoz."""

    full_name: str
    phone: str
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
