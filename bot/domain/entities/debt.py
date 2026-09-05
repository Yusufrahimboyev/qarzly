"""Domain entity: Debt & DebtProduct.

Har bir qarz yozuvi (operatsiyasi) ning biznes modeli. Bir qarzda bir nechta
tovar bo'lishi mumkin — har bir tovar DebtProduct sifatida saqlanadi.

Sana domainda `datetime.date` sifatida saqlanadi: matnli ("DD.MM.YYYY")
ko'rinish faqat presentation qatlamida hosil qilinadi. Aks holda saralash va
FIFO taqsimoti matn tartibida ishlab, noto'g'ri natija berardi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from enum import StrEnum

from bot.domain.entities.currency import Currency

# Domain invariantlari uchun chegaralar (BIGINT overflow va bema'ni
# kiritmalardan himoya).
MAX_MONEY = 9_000_000_000_000_000
MAX_QUANTITY = 1_000_000
MAX_PRODUCTS_PER_DEBT = 50


class DebtStatus(StrEnum):
    ACTIVE   = "active"
    PAID     = "paid"
    TRASHED  = "trashed"


@dataclass(frozen=True, slots=True)
class DebtProduct:
    """Bitta tovar yozuvi (qarz tarkibidagi har bir tovar).

    Har bir tovarning o'z valyutasi bor (UZS yoki USD) — bir xaridda
    ba'zi tovarlar so'mda, ba'zilari dollarda bo'lishi mumkin.
    """

    name: str
    quantity: int = 1
    price_per_unit: int = 0
    currency: Currency = Currency.UZS

    def __post_init__(self) -> None:
        # Valyuta matn ko'rinishida ("USD") kelsa ham entity ichida har doim
        # `Currency` bo'ladi — shu tufayli taqqoslash va serializatsiya
        # bir xil ishlaydi.
        if not isinstance(self.currency, Currency):
            object.__setattr__(self, "currency", Currency(str(self.currency).upper()))

    @property
    def total_price(self) -> int:
        return self.quantity * self.price_per_unit

    def validate(self) -> None:
        """Tovar invariantlarini tekshiradi (nom, miqdor, narx chegaralari).

        Bu tekshiruv API DTO'sidan mustaqil — bot, API yoki test qaysi yo'l
        bilan kelmasin, noto'g'ri tovar bazaga yozilmaydi.
        """
        if not self.name.strip():
            raise ValueError("Tovar nomi bo'sh bo'lishi mumkin emas.")
        if len(self.name) > 80:
            raise ValueError("Tovar nomi 80 belgidan uzun bo'lishi mumkin emas.")
        if not 1 <= self.quantity <= MAX_QUANTITY:
            raise ValueError(
                f"Tovar miqdori 1 va {MAX_QUANTITY} oralig'ida bo'lishi kerak."
            )
        if not 0 < self.price_per_unit <= MAX_MONEY:
            raise ValueError("Tovar narxi 0 dan katta va chegaradan kichik bo'lishi kerak.")
        if self.total_price > MAX_MONEY:
            raise ValueError("Tovarning jami narxi ruxsat etilgan chegaradan katta.")
        if not isinstance(self.currency, Currency):
            raise ValueError("Tovar valyutasi noto'g'ri (UZS yoki USD bo'lishi kerak).")

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "quantity": self.quantity,
            "price_per_unit": self.price_per_unit,
            "currency": self.currency.value,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DebtProduct:
        raw_currency = str(d.get("currency", Currency.UZS.value)).upper()
        try:
            currency = Currency(raw_currency)
        except ValueError:
            # Eski yoki buzilgan yozuvlarda valyuta noma'lum — UZS deb olamiz
            currency = Currency.UZS
        return cls(
            name=str(d.get("name", "")),
            quantity=int(d.get("quantity", 1)),
            price_per_unit=int(d.get("price_per_unit", 0)),
            currency=currency,
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
    debt_date: date
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
