"""Domain repository abstraktsiyasi: DebtRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod

from bot.domain.entities.debt import Debt, DebtStatus

ActiveDebtTotals = dict[int, dict[str, tuple[int, int]]]
"""client_id -> {valyuta: (jami_qoldiq_qarz, faol_qarzlar_soni)}."""


class DebtRepository(ABC):
    """Qarz operatsiyalari bilan ishlash bo'yicha interfeys."""

    @abstractmethod
    async def add(self, debt: Debt) -> Debt:
        """Yangi qarz yozuvini saqlaydi va ID bilan qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, debt_id: int) -> Debt | None:
        """ID bo'yicha qarzni qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def get_all_by_client_id(self, client_id: int) -> list[Debt]:
        """Mijozning barcha qarzlarini sanasi bo'yicha tartiblangan holda qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def get_active_by_client_id(self, client_id: int) -> list[Debt]:
        """Mijozning faol (yopilmagan) qarzlarini FIFO tartibida (eng eski birinchi) qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def update_remaining_debt(
        self,
        debt_id: int,
        remaining_debt: int,
        status: DebtStatus,
    ) -> None:
        """Qarzning qoldiq summasi va statusini yangilaydi."""
        raise NotImplementedError

    @abstractmethod
    async def get_all_active(self) -> list[Debt]:
        """Barcha yopilmagan faol qarzlarni qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def get_active_totals(self) -> ActiveDebtTotals:
        """Barcha mijozlar uchun faol qarzlar yig'indisini bitta so'rovda qaytaradi.

        Qaytaradi: {client_id: {valyuta: (jami_qoldiq_qarz, faol_qarzlar_soni)}}.
        Bu har bir mijoz uchun alohida so'rov (N+1) o'rniga bitta agregat so'rov.
        """
        raise NotImplementedError
