"""Formatlash va parser funksiyalari uchun testlar."""
from __future__ import annotations

from datetime import date, datetime

from bot.application.common.formatters import (
    clip_button_text,
    esc_html,
    format_date,
    format_money,
    normalize_phone,
    parse_date,
    parse_date_input,
    parse_money,
    to_date,
)
from bot.domain.entities.debt import MAX_MONEY


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


def test_parse_money_rejects_ambiguous_input() -> None:
    """Qat'iy parser noto'g'ri kiritmani jimgina "tuzatmasligi" kerak (M-03)."""
    assert parse_money("-100") is None      # ilgari 100 bo'lardi
    assert parse_money("abc123") is None    # ilgari 123 bo'lardi
    assert parse_money("1.5") is None       # ilgari 15 bo'lardi
    assert parse_money("12.34") is None
    assert parse_money("1 50 000") is None
    assert parse_money("1e9") is None


def test_parse_money_upper_bound() -> None:
    assert parse_money(str(MAX_MONEY)) == MAX_MONEY
    assert parse_money(str(MAX_MONEY + 1)) is None


def test_date_helpers_round_trip() -> None:
    assert parse_date("16.08.2026") == date(2026, 8, 16)
    assert parse_date("2026-08-16") == date(2026, 8, 16)
    assert parse_date("not-a-date") is None
    assert format_date(date(2025, 12, 15)) == "15.12.2025"
    assert format_date(None) == ""
    assert to_date("15.12.2025") == date(2025, 12, 15)
    assert to_date(date(2025, 12, 15)) == date(2025, 12, 15)


def test_to_date_raises_on_invalid() -> None:
    import pytest

    with pytest.raises(ValueError):
        to_date("15/13/2025")


def test_date_sorting_is_chronological() -> None:
    """Sanalar matn emas, `date` sifatida taqqoslanadi (C-03 regressiyasi)."""
    raw = ["31.01.2026", "01.02.2026", "15.12.2025"]
    parsed_dates = [parse_date(value) for value in raw]
    assert all(value is not None for value in parsed_dates)
    ordered = sorted(value for value in parsed_dates if value is not None)
    assert [format_date(d) for d in ordered] == [
        "15.12.2025",
        "31.01.2026",
        "01.02.2026",
    ]
