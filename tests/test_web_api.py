"""REST API va WebApp route'lari uchun testlar."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from aiohttp import web
from pydantic import SecretStr

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.infrastructure.web.routes import setup_routes
from bot.infrastructure.web.telegram_auth import (
    INIT_DATA_HEADER,
    create_auth_middleware,
    security_headers_middleware,
)
from tests.conftest import (
    FakeClientRepository,
    FakeDebtRepository,
    FakePaymentRepository,
)

TEST_BOT_TOKEN = "123456:test-token"


def make_init_data(bot_token: str, user_id: int = 42, auth_date: int | None = None) -> str:
    """Telegram Mini App initData'ni test uchun haqiqiy algoritm bilan imzolaydi."""
    params = {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAF-test-query",
        "user": json.dumps({"id": user_id, "first_name": "Test", "username": "tester"}),
    }
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(params) + f"&hash={calculated}"


def auth_header(bot_token: str = TEST_BOT_TOKEN, user_id: int = 42) -> dict[str, str]:
    return {INIT_DATA_HEADER: make_init_data(bot_token, user_id)}


def make_app(
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
    admin_ids: list[int],
) -> web.Application:
    """WebServer bilan bir xil konfiguratsiyadagi aiohttp app yaratadi."""
    settings = Settings(bot_token=SecretStr(TEST_BOT_TOKEN), admin_ids=admin_ids, database_url="postgresql://test:test@localhost:5432/test")
    app = web.Application(
        middlewares=[
            security_headers_middleware,
            create_auth_middleware(settings.token, settings.admin_ids),
        ]
    )
    app["client_service"] = ClientService(client_repo, debt_repo)
    app["debt_service"] = DebtService(client_repo, debt_repo, payment_repo)
    setup_routes(app)
    return app


@pytest.fixture
def aiohttp_app(
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
) -> web.Application:
    # admin_ids bo'sh — har qanday haqiqiy Telegram foydalanuvchisi kiradi
    return make_app(client_repo, debt_repo, payment_repo, admin_ids=[])


@pytest.mark.asyncio
async def test_health_check_open_without_auth(aiohttp_app: web.Application) -> None:
    from aiohttp.test_utils import TestClient, TestServer
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
async def test_api_rejects_missing_init_data(aiohttp_app: web.Application) -> None:
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        resp = await client.get("/api/stats")
        assert resp.status == 401

        resp = await client.post("/api/debts", json={})
        assert resp.status == 401
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_web_api_create_debt_and_pay(aiohttp_app: web.Application) -> None:
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        headers = auth_header()

        # 1. Create debt via API (2 dona × 2 500 000 = 5 000 000)
        debt_payload = {
            "client_name": "Aliyev Anvar",
            "client_phone": "+998901234567",
            "debt_date": "16.08.2026",
            "product_name": "Shina",
            "product_quantity": 2,
            "product_price": 2500000,
            "exchange_exists": True,
            "exchange_product_name": "Akkumulyator",
            "exchange_product_price": 800000,
            "given_money": 200000,
        }
        res_create = await client.post("/api/debts", json=debt_payload, headers=headers)
        assert res_create.status == 200
        data_create = await res_create.json()
        assert data_create["ok"] is True
        assert data_create["total_product_price"] == 5000000
        assert data_create["remaining_debt"] == 4000000
        client_id = data_create["client_id"]

        # 2. Check stats (valyutalar bo'yicha)
        res_stats = await client.get("/api/stats", headers=headers)
        assert res_stats.status == 200
        data_stats = await res_stats.json()
        assert data_stats["total_debt"] == {"UZS": 4000000}
        assert data_stats["debtors_count"] == 1
        assert data_stats["clients_count"] == 1

        # 3. Check client report
        res_report = await client.get(f"/api/clients/{client_id}/report", headers=headers)
        assert res_report.status == 200
        data_report = await res_report.json()
        assert data_report["client"]["full_name"] == "Aliyev Anvar"
        assert len(data_report["debts"]) == 1
        assert data_report["debts"][0]["product_quantity"] == 2
        assert data_report["debts"][0]["product_price"] == 5000000
        assert data_report["debts"][0]["currency"] == "UZS"
        assert data_report["total_remaining_debt"] == {"UZS": 4000000}

        # 4. Partial payment via API
        pay_payload = {
            "client_id": client_id,
            "payment_type": "partial",
            "amount": 500000,
            "payment_date": "16.08.2026",
        }
        res_pay = await client.post("/api/payments", json=pay_payload, headers=headers)
        assert res_pay.status == 200
        data_pay = await res_pay.json()
        assert data_pay["ok"] is True
        assert data_pay["paid_amount"] == 500000
        assert data_pay["currency"] == "UZS"
        assert data_pay["new_remaining"] == 3500000
        assert data_pay["remaining"] == {"UZS": 3500000}
        assert data_pay["is_closed"] is False

        # 5. Full payment via API
        pay_full_payload = {
            "client_id": client_id,
            "payment_type": "full",
            "payment_date": "16.08.2026",
        }
        res_pay_full = await client.post("/api/payments", json=pay_full_payload, headers=headers)
        assert res_pay_full.status == 200
        data_pay_full = await res_pay_full.json()
        assert data_pay_full["ok"] is True
        assert data_pay_full["paid_amount"] == {"UZS": 3500000}
        assert data_pay_full["new_remaining"] == {}
        assert data_pay_full["is_closed"] is True

    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_create_debt_requires_valid_phone(
    aiohttp_app: web.Application,
) -> None:
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        headers = auth_header()
        payload = {
            "client_name": "Aliyev Anvar",
            "client_phone": "12",
            "debt_date": "16.08.2026",
            "product_name": "Shina",
            "product_price": 1000000,
        }
        res = await client.post("/api/debts", json=payload, headers=headers)
        assert res.status == 400
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_create_debt_without_phone_succeeds(
    aiohttp_app: web.Application,
) -> None:
    """Telefon raqamisiz ham qarz muvaffaqiyatli yaratilishi kerak."""
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        headers = auth_header()
        payload = {
            "client_name": "Telefonsiz Mijoz",
            "client_phone": "",
            "debt_date": "16.08.2026",
            "product_name": "Moy",
            "product_price": 400000,
        }
        res = await client.post("/api/debts", json=payload, headers=headers)
        assert res.status == 200
        data = await res.json()
        assert data["ok"] is True
        assert data["remaining_debt"] == 400000
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_create_debt_with_products_array(
    aiohttp_app: web.Application,
) -> None:
    """API orqali products massivi bilan qarz yaratish."""
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        headers = auth_header()

        # 2 ta tovar: Shina (2×500k=1M) + Akkumulyator (1×800k=800k) = 1.8M
        # exchange: 300k, given: 200k -> qarz: 1 300 000
        payload = {
            "client_name": "Multiproduct Aliyev",
            "client_phone": "+998901234567",
            "debt_date": "16.08.2026",
            "products": [
                {"name": "Shina", "quantity": 2, "price_per_unit": 500000},
                {"name": "Akkumulyator", "quantity": 1, "price_per_unit": 800000},
            ],
            "currency": "UZS",
            "exchange_exists": True,
            "exchange_product_name": "Eski shina",
            "exchange_product_price": 300000,
            "given_money": 200000,
        }
        res = await client.post("/api/debts", json=payload, headers=headers)
        assert res.status == 200
        data = await res.json()
        assert data["ok"] is True
        assert data["total_product_price"] == 1800000
        assert data["remaining_debt"] == 1300000
        assert "products" in data
        assert len(data["products"]) == 2
        assert data["products"][0]["name"] == "Shina"
        assert data["products"][0]["quantity"] == 2
        assert data["products"][1]["name"] == "Akkumulyator"

        client_id = data["client_id"]

        # Report'da products ko'rinadi
        res_report = await client.get(
            f"/api/clients/{client_id}/report", headers=headers,
        )
        assert res_report.status == 200
        report = await res_report.json()
        assert len(report["debts"]) == 1
        assert len(report["debts"][0]["products"]) == 2
        assert report["debts"][0]["product_quantity"] == 3  # 2 + 1
        assert report["debts"][0]["product_price"] == 1800000
        assert report["debts"][0]["products"][0]["price_per_unit"] == 500000

        # Stats da ham ko'rinadi
        res_stats = await client.get("/api/stats", headers=headers)
        assert res_stats.status == 200
        stats = await res_stats.json()
        assert stats["total_debt"] == {"UZS": 1300000}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_create_debt_products_validation(
    aiohttp_app: web.Application,
) -> None:
    """products massividagi validation: bo'sh nom, narx 0."""
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        headers = auth_header()

        # Bo'sh nom
        payload = {
            "client_name": "Test",
            "client_phone": "+998901234567",
            "products": [{"name": "", "quantity": 1, "price_per_unit": 1000}],
        }
        res = await client.post("/api/debts", json=payload, headers=headers)
        assert res.status == 400

        # Narx 0
        payload2 = {
            "client_name": "Test",
            "client_phone": "+998901234567",
            "products": [{"name": "Tovar", "quantity": 1, "price_per_unit": 0}],
        }
        res2 = await client.post("/api/debts", json=payload2, headers=headers)
        assert res2.status == 400

    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_rejects_invalid_date(
    aiohttp_app: web.Application,
) -> None:
    """Noto'g'ri sana jimlik bilan 'bugun'ga aylanmasligi kerak — 400 qaytadi."""
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        headers = auth_header()

        # Noto'g'ri sana bilan qarz yaratish
        payload = {
            "client_name": "Sana Test",
            "client_phone": "+998901234567",
            "debt_date": "32.13.2026",
            "products": [{"name": "Shina", "quantity": 1, "price_per_unit": 1000}],
        }
        res = await client.post("/api/debts", json=payload, headers=headers)
        assert res.status == 400
        data = await res.json()
        assert "sana" in data["error"].lower() or "Sana" in data["error"]

        # Noto'g'ri sana bilan to'lov
        pay_payload = {
            "client_id": 1,
            "payment_type": "partial",
            "amount": 500,
            "payment_date": "not-a-date",
        }
        res2 = await client.post("/api/payments", json=pay_payload, headers=headers)
        assert res2.status == 400

        # Bo'sh sana yuborilsa — bugun ishlatiladi (400 emas)
        payload_ok = {
            "client_name": "Sana Test",
            "client_phone": "+998901234567",
            "debt_date": "",
            "products": [{"name": "Shina", "quantity": 1, "price_per_unit": 1000}],
        }
        res3 = await client.post("/api/debts", json=payload_ok, headers=headers)
        assert res3.status == 200
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_create_debt_rejects_too_long_name(
    aiohttp_app: web.Application,
) -> None:
    """80 belgidan uzun mijoz ismi yoki tovar nomi qabul qilinmaydi."""
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        headers = auth_header()

        payload = {
            "client_name": "a" * 81,
            "client_phone": "+998901234567",
            "products": [{"name": "Shina", "quantity": 1, "price_per_unit": 1000}],
        }
        res = await client.post("/api/debts", json=payload, headers=headers)
        assert res.status == 400

        payload2 = {
            "client_name": "Oddiy Ism",
            "client_phone": "+998901234567",
            "products": [{"name": "b" * 81, "quantity": 1, "price_per_unit": 1000}],
        }
        res2 = await client.post("/api/debts", json=payload2, headers=headers)
        assert res2.status == 400
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_create_debt_mixed_currencies(
    aiohttp_app: web.Application,
) -> None:
    """1-tovar dollar, 2-tovar so'm — 2 ta qarz yaratiladi, qoldiq valyutalar bo'yicha."""
    from aiohttp.test_utils import TestClient, TestServer
    server = TestServer(aiohttp_app)
    client = TestClient(server)
    await client.start_server()

    try:
        headers = auth_header()

        # Shina 120 $ + Moy 450 000 so'm; exchange 20 $; berilgan pul 50 000 so'm
        # Dollar qarz: 100 $; So'm qarz: 400 000
        payload = {
            "client_name": "Aralash Valyuta Mijoz",
            "client_phone": "+998905554433",
            "debt_date": "17.08.2026",
            "products": [
                {"name": "Shina", "quantity": 1, "price_per_unit": 120, "currency": "USD"},
                {"name": "Moy", "quantity": 1, "price_per_unit": 450000, "currency": "UZS"},
            ],
            "exchange_exists": True,
            "exchange_product_name": "Eski shina",
            "exchange_product_price": 20,
            "exchange_currency": "USD",
            "given_money": 50000,
            "given_currency": "UZS",
        }
        res = await client.post("/api/debts", json=payload, headers=headers)
        assert res.status == 200
        data = await res.json()
        assert data["ok"] is True
        assert len(data["debts"]) == 2
        assert data["remaining_by_currency"] == {"UZS": 400000, "USD": 100}

        # Stats umumiy qarzni valyutalar bo'yicha ko'rsatadi
        res_stats = await client.get("/api/stats", headers=headers)
        stats = await res_stats.json()
        assert stats["total_debt"] == {"UZS": 400000, "USD": 100}

        # Faqat dollar qarzni dollarda qisman to'lash
        res_pay = await client.post("/api/payments", json={
            "client_id": data["client_id"],
            "payment_type": "partial",
            "amount": 100,
            "currency": "USD",
            "payment_date": "18.08.2026",
        }, headers=headers)
        assert res_pay.status == 200
        pay = await res_pay.json()
        assert pay["remaining"] == {"UZS": 400000}
    finally:
        await client.close()


@pytest.mark.asyncio
async def test_api_rejects_non_admin_when_admin_ids_configured(
    client_repo: FakeClientRepository,
    debt_repo: FakeDebtRepository,
    payment_repo: FakePaymentRepository,
) -> None:
    from aiohttp.test_utils import TestClient, TestServer

    app = make_app(client_repo, debt_repo, payment_repo, admin_ids=[42])
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()

    try:
        # Ruxsat etilgan admin
        res = await client.get("/api/stats", headers=auth_header(user_id=42))
        assert res.status == 200

        # Boshqa foydalanuvchi
        res = await client.get("/api/stats", headers=auth_header(user_id=99))
        assert res.status == 403
    finally:
        await client.close()
