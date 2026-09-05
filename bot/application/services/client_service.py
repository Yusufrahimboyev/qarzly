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

        Identity qoidalari:

        - telefon berilgan bo'lsa — u asosiy identifikator. Mijoz faqat shu
          telefon bo'yicha topiladi va yaratish `ON CONFLICT` bilan atomik
          bajariladi (parallel so'rovlar dublikat yaratmaydi);
        - telefon berilmagan bo'lsa — faqat telefonsiz mijozlar orasidan ism
          bo'yicha qidiriladi.

        Bir xil ismli, ammo turli telefonli ikki kishi hech qachon bitta
        mijozga birlashtirilmaydi.

        Qaytaradi: (Client, created: bool)
        """
        clean_name = full_name.strip()
        if not clean_name:
            raise ValueError("Mijoz ismi bo'sh bo'lishi mumkin emas.")
        clean_phone = normalize_phone(phone)

        if clean_phone:
            return await self._clients.get_or_create_by_phone(
                Client(full_name=clean_name, phone=clean_phone)
            )

        existing = await self._clients.find_by_name_without_phone(clean_name)
        if existing is not None:
            return existing, False

        new_client = Client(full_name=clean_name, phone="")
        return await self._clients.add(new_client), True

    async def get_by_id(self, client_id: int) -> Client | None:
        """ID bo'yicha mijozni topadi."""
        return await self._clients.get_by_id(client_id)

    async def get_all_clients(self) -> list[Client]:
        """Barcha mijozlarni alifbo tartibida qaytaradi (engil so'rov)."""
        return await self._clients.get_all_alphabetical()

    async def get_all_summaries(self) -> list[ClientDebtSummary]:
        """Barcha faol yoki yopilgan qarzi bor mijozlarni alifbo tartibida qaytaradi.

        Barcha qarzlari korzinaga yuborilgan yoki o'chirilgan mijozlar jadvalda
        ortiqcha 0 so'm bo'lib ko'rinmasligi uchun chiqarilmaydi.
        """
        all_clients = await self._clients.get_all_alphabetical()
        active_totals = await self._debts.get_active_totals()
        latest_dates = await self._debts.get_client_latest_dates()
        # Yopilgan qarzlarning o'zi kerak emas — faqat qaysi mijozlarda
        # borligi kerak. Shu sababli barcha entity o'rniga engil agregat.
        paid_client_ids = await self._debts.get_client_ids_with_paid_debts()

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
            has_debt = active_count > 0

            # Faol qarzi ham, yopilgan qarzi ham bo'lmagan mijoz jadvalda
            # ko'rsatilmaydi (ortiqcha 0 so'mli qator bo'lmasligi uchun).
            if not has_debt and client.id not in paid_client_ids:
                continue

            summaries.append(
                ClientDebtSummary(
                    client=client,
                    remaining_by_currency=remaining,
                    active_debts_count=active_count,
                    latest_debt_date=latest_dates.get(client.id),
                )
            )

        return summaries


    async def get_debtor_summaries(self) -> list[ClientDebtSummary]:
        """Faqat qarzi bor (kamida bitta valyutada) mijozlarni alifbo bo'yicha qaytaradi."""
        all_summaries = await self.get_all_summaries()
        return [s for s in all_summaries if s.has_debt]
