"""Domain interfeysi: UserRepository.

Dependency Inversion — application qatlami shu abstraktsiyaga tayanadi,
konkret SQLite implementatsiyasiga emas. Test uchun soxta (fake) repo
yozish ham shu yerdan oson bo'ladi.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

from bot.domain.entities.user import User


class UserRepository(ABC):
    """Foydalanuvchilar ombori uchun shartnoma (contract)."""

    @abstractmethod
    async def add(self, user: User) -> None:
        """Yangi foydalanuvchini saqlaydi (mavjud bo'lsa — o'tkazib yuboradi)."""

    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        """Telegram ID bo'yicha foydalanuvchini qaytaradi yoki None."""
