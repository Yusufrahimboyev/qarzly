"""Konfiguratsiya (fail-closed authorization) uchun testlar."""
from __future__ import annotations

import pytest
from pydantic import SecretStr, ValidationError

from bot.core.config import Settings

TOKEN = SecretStr("123456:test-token")
DSN = SecretStr("postgresql://test:test@localhost:5432/test")


def test_empty_admin_ids_rejected() -> None:
    """ADMIN_IDS bo'sh bo'lsa ilova ishga tushmasligi kerak (C-01)."""
    with pytest.raises(ValidationError, match="ADMIN_IDS majburiy"):
        Settings(bot_token=TOKEN, admin_ids=[], database_url=DSN)


def test_open_access_requires_explicit_flag() -> None:
    settings = Settings(
        bot_token=TOKEN,
        admin_ids=[],
        allow_open_access=True,
        database_url=DSN,
    )
    assert settings.admin_id_list == []
    assert settings.allow_open_access is True


def test_admin_ids_parsed_from_string() -> None:
    settings = Settings(bot_token=TOKEN, admin_ids="111, 222", database_url=DSN)
    assert settings.admin_id_list == [111, 222]


def test_secrets_are_not_exposed_in_repr() -> None:
    """Token va DSN log/traceback'ga tushib ketmasligi kerak."""
    settings = Settings(bot_token=TOKEN, admin_ids=[1], database_url=DSN)
    dumped = repr(settings)
    assert "test-token" not in dumped
    assert "postgresql://test:test@" not in dumped
    assert settings.dsn.startswith("postgresql://")


def test_empty_database_url_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(bot_token=TOKEN, admin_ids=[1], database_url=SecretStr("  "))
