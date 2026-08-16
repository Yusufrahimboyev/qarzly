"""Domain entity: Debt & DebtProduct.

Har bir qarz yozuvi (operatsiyasi) ning biznes modeli. Bir qarzda bir nechta
tovar bo'lishi mumkin — har bir tovar DebtProduct sifatida saqlanadi.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum

from bot.domain.entities.currency import Currency


class DebtStatus(StrEnum):
    ACTIVE = "active"
    PAID = "paid"


@dataclass(frozen=True, slots=True)
class DebtProduct:
    """Bitta tovar yozuvi (qarz tarkibidagi har bir tovar).

    Har bir tovarning o'z valyutasi bor ("UZS" yoki "USD") — bir xaridda
    ba'zi tovarlar so'mda, ba'zilari dollarda bo'lishi mumkin.
    """

    name: str
    quantity: int = 1
    price_per_unit: int = 0
    currency: str = Currency.UZS.value

    @property
    def total_price(self) -> int:
        return self.quantity * self.price_per_unit

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "price_per_unit": self.price_per_unit,
            "currency": self.currency,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DebtProduct:
        return cls(
            name=str(d.get("name", "")),
            quantity=int(d.get("quantity", 1)),
            price_per_unit=int(d.get("price_per_unit", 0)),
            # Eski yozuvlarda currency yo'q — UZS deb olamiz
            currency=str(d.get("currency", Currency.UZS.value)).upper(),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_json(cls, raw: str) -> DebtProduct:
        return cls.from_dict(json.loads(raw))


def parse_products_json(raw: str) -> list[DebtProduct]:
    """JSON matndan tovarlar ro'yxatini parse qiladi.

    Eski yozuvlarda products_json bo'lishi mumkin emas — shu holda bo'sh ro'yxat
    qaytariladi.
    """
    if not raw or raw.strip() in ("", "[]"):
        return []
    try:
        items = json.loads(raw)
        if isinstance(items, list):
            return [DebtProduct.from_dict(p) for p in items if isinstance(p, dict)]
    except (json.JSONDecodeError, TypeError, KeyError):
        pass
    return []


def serialize_products_json(products: list[DebtProduct]) -> str:
    """Tovarlar ro'yxatini JSON matnga aylantiradi."""
    return json.dumps(
        [p.to_dict() for p in products], ensure_ascii=False
    )


def build_summary_name(products: list[DebtProduct]) -> str:
    """Tovarlar ro'yxatidan qisqacha bittagan nom yaratadi.

    Masalan: "Shina — 4 ta, Moy — 2 ta, Akkumulyator — 1 ta"
    """
    if not products:
        return ""
    if len(products) == 1:
        p = products[0]
        return f"{p.name} — {p.quantity} ta" if p.quantity > 1 else p.name
    parts = []
    for p in products:
        if p.quantity > 1:
            parts.append(f"{p.name} — {p.quantity} ta")
        else:
            parts.append(p.name)
    return ", ".join(parts)


@dataclass(frozen=True, slots=True)
class Debt:
    """Qarz operatsiyasi entity'si.

    products — tovarlar ro'yxati; har birining jami narxi
    (quantity × price_per_unit) yig'indisi product_price maydonida saqlanadi.

    product_name — barcha tovarlarning qisqacha birlashtirilgan nomi.
    product_quantity — barcha tovarlar jami miqdori.
    """

    client_id: int
    debt_date: str
    product_name: str
    product_price: int
    original_debt: int
    remaining_debt: int
    product_quantity: int = 1
    currency: Currency = Currency.UZS
    exchange_exists: bool = False
    exchange_product_name: str | None = None
    exchange_product_price: int = 0
    given_money: int = 0
    status: DebtStatus = DebtStatus.ACTIVE
    products: tuple[DebtProduct, ...] = ()
    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def is_paid(self) -> bool:
        return self.remaining_debt <= 0 or self.status == DebtStatus.PAID
