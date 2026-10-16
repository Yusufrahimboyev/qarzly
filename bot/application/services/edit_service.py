"""Application qatlami: EditService.

Mavjud mijoz (ism, telefon) va qarz (sana, tovarlar) ma'lumotlarini tahrirlash.
Har bir tahrir `edit_log` ga eski → yangi qiymatlar bilan yoziladi — Mini App
va botdagi "tahrirlangan" belgisi shu yozuvlardan olinadi.

Qarz summasi o'zgarsa qoldiq qayta hisoblanadi: yangi qarz − shu paytgacha
qaytarilgan pul. Yangi summa allaqachon qaytarilgan puldan kam bo'lsa tahrir
rad etiladi (to'lovlar tarixi buzilmasligi uchun).
"""
from __future__ import annotations

import logging
from dataclasses import replace
from datetime import date

from bot.application.common.formatters import (
    format_date,
    format_money,
    is_valid_phone,
    normalize_phone,
    to_date,
)
from bot.application.services.debt_service import DebtService
from bot.domain.entities.client import Client
from bot.domain.entities.debt import UNIT_PIECES, Debt, DebtProduct, DebtStatus
from bot.domain.entities.edit import EditRecord, FieldChange
from bot.domain.repositories.client_repository import ClientRepository
from bot.domain.repositories.debt_repository import DebtRepository
from bot.domain.repositories.edit_log_repository import EditLogRepository
from bot.domain.repositories.payment_repository import PaymentRepository
from bot.domain.repositories.unit_of_work import (
    NonTransactionalUnitOfWork,
    UnitOfWorkFactory,
)
from bot.i18n import _

logger = logging.getLogger(__name__)

MAX_NAME_LENGTH = 80


def describe_products(products: tuple[DebtProduct, ...] | list[DebtProduct]) -> str:
    """Tovarlar ro'yxatining qisqa matni: "Shina — 4 × 500 000 so'm; Moy — 1 × …"."""
    return "; ".join(
        f"{p.name} — {p.quantity} × {format_money(p.price_per_unit, p.currency)}"
        for p in products
    )


class EditService:
    """Mijoz va qarz ma'lumotlarini tahrirlash servisi."""

    def __init__(
        self,
        clients: ClientRepository,
        debts: DebtRepository,
        payments: PaymentRepository,
        edits: EditLogRepository,
        uow_factory: UnitOfWorkFactory | None = None,
        unit: str = UNIT_PIECES,
    ) -> None:
        self._unit = unit
        self._clients = clients
        self._debts = debts
        self._edits = edits
        self._uow_factory: UnitOfWorkFactory = uow_factory or (
            lambda: NonTransactionalUnitOfWork(clients, debts, payments, edits)
        )

    async def get_edits(self, client_id: int) -> list[EditRecord]:
        """Mijoz va uning qarzlari tahrirlari (eng yangisi birinchi)."""
        return await self._edits.get_by_client_id(client_id)

    async def update_client(
        self,
        client_id: int,
        full_name: str,
        phone: str,
        actor_id: int | None = None,
        actor_name: str = "",
    ) -> Client:
        """Mijoz ismi va telefonini o'zgartiradi."""
        full_name = " ".join(full_name.split())
        if not full_name:
            raise ValueError(_("Mijoz ismi bo'sh bo'lishi mumkin emas."))
        if len(full_name) > MAX_NAME_LENGTH:
            raise ValueError(_("Mijoz ismi 80 belgidan uzun bo'lishi mumkin emas."))
        phone = normalize_phone(phone) if phone.strip() else ""
        if phone and not is_valid_phone(phone):
            raise ValueError(_("Telefon raqami noto'g'ri (masalan: +998901234567)"))

        client = await self._clients.get_by_id(client_id)
        if client is None:
            raise ValueError(_("Mijoz topilmadi."))

        changes: list[FieldChange] = []
        if full_name != client.full_name:
            changes.append(FieldChange("full_name", client.full_name, full_name))
        if phone != client.phone:
            other = await self._clients.find_by_phone(phone) if phone else None
            if other is not None and other.id != client_id:
                raise ValueError(_(
                    "Bu telefon raqami boshqa mijozga tegishli: {name}.",
                    name=other.full_name,
                ))
            changes.append(FieldChange("phone", client.phone, phone))
        if not changes:
            raise ValueError(_("Hech narsa o'zgarmadi."))

        async with self._uow_factory() as uow:
            updated = await uow.clients.update(client_id, full_name, phone)
            if updated is None:
                raise ValueError(_("Mijoz topilmadi."))
            await uow.edits.add(EditRecord(
                client_id=client_id,
                changes=tuple(changes),
                edited_by=actor_id,
                edited_by_name=actor_name,
            ))
        logger.info("AUDIT client_edited client_id=%s actor=%s", client_id, actor_id)
        return updated

    async def update_debt(
        self,
        debt_id: int,
        debt_date: str | date,
        products: list[DebtProduct],
        actor_id: int | None = None,
        actor_name: str = "",
    ) -> Debt:
        """Qarz sanasi va tovarlarini o'zgartiradi, qoldiqni qayta hisoblaydi.

        Valyuta, exchange va boshlang'ich to'lov o'zgarmaydi.
        """
        debt = await self._debts.get_by_id(debt_id)
        if debt is None or debt.id is None:
            raise ValueError(_("Qarz topilmadi."))
        if debt.status == DebtStatus.TRASHED:
            raise ValueError(_("Korzinadagi qarzni tahrirlab bo'lmaydi."))

        new_date = to_date(debt_date)
        products = [replace(p, currency=debt.currency) for p in products]
        plan = DebtService._plan_debt(
            client_id=debt.client_id,
            debt_date=new_date,
            products=products,
            currency=debt.currency,
            exchange_exists=debt.exchange_exists,
            exchange_product_name=debt.exchange_product_name,
            exchange_product_price=debt.exchange_product_price,
            given_money=debt.given_money,
            unit=self._unit,
        )
        repaid = debt.original_debt - debt.remaining_debt
        new_remaining = plan.debt.original_debt - repaid
        if new_remaining < 0:
            raise ValueError(_(
                "Yangi qarz summasi ({amount}) allaqachon to'langan puldan ({paid}) "
                "kam bo'lishi mumkin emas.",
                amount=format_money(plan.debt.original_debt, debt.currency),
                paid=format_money(repaid, debt.currency),
            ))
        updated = replace(
            plan.debt,
            id=debt.id,
            remaining_debt=new_remaining,
            status=DebtStatus.ACTIVE if new_remaining > 0 else DebtStatus.PAID,
        )

        changes: list[FieldChange] = []
        if new_date != debt.debt_date:
            changes.append(FieldChange(
                "debt_date", format_date(debt.debt_date), format_date(new_date)
            ))
        if tuple(updated.products) != tuple(debt.products):
            changes.append(FieldChange(
                "products", describe_products(debt.products), describe_products(updated.products)
            ))
        if updated.original_debt != debt.original_debt:
            changes.append(FieldChange(
                "original_debt",
                format_money(debt.original_debt, debt.currency),
                format_money(updated.original_debt, debt.currency),
            ))
        if not changes:
            raise ValueError(_("Hech narsa o'zgarmadi."))

        async with self._uow_factory() as uow:
            saved = await uow.debts.update_details(debt, updated)
            if saved is None:
                raise ValueError(_(
                    "Qarz shu orada o'zgardi (masalan, to'lov qabul qilindi). "
                    "Ro'yxatni yangilab, qayta urinib ko'ring."
                ))
            if new_date != debt.debt_date and debt.given_money > 0:
                await uow.payments.update_initial_payment_date(debt.id, new_date)
            await uow.edits.add(EditRecord(
                client_id=debt.client_id,
                debt_id=debt.id,
                changes=tuple(changes),
                edited_by=actor_id,
                edited_by_name=actor_name,
            ))
        logger.info("AUDIT debt_edited debt_id=%s actor=%s", debt.id, actor_id)
        return saved
