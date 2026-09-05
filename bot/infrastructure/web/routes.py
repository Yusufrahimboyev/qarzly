"""Infrastructure qatlami: aiohttp web route'lari va REST API.

Telegram Mini App UI va uning backend API lari. /api/* route'lari
Telegram initData autentifikatsiyasidan o'tadi (server.py da ulanadi).
Pydantic orqali qat'iy ma'lumotlar validatsiyasi ta'minlangan.

Yozuv (mutation) endpointlari `Idempotency-Key` header'ini qo'llab-quvvatlaydi:
bir xil kalit bilan takror kelgan so'rov yangi qarz yoki to'lov yaratmaydi,
balki birinchi so'rovning javobini qaytaradi.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Annotated, Any

from aiohttp import web
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError

from bot.application.common.formatters import (
    aggregate_remaining,
    format_date,
    is_valid_phone,
    normalize_phone,
    parse_date,
    today,
)
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import (
    MAX_MONEY,
    MAX_PRODUCTS_PER_DEBT,
    MAX_QUANTITY,
    DebtProduct,
)
from bot.infrastructure.database.repositories.idempotency_repository import (
    IdempotencyStore,
)
from bot.infrastructure.web.telegram_auth import TG_USER_KEY

logger = logging.getLogger(__name__)

_WEB_DIR = Path(__file__).resolve().parents[3] / "web"
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"

# Typed aiohttp app kalitlari (string kalitlar NotAppKeyWarning beradi).
CLIENT_SERVICE_KEY: web.AppKey[ClientService] = web.AppKey("client_service", ClientService)
DEBT_SERVICE_KEY: web.AppKey[DebtService] = web.AppKey("debt_service", DebtService)
DATABASE_KEY: web.AppKey[Any] = web.AppKey("database", object)
IDEMPOTENCY_KEY: web.AppKey[IdempotencyStore] = web.AppKey(
    "idempotency_store", IdempotencyStore
)

IDEMPOTENCY_HEADER = "Idempotency-Key"

# Ro'yxat endpointlari uchun sahifa chegaralari.
DEFAULT_PAGE_LIMIT = 200
MAX_PAGE_LIMIT = 1000


# ==========================================
# PYDANTIC DTOs FOR REQUEST VALIDATION
# ==========================================

# Pydantic `min_length` strip'dan oldin ishlaydi — shu sababli bo'sh joydan
# iborat nom ("   ") DTO'dan o'tib ketardi. `strip_whitespace` bilan avval
# tozalanadi, keyin uzunlik tekshiriladi.
NonBlankName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=80),
]
OptionalName = Annotated[
    str,
    StringConstraints(strip_whitespace=True, max_length=80),
]


class ProductItemDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonBlankName
    quantity: int = Field(default=1, ge=1, le=MAX_QUANTITY)
    price_per_unit: int = Field(..., gt=0, le=MAX_MONEY)
    currency: str = Field(default="UZS")


class CreateDebtDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_name: NonBlankName
    client_phone: OptionalName = ""
    debt_date: OptionalName = ""
    products: list[ProductItemDTO] | None = Field(
        default=None, max_length=MAX_PRODUCTS_PER_DEBT
    )
    product_name: OptionalName = ""
    product_price: int = Field(default=0, ge=0, le=MAX_MONEY)
    product_quantity: int = Field(default=1, ge=1, le=MAX_QUANTITY)
    currency: str = Field(default="UZS")
    exchange_exists: bool = Field(default=False)
    exchange_product_name: OptionalName | None = None
    exchange_product_price: int = Field(default=0, ge=0, le=MAX_MONEY)
    exchange_currency: str = Field(default="UZS")
    given_money: int = Field(default=0, ge=0, le=MAX_MONEY)
    given_currency: str = Field(default="UZS")


class MakePaymentDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_id: int = Field(..., gt=0)
    payment_type: str = Field(default="full")
    amount: int = Field(default=0, ge=0, le=MAX_MONEY)
    currency: str = Field(default="UZS")
    payment_date: OptionalName = ""


class DebtIdsDTO(BaseModel):
    model_config = ConfigDict(extra="forbid")

    debt_ids: list[int] = Field(..., min_length=1, max_length=1000)


# ==========================================
# HELPERS
# ==========================================


def _actor_id(request: web.Request) -> int | None:
    """So'rovni bajarayotgan Telegram foydalanuvchi ID si (audit uchun)."""
    user = request.get(TG_USER_KEY)
    if isinstance(user, dict):
        raw_id = user.get("id")
        if isinstance(raw_id, int):
            return raw_id
    return None


def _validation_error_response(val_err: ValidationError) -> web.Response:
    first_err = val_err.errors()[0]
    field_name = " -> ".join(str(loc) for loc in first_err["loc"])
    return web.json_response(
        {"error": f"Noto'g'ri ma'lumot ({field_name}): {first_err['msg']}"},
        status=400,
    )


def _page_params(request: web.Request) -> tuple[int, int]:
    """`limit` va `offset` query parametrlarini xavfsiz o'qiydi."""
    try:
        limit = int(request.query.get("limit", DEFAULT_PAGE_LIMIT))
    except ValueError:
        limit = DEFAULT_PAGE_LIMIT
    try:
        offset = int(request.query.get("offset", 0))
    except ValueError:
        offset = 0
    limit = max(1, min(limit, MAX_PAGE_LIMIT))
    offset = max(0, offset)
    return limit, offset


class _IdempotencyGuard:
    """Mutation endpointlari uchun idempotency yordamchisi.

    Store sozlanmagan bo'lsa (masalan testlarda) shaffof ravishda o'chadi.
    """

    def __init__(self, request: web.Request, scope: str) -> None:
        self._store: IdempotencyStore | None = request.app.get(IDEMPOTENCY_KEY)
        self._key = request.headers.get(IDEMPOTENCY_HEADER, "").strip()
        self._scope = scope
        self._actor_id = _actor_id(request)
        self.reserved = False

    @property
    def active(self) -> bool:
        return bool(self._store is not None and self._key)

    async def check(self) -> web.Response | None:
        """Takroriy so'rovni aniqlaydi.

        Qaytaradi: darhol qaytarilishi kerak bo'lgan javob yoki None.
        """
        if not self.active or self._store is None:
            return None

        self.reserved = await self._store.reserve(self._scope, self._key, self._actor_id)
        if self.reserved:
            return None

        stored = await self._store.get_response(self._scope, self._key)
        if stored:
            logger.info(
                "Idempotent takroriy so'rov: scope=%s actor_id=%s",
                self._scope,
                self._actor_id,
            )
            return web.json_response(text=stored, content_type="application/json")

        return web.json_response(
            {"error": "Bir xil so'rov hozir bajarilmoqda. Biroz kuting."},
            status=409,
        )

    async def store_success(self, payload: dict) -> None:
        if self.active and self.reserved and self._store is not None:
            await self._store.save_response(
                self._scope, self._key, json.dumps(payload, ensure_ascii=False)
            )

    async def release(self) -> None:
        if self.active and self.reserved and self._store is not None:
            await self._store.release(self._scope, self._key)


# ==========================================
# WEB & HEALTH HANDLERS
# ==========================================


async def health_check(request: web.Request) -> web.Response:
    """Xizmat holatini qaytaradi (monitoring / keep-alive uchun).

    Agar database sozlangan bo'lsa, PostgreSQL ulanishini ham tekshiradi.
    """
    db = request.app.get(DATABASE_KEY)
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


def _summary_to_dict(summary) -> dict:
    return {
        "id": summary.client.id,
        "full_name": summary.client.full_name,
        "phone": summary.client.phone,
        "remaining": summary.remaining_by_currency,
        "active_debts_count": summary.active_debts_count,
        "has_debt": summary.has_debt,
        "latest_debt_date": format_date(summary.latest_debt_date),
        "created_at": (
            summary.client.created_at.isoformat() if summary.client.created_at else None
        ),
    }


def _debt_row_to_dict(debt, client_names: dict[int, str]) -> dict:
    return {
        "id": debt.id,
        "client_id": debt.client_id,
        "client_name": client_names.get(debt.client_id, "Noma'lum"),
        "product_name": debt.product_name,
        "product_quantity": debt.product_quantity,
        "product_price": debt.product_price,
        "currency": debt.currency.value,
        "original_debt": debt.original_debt,
        "remaining_debt": debt.remaining_debt,
        "debt_date": format_date(debt.debt_date),
        "status": debt.status.value,
    }


async def api_get_stats(request: web.Request) -> web.Response:
    """Umumiy statistikani qaytaradi (qarzlar valyutalar bo'yicha ajratilgan)."""
    client_service = request.app[CLIENT_SERVICE_KEY]
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
    client_service = request.app[CLIENT_SERVICE_KEY]
    summaries = await client_service.get_all_summaries()
    limit, offset = _page_params(request)
    page = summaries[offset : offset + limit]

    return web.json_response([_summary_to_dict(s) for s in page])


async def api_get_debtors(request: web.Request) -> web.Response:
    """Faqat faol qarzdorlarni qaytaradi."""
    client_service = request.app[CLIENT_SERVICE_KEY]
    debtors = await client_service.get_debtor_summaries()
    limit, offset = _page_params(request)
    page = debtors[offset : offset + limit]

    data = [{**_summary_to_dict(s), "has_debt": True} for s in page]
    return web.json_response(data)


async def api_get_client_report(request: web.Request) -> web.Response:
    """Mijozning to'liq hisobotini (tarixi, exchange, to'lovlar) qaytaradi."""
    debt_service = request.app[DEBT_SERVICE_KEY]
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
                "debt_date": format_date(d.debt_date),
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
                "payment_date": format_date(p.payment_date),
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
    client_service = request.app[CLIENT_SERVICE_KEY]
    debt_service = request.app[DEBT_SERVICE_KEY]

    try:
        raw_body = await request.json()
    except Exception:
        return web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    try:
        dto = CreateDebtDTO.model_validate(raw_body)
    except ValidationError as val_err:
        return _validation_error_response(val_err)

    client_name = dto.client_name
    client_phone = normalize_phone(dto.client_phone) if dto.client_phone else ""

    if client_phone and not is_valid_phone(client_phone):
        return web.json_response(
            {"error": "Telefon raqami noto'g'ri (masalan: +998901234567)"},
            status=400,
        )

    if dto.debt_date:
        debt_date = parse_date(dto.debt_date)
        if debt_date is None:
            return web.json_response(
                {"error": "Sana formati noto'g'ri (DD.MM.YYYY, masalan: 17.08.2026)"},
                status=400,
            )
    else:
        debt_date = today()

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
    if dto.products:
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
                    name=p.name,
                    quantity=p.quantity,
                    price_per_unit=p.price_per_unit,
                    currency=p_cur,
                )
            )
    else:
        if not dto.product_name:
            return web.json_response({"error": "Tovar nomi kiritilmadi"}, status=400)
        if dto.product_price <= 0:
            return web.json_response(
                {"error": "Tovar narxi 0 dan katta bo'lishi kerak"}, status=400
            )

    guard = _IdempotencyGuard(request, "create_debt")
    early = await guard.check()
    if early is not None:
        return early

    try:
        client, _ = await client_service.get_or_create(
            full_name=client_name,
            phone=client_phone,
        )
        if client.id is None:
            await guard.release()
            return web.json_response({"error": "Mijoz yaratishda xatolik"}, status=500)

        ex_name = dto.exchange_product_name or None
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
                product_name=dto.product_name,
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

        await guard.store_success(response)
        return web.json_response(response)
    except ValueError as exc:
        await guard.release()
        return web.json_response({"error": str(exc)}, status=400)
    except Exception:
        await guard.release()
        logger.exception(
            "Qarz yaratishda kutilmagan xatolik (actor_id=%s)", _actor_id(request)
        )
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik yuz berdi. Keyinroq urinib ko'ring."},
            status=500,
        )


async def api_make_payment(request: web.Request) -> web.Response:
    """To'lov qilish (to'liq yoki qisman) API handler'i."""
    debt_service = request.app[DEBT_SERVICE_KEY]

    try:
        raw_body = await request.json()
    except Exception:
        return web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    try:
        dto = MakePaymentDTO.model_validate(raw_body)
    except ValidationError as val_err:
        return _validation_error_response(val_err)

    try:
        currency = Currency(dto.currency.upper())
    except ValueError:
        return web.json_response(
            {"error": "Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak)"}, status=400
        )

    payment_type = dto.payment_type.lower()
    if dto.payment_date:
        payment_date = parse_date(dto.payment_date)
        if payment_date is None:
            return web.json_response(
                {"error": "To'lov sanasi noto'g'ri (DD.MM.YYYY)"},
                status=400,
            )
    else:
        payment_date = today()

    if payment_type not in ("full", "partial"):
        return web.json_response(
            {"error": "To'lov turi noto'g'ri (full yoki partial)"}, status=400
        )
    if payment_type == "partial" and dto.amount <= 0:
        return web.json_response(
            {"error": "To'lov summasi 0 dan katta bo'lishi kerak"}, status=400
        )

    guard = _IdempotencyGuard(request, "make_payment")
    early = await guard.check()
    if early is not None:
        return early

    try:
        if payment_type == "full":
            paid_map, summary = await debt_service.pay_full_debt(
                client_id=dto.client_id,
                payment_date=payment_date,
            )
            response = {
                "ok": True,
                "paid_amount": paid_map,
                "new_remaining": summary.remaining_by_currency,
                "is_closed": True,
            }
        else:
            paid_amount, new_remaining, summary = await debt_service.pay_partial_debt(
                client_id=dto.client_id,
                amount=dto.amount,
                payment_date=payment_date,
                currency=currency,
            )
            response = {
                "ok": True,
                "paid_amount": paid_amount,
                "currency": currency.value,
                "new_remaining": new_remaining,
                "remaining": summary.remaining_by_currency,
                "is_closed": not summary.has_debt,
            }

        await guard.store_success(response)
        return web.json_response(response)

    except ValueError as exc:
        await guard.release()
        return web.json_response({"error": str(exc)}, status=400)
    except Exception:
        await guard.release()
        logger.exception(
            "To'lov qilishda kutilmagan xatolik (actor_id=%s)", _actor_id(request)
        )
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik yuz berdi. Keyinroq urinib ko'ring."},
            status=500,
        )


# ==========================================
# KORZINA (TRASH) API HANDLERS
# ==========================================


async def _client_name_map(client_service: ClientService) -> dict[int, str]:
    all_clients = await client_service.get_all_clients()
    return {c.id: c.full_name for c in all_clients if c.id is not None}


async def api_get_paid_debts(request: web.Request) -> web.Response:
    """Yopilgan qarzlarni qaytaradi — Yopilganlar tab uchun.

    Har bir yozuvda mijoz_id, mijoz_nomi, tovar_nomi, sana, valyuta mavjud.
    """
    debt_service = request.app[DEBT_SERVICE_KEY]
    client_service = request.app[CLIENT_SERVICE_KEY]
    limit, offset = _page_params(request)

    paid_debts = await debt_service.get_all_paid(limit=limit, offset=offset)
    client_names = await _client_name_map(client_service)

    return web.json_response(
        [_debt_row_to_dict(d, client_names) for d in paid_debts]
    )


async def _read_debt_ids(request: web.Request) -> tuple[list[int] | None, web.Response | None]:
    try:
        body = await request.json()
    except Exception:
        return None, web.json_response({"error": "Yaroqsiz JSON format"}, status=400)

    try:
        dto = DebtIdsDTO.model_validate(body)
    except ValidationError as val_err:
        return None, _validation_error_response(val_err)

    if not all(i > 0 for i in dto.debt_ids):
        return None, web.json_response(
            {"error": "Barcha debt_ids musbat butun son bo'lishi kerak"}, status=400
        )
    return dto.debt_ids, None


async def api_trash_move(request: web.Request) -> web.Response:
    """Tanlangan yopilgan qarzlarni korzinaga ko'chiradi.

    Body: {"debt_ids": [1, 2, 3]}
    """
    debt_service = request.app[DEBT_SERVICE_KEY]

    debt_ids, error = await _read_debt_ids(request)
    if error is not None:
        return error

    try:
        moved = await debt_service.move_to_trash(debt_ids or [], actor_id=_actor_id(request))
        return web.json_response({"ok": True, "moved": moved})
    except Exception:
        logger.exception("Korzinaga ko'chirishda xatolik")
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik"}, status=500
        )


async def api_get_trash(request: web.Request) -> web.Response:
    """Korzina elementlarini qaytaradi."""
    debt_service = request.app[DEBT_SERVICE_KEY]
    client_service = request.app[CLIENT_SERVICE_KEY]
    limit, offset = _page_params(request)

    trashed_debts = await debt_service.get_all_trashed(limit=limit, offset=offset)
    client_names = await _client_name_map(client_service)

    return web.json_response(
        [_debt_row_to_dict(d, client_names) for d in trashed_debts]
    )


async def api_trash_restore(request: web.Request) -> web.Response:
    """Korzinadan tanlangan elementlarni yopilganga qaytaradi.

    Body: {"debt_ids": [1, 2, 3]}
    """
    debt_service = request.app[DEBT_SERVICE_KEY]

    debt_ids, error = await _read_debt_ids(request)
    if error is not None:
        return error

    try:
        restored = await debt_service.restore_from_trash(
            debt_ids or [], actor_id=_actor_id(request)
        )
        return web.json_response({"ok": True, "restored": restored})
    except Exception:
        logger.exception("Korzinadan qaytarishda xatolik")
        return web.json_response(
            {"error": "Serverda kutilmagan xatolik"}, status=500
        )


async def api_trash_purge(request: web.Request) -> web.Response:
    """Korzinani butunlay tozalaydi (qayta tiklab bo'lmaydi).

    O'chirilgan qarzlar `trash`, to'lov tarixi esa `trash_payments`
    arxivida saqlanadi — moliyaviy audit trail yo'qolmaydi.
    """
    debt_service = request.app[DEBT_SERVICE_KEY]

    try:
        deleted = await debt_service.purge_trash(actor_id=_actor_id(request))
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
