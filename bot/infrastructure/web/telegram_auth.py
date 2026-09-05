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
from collections import deque
from urllib.parse import parse_qsl

from aiohttp import web

logger = logging.getLogger(__name__)

INIT_DATA_HEADER = "X-Telegram-Init-Data"
# Typed request kaliti — string kalitlar NotAppKeyWarning beradi.
TG_USER_KEY: web.RequestKey[dict] = web.RequestKey("tg_user", dict)
MAX_INIT_DATA_AGE_SECONDS = 24 * 60 * 60  # 24 soat — replay hujumlaridan himoya
# Telefon va server soati orasidagi kichik farq normal; undan kattasi
# (kelajakdagi auth_date) qalbaki yoki manipulyatsiya qilingan deb qaraladi.
CLOCK_SKEW_SECONDS = 60

# Mini App sahifasi uchun Content-Security-Policy: faqat Telegram SDK va
# Google Fonts manbalariga ruxsat beriladi.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' https://telegram.org; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; "
    "img-src 'self' data: https:; "
    "connect-src 'self'; "
    "frame-ancestors https://web.telegram.org https://telegram.org; "
    "base-uri 'self'; "
    "form-action 'self'"
)


def validate_init_data(
    raw_init_data: str,
    bot_token: str,
    max_age_seconds: int = MAX_INIT_DATA_AGE_SECONDS,
    clock_skew_seconds: int = CLOCK_SKEW_SECONDS,
) -> dict | None:
    """Telegram initData imzosini tekshiradi va user obyektini qaytaradi.

    Imzo noto'g'ri, eskirgan, kelajakdagi sanali yoki user yo'q bo'lsa
    None qaytaradi.
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
        if auth_date <= 0:
            return None
        age = time.time() - auth_date
        # Yosh oralig'i: -clock_skew <= age <= max_age
        if age < -clock_skew_seconds or age > max_age_seconds:
            return None

        user = json.loads(pairs.get("user", "{}"))
        if not isinstance(user, dict) or "id" not in user:
            return None
        return user
    except (ValueError, TypeError, json.JSONDecodeError):
        return None


class SlidingWindowRateLimiter:
    """Oddiy in-memory sliding-window rate limiter.

    Bir process doirasida ishlaydi (bitta instansiya uchun yetarli). Bir
    nechta replica bo'lsa, Redis asosidagi limiterga o'tish kerak.
    """

    def __init__(self, limit: int, window_seconds: int = 60) -> None:
        self._limit = limit
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

    def allow(self, key: str, now: float | None = None) -> bool:
        """Kalit uchun so'rovga ruxsat berilsa True qaytaradi."""
        current = time.monotonic() if now is None else now
        bucket = self._hits.get(key)
        if bucket is None:
            bucket = deque()
            self._hits[key] = bucket

        threshold = current - self._window
        while bucket and bucket[0] < threshold:
            bucket.popleft()

        if len(bucket) >= self._limit:
            return False

        bucket.append(current)
        self._cleanup(threshold)
        return True

    def _cleanup(self, threshold: float) -> None:
        """Eskirgan kalitlarni tozalaydi (xotira o'sib ketmasligi uchun)."""
        if len(self._hits) < 1000:
            return
        stale = [key for key, hits in self._hits.items() if not hits or hits[-1] < threshold]
        for key in stale:
            self._hits.pop(key, None)


def create_auth_middleware(
    bot_token: str,
    admin_ids: list[int] | str | None = None,
    *,
    allow_open_access: bool = False,
    rate_limit_per_minute: int = 120,
    max_age_seconds: int = MAX_INIT_DATA_AGE_SECONDS,
):
    """/api/* route'lari uchun Telegram initData autentifikatsiya middleware'i.

    - Imzosiz/eskirgan initData yoki Telegram ichidan ochilmagan sahifa → 401.
    - ADMIN_IDS ro'yxatidagi foydalanuvchigina kiradi (aks holda 403).
    - ADMIN_IDS bo'sh bo'lsa kirish taqiqlanadi; ochiq rejim faqat
      `allow_open_access=True` bilan (development) ishlaydi.
    - Har bir foydalanuvchi/IP uchun daqiqadagi so'rovlar soni cheklanadi;
      muvaffaqiyatsiz autentifikatsiya urinishlari ham hisobga olinadi (429).
    """
    allowed_ids: set[int] = set()
    if isinstance(admin_ids, str):
        allowed_ids = {int(x.strip()) for x in admin_ids.split(",") if x.strip().isdigit()}
    elif admin_ids:
        allowed_ids = {int(x) for x in admin_ids}

    limiter = SlidingWindowRateLimiter(limit=rate_limit_per_minute)

    @web.middleware
    async def telegram_auth_middleware(
        request: web.Request,
        handler,
    ):
        if not request.path.startswith("/api/"):
            return await handler(request)

        # Rate limit avval IP bo'yicha — imzosi yo'q so'rovlar ham cheklanadi.
        client_key = request.remote or "unknown"
        if not limiter.allow(f"ip:{client_key}"):
            logger.warning("Rate limit oshib ketdi: remote=%s path=%s", client_key, request.path)
            return web.json_response(
                {"error": "So'rovlar juda tez-tez yuborildi. Biroz kuting."},
                status=429,
                headers={"Retry-After": "60"},
            )

        raw_init_data = request.headers.get(INIT_DATA_HEADER, "")
        user = validate_init_data(
            raw_init_data, bot_token, max_age_seconds=max_age_seconds
        )
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

        user_id = user.get("id")
        if not allowed_ids and not allow_open_access:
            logger.error(
                "ADMIN_IDS sozlanmagan — API kirishi rad etildi: user_id=%s", user_id
            )
            return web.json_response(
                {"error": "Sizga bu ma'lumotlarga kirish huquqi berilmagan."},
                status=403,
            )

        if allowed_ids and user_id not in allowed_ids:
            logger.warning("API'ga admin bo'lmagan foydalanuvchi urindi: %s", user_id)
            return web.json_response(
                {"error": "Sizga bu ma'lumotlarga kirish huquqi berilmagan."},
                status=403,
            )

        if not limiter.allow(f"user:{user_id}"):
            logger.warning("Foydalanuvchi rate limitdan oshdi: user_id=%s", user_id)
            return web.json_response(
                {"error": "So'rovlar juda tez-tez yuborildi. Biroz kuting."},
                status=429,
                headers={"Retry-After": "60"},
            )

        request[TG_USER_KEY] = user
        return await handler(request)

    return telegram_auth_middleware


@web.middleware
async def security_headers_middleware(request: web.Request, handler):
    """Har bir javobga asosiy xavfsizlik header'larini qo'shadi.

    E'tibor: X-Frame-Options o'rnatilmaydi — Telegram Web versiyasi Mini App'ni
    iframe ichida ochadi, bu header uni buzardi. Uning o'rniga CSP dagi
    `frame-ancestors` Telegram domenlarini aniq ko'rsatadi.
    """
    response = await handler(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)

    if request.path.startswith("/api/"):
        # Javoblarda mijozlarning shaxsiy ma'lumotlari bor — hech qayerda
        # keshlanmasligi va initData bo'yicha ajratilishi kerak.
        response.headers.setdefault("Cache-Control", "no-store")
        response.headers.setdefault("Vary", INIT_DATA_HEADER)
    return response
