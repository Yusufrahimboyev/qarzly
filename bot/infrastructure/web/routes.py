"""Infrastructure qatlami: aiohttp web route'lari va REST API.

Telegram Mini App UI va uning backend API lari. /api/* route'lari
Telegram initData autentifikatsiyasidan o'tadi (server.py da ulanadi).
Pydantic orqali qat'iy ma'lumotlar validatsiyasi ta'minlangan.
"""
from __future__ import annotations

import logging
from pathlib import Path

from aiohttp import web
from pydantic import BaseModel, Field, ValidationError

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
from bot.domain.entities.debt import DebtProduct

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parents[3] / "web"
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"


# ==========================================
# PYDANTIC DTOs FOR REQUEST VALIDATION
# ==========================================


class ProductItemDTO(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    quantity: int = Field(default=1, ge=1)
    price_per_unit: int = Field(..., gt=0)
    currency: str = Field(default="UZS")


class CreateDebtDTO(BaseModel):
    client_name: str = Field(..., min_length=1, max_length=80)
    client_phone: str = Field(default="")
    debt_date: str = Field(default="")
    products: list[ProductItemDTO] | None = None
    product_name: str = Field(default="")
    product_price: int = Field(default=0, ge=0)
    product_quantity: int = Field(default=1, ge=1)
    currency: str = Field(default="UZS")
    exchange_exists: bool = Field(default=False)
    exchange_product_name: str | None = None
    exchange_product_price: int = Field(default=0, ge=0)
    exchange_currency: str = Field(default="UZS")
    given_money: int = Field(default=0, ge=0)
    given_currency: str = Field(default="UZS")


class MakePaymentDTO(BaseModel):
    client_id: int = Field(..., gt=0)
    payment_type: str = Field(default="full")
    amount: int = Field(default=0, ge=0)
    currency: str = Field(default="UZS")
    payment_date: str = Field(default="")


# ==========================================
# WEB & HEALTH HANDLERS
# ==========================================


async def health_check(request: web.Request) -> web.Response:
    """Xizmat holatini qaytaradi (monitoring / keep-alive uchun).

    Agar database sozlangan bo'lsa, PostgreSQL ulanishini ham tekshiradi.
    """
    db = request.app.get("database")
    db_ok = True
    if db is not None:
        db_ok = await db.ping()

    status = "ok" if db_ok else "degraded"
    status_code = 200 if db_ok else 503

    return web.json_response(
        {
            "status": status,
            "database": "connected" if db_ok else "disconnected",
            "service": "Qarz Daftar Telegram Bot & WebApp",
        },
        status=status_code,
    )


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

    Pydantic DTO orqali ma'lumotlar to'liq validatsiyadan o'tkaziladi.
    """
    client_service: ClientService = request.app["client_service"]
    debt_service: DebtService = request.app["debt_service"]

    try:
        raw_body = await request.json()
    except Exception:
        return web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    try:
        dto = CreateDebtDTO.model_validate(raw_body)
    except ValidationError as val_err:
        first_err = val_err.errors()[0]
        field_name = " -> ".join(str(loc) for loc in first_err["loc"])
        return web.json_response(
            {"error": f"Noto'g'ri ma'lumot ({field_name}): {first_err['msg']}"},
            status=400,
        )

    client_name = dto.client_name.strip()
    client_phone = normalize_phone(dto.client_phone) if dto.client_phone.strip() else ""

    if client_phone and not is_valid_phone(client_phone):
        return web.json_response(
            {"error": "Telefon raqami noto'g'ri (masalan: +998901234567)"},
            status=400,
        )

    if dto.debt_date.strip():
        debt_date = parse_date_input(dto.debt_date.strip())
        if debt_date is None:
            return web.json_response(
                {"error": "Sana formati noto'g'ri (DD.MM.YYYY, masalan: 17.08.2026)"},
                status=400,
            )
    else:
        debt_date = today_str()

    try:
        exchange_currency = Currency(dto.exchange_currency.upper())
        given_currency = Currency(dto.given_currency.upper())
    except ValueError:
        return web.json_response(
            {"error": "Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak)"},
            status=400,
        )

    # Products massivi mavjud bo'lsa
    products: list[DebtProduct] | None = None
    if dto.products and len(dto.products) > 0:
        products = []
        for idx, p in enumerate(dto.products):
            try:
                p_cur = Currency(p.currency.upper())
            except ValueError:
                return web.json_response(
                    {"error": f"{idx + 1}-tovar valyutasi noto'g'ri (UZS yoki USD)"},
                    status=400,
                )
            products.append(
                DebtProduct(
                    name=p.name.strip(),
                    quantity=p.quantity,
                    price_per_unit=p.price_per_unit,
                    currency=p_cur.value,
                )
            )
    else:
        if not dto.product_name.strip():
            return web.json_response({"error": "Tovar nomi kiritilmadi"}, status=400)
        if dto.product_price <= 0:
            return web.json_response(
                {"error": "Tovar narxi 0 dan katta bo'lishi kerak"}, status=400
            )

    try:
        client, _ = await client_service.get_or_create(
            full_name=client_name,
            phone=client_phone,
        )
        if client.id is None:
            return web.json_response({"error": "Mijoz yaratishda xatolik"}, status=500)

        ex_name = (
            dto.exchange_product_name.strip()
            if dto.exchange_product_name
            else None
        )
        if products:
            saved_debts = await debt_service.create_debts(
                client_id=client.id,
                debt_date=debt_date,
                products=products,
                exchange_exists=dto.exchange_exists,
                exchange_product_name=ex_name,
                exchange_product_price=dto.exchange_product_price,
                exchange_currency=exchange_currency,
                given_money=dto.given_money,
                given_currency=given_currency,
            )
        else:
            single_cur = Currency(dto.currency.upper())
            saved_single = await debt_service.create_debt(
                client_id=client.id,
                debt_date=debt_date,
                product_name=dto.product_name.strip(),
                product_price=dto.product_price,
                product_quantity=dto.product_quantity,
                currency=single_cur,
                exchange_exists=dto.exchange_exists,
                exchange_product_name=ex_name,
                exchange_product_price=dto.exchange_product_price,
                given_money=dto.given_money,
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
        raw_body = await request.json()
    except Exception:
        return web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    try:
        dto = MakePaymentDTO.model_validate(raw_body)
    except ValidationError as val_err:
        first_err = val_err.errors()[0]
        field_name = " -> ".join(str(loc) for loc in first_err["loc"])
        return web.json_response(
            {"error": f"Noto'g'ri ma'lumot ({field_name}): {first_err['msg']}"},
            status=400,
        )

    try:
        currency = Currency(dto.currency.upper())
    except ValueError:
        return web.json_response(
            {"error": "Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak)"}, status=400
        )

    payment_type = dto.payment_type.lower()
    if dto.payment_date.strip():
        payment_date = parse_date_input(dto.payment_date.strip())
        if payment_date is None:
            return web.json_response(
                {"error": "To'lov sanasi noto'g'ri (DD.MM.YYYY)"},
                status=400,
            )
    else:
        payment_date = today_str()

    try:
        if payment_type == "full":
            paid_map, summary = await debt_service.pay_full_debt(
                client_id=dto.client_id,
                payment_date=payment_date,
            )
            return web.json_response({
                "ok": True,
                "paid_amount": paid_map,
                "new_remaining": summary.remaining_by_currency,
                "is_closed": True,
            })
        elif payment_type == "partial":
            if dto.amount <= 0:
                return web.json_response(
                    {"error": "To'lov summasi 0 dan katta bo'lishi kerak"}, status=400
                )

            paid_amount, new_remaining, summary = await debt_service.pay_partial_debt(
                client_id=dto.client_id,
                amount=dto.amount,
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


# ==========================================
# KORZINA (TRASH) API HANDLERS
# ==========================================


async def api_get_paid_debts(request: web.Request) -> web.Response:
    """Barcha yopilgan qarzlarni qaytaradi — Yopilganlar tab uchun.

    Har bir yozuvda mijoz_id, mijoz_nomi, tovar_nomi, sana, valyuta mavjud.
    """
    debt_service: DebtService = request.app["debt_service"]
    client_service: ClientService = request.app["client_service"]

    paid_debts = await debt_service.get_all_paid()

    # Mijozlar ID -> ism xaritasini tuzamiz (bitta so'rovda)
    summaries = await client_service.get_all_summaries()
    client_names: dict[int, str] = {
        s.client.id: s.client.full_name
        for s in summaries
        if s.client.id is not None
    }

    data = [
        {
            "id": d.id,
            "client_id": d.client_id,
            "client_name": client_names.get(d.client_id, "Noma'lum"),
            "product_name": d.product_name,
            "product_quantity": d.product_quantity,
            "product_price": d.product_price,
            "currency": d.currency.value,
            "original_debt": d.original_debt,
            "remaining_debt": d.remaining_debt,
            "debt_date": d.debt_date,
            "status": d.status.value,
        }
        for d in paid_debts
    ]
    return web.json_response(data)


async def api_trash_move(request: web.Request) -> web.Response:
    """Tanlangan yopilgan qarzlarni korzinaga ko'chiradi.

    Body: {"debt_ids": [1, 2, 3]}
    """
    debt_service: DebtService = request.app["debt_service"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    debt_ids = body.get("debt_ids")
    if not isinstance(debt_ids, list) or not debt_ids:
        return web.json_response(
            {"error": "debt_ids ro'yxati bo'sh yoki noto'g'ri"}, status=400
        )
    if not all(isinstance(i, int) and i > 0 for i in debt_ids):
        return web.json_response(
            {"error": "Barcha debt_ids musbat butun son bo'lishi kerak"}, status=400
        )

    try:
        moved = await debt_service.move_to_trash(debt_ids)
        return web.json_response({"ok": True, "moved": moved})
    except Exception:
        logger.exception("Korzinaga ko'chirishda xatolik")
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik"}, status=500
        )


async def api_get_trash(request: web.Request) -> web.Response:
    """Barcha korzina elementlarini qaytaradi."""
    debt_service: DebtService = request.app["debt_service"]
    client_service: ClientService = request.app["client_service"]

    trashed_debts = await debt_service.get_all_trashed()

    summaries = await client_service.get_all_summaries()
    client_names: dict[int, str] = {
        s.client.id: s.client.full_name
        for s in summaries
        if s.client.id is not None
    }

    data = [
        {
            "id": d.id,
            "client_id": d.client_id,
            "client_name": client_names.get(d.client_id, "Noma'lum"),
            "product_name": d.product_name,
            "product_quantity": d.product_quantity,
            "product_price": d.product_price,
            "currency": d.currency.value,
            "original_debt": d.original_debt,
            "remaining_debt": d.remaining_debt,
            "debt_date": d.debt_date,
            "status": d.status.value,
        }
        for d in trashed_debts
    ]
    return web.json_response(data)


async def api_trash_restore(request: web.Request) -> web.Response:
    """Korzinadan tanlangan elementlarni yopilganga qaytaradi.

    Body: {"debt_ids": [1, 2, 3]}
    """
    debt_service: DebtService = request.app["debt_service"]

    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    debt_ids = body.get("debt_ids")
    if not isinstance(debt_ids, list) or not debt_ids:
        return web.json_response(
            {"error": "debt_ids ro'yxati bo'sh yoki noto'g'ri"}, status=400
        )
    if not all(isinstance(i, int) and i > 0 for i in debt_ids):
        return web.json_response(
            {"error": "Barcha debt_ids musbat butun son bo'lishi kerak"}, status=400
        )

    try:
        restored = await debt_service.restore_from_trash(debt_ids)
        return web.json_response({"ok": True, "restored": restored})
    except Exception:
        logger.exception("Korzinadan qaytarishda xatolik")
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik"}, status=500
        )


async def api_trash_purge(request: web.Request) -> web.Response:
    """Korzinani butunlay tozalaydi (qayta tiklab bo'lmaydi).

    O'chirilgan yozuvlar Supabase trash jadvalida arxivlanadi.
    """
    debt_service: DebtService = request.app["debt_service"]

    try:
        deleted = await debt_service.purge_trash()
        return web.json_response({"ok": True, "deleted": deleted})
    except Exception:
        logger.exception("Korzinani tozalashda xatolik")
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik"}, status=500
        )



def setup_routes(app: web.Application) -> None:
    """Route'larni aiohttp ilovasiga ro'yxatga oladi."""
    # Web UI & Health
    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_check)

    # REST APIs — asosiy
    app.router.add_get("/api/stats", api_get_stats)
    app.router.add_get("/api/summaries", api_get_summaries)
    app.router.add_get("/api/debtors", api_get_debtors)
    app.router.add_get("/api/clients/{id}/report", api_get_client_report)
    app.router.add_post("/api/debts", api_create_debt)
    app.router.add_post("/api/payments", api_make_payment)

    # REST APIs — Korzina (Trash)
    app.router.add_get("/api/paid-debts", api_get_paid_debts)
    app.router.add_post("/api/trash/move", api_trash_move)
    app.router.add_get("/api/trash", api_get_trash)
    app.router.add_post("/api/trash/restore", api_trash_restore)
    app.router.add_post("/api/trash/purge", api_trash_purge)

    # Static assets
    if _STATIC_DIR.exists():
        app.router.add_static("/static/", _STATIC_DIR, name="static")
