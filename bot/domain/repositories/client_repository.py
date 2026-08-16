"""Domain repository abstraktsiyasi: ClientRepository."""
from __future__ import annotations

from abc import ABC, abstractmethod

from bot.domain.entities.client import Client


class ClientRepository(ABC):
    """Mijozlar bilan ishlash bo'yicha interfeys."""

    @abstractmethod
    async def add(self, client: Client) -> Client:
        """Yangi mijozni saqlaydi va ID bilan qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(self, client_id: int) -> Client | None:
        """ID bo'yicha mijozni qaytaradi."""
        raise NotImplementedError

    @abstractmethod
    async def find_by_phone(self, phone: str) -> Client | None:
        """Telefon raqami bo'yicha mijozni topadi."""
        raise NotImplementedError

    @abstractmethod
    async def find_by_name(self, full_name: str) -> Client | None:
        """Ism-familiya bo'yicha mijozni topadi (case-insensitive)."""
        raise NotImplementedError

    @abstractmethod
    async def get_all_alphabetical(self) -> list[Client]:
        """Barcha mijozlarni alfavit tartibida qaytaradi."""
        raise NotImplementedError
