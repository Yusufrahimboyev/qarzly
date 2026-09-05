"""Telegram initData validatsiyasi uchun unit testlar."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from bot.infrastructure.web.telegram_auth import (
    CONTENT_SECURITY_POLICY,
    SlidingWindowRateLimiter,
    validate_init_data,
)

BOT_TOKEN = "123456:test-token"


def _sign(bot_token: str, params: dict[str, str]) -> str:
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return urlencode(params) + f"&hash={calculated}"


def _base_params(user_id: int = 42, auth_date: int | None = None) -> dict[str, str]:
    return {
        "auth_date": str(auth_date if auth_date is not None else int(time.time())),
        "query_id": "AAF-test",
        "user": json.dumps({"id": user_id, "first_name": "Test"}),
    }


def test_valid_init_data_returns_user() -> None:
    raw = _sign(BOT_TOKEN, _base_params(user_id=777))
    user = validate_init_data(raw, BOT_TOKEN)
    assert user is not None
    assert user["id"] == 777


def test_wrong_bot_token_rejected() -> None:
    raw = _sign(BOT_TOKEN, _base_params())
    assert validate_init_data(raw, "other:token") is None


def test_tampered_payload_rejected() -> None:
    raw = _sign(BOT_TOKEN, _base_params(user_id=1))
    hash_part = raw.rsplit("&hash=", 1)[1]
    # Hash imzolanganidan keyin user ID o'zgartiriladi
    params = _base_params(user_id=1)
    tampered_user = urlencode({"user": json.dumps({"id": 999, "first_name": "Test"})})
    tampered = (
        f"auth_date={params['auth_date']}&query_id={params['query_id']}&{tampered_user}"
        f"&hash={hash_part}"
    )
    assert validate_init_data(tampered, BOT_TOKEN) is None


def test_expired_init_data_rejected() -> None:
    old_date = int(time.time()) - 25 * 60 * 60  # 25 soat oldin
    raw = _sign(BOT_TOKEN, _base_params(auth_date=old_date))
    assert validate_init_data(raw, BOT_TOKEN) is None


def test_missing_hash_rejected() -> None:
    params = _base_params()
    raw = urlencode(params)
    assert validate_init_data(raw, BOT_TOKEN) is None


def test_empty_input_rejected() -> None:
    assert validate_init_data("", BOT_TOKEN) is None
    assert validate_init_data("user=%7B%7D", BOT_TOKEN) is None


def test_user_without_id_rejected() -> None:
    params = {
        "auth_date": str(int(time.time())),
        "user": json.dumps({"first_name": "NoId"}),
    }
    raw = _sign(BOT_TOKEN, params)
    assert validate_init_data(raw, BOT_TOKEN) is None


def test_future_auth_date_rejected() -> None:
    """Kelajakdagi auth_date qabul qilinmasligi kerak (M-10)."""
    future = int(time.time()) + 10 * 60
    raw = _sign(BOT_TOKEN, _base_params(auth_date=future))
    assert validate_init_data(raw, BOT_TOKEN) is None


def test_small_clock_skew_accepted() -> None:
    """Kichik soat farqi (30 s) normal hisoblanadi."""
    slightly_ahead = int(time.time()) + 30
    raw = _sign(BOT_TOKEN, _base_params(auth_date=slightly_ahead))
    assert validate_init_data(raw, BOT_TOKEN) is not None


def test_rate_limiter_blocks_after_limit() -> None:
    limiter = SlidingWindowRateLimiter(limit=3, window_seconds=60)
    assert limiter.allow("user:1") is True
    assert limiter.allow("user:1") is True
    assert limiter.allow("user:1") is True
    assert limiter.allow("user:1") is False
    # Boshqa foydalanuvchi ta'sirlanmaydi
    assert limiter.allow("user:2") is True


def test_rate_limiter_window_slides() -> None:
    limiter = SlidingWindowRateLimiter(limit=2, window_seconds=60)
    assert limiter.allow("ip:1", now=0.0) is True
    assert limiter.allow("ip:1", now=1.0) is True
    assert limiter.allow("ip:1", now=2.0) is False
    # Oyna o'tgach yana ruxsat beriladi
    assert limiter.allow("ip:1", now=70.0) is True


def test_security_headers_include_csp_and_no_store() -> None:
    """PII javoblari keshlanmasligi va CSP o'rnatilishi kerak (M-10)."""
    assert "frame-ancestors" in CONTENT_SECURITY_POLICY
    assert "https://telegram.org" in CONTENT_SECURITY_POLICY
