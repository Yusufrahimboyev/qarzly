"""Application qatlami: DebtService.

Qarzlar hisob-kitobi, yaratish, to'liq va qisman to'lovlar (FIFO), hisobotlar
generatsiyasi. Har bir qarz o'z valyutasida (so'm yoki dollar) saqlanadi —
summalar valyutalar bo'yicha aralashtirilmaydi.
"""
from __future__ import annotations

import asyncio

from bot.application.common.formatters import format_money
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import Debt, DebtStatus
from bot.domain.entities.payment import Payment, PaymentType
from bot.domain.entities.report import ClientDebtSummary, ClientReport
from bot.domain.repositories.client_repository import ClientRepository
from bot.domain.repositories.debt_repository import DebtRepository
from bot.domain.repositories.payment_repository import PaymentRepository


def _sum_by(items, attr: str) -> dict[str, int]:
    """Obyektlar ro'yxatidagi maydonni valyuta bo'yicha yig'adi."""
    totals: dict[str, int] = {}
    for item in items:
        currency = str(item.currency)
        totals[currency] = totals.get(currency, 0) + getattr(item, attr)
    return totals


class DebtService:
    """Qarzlar va to'lovlar biznes-mantiq servisi."""

    def __init__(
        self,
        clients: ClientRepository,
        debts: DebtRepository,
        payments: PaymentRepository,
    ) -> None:
        self._clients = clients
        self._debts = debts
        self._payments = payments
        # O'zgartiruvchi operatsiyalar (yaratish/to'lash) ketma-ket bajarilishi
        # uchun lock — aks holda bir vaqtda kelgan ikki to'lov (bot va Mini App)
        # bir xil qarzni ikki marta hisoblab yuborishi mumkin.
        self._mutation_lock = asyncio.Lock()

    async def create_debt(
        self,
        client_id: int,
        debt_date: str,
        product_name: str,
        product_price: int,
        product_quantity: int = 1,
        currency: Currency = Currency.UZS,
        exchange_exists: bool = False,
        exchange_product_name: str | None = None,
        exchange_product_price: int = 0,
        given_money: int = 0,
    ) -> Debt:
        """Yangi qarz yozuvini hisoblab bazaga kiritadi.

        product_price — BIR DONA narxi; jami narx miqdorga ko'paytiriladi.
        Butun yozuv (narx, exchange, berilgan pul, qarz) bitta valyutada.

        Formula:
        original_debt = (product_price * product_quantity)
                        - exchange_product_price - given_money
        """
        async with self._mutation_lock:
            if product_price <= 0:
                raise ValueError("Tovar narxi 0 dan katta bo'lishi shart.")
            if product_quantity < 1:
                raise ValueError("Miqdor (nechta) 1 dan kichik bo'lishi mumkin emas.")
            if not isinstance(currency, Currency):
                raise ValueError("Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak).")

            total_product_price = product_price * product_quantity

            actual_exchange_price = exchange_product_price if exchange_exists else 0
            actual_exchange_name = exchange_product_name if exchange_exists else None

            if actual_exchange_price < 0 or given_money < 0:
                raise ValueError("Exchange narxi yoki berilgan pul manfiy bo'lishi mumkin emas.")

            total_deductions = actual_exchange_price + given_money
            if total_deductions > total_product_price:
                deductions_str = format_money(total_deductions, currency)
                total_str = format_money(total_product_price, currency)
                raise ValueError(
                    f"Exchange narxi va berilgan pul yig'indisi ({deductions_str}) "
                    f"tovarlar jami narxidan ({total_str}) katta bo'lishi mumkin emas."
                )

            original_debt = total_product_price - total_deductions
            remaining_debt = original_debt
            status = DebtStatus.ACTIVE if remaining_debt > 0 else DebtStatus.PAID

            debt = Debt(
                client_id=client_id,
                debt_date=debt_date,
                product_name=product_name.strip(),
                product_quantity=product_quantity,
                product_price=total_product_price,
                currency=currency,
                exchange_exists=exchange_exists,
                exchange_product_name=actual_exchange_name,
                exchange_product_price=actual_exchange_price,
                given_money=given_money,
                original_debt=original_debt,
                remaining_debt=remaining_debt,
                status=status,
            )
            saved_debt = await self._debts.add(debt)

            # Agar boshlang'ich pul berilgan bo'lsa, to'lovlar tarixiga INITIAL sifatida yozamiz
            if given_money > 0 and saved_debt.id is not None:
                await self._payments.add(
                    Payment(
                        client_id=client_id,
                        debt_id=saved_debt.id,
                        amount=given_money,
                        currency=currency,
                        payment_type=PaymentType.INITIAL,
                        payment_date=debt_date,
                    )
                )

            return saved_debt

    async def pay_full_debt(
        self,
        client_id: int,
        payment_date: str,
    ) -> tuple[dict[str, int], ClientDebtSummary]:
        """Mijozning barcha mavjud qarzlarini (barcha valyutalarda) to'liq yopadi.

        Qaytaradi: (valyutalar_bo'yicha_to'langan_summa, yangilangan_summary)
        """
        async with self._mutation_lock:
            active_debts = await self._debts.get_active_by_client_id(client_id)
            if not active_debts:
                client = await self._clients.get_by_id(client_id)
                if client is None:
                    raise ValueError("Mijoz topilmadi.")
                return {}, ClientDebtSummary(client=client)

            paid_by_currency: dict[str, int] = {}
            for debt in active_debts:
                if debt.id is None:
                    continue
                pay_amount = debt.remaining_debt
                if pay_amount > 0:
                    await self._debts.update_remaining_debt(
                        debt_id=debt.id,
                        remaining_debt=0,
                        status=DebtStatus.PAID,
                    )
                    await self._payments.add(
                        Payment(
                            client_id=client_id,
                            debt_id=debt.id,
                            amount=pay_amount,
                            currency=debt.currency,
                            payment_type=PaymentType.FULL,
                            payment_date=payment_date,
                        )
                    )
                    key = debt.currency.value
                    paid_by_currency[key] = paid_by_currency.get(key, 0) + pay_amount

            client = await self._clients.get_by_id(client_id)
            if client is None:
                raise ValueError("Mijoz topilmadi.")

            summary = ClientDebtSummary(client=client)
            return paid_by_currency, summary

    async def pay_partial_debt(
        self,
        client_id: int,
        amount: int,
        payment_date: str,
        currency: Currency = Currency.UZS,
    ) -> tuple[int, int, ClientDebtSummary]:
        """Mijozning tanlangan valyutadagi qarzidan ma'lum miqdorni to'laydi.

        FIFO: shu valyutadagi eng eski qarzdan boshlab yopadi. Boshqa valyutadagi
        qarzlarga ta'sir qilmaydi.

        Qaytaradi: (to'langan_summa, shu_valyutadagi_qolgan, yangilangan_summary)
        """
        async with self._mutation_lock:
            if amount <= 0:
                raise ValueError("To'lov summasi 0 dan katta bo'lishi shart.")
            if not isinstance(currency, Currency):
                raise ValueError("Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak).")

            active_debts = await self._debts.get_active_by_client_id(client_id)
            currency_debts = [d for d in active_debts if d.currency == currency]
            total_remaining = sum(d.remaining_debt for d in currency_debts)

            if total_remaining == 0:
                currency_label = "so'mda" if currency == Currency.UZS else "dollarda"
                raise ValueError(
                    f"Ushbu mijozda {currency_label} to'lanishi kerak bo'lgan faol qarz yo'q."
                )

            if amount > total_remaining:
                raise ValueError(
                    f"To'lov summasi mavjud qarzdan ({format_money(total_remaining, currency)}) "
                    f"katta bo'lishi mumkin emas."
                )

            remaining_to_allocate = amount
            for debt in currency_debts:
                if debt.id is None or remaining_to_allocate <= 0:
                    break

                pay_for_this = min(remaining_to_allocate, debt.remaining_debt)
                new_debt_remaining = debt.remaining_debt - pay_for_this
                new_status = DebtStatus.PAID if new_debt_remaining == 0 else DebtStatus.ACTIVE

                await self._debts.update_remaining_debt(
                    debt_id=debt.id,
                    remaining_debt=new_debt_remaining,
                    status=new_status,
                )

                p_type = (
                    PaymentType.FULL
                    if (new_debt_remaining == 0 and pay_for_this == debt.remaining_debt)
                    else PaymentType.PARTIAL
                )

                await self._payments.add(
                    Payment(
                        client_id=client_id,
                        debt_id=debt.id,
                        amount=pay_for_this,
                        currency=debt.currency,
                        payment_type=p_type,
                        payment_date=payment_date,
                    )
                )

                remaining_to_allocate -= pay_for_this

            new_total_remaining = total_remaining - amount
            new_active_debts = await self._debts.get_active_by_client_id(client_id)
            client = await self._clients.get_by_id(client_id)
            if client is None:
                raise ValueError("Mijoz topilmadi.")

            remaining_map = _sum_by(new_active_debts, "remaining_debt")
            summary = ClientDebtSummary(
                client=client,
                remaining_by_currency={
                    cur: value for cur, value in remaining_map.items() if value > 0
                },
                active_debts_count=len(new_active_debts),
            )
            return amount, new_total_remaining, summary

    async def get_client_report(self, client_id: int) -> ClientReport:
        """Mijozning barcha qarz va to'lovlari bo'yicha to'liq hisobotini shakllantiradi."""
        client = await self._clients.get_by_id(client_id)
        if client is None:
            raise ValueError("Mijoz topilmadi.")

        debts = await self._debts.get_all_by_client_id(client_id)
        payments = await self._payments.get_by_client_id(client_id)

        # Qarz olingandan keyingi to'lovlar (INITIAL bo'lmaganlar)
        paid_after = [
            p for p in payments if p.payment_type in (PaymentType.FULL, PaymentType.PARTIAL)
        ]
        active_debts = [d for d in debts if d.status == DebtStatus.ACTIVE]

        return ClientReport(
            client=client,
            debts=debts,
            payments=payments,
            total_product_price=_sum_by(debts, "product_price"),
            total_exchange_price=_sum_by(debts, "exchange_product_price"),
            total_given_money=_sum_by(debts, "given_money"),
            total_original_debt=_sum_by(debts, "original_debt"),
            total_paid_after=_sum_by(paid_after, "amount"),
            total_remaining_debt=_sum_by(active_debts, "remaining_debt"),
        )
