"""Infrastructure qatlami: aiohttp web route'lari va REST API.

Telegram Mini App UI va uning backend API lari. /api/* route'lari
Telegram initData autentifikatsiyasidan o'tadi (server.py da ulanadi).
"""
from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web

from bot.application.common.formatters import (
    aggregate_remaining,
    is_valid_phone,
    normalize_phone,
    parse_date_input,
    today_str,
)
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.domain.entities.currency import Currency

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parents[3] / "web"
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"


async def health_check(request: web.Request) -> web.Response:
    """Xizmat holatini qaytaradi (monitoring / keep-alive uchun)."""
    return web.json_response({"status": "ok", "service": "Qarz Daftar Telegram Bot & WebApp"})


async def index_handler(request: web.Request) -> web.StreamResponse:
    """Mini App bosh sahifasini (index.html) qaytaradi."""
    index_path = _TEMPLATES_DIR / "index.html"
    if index_path.exists():
        return web.FileResponse(index_path)
    return web.Response(
        text="<h1>Qarz Daftar WebApp</h1><p>Frontend fayllari topilmadi.</p>",
        content_type="text/html",
    )


# ==========================================
# REST API HANDLERS
# ==========================================


async def api_get_stats(request: web.Request) -> web.Response:
    """Umumiy statistikani qaytaradi (qarzlar valyutalar bo'yicha ajratilgan)."""
    client_service: ClientService = request.app["client_service"]
    summaries = await client_service.get_all_summaries()

    debtors_count = sum(1 for s in summaries if s.has_debt)
    clients_count = len(summaries)

    return web.json_response({
        "total_debt": aggregate_remaining(summaries),
        "debtors_count": debtors_count,
        "clients_count": clients_count,
    })


async def api_get_summaries(request: web.Request) -> web.Response:
    """Barcha mijozlarni alifbo tartibidagi qarz ma'lumotlari bilan qaytaradi."""
    client_service: ClientService = request.app["client_service"]
    summaries = await client_service.get_all_summaries()

    data = [
        {
            "id": s.client.id,
            "full_name": s.client.full_name,
            "phone": s.client.phone,
            "remaining": s.remaining_by_currency,
            "active_debts_count": s.active_debts_count,
            "has_debt": s.has_debt,
        }
        for s in summaries
    ]
    return web.json_response(data)


async def api_get_debtors(request: web.Request) -> web.Response:
    """Faqat faol qarzdorlarni qaytaradi."""
    client_service: ClientService = request.app["client_service"]
    debtors = await client_service.get_debtor_summaries()

    data = [
        {
            "id": s.client.id,
            "full_name": s.client.full_name,
            "phone": s.client.phone,
            "remaining": s.remaining_by_currency,
            "active_debts_count": s.active_debts_count,
            "has_debt": True,
        }
        for s in debtors
    ]
    return web.json_response(data)


async def api_get_client_report(request: web.Request) -> web.Response:
    """Mijozning to'liq hisobotini (tarixi, exchange, to'lovlar) qaytaradi."""
    debt_service: DebtService = request.app["debt_service"]
    client_id_str = request.match_info.get("id")

    if not client_id_str or not client_id_str.isdigit():
        return web.json_response({"error": "Noto'g'ri client ID"}, status=400)

    client_id = int(client_id_str)
    try:
        report = await debt_service.get_client_report(client_id)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=404)

    return web.json_response({
        "client": {
            "id": report.client.id,
            "full_name": report.client.full_name,
            "phone": report.client.phone,
        },
        "debts": [
            {
                "id": d.id,
                "debt_date": d.debt_date,
                "product_name": d.product_name,
                "product_quantity": d.product_quantity,
                "product_price": d.product_price,
                "currency": d.currency.value,
                "exchange_exists": d.exchange_exists,
                "exchange_product_name": d.exchange_product_name,
                "exchange_product_price": d.exchange_product_price,
                "given_money": d.given_money,
                "original_debt": d.original_debt,
                "remaining_debt": d.remaining_debt,
                "status": d.status.value,
                "products": [p.to_dict() for p in d.products],
            }
            for d in report.debts
        ],
        "payments": [
            {
                "id": p.id,
                "debt_id": p.debt_id,
                "amount": p.amount,
                "currency": p.currency.value,
                "payment_type": p.payment_type.value,
                "payment_date": p.payment_date,
            }
            for p in report.payments
        ],
        "total_product_price": report.total_product_price,
        "total_exchange_price": report.total_exchange_price,
        "total_given_money": report.total_given_money,
        "total_original_debt": report.total_original_debt,
        "total_paid_after": report.total_paid_after,
        "total_remaining_debt": report.total_remaining_debt,
    })


async def api_create_debt(request: web.Request) -> web.Response:
    """Yangi qarz yaratish API handler'i.

    'products' massivi yoki bitta tovar parametrlari (product_name/quantity/price)
    orqali qarz yaratish mumkin. Har bir tovarning o'z valyutasi bo'lishi mumkin
    ("UZS"/"USD") — aralash valyutadagi tovarlar alohida qarzlarga bo'linadi.
    """
    from bot.domain.entities.debt import DebtProduct

    client_service: ClientService = request.app["client_service"]
    debt_service: DebtService = request.app["debt_service"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    client_name = str(body.get("client_name", "")).strip()
    client_phone = normalize_phone(str(body.get("client_phone", "")))
    raw_date = str(body.get("debt_date", "")).strip()
    if raw_date:
        debt_date = parse_date_input(raw_date)
        if debt_date is None:
            return web.json_response(
                {"error": "Sana formati noto'g'ri (DD.MM.YYYY, masalan: 17.08.2026)"},
                status=400,
            )
    else:
        debt_date = today_str()

    if not client_name:
        return web.json_response({"error": "Mijoz ismi kiritilmadi"}, status=400)
    if len(client_name) > 80:
        return web.json_response(
            {"error": "Mijoz ismi 80 belgidan oshmasligi kerak"}, status=400
        )
    if not is_valid_phone(client_phone):
        return web.json_response(
            {"error": "Telefon raqami noto'g'ri (masalan: +998901234567)"}, status=400
        )

    try:
        exchange_exists = bool(body.get("exchange_exists", False))
        exchange_product_name = (
            str(body.get("exchange_product_name", "")).strip() or None
            if exchange_exists
            else None
        )
        exchange_product_price = (
            int(body.get("exchange_product_price", 0)) if exchange_exists else 0
        )
        exchange_currency_raw = str(body.get("exchange_currency", Currency.UZS.value)).upper()
        given_money = int(body.get("given_money", 0))
        given_currency_raw = str(body.get("given_currency", Currency.UZS.value)).upper()
    except (ValueError, TypeError):
        return web.json_response({"error": "Narxlar butun son bo'lishi kerak"}, status=400)

    try:
        exchange_currency = Currency(exchange_currency_raw)
        given_currency = Currency(given_currency_raw)
    except ValueError:
        return web.json_response(
            {"error": "Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak)"}, status=400
        )

    # --- products massivi yoki bitta tovar parametrlari ---
    raw_products = body.get("products")
    products: list[DebtProduct] | None = None
    product_name = str(body.get("product_name", "")).strip()
    single_currency_raw = str(body.get("currency", Currency.UZS.value)).upper()
    try:
        single_currency = Currency(single_currency_raw)
    except ValueError:
        return web.json_response(
            {"error": "Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak)"}, status=400
        )

    if isinstance(raw_products, list) and len(raw_products) > 0:
        # Ko'p tovarli: har bir element name, quantity, price_per_unit, currency
        try:
            products = []
            for idx, p in enumerate(raw_products):
                p_name = str(p.get("name", "")).strip()
                p_qty = int(p.get("quantity", 1))
                p_price = int(p.get("price_per_unit", 0))
                p_currency_raw = str(p.get("currency", Currency.UZS.value)).upper()
                try:
                    p_currency = Currency(p_currency_raw)
                except ValueError:
                    return web.json_response(
                        {"error": f"{idx + 1}-tovar valyutasi noto'g'ri (UZS yoki USD)"},
                        status=400,
                    )
                if not p_name:
                    return web.json_response(
                        {"error": f"{idx + 1}-tovar nomi kiritilmadi"}, status=400,
                    )
                if len(p_name) > 80:
                    return web.json_response(
                        {"error": f"{idx + 1}-tovar nomi 80 belgidan oshmasligi kerak"},
                        status=400,
                    )
                if p_price <= 0:
                    return web.json_response(
                        {"error": f"{idx + 1}-tovar narxi 0 dan katta bo'lishi kerak"},
                        status=400,
                    )
                if p_qty < 1:
                    return web.json_response(
                        {"error": f"{idx + 1}-tovar miqdori 1 dan kichik bo'lmasligi kerak"},
                        status=400,
                    )
                products.append(DebtProduct(
                    name=p_name,
                    quantity=p_qty,
                    price_per_unit=p_price,
                    currency=p_currency.value,
                ))
        except (ValueError, TypeError, AttributeError):
            return web.json_response(
                {"error": "Tovarlar massivi noto'g'ri formatda (name, quantity, price_per_unit)"},
                status=400,
            )
    else:
        # Bitta tovar (eski usul)
        try:
            product_price = int(body.get("product_price", 0))
            product_quantity = int(body.get("product_quantity", 1))
        except (ValueError, TypeError):
            return web.json_response({"error": "Narxlar butun son bo'lishi kerak"}, status=400)

        if not product_name:
            return web.json_response({"error": "Tovar nomi kiritilmadi"}, status=400)
        if product_price <= 0:
            return web.json_response(
                {"error": "Tovar narxi 0 dan katta bo'lishi kerak"}, status=400,
            )
        if product_quantity < 1:
            return web.json_response(
                {"error": "Miqdor (nechta) 1 dan kichik bo'lmasligi kerak"}, status=400,
            )

    try:
        client, _ = await client_service.get_or_create(
            full_name=client_name,
            phone=client_phone,
        )
        if client.id is None:
            return web.json_response({"error": "Mijoz yaratishda xatolik"}, status=500)

        if products:
            saved_debts = await debt_service.create_debts(
                client_id=client.id,
                debt_date=debt_date,
                products=products,
                exchange_exists=exchange_exists,
                exchange_product_name=exchange_product_name,
                exchange_product_price=exchange_product_price,
                exchange_currency=exchange_currency,
                given_money=given_money,
                given_currency=given_currency,
            )
        else:
            saved_single = await debt_service.create_debt(
                client_id=client.id,
                debt_date=debt_date,
                product_name=product_name,
                product_price=product_price,
                product_quantity=product_quantity,
                currency=single_currency,
                exchange_exists=exchange_exists,
                exchange_product_name=exchange_product_name,
                exchange_product_price=exchange_product_price,
                given_money=given_money,
            )
            saved_debts = [saved_single]

        all_products = [p for d in saved_debts for p in d.products]
        total_product_price = sum(p.total_price for p in all_products)
        remaining_map: dict[str, int] = {}
        for d in saved_debts:
            remaining_map[d.currency.value] = (
                remaining_map.get(d.currency.value, 0) + d.remaining_debt
            )

        response: dict = {
            "ok": True,
            "client_id": client.id,
            "debts": [
                {
                    "debt_id": d.id,
                    "currency": d.currency.value,
                    "total_product_price": d.product_price,
                    "remaining_debt": d.remaining_debt,
                }
                for d in saved_debts
            ],
            "total_product_price": total_product_price,
            "remaining_by_currency": remaining_map,
            "products": [p.to_dict() for p in all_products],
        }
        # Bitta valyutali holatda eskicha int maydonlar ham qaytaramiz
        if len(remaining_map) == 1:
            response["remaining_debt"] = next(iter(remaining_map.values()))

        return web.json_response(response)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except Exception:
        logger.exception("Qarz yaratishda kutilmagan xatolik")
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik yuz berdi. Keyinroq urinib ko'ring."},
            status=500,
        )


async def api_make_payment(request: web.Request) -> web.Response:
    """To'lov qilish (to'liq yoki qisman) API handler'i."""
    debt_service: DebtService = request.app["debt_service"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    try:
        client_id = int(body.get("client_id", 0))
        payment_type = str(body.get("payment_type", "full")).lower()
        currency_raw = str(body.get("currency", Currency.UZS.value)).upper()
        raw_date = str(body.get("payment_date", "")).strip()
        if raw_date:
            payment_date = parse_date_input(raw_date)
            if payment_date is None:
                return web.json_response(
                    {"error": "To'lov sanasi noto'g'ri (DD.MM.YYYY)"},
                    status=400,
                )
        else:
            payment_date = today_str()
    except (ValueError, TypeError):
        return web.json_response({"error": "Noto'g'ri parametrlar"}, status=400)

    if client_id <= 0:
        return web.json_response({"error": "Mijoz tanlanmadi"}, status=400)
    try:
        currency = Currency(currency_raw)
    except ValueError:
        return web.json_response(
            {"error": "Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak)"}, status=400
        )

    try:
        if payment_type == "full":
            paid_map, summary = await debt_service.pay_full_debt(
                client_id=client_id,
                payment_date=payment_date,
            )
            return web.json_response({
                "ok": True,
                "paid_amount": paid_map,
                "new_remaining": summary.remaining_by_currency,
                "is_closed": True,
            })
        elif payment_type == "partial":
            amount = int(body.get("amount", 0))
            if amount <= 0:
                return web.json_response(
                    {"error": "To'lov summasi 0 dan katta bo'lishi kerak"}, status=400
                )

            paid_amount, new_remaining, summary = await debt_service.pay_partial_debt(
                client_id=client_id,
                amount=amount,
                payment_date=payment_date,
                currency=currency,
            )
            return web.json_response({
                "ok": True,
                "paid_amount": paid_amount,
                "currency": currency.value,
                "new_remaining": new_remaining,
                "remaining": summary.remaining_by_currency,
                "is_closed": not summary.has_debt,
            })
        else:
            return web.json_response(
                {"error": "To'lov turi noto'g'ri (full yoki partial)"}, status=400
            )

    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except Exception:
        logger.exception("To'lov qilishda kutilmagan xatolik")
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik yuz berdi. Keyinroq urinib ko'ring."},
            status=500,
        )


def setup_routes(app: web.Application) -> None:
    """Route'larni aiohttp ilovasiga ro'yxatga oladi."""
    # Web UI & Health
    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_check)

    # REST APIs
    app.router.add_get("/api/stats", api_get_stats)
    app.router.add_get("/api/summaries", api_get_summaries)
    app.router.add_get("/api/debtors", api_get_debtors)
    app.router.add_get("/api/clients/{id}/report", api_get_client_report)
    app.router.add_post("/api/debts", api_create_debt)
    app.router.add_post("/api/payments", api_make_payment)

    # Static assets
    if _STATIC_DIR.exists():
        app.router.add_static("/static/", _STATIC_DIR, name="static")
