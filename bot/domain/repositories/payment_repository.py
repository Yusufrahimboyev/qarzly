"""Domain repository abstraktsiyasi: PaymentRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod

from bot.domain.entities.payment import Payment


class PaymentRepository(ABC):
    """To'lovlar bilan ishlash bo'yicha interfeys."""

    @abstractmethod
    async def add(self, payment: Payment) -> Payment:
        """Yangi to'lovni saqlaydi va ID bilan qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_client_id(self, client_id: int) -> list[Payment]:
        """Mijoz bo'yicha barcha to'lovlar tarixini qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_debt_id(self, debt_id: int) -> list[Payment]:
        """Muayyan qarz bo'yicha to'lovlarni qaytaradi."""
        raise NotImplementedError
