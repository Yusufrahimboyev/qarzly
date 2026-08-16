"""Formatlash va parser funksiyalari uchun testlar."""
from __future__ import annotations

from datetime import datetime

from bot.application.common.formatters import (
    clip_button_text,
    esc_html,
    format_money,
    normalize_phone,
    parse_date_input,
    parse_money,
)


def test_esc_html() -> None:
    """Foydalanuvchi kiritgan matn Telegram HTML'ni buzmasligi kerak."""
    assert esc_html("Ali <Bek> & Co") == "Ali &lt;Bek&gt; &amp; Co"
    assert esc_html("Oddiy ism") == "Oddiy ism"
    assert esc_html(123) == "123"


def test_clip_button_text() -> None:
    """Inline tugma matni 64 belgidan oshmasligi kerak."""
    assert clip_button_text("qisqa") == "qisqa"
    long_text = "🔴 " + "a" * 100
    clipped = clip_button_text(long_text)
    assert len(clipped) <= 64
    assert clipped.endswith("…")


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
