"""Filiallar ro'yxati (kod -> ko'rinadigan nom) va ularning baza sxemalari.

Hamma filial bitta PostgreSQL (Supabase) bazasida, lekin har biri o'z sxemasida
(ya'ni jadvallari alohida). Mangit — mavjud ma'lumotlar turgan `public` sxemasi:
unga tegilmaydi. Har filialning o'z boti bor: bot qaysi filialga xizmat qilishi
`.env` dagi `BRANCH` bilan tanlanadi. Yangi filial qo'shish: shu yerga yozuv qo'shing.
"""
from __future__ import annotations

DEFAULT_BRANCH = "mangit"

BRANCH_TITLES: dict[str, str] = {
    "mangit": "Mangit",
    "nukus": "Nukus",
    "lassa": "Lassa",
}

# None — standart (`public`) sxema. Sxema nomi kod bilan bir xil.
BRANCH_SCHEMAS: dict[str, str | None] = {
    "mangit": None,
    "nukus": "nukus",
    "lassa": "lassa",
}

# Moy (Oil) daftari: filialning alohida qarz daftari (o'z sxemasi), miqdori
# litrda. `.env` dagi OIL_ENABLED bilan har bot uchun alohida yoqiladi.
OIL_SUFFIX = "_oil"


def oil_code(code: str) -> str:
    """Filialning Oil daftari kodi va sxemasi, masalan "lassa_oil"."""
    return f"{code}{OIL_SUFFIX}"


def oil_title(code: str) -> str:
    return f"{BRANCH_TITLES[code]} Oil"
