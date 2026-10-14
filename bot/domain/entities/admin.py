"""Domain entity: Admin.

Botdan foydalana oladigan Telegram foydalanuvchisi. `.env` dagi ADMIN_IDS —
asosiy adminlar (o'chirib bo'lmaydi); qolganlari bazada saqlanadi va uchala
filial botiga birdek amal qiladi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class Admin:
    telegram_id: int
    full_name: str = ""
    is_root: bool = False
    added_by: int | None = None
    created_at: datetime | None = None
