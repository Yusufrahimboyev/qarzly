"""Domain repository abstraktsiyasi: EditLogRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod

from bot.domain.entities.edit import EditRecord


class EditLogRepository(ABC):
    """Tahrirlar tarixi (append-only)."""

    @abstractmethod
    async def add(self, record: EditRecord) -> EditRecord:
        """Tahrir yozuvini saqlaydi."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_client_id(self, client_id: int) -> list[EditRecord]:
        """Mijoz va uning qarzlari tahrirlari (eng yangisi birinchi)."""
        raise NotImplementedError
