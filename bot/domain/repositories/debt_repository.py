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

    @abstractmethod
    async def get_client_latest_dates(self) -> dict[int, str]:
        """Mijozlar bo'yicha eng oxirgi qarz sanalarini qaytaradi (client_id -> max_date)."""
        raise NotImplementedError

    # ------------------------------------------------------------------
    # Korzina (Trash) operatsiyalari
    # ------------------------------------------------------------------

    @abstractmethod
    async def get_all_paid(self) -> list[Debt]:
        """Barcha yopilgan (paid) qarzlarni qaytaradi — Yopilganlar tab uchun."""
        raise NotImplementedError

    @abstractmethod
    async def get_paid_by_client_id(self, client_id: int) -> list[Debt]:
        """Berilgan mijozning yopilgan qarzlarini qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def move_to_trash(self, debt_ids: list[int]) -> int:
        """Ko'rsatilgan IDlardagi yopilgan qarzlarni 'trashed' statusiga o'tkazadi.

        Faqat status='paid' bo'lgan qarzlar o'tkaziladi.
        Qaytaradi: o'zgartirilgan yozuvlar soni.
        """
        raise NotImplementedError

    @abstractmethod
    async def restore_from_trash(self, debt_ids: list[int]) -> int:
        """Ko'rsatilgan IDlardagi trashed qarzlarni 'paid' statusiga qaytaradi.

        Qaytaradi: o'zgartirilgan yozuvlar soni.
        """
        raise NotImplementedError

    @abstractmethod
    async def get_all_trashed(self) -> list[Debt]:
        """Barcha korzinaga yuborilgan (trashed) qarzlarni qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def purge_trash(self) -> int:
        """Korzinani butunlay tozalaydi:
        1. Barcha 'trashed' qarzlarni trash arxiv jadvaliga ko'chiradi (mijoz nomi bilan).
        2. debts jadvalidan o'chiradi (ON DELETE RESTRICT sababli payments avval o'chiriladi).

        Qaytaradi: o'chirilgan yozuvlar soni.
        """
        raise NotImplementedError

