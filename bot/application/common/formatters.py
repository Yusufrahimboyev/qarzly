"""Formatlash va parser utilitalari.

Pul summalari, telefon raqamlari va sanalarni to'g'ri qayta ishlash.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from html import escape
from zoneinfo import ZoneInfo

from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import MAX_MONEY


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


def today() -> date:
    """Bugungi sanani (Toshkent vaqti) `datetime.date` sifatida qaytaradi."""
    return now_local().date()


def today_str() -> str:
    """Bugungi sanani 'DD.MM.YYYY' ko'rinishida (Toshkent vaqti) qaytaradi."""
    return format_date(today())


def format_date(value: date | datetime | None) -> str:
    """Sanani foydalanuvchiga ko'rsatiladigan 'DD.MM.YYYY' matniga aylantiradi.

    Sana domainda va bazada `DATE` sifatida saqlanadi — matnli format faqat
    shu yerda, presentation chegarasida hosil qilinadi.
    """
    if value is None:
        return ""
    if isinstance(value, datetime):
        value = value.date()
    return value.strftime("%d.%m.%Y")


def to_date(value: date | datetime | str) -> date:
    """Sanani `datetime.date` ga keltiradi (matn bo'lsa parse qiladi).

    Servis va repository qatlamlari faqat `date` bilan ishlaydi; matnli sana
    faqat tashqi chegarada (bot, API) qabul qilinadi.
    """
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    parsed = parse_date(str(value))
    if parsed is None:
        raise ValueError(
            "Sana formati noto'g'ri (DD.MM.YYYY, masalan: 17.08.2026)."
        )
    return parsed


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


# Pul chegarasi domainda belgilangan (MAX_MONEY) — parser ham aynan shu
# chegaraga tayanadi, ya'ni bitta manba.

# "1 500 000", "1.500.000", "2,500,000" yoki "2500000" — guruhlar aynan
# 3 xonali bo'lishi shart. Shu sababli "1.5" yoki "-100" qabul qilinmaydi.
_MONEY_RE = re.compile(r"^\d{1,3}(?:[ \u00a0_.,]\d{3})+$|^\d+$")
_MONEY_SUFFIX_RE = re.compile(
    r"\s*(so\u2018m|so'm|som|sum|uzs|usd|dollar|\$)\.?$",
    re.IGNORECASE,
)


def parse_money(text: str) -> int | None:
    """Foydalanuvchi kiritgan pul matnini butun songa aylantiradi.

    Masalan: "1 500 000", "1.500.000", "1500000 so'm", "2,500,000" -> 1500000.

    Qat'iy parser: raqam bo'lmagan belgilarni jimgina tashlab yubormaydi.
    "-100", "abc123", "1.5" kabi kiritmalar None qaytaradi — aks holda
    foydalanuvchi kutmagan summa saqlanib qolardi.
    """
    if not text:
        return None

    value = _MONEY_SUFFIX_RE.sub("", str(text).strip()).strip()
    if not value or not _MONEY_RE.fullmatch(value):
        return None

    digits = re.sub(r"[ \u00a0_.,]", "", value)
    try:
        parsed = int(digits)
    except ValueError:
        return None
    return parsed if 0 <= parsed <= MAX_MONEY else None


# Qo'llab-quvvatlanadigan sana formatlari (parse tartibi muhim).
_DATE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("%d.%m.%Y", r"^\d{1,2}\.\d{1,2}\.\d{4}$"),
    ("%d/%m/%Y", r"^\d{1,2}/\d{1,2}/\d{4}$"),
    ("%d-%m-%Y", r"^\d{1,2}-\d{1,2}-\d{4}$"),
    ("%Y-%m-%d", r"^\d{4}-\d{1,2}-\d{1,2}$"),
    ("%Y.%m.%d", r"^\d{4}\.\d{1,2}\.\d{1,2}$"),
    ("%d.%m.%y", r"^\d{1,2}\.\d{1,2}\.\d{2}$"),
)

_TODAY_WORDS = ("bugun", "today", "hozir", "current")


def parse_date(text: str) -> date | None:
    """Foydalanuvchi kiritgan sanani `datetime.date` ga aylantiradi.

    Qo'llab-quvvatlaydi:
    - 'bugun', 'today' -> hozirgi sana
    - '16.08.2026', '16/08/2026', '16-08-2026'
    - '2026-08-16', '2026.08.16'
    - '16.08.26'
    """
    if not text:
        return None

    cleaned = str(text).strip().lower()
    if cleaned in _TODAY_WORDS:
        return today()

    for fmt, regex in _DATE_PATTERNS:
        if re.match(regex, cleaned):
            try:
                dt = datetime.strptime(cleaned, fmt)
            except ValueError:
                continue
            if dt.year < 100:
                dt = dt.replace(year=2000 + dt.year)
            return dt.date()

    return None


def parse_date_input(text: str) -> str | None:
    """`parse_date` ning matnli ko'rinishi ('DD.MM.YYYY' yoki None)."""
    parsed = parse_date(text)
    return format_date(parsed) if parsed is not None else None


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
