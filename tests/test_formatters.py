"""Formatlash va parser funksiyalari uchun testlar."""
from __future__ import annotations

from datetime import datetime

from bot.application.common.formatters import (
    format_money,
    normalize_phone,
    parse_date_input,
    parse_money,
)


def test_format_money() -> None:
    assert format_money(1500000) == "1 500 000 so'm"
    assert format_money(0) == "0 so'm"
    assert format_money(25000) == "25 000 so'm"
    assert format_money(123456789) == "123 456 789 so'm"


def test_parse_money() -> None:
    assert parse_money("1 500 000") == 1500000
    assert parse_money("1.500.000 so'm") == 1500000
    assert parse_money("2500000") == 2500000
    assert parse_money("0") == 0
    assert parse_money("") is None
    assert parse_money("abc") is None


def test_parse_date_input() -> None:
    today_str = datetime.now().strftime("%d.%m.%Y")
    assert parse_date_input("bugun") == today_str
    assert parse_date_input("today") == today_str
    assert parse_date_input("16.08.2026") == "16.08.2026"
    assert parse_date_input("16/08/2026") == "16.08.2026"
    assert parse_date_input("2026-08-16") == "16.08.2026"
    assert parse_date_input("not-a-date") is None


def test_normalize_phone() -> None:
    assert normalize_phone("+998901234567") == "+998901234567"
    assert normalize_phone("998901234567") == "+998901234567"
    assert normalize_phone("901234567") == "+998901234567"
    assert normalize_phone("+998 90 123 45 67") == "+998901234567"
