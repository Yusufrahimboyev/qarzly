"""Testlar uchun in-memory fake repository fixture'lar.

Tashqi bazaga bog'lanmasdan tezkor va mustaqil unit testlarni ta'minlaydi.
"""
from __future__ import annotations

from datetime import datetime

import pytest

from bot.domain.entities.client import Client
from bot.domain.entities.debt import Debt, DebtStatus
from bot.domain.entities.payment import Payment
from bot.domain.entities.user import User
from bot.domain.repositories.client_repository import ClientRepository
from bot.domain.repositories.debt_repository import DebtRepository
from bot.domain.repositories.payment_repository import PaymentRepository
from bot.domain.repositories.user_repository import UserRepository


class FakeUserRepository(UserRepository):
    """In-memory UserRepository."""

    def __init__(self) -> None:
        self._store: dict[int, User] = {}
        self._id_seq = 1

    async def add(self, user: User) -> None:
        if user.telegram_id not in self._store:
            saved_user = User(
                id=self._id_seq,
                telegram_id=user.telegram_id,
                username=user.username,
                full_name=user.full_name,
                created_at=user.created_at or datetime.now(),
            )
            self._id_seq += 1
            self._store[user.telegram_id] = saved_user

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self._store.get(telegram_id)


class FakeClientRepository(ClientRepository):
    """In-memory ClientRepository."""

    def __init__(self) -> None:
        self._store: dict[int, Client] = {}
        self._id_seq = 1

    async def add(self, client: Client) -> Client:
        client_id = self._id_seq
        self._id_seq += 1
        saved = Client(
            id=client_id,
            full_name=client.full_name,
            phone=client.phone,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self._store[client_id] = saved
        return saved

    async def get_by_id(self, client_id: int) -> Client | None:
        return self._store.get(client_id)

    async def find_by_phone(self, phone: str) -> Client | None:
        clean = phone.strip()
        for c in self._store.values():
            if c.phone == clean:
                return c
        return None

    async def find_by_name(self, full_name: str) -> Client | None:
        clean = full_name.strip().lower()
        for c in self._store.values():
            if c.full_name.strip().lower() == clean:
                return c
        return None

    async def get_all_alphabetical(self) -> list[Client]:
        return sorted(self._store.values(), key=lambda c: c.full_name.lower())


class FakeDebtRepository(DebtRepository):
    """In-memory DebtRepository."""

    def __init__(self) -> None:
        self._store: dict[int, Debt] = {}
        self._id_seq = 1

    async def add(self, debt: Debt) -> Debt:
        debt_id = self._id_seq
        self._id_seq += 1
        saved = Debt(
            id=debt_id,
            client_id=debt.client_id,
            debt_date=debt.debt_date,
            product_name=debt.product_name,
            product_quantity=debt.product_quantity,
            product_price=debt.product_price,
            currency=debt.currency,
            exchange_exists=debt.exchange_exists,
            exchange_product_name=debt.exchange_product_name,
            exchange_product_price=debt.exchange_product_price,
            given_money=debt.given_money,
            original_debt=debt.original_debt,
            remaining_debt=debt.remaining_debt,
            products=debt.products,
            status=debt.status,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        self._store[debt_id] = saved
        return saved

    async def get_by_id(self, debt_id: int) -> Debt | None:
        return self._store.get(debt_id)

    async def get_all_by_client_id(self, client_id: int) -> list[Debt]:
        return [
            d for d in self._store.values()
            if d.client_id == client_id and d.status != DebtStatus.TRASHED
        ]


    async def get_active_by_client_id(self, client_id: int) -> list[Debt]:
        return [
            d for d in self._store.values()
            if d.client_id == client_id and d.status == DebtStatus.ACTIVE and d.remaining_debt > 0
        ]

    async def get_all_active(self) -> list[Debt]:
        return [
            d for d in self._store.values()
            if d.status == DebtStatus.ACTIVE and d.remaining_debt > 0
        ]

    async def get_active_totals(self) -> dict[int, dict[str, tuple[int, int]]]:
        totals: dict[int, dict[str, tuple[int, int]]] = {}
        for d in self._store.values():
            if d.status == DebtStatus.ACTIVE and d.remaining_debt > 0:
                cur = d.currency.value
                prev_sum, prev_count = totals.setdefault(d.client_id, {}).get(cur, (0, 0))
                totals[d.client_id][cur] = (prev_sum + d.remaining_debt, prev_count + 1)
        return totals

    async def update_remaining_debt(
        self,
        debt_id: int,
        remaining_debt: int,
        status: DebtStatus,
    ) -> None:
        debt = self._store.get(debt_id)
        if debt is not None:
            updated = Debt(
                id=debt.id,
                client_id=debt.client_id,
                debt_date=debt.debt_date,
                product_name=debt.product_name,
                product_quantity=debt.product_quantity,
                product_price=debt.product_price,
                currency=debt.currency,
                exchange_exists=debt.exchange_exists,
                exchange_product_name=debt.exchange_product_name,
                exchange_product_price=debt.exchange_product_price,
                given_money=debt.given_money,
                original_debt=debt.original_debt,
                remaining_debt=remaining_debt,
                products=debt.products,
                status=status,
                created_at=debt.created_at,
                updated_at=datetime.now(),
            )
            self._store[debt_id] = updated

    # ------------------------------------------------------------------
    # Korzina (Trash) operatsiyalari
    # ------------------------------------------------------------------

    async def get_all_paid(self) -> list[Debt]:
        return [d for d in self._store.values() if d.status == DebtStatus.PAID]

    async def get_paid_by_client_id(self, client_id: int) -> list[Debt]:
        return [
            d for d in self._store.values()
            if d.client_id == client_id and d.status == DebtStatus.PAID
        ]

    async def move_to_trash(self, debt_ids: list[int]) -> int:
        count = 0
        for debt_id in debt_ids:
            d = self._store.get(debt_id)
            if d is not None and d.status == DebtStatus.PAID:
                self._store[debt_id] = Debt(
                    id=d.id, client_id=d.client_id, debt_date=d.debt_date,
                    product_name=d.product_name, product_quantity=d.product_quantity,
                    product_price=d.product_price, currency=d.currency,
                    exchange_exists=d.exchange_exists,
                    exchange_product_name=d.exchange_product_name,
                    exchange_product_price=d.exchange_product_price,
                    given_money=d.given_money, original_debt=d.original_debt,
                    remaining_debt=d.remaining_debt, products=d.products,
                    status=DebtStatus.TRASHED,
                    created_at=d.created_at, updated_at=datetime.now(),
                )
                count += 1
        return count

    async def restore_from_trash(self, debt_ids: list[int]) -> int:
        count = 0
        for debt_id in debt_ids:
            d = self._store.get(debt_id)
            if d is not None and d.status == DebtStatus.TRASHED:
                self._store[debt_id] = Debt(
                    id=d.id, client_id=d.client_id, debt_date=d.debt_date,
                    product_name=d.product_name, product_quantity=d.product_quantity,
                    product_price=d.product_price, currency=d.currency,
                    exchange_exists=d.exchange_exists,
                    exchange_product_name=d.exchange_product_name,
                    exchange_product_price=d.exchange_product_price,
                    given_money=d.given_money, original_debt=d.original_debt,
                    remaining_debt=d.remaining_debt, products=d.products,
                    status=DebtStatus.PAID,
                    created_at=d.created_at, updated_at=datetime.now(),
                )
                count += 1
        return count

    async def get_all_trashed(self) -> list[Debt]:
        return [d for d in self._store.values() if d.status == DebtStatus.TRASHED]

    async def purge_trash(self) -> int:
        """Barcha trashed qarzlarni in-memory store dan o'chiradi."""
        to_delete = [
            debt_id for debt_id, d in self._store.items()
            if d.status == DebtStatus.TRASHED
        ]
        for debt_id in to_delete:
            del self._store[debt_id]
        return len(to_delete)




class FakePaymentRepository(PaymentRepository):
    """In-memory PaymentRepository."""

    def __init__(self) -> None:
        self._store: dict[int, Payment] = {}
        self._id_seq = 1

    async def add(self, payment: Payment) -> Payment:
        pay_id = self._id_seq
        self._id_seq += 1
        saved = Payment(
            id=pay_id,
            client_id=payment.client_id,
            debt_id=payment.debt_id,
            amount=payment.amount,
            currency=payment.currency,
            payment_type=payment.payment_type,
            payment_date=payment.payment_date,
            created_at=datetime.now(),
        )
        self._store[pay_id] = saved
        return saved

    async def get_by_client_id(self, client_id: int) -> list[Payment]:
        return [
            p for p in self._store.values()
            if p.client_id == client_id
        ]

    async def get_by_debt_id(self, debt_id: int) -> list[Payment]:
        return [
            p for p in self._store.values()
            if p.debt_id == debt_id
        ]


# ==========================================
# FIXTURES
# ==========================================


@pytest.fixture
def fake_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def user_repo() -> FakeUserRepository:
    return FakeUserRepository()


@pytest.fixture
def client_repo() -> FakeClientRepository:
    return FakeClientRepository()


@pytest.fixture
def debt_repo() -> FakeDebtRepository:
    return FakeDebtRepository()


@pytest.fixture
def payment_repo() -> FakePaymentRepository:
    return FakePaymentRepository()
