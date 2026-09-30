"""Filiallar: alohida baza, API/bot yo'naltirishi va sozlamalar uchun testlar."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.user_service import UserService
from bot.infrastructure.branches import Branch, BranchRegistry
from bot.infrastructure.web.routes import (
    BRANCH_REGISTRY_KEY,
    branch_middleware,
    setup_routes,
)
from bot.infrastructure.web.telegram_auth import create_auth_middleware
from bot.presentation.middlewares.dependency_middleware import DependencyMiddleware
from tests.conftest import (
    FakeClientRepository,
    FakeDebtRepository,
    FakePaymentRepository,
    FakeUserRepository,
)
from tests.test_web_api import TEST_BOT_TOKEN, auth_header

DEBT = {
    "client_name": "Aliyev Anvar",
    "client_phone": "+998901234567",
    "debt_date": "16.08.2026",
    "product_name": "Shina",
    "product_quantity": 1,
    "product_price": 1_000_000,
}


def make_branch(code: str, title: str) -> Branch:
    """Har chaqiruvda alohida (bir-biridan mustaqil) in-memory baza."""
    clients, debts, payments = (
        FakeClientRepository(),
        FakeDebtRepository(),
        FakePaymentRepository(),
    )
    return Branch(
        code=code,
        title=title,
        client_service=ClientService(clients, debts),
        debt_service=DebtService(clients, debts, payments),
        user_service=UserService(FakeUserRepository()),
    )


@pytest.fixture
def registry() -> BranchRegistry:
    return BranchRegistry(
        [
            make_branch("mangit", "Mangit"),
            make_branch("nukus", "Nukus"),
            make_branch("lassa", "Lassa"),
        ],
        default="mangit",
    )


@pytest.fixture
async def client(registry: BranchRegistry):
    app = web.Application(
        middlewares=[
            create_auth_middleware(TEST_BOT_TOKEN, [], allow_open_access=True),
            branch_middleware,
        ]
    )
    app[BRANCH_REGISTRY_KEY] = registry
    setup_routes(app)
    test_client = TestClient(TestServer(app))
    await test_client.start_server()
    yield test_client
    await test_client.close()


async def _clients_count(client: TestClient, branch: str | None) -> int:
    headers = auth_header()
    if branch:
        headers["X-Branch"] = branch
    resp = await client.get("/api/stats", headers=headers)
    assert resp.status == 200
    return (await resp.json())["clients_count"]


async def test_branches_have_separate_data(client: TestClient) -> None:
    headers = {**auth_header(), "X-Branch": "nukus"}
    resp = await client.post("/api/debts", json=DEBT, headers=headers)
    assert resp.status == 200

    assert await _clients_count(client, "nukus") == 1
    assert await _clients_count(client, "mangit") == 0
    assert await _clients_count(client, "lassa") == 0


async def test_missing_header_uses_default_branch(client: TestClient) -> None:
    resp = await client.post("/api/debts", json=DEBT, headers=auth_header())
    assert resp.status == 200

    assert await _clients_count(client, None) == 1
    assert await _clients_count(client, "mangit") == 1
    assert await _clients_count(client, "nukus") == 0


async def test_unknown_branch_is_rejected(client: TestClient) -> None:
    headers = {**auth_header(), "X-Branch": "samarqand"}
    resp = await client.post("/api/debts", json=DEBT, headers=headers)
    assert resp.status == 400

    assert await _clients_count(client, None) == 0


async def test_branch_list_endpoint(client: TestClient) -> None:
    resp = await client.get("/api/branches", headers=auth_header())
    assert resp.status == 200
    data = await resp.json()
    assert [b["code"] for b in data["branches"]] == ["mangit", "nukus", "lassa"]
    assert data["default"] == "mangit"


async def test_branch_endpoint_requires_auth(client: TestClient) -> None:
    resp = await client.get("/api/branches")
    assert resp.status == 401


class StubPreferences:
    def __init__(self, stored: dict[int, str]) -> None:
        self._stored = stored

    async def get(self, telegram_id: int) -> str | None:
        return self._stored.get(telegram_id)


async def _injected(registry: BranchRegistry, stored: dict[int, str], user_id: int):
    from aiogram.types import CallbackQuery, Message

    middleware = DependencyMiddleware(
        registry=registry,
        preferences=StubPreferences(stored),  # type: ignore[arg-type]
        settings=SimpleNamespace(),  # type: ignore[arg-type]
    )
    event = Message.model_construct(from_user=SimpleNamespace(id=user_id))
    assert isinstance(event, (Message, CallbackQuery))
    seen: dict = {}

    async def handler(_event, data):
        seen.update(data)

    await middleware(handler, event, {})
    return seen


async def test_bot_uses_selected_branch_services(registry: BranchRegistry) -> None:
    data = await _injected(registry, {7: "lassa"}, user_id=7)
    lassa = registry.get("lassa")
    assert data["branch"] is lassa
    assert data["client_service"] is lassa.client_service
    assert data["debt_service"] is lassa.debt_service


@pytest.mark.parametrize("stored", [{}, {7: "removed-branch"}])
async def test_bot_falls_back_to_default_branch(
    registry: BranchRegistry, stored: dict[int, str]
) -> None:
    data = await _injected(registry, stored, user_id=7)
    assert data["branch"] is registry.default


def test_every_branch_has_title_and_schema() -> None:
    from bot.core.branches import BRANCH_SCHEMAS, BRANCH_TITLES, DEFAULT_BRANCH

    assert BRANCH_TITLES.keys() == BRANCH_SCHEMAS.keys()
    # Mavjud ma'lumotlar turgan public sxema faqat asosiy filialniki.
    assert BRANCH_SCHEMAS[DEFAULT_BRANCH] is None
    others = [v for k, v in BRANCH_SCHEMAS.items() if k != DEFAULT_BRANCH]
    assert all(others) and len(set(others)) == len(others)


def test_registry_rejects_unknown_default() -> None:
    with pytest.raises(ValueError):
        BranchRegistry([make_branch("mangit", "Mangit")], default="nukus")
