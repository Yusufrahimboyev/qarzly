"""Qarz yaratishda tugmalar orqali tanlanadigan tovar katalogi.

Tovar nomi shu tanlovlardan bitta matn qilib yig'iladi
(masalan: "Shina Kumho R16") — bazada alohida ustunlar kerak emas.
"""
from __future__ import annotations

PRODUCT_TYPES: dict[str, str] = {
    "shina": "Shina",
    "diska": "Diska",
    "akkum": "Akkumulyator",
}

BRANDS: dict[str, list[str]] = {
    "shina": ["Lassa", "Bars", "Kumho"],
    "diska": ["Zitto", "Falcon", "Qo'qon diska", "Литий диска", "Диска"],
    "akkum": ["Jazz", "Qaynar", "Energy", "Delkor"],
}

# Akkumulyator razmeri tugmalar orqali tanlanadi, qolganlari qo'lda yoziladi.
AKKUM_SIZES_AH: list[int] = [35, 45, 55, 60, 62, 66, 75, 90, 100, 132, 190, 240]

MONTHS: list[str] = [
    "Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
    "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr",
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
