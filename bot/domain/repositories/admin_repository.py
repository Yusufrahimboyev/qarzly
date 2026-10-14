"""Domain repository abstraktsiyasi: AdminRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod

from bot.domain.entities.admin import Admin


class AdminRepository(ABC):
    """Bazadagi (qo'shilgan) adminlar — barcha filial botlari uchun umumiy."""

    @abstractmethod
    async def list(self) -> list[Admin]:
        """Barcha qo'shilgan adminlar (qo'shilgan vaqti bo'yicha)."""
        raise NotImplementedError

    @abstractmethod
    async def add(self, admin: Admin) -> None:
        """Adminni qo'shadi (mavjud bo'lsa ismini yangilaydi)."""
        raise NotImplementedError

    @abstractmethod
    async def remove(self, telegram_id: int) -> bool:
        """Adminni o'chiradi; topilmasa False."""
        raise NotImplementedError
