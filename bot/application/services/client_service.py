"""Application qatlami: ClientService.

Mijozlar bilan ishlash use-case'lari (yaratish, qidirish, alifbo tartibidagi hisobotlar).
"""
from __future__ import annotations

from bot.application.common.formatters import normalize_phone
from bot.domain.entities.client import Client
from bot.domain.entities.report import ClientDebtSummary
from bot.domain.repositories.client_repository import ClientRepository
from bot.domain.repositories.debt_repository import DebtRepository


class ClientService:
    """Mijozlar boshqaruvi servisi."""

    def __init__(
        self,
        clients: ClientRepository,
        debts: DebtRepository,
    ) -> None:
        self._clients = clients
        self._debts = debts

    async def get_or_create(self, full_name: str, phone: str) -> tuple[Client, bool]:
        """Mijozni telefon yoki ism bo'yicha qidiradi, topilmasa yangi yaratadi.

        Qaytaradi: (Client, created: bool)
        """
        clean_name = full_name.strip()
        clean_phone = normalize_phone(phone)

        # 1. Telefon orqali qidirish
        existing = await self._clients.find_by_phone(clean_phone)
        if existing is not None:
            return existing, False

        # 2. Ism bo'yicha qidirish
        existing = await self._clients.find_by_name(clean_name)
        if existing is not None:
            return existing, False

        # 3. Yangi mijoz yaratish
        new_client = Client(
            full_name=clean_name,
            phone=clean_phone,
        )
        saved_client = await self._clients.add(new_client)
        return saved_client, True

    async def get_by_id(self, client_id: int) -> Client | None:
        """ID bo'yicha mijozni topadi."""
        return await self._clients.get_by_id(client_id)

    async def get_all_summaries(self) -> list[ClientDebtSummary]:
        """Barcha mijozlarni alifbo tartibida jami qarz holati bilan qaytaradi."""
        all_clients = await self._clients.get_all_alphabetical()
        summaries: list[ClientDebtSummary] = []

        for client in all_clients:
            if client.id is None:
                continue
            active_debts = await self._debts.get_active_by_client_id(client.id)
            total_remaining = sum(d.remaining_debt for d in active_debts)
            summaries.append(
                ClientDebtSummary(
                    client=client,
                    total_remaining_debt=total_remaining,
                    active_debts_count=len(active_debts),
                )
            )

        return summaries

    async def get_debtor_summaries(self) -> list[ClientDebtSummary]:
        """Faqat qarzi bor (total_remaining_debt > 0) mijozlarni alifbo bo'yicha qaytaradi."""
        all_summaries = await self.get_all_summaries()
        return [s for s in all_summaries if s.total_remaining_debt > 0]
