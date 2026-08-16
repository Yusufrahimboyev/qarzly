"""Formatlash va parser utilitalari.

Pul summalari, telefon raqamlari va sanalarni to'g'ri qayta ishlash.
"""
from __future__ import annotations

import re
from datetime import datetime


def format_money(amount: int | float) -> str:
    """Pul miqdorini minglik probellar bilan chiroyli formatlaydi.

    Masalan: 1500000 -> "1 500 000 so'm"
    """
    int_val = int(round(amount))
    formatted = f"{int_val:,}".replace(",", " ")
    return f"{formatted} so'm"


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
    now = datetime.now()

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
