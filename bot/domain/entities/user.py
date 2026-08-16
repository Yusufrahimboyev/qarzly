"""Domain entity: User.

Bu obyekt hech qanday framework yoki DB texnologiyasiga bog'liq emas — sof
biznes tushunchasi. Infratuzilma qatlami (SQLite) shu entity'ga o'giriladi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class User:
    """Ro'yxatdan o'tgan foydalanuvchi."""

    telegram_id: int
    full_name: str
    username: str | None = None
    id: int | None = None
    created_at: datetime | None = None
