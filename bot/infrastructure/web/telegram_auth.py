"""Telegram Mini App initData validatsiyasi va API autentifikatsiya middleware'i.

Telegram Mini App har bir sessiya uchun `initData` query-stringini imzolaydi
(HMAC-SHA256, kalit — "WebAppData" dan bot tokeni). Faqat shu imzoni
tekshirgandagina so'rov haqiqiy Telegram foydalanuvchisidan kelganini
bilamiz — URLni bilgan har qanday begona shaxs API'ga kira olmaydi.

Imzo algoritmi: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import time
from urllib.parse import parse_qsl

from aiohttp import web

logger = logging.getLogger(__name__)

INIT_DATA_HEADER = "X-Telegram-Init-Data"
MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60  # 24 soat — replay hujumlaridan himoya


def validate_init_data(
    raw_init_data: str,
    bot_token: str,
    max_age_seconds: int = MAX_INIT_DATA_AGE_SECONDS,
) -> dict | None:
    """Telegram initData imzosini tekshiradi va user obyektini qaytaradi.

    Imzo noto'g'ri, eskirgan yoki user yo'q bo'lsa None qaytaradi.
    """
    if not raw_init_data or not bot_token:
        return None

    try:
        pairs = dict(parse_qsl(raw_init_data, keep_blank_values=True))
        received_hash = pairs.pop("hash", "")
        if not received_hash:
            return None

        # data_check_string: har bir parametr "key=value" ko'rinishida,
        # alfavit bo'yicha saralangan, "\n" bilan ajratilgan
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))

        secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
        calculated_hash = hmac.new(
            secret_key, data_check_string.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        auth_date = int(pairs.get("auth_date", "0"))
        if auth_date <= 0 or (time.time() - auth_date) > max_age_seconds:
            return None

        user = json.loads(pairs.get("user", "{}"))
        if not isinstance(user, dict) or "id" not in user:
            return None
        return user
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


def create_auth_middleware(bot_token: str, admin_ids: list[int]):
    """/api/* route'lari uchun Telegram initData autentifikatsiya middleware'i.

    - Imszosiz/eskirgan initData yoki Telegram ichidan ochilmagan sahifa → 401.
    - ADMIN_IDS sozlangan bo'lsa, ro'yxatdagi foydalanuvchigina kiradi (403).
    - ADMIN_IDS bo'sh bo'lsa har qanday haqiqiy Telegram foydalanuvchisi kiradi
      (bot tomonidagi AdminMiddleware bilan bir xil qoida).
    """

    @web.middleware
    async def telegram_auth_middleware(
        request: web.Request,
        handler,
    ):
        if not request.path.startswith("/api/"):
            return await handler(request)

        raw_init_data = request.headers.get(INIT_DATA_HEADER, "")
        user = validate_init_data(raw_init_data, bot_token)
        if user is None:
            logger.warning(
                "API'ga ruxsatsiz so'rov: path=%s remote=%s",
                request.path,
                request.remote,
            )
            return web.json_response(
                {"error": "Ruxsat berilmagan. Ilovani Telegram ichida oching."},
                status=401,
            )

        if admin_ids and user.get("id") not in admin_ids:
            logger.warning("API'ga admin bo'lmagan foydalanuvchi urindi: %s", user.get("id"))
            return web.json_response(
                {"error": "Sizga bu ma'lumotlarga kirish huquqi berilmagan."},
                status=403,
            )

        request["tg_user"] = user
        return await handler(request)

    return telegram_auth_middleware


@web.middleware
async def security_headers_middleware(request: web.Request, handler):
    """Har bir javurga asosiy xavfsizlik header'larini qo'shadi.

    E'tibor: X-Frame-Options o'rnatilmaydi — Telegram Web versiyasi Mini App'ni
    iframe ichida ochadi, bu header uni buzardi.
    """
    response = await handler(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response
