"""Domain abstraktsiyasi: Unit of Work.

Bitta use-case doirasidagi barcha yozuvlar (qarz + to'lov, bir nechta
valyutadagi qarzlar) bitta atomik chegarada bajarilishi kerak: yo hammasi
saqlanadi, yo hech biri. Aks holda oraliq xatoda qarz kamayib, to'lov tarixi
yozilmay qolishi mumkin.

Application qatlami shu interfeysga tayanadi; PostgreSQL tranzaksiyasi
infrastructure qatlamida amalga oshiriladi.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from types import TracebackType

from bot.domain.repositories.client_repository import ClientRepository
from bot.domain.repositories.debt_repository import DebtRepository
from bot.domain.repositories.payment_repository import PaymentRepository


class UnitOfWork(ABC):
    """Atomik yozuv chegarasi va unga bog'langan repository'lar."""

    clients: ClientRepository
    debts: DebtRepository
    payments: PaymentRepository

    @abstractmethod
    async def begin(self) -> None:
        """Tranzaksiyani boshlaydi."""
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        """O'zgarishlarni yakunlaydi."""
        raise NotImplementedError

    @abstractmethod
    async def rollback(self) -> None:
        """O'zgarishlarni bekor qiladi."""
        raise NotImplementedError

    async def release(self) -> None:
        """Tranzaksiya resurslarini qaytaradi (connection va h.k.)."""
        return None

    async def __aenter__(self) -> UnitOfWork:
        await self.begin()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self.rollback()
            else:
                await self.commit()
        finally:
            await self.release()


UnitOfWorkFactory = Callable[[], UnitOfWork]
"""Har bir use-case uchun yangi Unit of Work yaratuvchi funksiya."""


class NonTransactionalUnitOfWork(UnitOfWork):
    """Tranzaksiyasiz UoW — testlardagi in-memory repository'lar uchun.

    Biznes-mantiq oqimini o'zgartirmaydi, ammo hech qanday atomiklik
    kafolatini bermaydi. Productionda `PgUnitOfWork` ishlatiladi.
    """

    def __init__(
        self,
        clients: ClientRepository,
        debts: DebtRepository,
        payments: PaymentRepository,
    ) -> None:
        self.clients = clients
        self.debts = debts
        self.payments = payments

    async def begin(self) -> None:
        return None

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None
