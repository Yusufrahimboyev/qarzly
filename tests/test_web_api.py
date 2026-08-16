"""REST API va WebApp route'lari uchun testlar."""
from __future__ import annotations

import aiohttp
from aiohttp import web
import pytest

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.infrastructure.database.repositories.client_repository import (
    SqliteClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import (
    SqliteDebtRepository,
)
from bot.infrastructure.database.repositories.payment_repository import (
    SqlitePaymentRepository,
)
from bot.infrastructure.web.routes import setup_routes


@pytest.fixture
def aiohttp_app(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> web.Application:
    app = web.Application()
    app["client_service"] = ClientService(client_repo, debt_repo)
    app["debt_service"] = DebtService(client_repo, debt_repo, payment_repo)
    setup_routes(app)
    return app


@pytest.mark.asyncio
async def test_health_check(aiohttp_app: web.Application) -> None:
    from aiohttp.test_utils import TestServer, TestClient
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/health")
        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "ok"
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_web_api_create_debt_and_pay(aiohttp_app: web.Application) -> None:
    from aiohttp.test_utils import TestServer, TestClient
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        # 1. Create debt via API
        debt_payload = {
            "client_name": "Aliyev Anvar",
            "client_phone": "+998901234567",
            "debt_date": "16.08.2026",
            "product_name": "Shina",
            "product_price": 2500000,
            "exchange_exists": True,
            "exchange_product_name": "Akkumulyator",
            "exchange_product_price": 800000,
            "given_money": 200000,
        }
        res_create = await client.post("/api/debts", json=debt_payload)
        assert res_create.status == 200
        data_create = await res_create.json()
        assert data_create["ok"] is True
        assert data_create["remaining_debt"] == 1500000
        client_id = data_create["client_id"]

        # 2. Check stats
        res_stats = await client.get("/api/stats")
        assert res_stats.status == 200
        data_stats = await res_stats.json()
        assert data_stats["total_debt"] == 1500000
        assert data_stats["debtors_count"] == 1
        assert data_stats["clients_count"] == 1

        # 3. Check client report
        res_report = await client.get(f"/api/clients/{client_id}/report")
        assert res_report.status == 200
        data_report = await res_report.json()
        assert data_report["client"]["full_name"] == "Aliyev Anvar"
        assert len(data_report["debts"]) == 1
        assert data_report["total_remaining_debt"] == 1500000

        # 4. Partial payment via API
        pay_payload = {
            "client_id": client_id,
            "payment_type": "partial",
            "amount": 500000,
            "payment_date": "16.08.2026",
        }
        res_pay = await client.post("/api/payments", json=pay_payload)
        assert res_pay.status == 200
        data_pay = await res_pay.json()
        assert data_pay["ok"] is True
        assert data_pay["paid_amount"] == 500000
        assert data_pay["new_remaining"] == 1000000
        assert data_pay["is_closed"] is False

        # 5. Full payment via API
        pay_full_payload = {
            "client_id": client_id,
            "payment_type": "full",
            "payment_date": "16.08.2026",
        }
        res_pay_full = await client.post("/api/payments", json=pay_full_payload)
        assert res_pay_full.status == 200
        data_pay_full = await res_pay_full.json()
        assert data_pay_full["ok"] is True
        assert data_pay_full["paid_amount"] == 1000000
        assert data_pay_full["new_remaining"] == 0
        assert data_pay_full["is_closed"] is True

    finally:
        await client.close()
