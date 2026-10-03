"""Inline rejim: qarzdorlarni qidirish, sahifalash va adminlik tekshiruvi."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.types import InlineQuery, User
from pydantic import SecretStr

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import DebtProduct
from bot.presentation.handlers.inline_debtors import PAGE_SIZE, inline_debtors
from bot.presentation.middlewares.admin_middleware import AdminMiddleware

BRANCH = SimpleNamespace(title="Mangit")


class StubInlineQuery(InlineQuery):
    """`answer()` chaqiruvini Telegram o'rniga yozib boradi."""

    @classmethod
    def build(cls, text: str = "", offset: str = "", user_id: int = 1) -> StubInlineQuery:
        return cls(
            id="q",
            from_user=User(id=user_id, is_bot=False, first_name="A"),
            query=text,
            offset=offset,
        )

    async def answer(self, results, **kwargs) -> None:
        object.__setattr__(self, "_results", results)
        object.__setattr__(self, "_kwargs", kwargs)

    @property
    def titles(self) -> list[str]:
        return [r.title for r in self._results]


@pytest.fixture
def services(client_repo, debt_repo, payment_repo):
    clients = ClientService(client_repo, debt_repo)
    debts = DebtService(clients=client_repo, debts=debt_repo, payments=payment_repo)
    return clients, debts


async def add_debt(clients, debts, name: str, phone: str, price: int) -> None:
    client, _ = await clients.get_or_create(name, phone)
    await debts.create_debts(
        client_id=client.id,
        debt_date="05.03.2026",
        products=[DebtProduct(name="Shina", quantity=1, price_per_unit=price,
                              currency=Currency.UZS)],
        exchange_exists=False,
        exchange_product_name=None,
        exchange_product_price=0,
        exchange_currency=Currency.UZS,
        given_money=0,
        given_currency=Currency.UZS,
    )


async def test_search_by_name_and_phone(services) -> None:
    clients, debts = services
    await add_debt(clients, debts, "Aziz Aka", "+998901112233", 2_400_000)
    await add_debt(clients, debts, "Akbar", "+998907778899", 100_000)
    await clients.get_or_create("Qarzsiz", "")

    query = StubInlineQuery.build("aziz")
    await inline_debtors(query, clients, BRANCH)
    assert query.titles == ["🔴 Aziz Aka — 2 400 000 so'm"]
    assert query._kwargs["is_personal"] is True
    assert query._kwargs["cache_time"] == 0

    card = query._results[0].input_message_content.message_text
    assert "Aziz Aka" in card and "Mangit" in card and "2 400 000 so'm" in card
    assert "05.03.2026" in card

    by_phone = StubInlineQuery.build("7778")
    await inline_debtors(by_phone, clients, BRANCH)
    assert by_phone.titles == ["🔴 Akbar — 100 000 so'm"]

    everyone = StubInlineQuery.build("")
    await inline_debtors(everyone, clients, BRANCH)
    assert len(everyone.titles) == 2  # qarzi yo'q mijoz chiqmaydi


async def test_paginates_over_page_size(services) -> None:
    clients, debts = services
    for i in range(PAGE_SIZE + 3):
        await add_debt(clients, debts, f"Mijoz {i:03d}", "", 1000)

    first = StubInlineQuery.build("")
    await inline_debtors(first, clients, BRANCH)
    assert len(first.titles) == PAGE_SIZE
    assert first._kwargs["next_offset"] == str(PAGE_SIZE)

    second = StubInlineQuery.build("", offset=str(PAGE_SIZE))
    await inline_debtors(second, clients, BRANCH)
    assert len(second.titles) == 3
    assert second._kwargs["next_offset"] == ""


async def test_non_admin_gets_empty_results() -> None:
    settings = Settings(bot_token=SecretStr("1:x"), admin_ids=[1], database_url=SecretStr("pg://x"))
    called = False

    async def handler(_event, _data) -> None:
        nonlocal called
        called = True

    query = StubInlineQuery.build("aziz", user_id=999)
    await AdminMiddleware(settings)(handler, query, {})

    assert not called
    assert query._results == []
    assert query._kwargs["is_personal"] is True

