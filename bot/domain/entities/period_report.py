"""Domain entity: PeriodReport — sana oralig'i bo'yicha umumiy hisobot.

Excel eksporti uchun tayyor, allaqachon hisoblangan model. Hech qanday
formatlash yoki kutubxona bu yerda ishlatilmaydi: infrastructure qatlami
faqat shu modelni varaqlarga yozadi.

Barcha pul summalari valyuta bo'yicha ajratilgan (`MoneyMap`) — so'm va
dollar hech qachon qo'shilmaydi.

Balans tenglamasi (har bir valyuta uchun alohida):

    opening_debt + given_total - returned_total == closing_debt

`initial_total` (qarz yaratilganda darhol berilgan pul) bu tenglamaga
kirmaydi: u allaqachon `original_debt` dan ayrilgan, ya'ni `given_total`
ichida hisobga olingan. Shuning uchun u alohida, ma'lumot uchun saqlanadi.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from bot.domain.entities.debt import Debt
from bot.domain.entities.payment import Payment
from bot.domain.entities.report import MoneyMap, empty_money


@dataclass(frozen=True, slots=True)
class PeriodClientRow:
    """Mijozlar kesimidagi bitta qator (davr ichidagi qarzlar bo'yicha).

    `given`, `paid` va `remaining` aynan shu davrda ochilgan qarzlarga
    tegishli, shuning uchun har doim `given - paid == remaining`.
    """

    client_id: int
    full_name: str
    phone: str
    debt_date: date | None
    given: MoneyMap = field(default_factory=empty_money)
    paid: MoneyMap = field(default_factory=empty_money)
    remaining: MoneyMap = field(default_factory=empty_money)
    cash_paid: MoneyMap = field(default_factory=empty_money)
    """Davr ichida shu mijozdan naqd tushgan pul (eski qarzlarga ham tegishli)."""

    @property
    def is_closed(self) -> bool:
        """Davrdagi qarzlari to'liq yopilganmi."""
        return not any(amount > 0 for amount in self.remaining.values())

    @property
    def status_label(self) -> str:
        return "Yopilgan" if self.is_closed else "Qarzdor"


@dataclass(frozen=True, slots=True)
class TopDebtorRow:
    """Eng katta qarzdorlar ro'yxatining bitta qatori.

    Davrga bog'liq emas — mijozning HOZIRGI ochiq qarzi. "Kimda qancha pul
    qolib ketgan" degan savolga davr chegarasidan qat'i nazar javob beradi.
    """

    client_id: int
    full_name: str
    phone: str
    remaining: MoneyMap = field(default_factory=empty_money)


@dataclass(frozen=True, slots=True)
class PeriodMonthRow:
    """Oyma-oy hisobotning bitta qatori.

    `closing` — oy oxiridagi kumulyativ qarzdorlik (davr boshidagi qoldiqdan
    boshlab yig'iladi), ya'ni "qolgan qarz" ustuni.
    """

    year: int
    month: int
    given: MoneyMap = field(default_factory=empty_money)
    returned: MoneyMap = field(default_factory=empty_money)
    closing: MoneyMap = field(default_factory=empty_money)

    @property
    def label(self) -> str:
        return f"{MONTH_NAMES[self.month - 1]} {self.year}"


MONTH_NAMES: tuple[str, ...] = (
    "Yanvar",
    "Fevral",
    "Mart",
    "Aprel",
    "May",
    "Iyun",
    "Iyul",
    "Avgust",
    "Sentabr",
    "Oktabr",
    "Noyabr",
    "Dekabr",
)


@dataclass(frozen=True, slots=True)
class PeriodReport:
    """Davr (sana oralig'i) bo'yicha to'liq hisobot.

    `debts` va `payments` — davr ichidagi xom yozuvlar (Excel'dagi tafsilot
    varaqlari uchun); `client_names` ularni mijoz nomiga bog'lash uchun.
    """

    date_from: date
    date_to: date

    # 1. Umumiy natija
    opening_debt: MoneyMap = field(default_factory=empty_money)
    given_total: MoneyMap = field(default_factory=empty_money)
    returned_total: MoneyMap = field(default_factory=empty_money)
    initial_total: MoneyMap = field(default_factory=empty_money)
    closing_debt: MoneyMap = field(default_factory=empty_money)

    clients_total: int = 0
    debtors_total: int = 0
    period_clients_total: int = 0
    closed_debts_count: int = 0
    open_debts_count: int = 0
    trashed_debts_count: int = 0

    # Hisobot kuni (date_to) bo'yicha kunlik harakat
    day_given: MoneyMap = field(default_factory=empty_money)
    day_returned: MoneyMap = field(default_factory=empty_money)
    day_new_debts: int = 0
    day_closed_debts: int = 0

    # 3-5. Kesimlar
    months: tuple[PeriodMonthRow, ...] = ()
    client_rows: tuple[PeriodClientRow, ...] = ()
    top_by_uzs: tuple[TopDebtorRow, ...] = ()
    top_by_usd: tuple[TopDebtorRow, ...] = ()

    # Tafsilot varaqlari uchun xom ma'lumot
    debts: tuple[Debt, ...] = ()
    payments: tuple[Payment, ...] = ()
    client_names: dict[int, str] = field(default_factory=dict)
    remaining_as_of: dict[int, int] = field(default_factory=dict)
    """{debt_id: davr oxiridagi qoldiq} — bugungi `remaining_debt` emas."""

    @property
    def is_empty(self) -> bool:
        """Davr ichida umuman harakat bo'lmaganmi."""
        return not self.debts and not self.payments
