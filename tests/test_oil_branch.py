"""Moy (Oil) daftari: litr birligi, alohida ma'lumot va Mini App filial ro'yxati."""
from __future__ import annotations

from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from pydantic import SecretStr

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.edit_service import EditService
from bot.application.services.user_service import UserService
from bot.core.branches import oil_code, oil_title
from bot.core.config import Settings
from bot.domain.entities.client import Client
from bot.domain.entities.debt import UNIT_LITRES, UNIT_PIECES, DebtProduct, build_summary_name
from bot.infrastructure.branches import Branch, BranchRegistry
from bot.infrastructure.web.routes import BRANCH_REGISTRY_KEY, branch_middleware, setup_routes
from bot.infrastructure.web.telegram_auth import create_auth_middleware
from tests.conftest import (
    FakeClientRepository,
    FakeDebtRepository,
    FakeEditLogRepository,
    FakePaymentRepository,
    FakeUserRepository,
)
from tests.test_web_api import TEST_BOT_TOKEN, auth_header

DSN = SecretStr("postgresql://test:test@localhost:5432/test")


def test_summary_name_uses_unit() -> None:
    oil = [DebtProduct(name="Mobil 5W-30", quantity=4, price_per_unit=1)]
    assert build_summary_name(oil, UNIT_LITRES) == "Mobil 5W-30 — 4 litr"
    assert build_summary_name(oil) == "Mobil 5W-30 — 4 ta"


def test_oil_names() -> None:
    assert oil_code("lassa") == "lassa_oil"
    assert oil_title("lassa") == "Lassa Oil"


def test_oil_disabled_by_default() -> None:
    settings = Settings(
        bot_token=SecretStr("1:x"), admin_ids=[1], database_url=DSN, _env_file=None  # type: ignore[call-arg]
    )
    assert settings.oil_enabled is False


async def test_oil_debt_and_edit_are_named_in_litres() -> None:
    clients, debts, payments = FakeClientRepository(), FakeDebtRepository(), FakePaymentRepository()
    service = DebtService(clients, debts, payments, unit=UNIT_LITRES)
    edits = EditService(clients, debts, payments, FakeEditLogRepository(), unit=UNIT_LITRES)
    client = await clients.add(Client(full_name="Ali", phone=""))

    [debt] = await service.create_debts(
        client.id, "16.08.2026", [DebtProduct(name="Mobil", quantity=4, price_per_unit=100_000)]
    )
    assert debt.product_name == "Mobil — 4 litr"

    saved = await edits.update_debt(
        debt.id, "16.08.2026", [DebtProduct(name="Shell", quantity=5, price_per_unit=100_000)]
    )
    assert saved.product_name == "Shell — 5 litr"


def _branch(code: str, title: str, unit: str = "ta") -> Branch:
    clients, debts, payments = FakeClientRepository(), FakeDebtRepository(), FakePaymentRepository()
    return Branch(
        code=code,
        title=title,
        unit=unit,
        client_service=ClientService(clients, debts),
        debt_service=DebtService(clients, debts, payments, unit=unit),
        user_service=UserService(FakeUserRepository()),
    )


async def test_mini_app_sees_both_books_with_units_and_separate_data() -> None:
    registry = BranchRegistry(
        [_branch("lassa", "Lassa"), _branch("lassa_oil", "Lassa Oil", UNIT_LITRES)], "lassa"
    )
    app = web.Application(middlewares=[
        create_auth_middleware(TEST_BOT_TOKEN, [], allow_open_access=True),
        branch_middleware,
    ])
    app[BRANCH_REGISTRY_KEY] = registry
    setup_routes(app)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        data = await (await client.get("/api/branches", headers=auth_header())).json()
        assert data == {
            "branches": [
                {"code": "lassa", "title": "Lassa", "unit": "ta"},
                {"code": "lassa_oil", "title": "Lassa Oil", "unit": "litr"},
            ],
            "default": "lassa",
        }
        resp = await client.post(
            "/api/debts",
            headers={**auth_header(), "X-Branch": "lassa_oil"},
            json={
                "client_name": "Ali",
                "debt_date": "16.08.2026",
                "products": [{"name": "Mobil", "quantity": 4, "price_per_unit": 100_000}],
            },
        )
        assert resp.status == 200, await resp.text()
        oil = await (
            await client.get("/api/summaries", headers={**auth_header(), "X-Branch": "lassa_oil"})
        ).json()
        main = await (await client.get("/api/summaries", headers=auth_header())).json()
        assert len(oil) == 1 and main == []
        oil_headers = {**auth_header(), "X-Branch": "lassa_oil"}
        report = await (
            await client.get(f"/api/clients/{oil[0]['id']}/report", headers=oil_headers)
        ).json()
        assert report["debts"][0]["product_name"] == "Mobil — 4 litr"
    finally:
        await client.close()


def test_product_unit_overrides_book_unit() -> None:
    """Oil daftarida har bir tovar litr yoki dona bo'lishi mumkin."""
    products = [
        DebtProduct(name="Mobil", quantity=4, price_per_unit=1, unit=UNIT_LITRES),
        DebtProduct(name="Filtr", quantity=2, price_per_unit=1, unit=UNIT_PIECES),
        DebtProduct(name="Shell", quantity=3, price_per_unit=1),  # birliksiz — daftarniki
    ]
    assert build_summary_name(products, UNIT_LITRES) == (
        "Mobil — 4 litr, Filtr — 2 ta, Shell — 3 litr"
    )


def test_product_unit_round_trips_and_old_records_have_none() -> None:
    p = DebtProduct(name="Filtr", quantity=2, price_per_unit=1, unit=UNIT_PIECES)
    assert DebtProduct.from_dict(p.to_dict()) == p
    old = DebtProduct.from_dict({"name": "Mobil", "quantity": 4, "price_per_unit": 1})
    assert old.unit is None
    assert "unit" not in old.to_dict()
    # Noma'lum birlik — birliksiz deb olinadi (buzilgan yozuv bazani sindirmasin)
    assert DebtProduct.from_dict({"name": "X", "unit": "kg"}).unit is None


def test_product_rejects_unknown_unit() -> None:
    import pytest

    with pytest.raises(ValueError):
        DebtProduct(name="X", quantity=1, price_per_unit=1, unit="kg").validate()


async def test_api_accepts_per_product_unit_on_create_and_edit() -> None:
    registry = BranchRegistry([_branch("lassa_oil", "Lassa Oil", UNIT_LITRES)], "lassa_oil")
    app = web.Application(middlewares=[
        create_auth_middleware(TEST_BOT_TOKEN, [], allow_open_access=True),
        branch_middleware,
    ])
    app[BRANCH_REGISTRY_KEY] = registry
    setup_routes(app)
    client = TestClient(TestServer(app))
    await client.start_server()
    try:
        resp = await client.post(
            "/api/debts",
            headers=auth_header(),
            json={
                "client_name": "Ali",
                "debt_date": "16.08.2026",
                "products": [
                    {"name": "Mobil", "quantity": 4, "price_per_unit": 100_000, "unit": "litr"},
                    {"name": "Filtr", "quantity": 2, "price_per_unit": 50_000, "unit": "ta"},
                ],
            },
        )
        assert resp.status == 200, await resp.text()
        [summary] = await (await client.get("/api/summaries", headers=auth_header())).json()
        report = await (
            await client.get(f"/api/clients/{summary['id']}/report", headers=auth_header())
        ).json()
        debt = report["debts"][0]
        assert debt["product_name"] == "Mobil — 4 litr, Filtr — 2 ta"
        assert [p.get("unit") for p in debt["products"]] == ["litr", "ta"]

        bad = await client.post(
            "/api/debts",
            headers=auth_header(),
            json={
                "client_name": "Ali",
                "debt_date": "16.08.2026",
                "products": [{"name": "X", "quantity": 1, "price_per_unit": 1, "unit": "kg"}],
            },
        )
        assert bad.status == 400
    finally:
        await client.close()
