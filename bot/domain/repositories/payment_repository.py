"""Domain repository abstraktsiyasi: PaymentRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

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

    @abstractmethod
    async def get_by_date_range(self, date_from: date, date_to: date) -> list[Payment]:
        """Sana oralig'idagi (ikki chegara ham kiradi) barcha to'lovlarni qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def sum_repayments_before(self, before: date) -> dict[str, int]:
        """`before` sanasigacha (o'zi kirmaydi) qaytarilgan pul yig'indisi.

        Faqat 'full' va 'partial' to'lovlar hisoblanadi. 'initial' (qarz
        yaratilganda berilgan pul) allaqachon `original_debt` dan ayrilgan —
        uni qo'shish qoldiqni ikki marta kamaytirib yuborardi.
        """
        raise NotImplementedError
