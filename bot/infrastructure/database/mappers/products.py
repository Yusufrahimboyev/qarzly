"""Tovarlar ro'yxatining JSON serializatsiyasi (persistence tafsiloti).

`products_json` ustuni — bazada saqlash usuli, domain qoidasi emas. Shuning
uchun JSON bilan ishlash domain entity'sida emas, infrastructure qatlamida
joylashgan.
"""
from __future__ import annotations

import json
from collections.abc import Iterable

from bot.domain.entities.debt import DebtProduct


def parse_products_json(raw: str | None) -> list[DebtProduct]:
    """JSON matndan tovarlar ro'yxatini parse qiladi.

    Eski yozuvlarda products_json bo'lmasligi mumkin — shu holda bo'sh ro'yxat
    qaytariladi.
    """
    if not raw or raw.strip() in ("", "[]"):
        return []
    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return []
    if not isinstance(items, list):
        return []
    return [DebtProduct.from_dict(p) for p in items if isinstance(p, dict)]


def serialize_products_json(products: Iterable[DebtProduct]) -> str:
    """Tovarlar ro'yxatini JSON matnga aylantiradi."""
    return json.dumps([p.to_dict() for p in products], ensure_ascii=False)
