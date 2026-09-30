"""Filiallar ro'yxati (kod -> ko'rinadigan nom) va ularning baza sxemalari.

Hamma filial bitta PostgreSQL (Supabase) bazasida, lekin har biri o'z sxemasida
(ya'ni jadvallari alohida). Mangit — mavjud ma'lumotlar turgan `public` sxemasi:
unga tegilmaydi. Yangi filial qo'shish: shu yerga yozuv qo'shing.
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
