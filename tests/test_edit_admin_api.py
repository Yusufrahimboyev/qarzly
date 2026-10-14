"""API: mijoz/qarz tahriri, hisobotdagi "tahrirlangan" ma'lumoti va adminlar."""
from __future__ import annotations

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from bot.application.services.admin_service import AdminService
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.edit_service import EditService
from bot.infrastructure.web.routes import (
    ADMIN_SERVICE_KEY,
    CLIENT_SERVICE_KEY,
    DEBT_SERVICE_KEY,
    EDIT_SERVICE_KEY,
    setup_routes,
)
from bot.infrastructure.web.telegram_auth import create_auth_middleware
from tests.conftest import (
    FakeAdminRepository,
    FakeClientRepository,
    FakeDebtRepository,
    FakeEditLogRepository,
    FakePaymentRepository,
)
from tests.test_web_api import TEST_BOT_TOKEN, auth_header

ROOT = 42  # auth_header() standart foydalanuvchisi


@pytest.fixture
async def api():
    clients, debts, payments = FakeClientRepository(), FakeDebtRepository(), FakePaymentRepository()
    admins = AdminService(FakeAdminRepository(), [ROOT])
    app = web.Application(middlewares=[
        create_auth_middleware(TEST_BOT_TOKEN, [ROOT], is_admin=admins.is_admin),
    ])
    app[CLIENT_SERVICE_KEY] = ClientService(clients, debts)
    app[DEBT_SERVICE_KEY] = DebtService(clients, debts, payments)
    app[EDIT_SERVICE_KEY] = EditService(clients, debts, payments, FakeEditLogRepository())
    app[ADMIN_SERVICE_KEY] = admins
    setup_routes(app)
    client = TestClient(TestServer(app))
    await client.start_server()
    yield client
    await client.close()


async def _create_debt(api: TestClient) -> dict:
    resp = await api.post("/api/debts", headers=auth_header(), json={
        "client_name": "Aliyev Anvar",
        "client_phone": "+998901234567",
        "debt_date": "16.08.2026",
        "products": [{"name": "Shina", "quantity": 1, "price_per_unit": 1_000_000}],
    })
    assert resp.status == 200, await resp.text()
    summaries = await (await api.get("/api/summaries", headers=auth_header())).json()
    report = await (
        await api.get(f"/api/clients/{summaries[0]['id']}/report", headers=auth_header())
    ).json()
    return report


async def test_edit_client_and_debt_shows_last_edit_in_report(api: TestClient) -> None:
    report = await _create_debt(api)
    client_id, debt_id = report["client"]["id"], report["debts"][0]["id"]
    assert report["client"]["last_edit"] is None and report["debts"][0]["last_edit"] is None

    resp = await api.patch(f"/api/clients/{client_id}", headers=auth_header(), json={
        "full_name": "Aliyev Anvarjon", "phone": "+998901234567",
    })
    assert resp.status == 200, await resp.text()
    resp = await api.patch(f"/api/debts/{debt_id}", headers=auth_header(), json={
        "debt_date": "17.08.2026",
        "products": [{"name": "Shina", "quantity": 2, "price_per_unit": 1_000_000}],
    })
    assert resp.status == 200, await resp.text()
    assert (await resp.json())["remaining_debt"] == 2_000_000

    report = await (await api.get(f"/api/clients/{client_id}/report", headers=auth_header())).json()
    assert report["client"]["full_name"] == "Aliyev Anvarjon"
    assert report["client"]["last_edit"]["changes"] == [
        {"field": "full_name", "old": "Aliyev Anvar", "new": "Aliyev Anvarjon"}
    ]
    debt_edit = report["debts"][0]["last_edit"]
    assert [c["field"] for c in debt_edit["changes"]] == ["debt_date", "products", "original_debt"]
    assert debt_edit["edited_at"]


async def test_edit_errors_are_400(api: TestClient) -> None:
    report = await _create_debt(api)
    debt_id = report["debts"][0]["id"]
    resp = await api.patch(f"/api/debts/{debt_id}", headers=auth_header(), json={
        "debt_date": "yo'q", "products": [{"name": "Shina", "price_per_unit": 5}],
    })
    assert resp.status == 400
    resp = await api.patch(f"/api/debts/{debt_id}", headers=auth_header(), json={
        "debt_date": "16.08.2026", "products": [],
    })
    assert resp.status == 400


async def test_added_admin_gets_access_and_removed_loses_it(api: TestClient) -> None:
    assert (await api.get("/api/stats", headers=auth_header(user_id=555))).status == 403

    resp = await api.post("/api/admins", headers=auth_header(), json={
        "telegram_id": 555, "full_name": "Ali",
    })
    assert resp.status == 200, await resp.text()
    assert (await api.get("/api/stats", headers=auth_header(user_id=555))).status == 200

    data = await (await api.get("/api/admins", headers=auth_header())).json()
    listed = [(a["telegram_id"], a["is_root"]) for a in data["admins"]]
    assert listed == [(ROOT, True), (555, False)]

    assert (await api.delete(f"/api/admins/{ROOT}", headers=auth_header(user_id=555))).status == 400
    assert (await api.delete("/api/admins/555", headers=auth_header())).status == 200
    assert (await api.get("/api/stats", headers=auth_header(user_id=555))).status == 403
