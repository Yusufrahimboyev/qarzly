"""Formatlash va parser utilitalari.

Pul summalari, telefon raqamlari va sanalarni to'g'ri qayta ishlash.
"""
from __future__ import annotations

import re
from datetime import datetime
from html import escape
from zoneinfo import ZoneInfo

from bot.domain.entities.currency import Currency


def esc_html(text: object) -> str:
    """Foydalanuvchi kiritgan matnni Telegram HTML rejimi uchun xavfsiz qiladi.

    Ism yoki tovar nomida "<", ">", "&" bo'lsa, escape qilinmasa Telegram
    "can't parse entities" xatosi qaytaradi va xabar umuman yuborilmaydi.
    """
    return escape(str(text))


def clip_button_text(text: str, max_len: int = 64) -> str:
    """Inline tugma matnini Telegram chegarasiga (64 belgi) sig'diradi.

    Uzun ism + summa ko'p belgi bo'lsa Telegram butun keyboard'ni
    qabul qilmaydi — shuning uchun matn kesib qisqartiriladi.
    """
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"

# Server (masalan Render) UTC da ishlashi mumkin — "bugun" sanasi har doim
# O'zbekiston vaqti bo'yicha hisoblanishi kerak.
_TASHKENT_TZ = ZoneInfo("Asia/Tashkent")

# Ko'rsatish tartibi: avval so'm, keyin dollar
_CURRENCY_DISPLAY_ORDER: tuple[str, str] = (Currency.UZS.value, Currency.USD.value)


def now_local() -> datetime:
    """O'zbekiston (Toshkent) vaqti bo'yicha joriy vaqtni qaytaradi."""
    return datetime.now(_TASHKENT_TZ)


def today_str() -> str:
    """Bugungi sanani 'DD.MM.YYYY' ko'rinishida (Toshkent vaqti) qaytaradi."""
    return now_local().strftime("%d.%m.%Y")


def format_money(amount: int | float, currency: str | Currency = Currency.UZS) -> str:
    """Pul miqdorini valyutasiga mos ravishda formatlaydi.

    Masalan: (1500000, UZS) -> "1 500 000 so'm"; (200, USD) -> "200 $".
    """
    int_val = int(round(amount))
    formatted = f"{int_val:,}".replace(",", " ")
    cur = str(currency)
    if cur == Currency.USD.value:
        return f"{formatted} $"
    return f"{formatted} so'm"


def format_money_map(amounts: dict[str, int]) -> str:
    """Bir nechta valyutadagi summalarni bitta qatorga yig'adi.

    Masalan: {"UZS": 1500000, "USD": 200} -> "1 500 000 so'm + 200 $"
    """
    parts = [
        format_money(amounts[cur], cur)
        for cur in _CURRENCY_DISPLAY_ORDER
        if amounts.get(cur, 0) > 0
    ]
    return " + ".join(parts) if parts else format_money(0)


def aggregate_remaining(summaries) -> dict[str, int]:
    """Bir nechta mijoz summary'larining qoldiq qarzlarini valyuta bo'yicha yig'adi."""
    totals: dict[str, int] = {}
    for summary in summaries:
        for cur, amount in summary.remaining_by_currency.items():
            totals[cur] = totals.get(cur, 0) + amount
    return totals


def parse_money(text: str) -> int | None:
    """Foydalanuvchi kiritgan pul matnini butun songa aylantiradi.

    Masalan: "1 500 000", "1.500.000", "1500000 so'm", "2,500,000" -> 1500000.
    Agar noto'g'ri yoki manfiy bo'lsa None qaytaradi.
    """
    if not text:
        return None

    # Faqat raqamlarni ajratib olamiz
    cleaned = re.sub(r"[^\d]", "", text.strip())
    if not cleaned:
        return None

    try:
        val = int(cleaned)
        return val if val >= 0 else None
    except ValueError:
        return None


def parse_date_input(text: str) -> str | None:
    """Foydalanuvchi kiritgan sanani 'DD.MM.YYYY' formatiga standartlashtiradi.

    Qo'llab-quvvatlaydi:
    - 'bugun', 'today' -> hozirgi sana
    - '16.08.2026', '16/08/2026', '16-08-2026'
    - '2026-08-16', '2026.08.16'
    - '16.08.26'
    """
    cleaned = text.strip().lower()
    now = now_local()

    if cleaned in ("bugun", "today", "hozir", "current"):
        return now.strftime("%d.%m.%Y")

    # Turli xil sana formatlarini tekshirish
    date_patterns = [
        ("%d.%m.%Y", r"^\d{1,2}\.\d{1,2}\.\d{4}$"),
        ("%d/%m/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
        ("%d-%m-%Y", r"^\d{1,2}-\d{1,2}-\d{4}$"),
        ("%Y-%m-%d", r"^\d{4}-\d{1,2}-\d{1,2}$"),
        ("%Y.%m.%d", r"^\d{4}\.\d{1,2}\.\d{1,2}$"),
        ("%d.%m.%y", r"^\d{1,2}\.\d{1,2}\.\d{2}$"),
    ]

    for fmt, regex in date_patterns:
        if re.match(regex, cleaned):
            try:
                dt = datetime.strptime(cleaned, fmt)
                # Kelajak yoki o'tmish sanasini to'g'ri 4 xonali yil bilan formatlash
                if dt.year < 100:
                    dt = dt.replace(year=2000 + dt.year)
                return dt.strftime("%d.%m.%Y")
            except ValueError:
                continue

    return None


def normalize_phone(phone: str) -> str:
    """Telefon raqamini tozalaydi va standart formatga keltiradi."""
    cleaned = re.sub(r"[^\d+]", "", phone.strip())
    if cleaned.startswith("998") and not cleaned.startswith("+"):
        cleaned = "+" + cleaned
    elif len(cleaned) == 9 and cleaned.isdigit():
        cleaned = "+998" + cleaned
    return cleaned


def is_valid_phone(phone: str) -> bool:
    """Tozalangan telefon raqami amaldymi (7-15 raqam) ekanini tekshiradi."""
    digits = re.sub(r"\D", "", phone)
    return 7 <= len(digits) <= 15
