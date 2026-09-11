"""Application qatlami: davr hisobotini xom ma'lumotdan yig'ish (sof funksiya).

Bu modulda I/O yo'q — barcha yozuvlar tayyor ro'yxat sifatida beriladi.
Shu sababli hisob-kitob mantig'i bazasiz, to'g'ridan-to'g'ri unit testlar
bilan tekshiriladi.

MUHIM (ikki marta hisoblash muammosi):
`original_debt = tovarlar narxi − exchange − berilgan_pul` ko'rinishida
saqlanadi, ya'ni qarz yaratilganda darhol berilgan pul undan ALLAQACHON
ayrilgan. Ammo o'sha pul `payments` jadvaliga ham `initial` turi bilan
yoziladi. Agar `initial` to'lovlar "qaytarilgan pul" ga qo'shilsa, qoldiq
ikki marta kamayib ketardi — shuning uchun davr arifmetikasida faqat
`full` va `partial` to'lovlar qatnashadi, `initial` esa alohida ko'rsatiladi.
"""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import date

from bot.domain.entities.client import Client
from bot.domain.entities.debt import Debt, DebtStatus
from bot.domain.entities.payment import Payment, PaymentType
from bot.domain.entities.period_report import (
    PeriodClientRow,
    PeriodMonthRow,
    PeriodReport,
    TopDebtorRow,
)
from bot.domain.entities.report import MoneyMap

TOP_DEBTORS_LIMIT = 10

_REPAYMENT_TYPES = (PaymentType.FULL, PaymentType.PARTIAL)


def _add(target: MoneyMap, currency: str, amount: int) -> None:
    """Valyuta bo'yicha summani qo'shadi (0 bo'lsa ham kalitni yaratadi)."""
    target[currency] = target.get(currency, 0) + amount


def _combine(*maps: MoneyMap, signs: Sequence[int] | None = None) -> MoneyMap:
    """Bir nechta MoneyMap'ni ishorali qo'shadi: (a, b, c) & (+1, +1, -1)."""
    multipliers = signs or [1] * len(maps)
    result: MoneyMap = {}
    for money, sign in zip(maps, multipliers, strict=True):
        for currency, amount in money.items():
            _add(result, currency, sign * amount)
    return result


def _month_key(value: date) -> tuple[int, int]:
    return value.year, value.month


def _month_range(date_from: date, date_to: date) -> list[tuple[int, int]]:
    """Davrni qamrab olgan (yil, oy) juftliklari ketma-ketligi."""
    keys: list[tuple[int, int]] = []
    year, month = date_from.year, date_from.month
    last = _month_key(date_to)
    while (year, month) <= last:
        keys.append((year, month))
        month += 1
        if month > 12:
            year, month = year + 1, 1
    return keys


def _is_repayment(payment: Payment) -> bool:
    return payment.payment_type in _REPAYMENT_TYPES


def validate_period_bounds(
    date_from: date,
    date_to: date,
    today: date,
) -> str | None:
    """Davr chegaralarini tekshiradi; xato bo'lsa foydalanuvchi uchun matn.

    Kelajakdagi tugash sanasi taqiqlangan: hali sodir bo'lmagan kunlar uchun
    hisobot berish "davr oxiridagi qarzdorlik" ni noto'g'ri ko'rsatardi.
    Boshlanish sanasi tugash sanasidan keyin bo'lishi ham mumkin emas.
    """
    if date_to > today:
        return (
            "Tugash sanasi bugundan keyin bo'lishi mumkin emas.\n"
            f"Eng kech sana: <b>{today:%d.%m.%Y}</b>"
        )
    if date_from > date_to:
        return (
            "Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas.\n"
            f"Boshlanish sanasi: <b>{date_from:%d.%m.%Y}</b>"
        )
    return None


def build_period_report(
    *,
    date_from: date,
    date_to: date,
    debts: Iterable[Debt],
    payments: Iterable[Payment],
    clients: Iterable[Client],
    opening_given: MoneyMap,
    opening_repaid: MoneyMap,
    repaid_by_debt: dict[int, int],
    active_totals: dict[int, dict[str, tuple[int, int]]],
) -> PeriodReport:
    """Davr hisobotini yig'adi.

    `debts` va `payments` — aynan [date_from; date_to] oralig'idagi yozuvlar.
    `opening_given` / `opening_repaid` — davr boshigacha bo'lgan agregatlar.
    `repaid_by_debt` — {debt_id: `date_to` gacha qaytarilgan summa}; qarzning
    DAVR OXIRIDAGI qoldig'i shundan hisoblanadi, `remaining_debt` (bugungi
    qoldiq) dan emas — aks holda o'tgan davr hisobotida varaqlar bir-biriga
    to'g'ri kelmasdi.
    `active_totals` — hozirgi ochiq qarzlar (eng katta qarzdorlar va qarzdorlar
    soni uchun; davr chegarasiga bog'liq emas).
    """
    period_debts = tuple(debts)
    period_payments = tuple(payments)
    client_list = list(clients)
    client_names = {c.id: c.full_name for c in client_list if c.id is not None}
    client_phones = {c.id: c.phone for c in client_list if c.id is not None}

    opening_debt = _combine(opening_given, opening_repaid, signs=(1, -1))

    given_total: MoneyMap = {}
    initial_total: MoneyMap = {}
    returned_total: MoneyMap = {}

    open_count = closed_count = trashed_count = 0

    for debt in period_debts:
        _add(given_total, str(debt.currency), debt.original_debt)
        if debt.status == DebtStatus.TRASHED:
            trashed_count += 1
        elif debt.original_debt - repaid_by_debt.get(debt.id or 0, 0) <= 0:
            closed_count += 1
        else:
            open_count += 1

    for payment in period_payments:
        bucket = returned_total if _is_repayment(payment) else initial_total
        _add(bucket, str(payment.currency), payment.amount)

    closing_debt = _combine(opening_debt, given_total, returned_total, signs=(1, 1, -1))

    # Har bir qarzning davr oxiridagi qoldig'i (bugungi holat emas).
    remaining_as_of = {
        debt.id: max(debt.original_debt - repaid_by_debt.get(debt.id, 0), 0)
        for debt in period_debts
        if debt.id is not None
    }

    return PeriodReport(
        date_from=date_from,
        date_to=date_to,
        opening_debt=opening_debt,
        given_total=given_total,
        returned_total=returned_total,
        initial_total=initial_total,
        closing_debt=closing_debt,
        clients_total=len(client_list),
        debtors_total=_count_debtors(active_totals),
        period_clients_total=len(
            {d.client_id for d in period_debts} | {p.client_id for p in period_payments}
        ),
        closed_debts_count=closed_count,
        open_debts_count=open_count,
        trashed_debts_count=trashed_count,
        months=_build_months(
            date_from=date_from,
            date_to=date_to,
            debts=period_debts,
            payments=period_payments,
            opening_debt=opening_debt,
        ),
        client_rows=_build_client_rows(
            debts=period_debts,
            payments=period_payments,
            client_names=client_names,
            client_phones=client_phones,
            remaining_as_of=remaining_as_of,
        ),
        top_by_uzs=_build_top(active_totals, client_names, client_phones, "UZS"),
        top_by_usd=_build_top(active_totals, client_names, client_phones, "USD"),
        debts=period_debts,
        payments=period_payments,
        client_names=client_names,
        remaining_as_of=remaining_as_of,
    )


def _count_debtors(active_totals: dict[int, dict[str, tuple[int, int]]]) -> int:
    """Hozirda qarzi bor mijozlar soni."""
    return sum(
        1
        for totals in active_totals.values()
        if any(remaining > 0 for remaining, _ in totals.values())
    )


def _build_months(
    *,
    date_from: date,
    date_to: date,
    debts: Sequence[Debt],
    payments: Sequence[Payment],
    opening_debt: MoneyMap,
) -> tuple[PeriodMonthRow, ...]:
    """Oyma-oy berilgan/qaytgan summalar va oy oxiridagi kumulyativ qoldiq."""
    given_by_month: dict[tuple[int, int], MoneyMap] = {}
    returned_by_month: dict[tuple[int, int], MoneyMap] = {}

    for debt in debts:
        bucket = given_by_month.setdefault(_month_key(debt.debt_date), {})
        _add(bucket, str(debt.currency), debt.original_debt)

    for payment in payments:
        if not _is_repayment(payment):
            continue
        bucket = returned_by_month.setdefault(_month_key(payment.payment_date), {})
        _add(bucket, str(payment.currency), payment.amount)

    rows: list[PeriodMonthRow] = []
    running = dict(opening_debt)

    for year, month in _month_range(date_from, date_to):
        given = given_by_month.get((year, month), {})
        returned = returned_by_month.get((year, month), {})
        running = _combine(running, given, returned, signs=(1, 1, -1))
        rows.append(
            PeriodMonthRow(
                year=year,
                month=month,
                given=dict(given),
                returned=dict(returned),
                closing=dict(running),
            )
        )

    return tuple(rows)


def _build_client_rows(
    *,
    debts: Sequence[Debt],
    payments: Sequence[Payment],
    client_names: dict[int, str],
    client_phones: dict[int, str],
    remaining_as_of: dict[int, int],
) -> tuple[PeriodClientRow, ...]:
    """Mijozlar kesimi (davr oxiridagi holat bo'yicha).

    `given`, `paid`, `remaining` — faqat shu davrda ochilgan qarzlar bo'yicha
    va DAVR OXIRIGA hisoblangan, shuning uchun har doim
    `given - paid == remaining`. `cash_paid` esa davr ichida naqd tushgan pul
    (eski qarzlarga ham tegishli bo'lishi mumkin), shu sababli alohida ustun.
    """
    given: dict[int, MoneyMap] = {}
    paid: dict[int, MoneyMap] = {}
    remaining: dict[int, MoneyMap] = {}
    cash: dict[int, MoneyMap] = {}
    latest_date: dict[int, date] = {}

    for debt in debts:
        cid = debt.client_id
        currency = str(debt.currency)
        left = remaining_as_of.get(debt.id or 0, debt.remaining_debt)
        _add(given.setdefault(cid, {}), currency, debt.original_debt)
        _add(paid.setdefault(cid, {}), currency, debt.original_debt - left)
        _add(remaining.setdefault(cid, {}), currency, left)
        previous = latest_date.get(cid)
        if previous is None or debt.debt_date > previous:
            latest_date[cid] = debt.debt_date

    for payment in payments:
        if not _is_repayment(payment):
            continue
        _add(cash.setdefault(payment.client_id, {}), str(payment.currency), payment.amount)

    rows = [
        PeriodClientRow(
            client_id=cid,
            full_name=client_names.get(cid, f"ID {cid}"),
            phone=client_phones.get(cid, ""),
            debt_date=latest_date.get(cid),
            given=given.get(cid, {}),
            paid=paid.get(cid, {}),
            remaining=remaining.get(cid, {}),
            cash_paid=cash.get(cid, {}),
        )
        for cid in given.keys() | cash.keys()
    ]
    rows.sort(key=lambda row: row.full_name.lower())
    return tuple(rows)


def _build_top(
    active_totals: dict[int, dict[str, tuple[int, int]]],
    client_names: dict[int, str],
    client_phones: dict[int, str],
    currency: str,
) -> tuple[TopDebtorRow, ...]:
    """Berilgan valyuta bo'yicha eng katta qarzdorlar (Top-10).

    So'm va dollar aralashtirilmaydi: kurs noma'lum bo'lgani uchun ikki
    valyuta bitta ro'yxatda taqqoslanmaydi, har biri o'z ro'yxatiga tushadi.
    """
    scored: list[tuple[int, int]] = [
        (client_id, totals[currency][0])
        for client_id, totals in active_totals.items()
        if totals.get(currency, (0, 0))[0] > 0
    ]
    scored.sort(key=lambda item: item[1], reverse=True)

    return tuple(
        TopDebtorRow(
            client_id=client_id,
            full_name=client_names.get(client_id, f"ID {client_id}"),
            phone=client_phones.get(client_id, ""),
            remaining={currency: amount},
        )
        for client_id, amount in scored[:TOP_DEBTORS_LIMIT]
    )
