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

        Bo'sh telefon bilan qidirilmaydi — aks holda birinchi uchragan
        telefonsiz mijozga noto'g'ri bog'lanib qolardi.

        Qaytaradi: (Client, created: bool)
        """
        clean_name = full_name.strip()
        clean_phone = normalize_phone(phone)

        # 1. Telefon orqali qidirish (faqat telefon kiritilgan bo'lsa)
        if clean_phone:
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
        """Barcha mijozlarni alifbo tartibida qarz holati bilan qaytaradi.

        Qarzlar valyuta bo'yicha ajratilgan: so'm va dollar alohida yig'iladi.
        """
        all_clients = await self._clients.get_all_alphabetical()
        active_totals = await self._debts.get_active_totals()

        summaries: list[ClientDebtSummary] = []
        for client in all_clients:
            if client.id is None:
                continue
            per_currency = active_totals.get(client.id, {})
            remaining = {
                currency: totals[0]
                for currency, totals in per_currency.items()
                if totals[0] > 0
            }
            active_count = sum(totals[1] for totals in per_currency.values())
            summaries.append(
                ClientDebtSummary(
                    client=client,
                    remaining_by_currency=remaining,
                    active_debts_count=active_count,
                )
            )

        return summaries

    async def get_debtor_summaries(self) -> list[ClientDebtSummary]:
        """Faqat qarzi bor (kamida bitta valyutada) mijozlarni alifbo bo'yicha qaytaradi."""
        all_summaries = await self.get_all_summaries()
        return [s for s in all_summaries if s.has_debt]
