"""Qarz yaratishda tugmalar orqali tanlanadigan tovar katalogi.

Tovar nomi shu tanlovlardan bitta matn qilib yig'iladi
(masalan: "Shina Kumho R16") — bazada alohida ustunlar kerak emas.
"""
from __future__ import annotations

from bot.i18n import N_

# Tur nomlari tugmada tarjima qilinadi (`_()`), tovar nomida esa lotinda qoladi.
PRODUCT_TYPES: dict[str, str] = {
    "shina": N_("Shina"),
    "diska": N_("Diska"),
    "akkum": N_("Akkumulyator"),
}

BRANDS: dict[str, list[str]] = {
    "shina": ["Lassa", "Bars", "Kumho"],
    "diska": ["Zitto", "Falcon", "Qo'qon diska", "Литий диска", "Диска"],
    "akkum": [
        "Jazz", "Qaynar", "Energy", "Delkor",
        "Atlant", "Inera", "Largo", "Vinco", "Rover", "Wolter",
    ],
}

# Akkumulyator razmeri tugmalar orqali tanlanadi, qolganlari qo'lda yoziladi.
# Brendga xos ro'yxat bo'lmasa (yoki brend qo'lda yozilgan bo'lsa) — umumiy ro'yxat.
DEFAULT_AKKUM_SIZES: list[str] = [
    f"{ah}Ah" for ah in (35, 45, 55, 60, 62, 66, 75, 90, 100, 132, 190, 240)
]

_JAZZ_SIZES: list[str] = [
    "35R но", "35L но", "50R но", "50L но", "50L EFB",
    "60L но", "60R но", "70L EFB", "75L но", "75R но", "75R сз", "75L сз",
    "90R но", "90L но", "100 ач", "140 ач", "190 ач", "225 ач", "240 ач",
]

AKKUM_SIZES: dict[str, list[str]] = {
    "Jazz": _JAZZ_SIZES,
    # Vaqtincha Jazz razmerlari — o'z ro'yxatlari kelguncha.
    "Qaynar": _JAZZ_SIZES,
    "Energy": _JAZZ_SIZES,
    "Delkor": _JAZZ_SIZES,
    "Atlant": ["60/45L сз", "60/45R сз", "90/77L сз", "132/105 ач", "190/150 ач"],
    "Inera": ["36R ач", "60L ач"],
    "Largo": ["36L ач"],
    "Vinco": ["60R ач", "75L ач"],
    "Rover": ["60R ач"],
    "Wolter": ["60R ач"],
}


def akkum_sizes(brand: str) -> list[str]:
    """Brendning akkumulyator razmerlari (bo'lmasa — umumiy ro'yxat)."""
    return AKKUM_SIZES.get(brand, DEFAULT_AKKUM_SIZES)


MONTHS: list[str] = [
    N_("Yanvar"), N_("Fevral"), N_("Mart"), N_("Aprel"), N_("May"), N_("Iyun"),
    N_("Iyul"), N_("Avgust"), N_("Sentabr"), N_("Oktabr"), N_("Noyabr"), N_("Dekabr"),
]


def build_product_name(type_key: str, brand: str, size: str) -> str:
    """Tanlangan tur, brend va razmerdan tovar nomini yig'adi.

    Brend nomida tur so'zi bo'lsa ("Qo'qon diska"), tur takrorlanmaydi.
    """
    type_label = PRODUCT_TYPES[type_key]
    brand_lower = brand.lower()
    if type_label.lower() in brand_lower or "диска" in brand_lower:
        parts = [brand, size]
    else:
        parts = [type_label, brand, size]
    return " ".join(p for p in parts if p)
