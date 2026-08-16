"""Application qatlami: DebtService.

Qarzlar hisob-kitobi, yaratish, to'liq va qisman to'lovlar (FIFO), hisobotlar generatsiyasi.
"""
from __future__ import annotations

from bot.application.common.formatters import format_money
from bot.domain.entities.client import Client
from bot.domain.entities.debt import Debt, DebtStatus
from bot.domain.entities.payment import Payment, PaymentType
from bot.domain.entities.report import ClientDebtSummary, ClientReport
from bot.domain.repositories.client_repository import ClientRepository
from bot.domain.repositories.debt_repository import DebtRepository
from bot.domain.repositories.payment_repository import PaymentRepository


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

    async def create_debt(
        self,
        client_id: int,
        debt_date: str,
        product_name: str,
        product_price: int,
        exchange_exists: bool = False,
        exchange_product_name: str | None = None,
        exchange_product_price: int = 0,
        given_money: int = 0,
    ) -> Debt:
        """Yangi qarz yozuvini hisoblab bazaga kiritadi.

        Formula:
        original_debt = product_price - exchange_product_price - given_money
        """
        if product_price <= 0:
            raise ValueError("Tovar narxi 0 dan katta bo'lishi shart.")

        actual_exchange_price = exchange_product_price if exchange_exists else 0
        actual_exchange_name = exchange_product_name if exchange_exists else None

        if actual_exchange_price < 0 or given_money < 0:
            raise ValueError("Exchange narxi yoki berilgan pul manfiy bo'lishi mumkin emas.")

        total_deductions = actual_exchange_price + given_money
        if total_deductions > product_price:
            raise ValueError(
                f"Exchange narxi va berilgan pul yig'indisi ({format_money(total_deductions)}) "
                f"tovar narxidan ({format_money(product_price)}) katta bo'lishi mumkin emas."
            )

        original_debt = product_price - total_deductions
        remaining_debt = original_debt
        status = DebtStatus.ACTIVE if remaining_debt > 0 else DebtStatus.PAID

        debt = Debt(
            client_id=client_id,
            debt_date=debt_date,
            product_name=product_name.strip(),
            product_price=product_price,
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
                    payment_type=PaymentType.INITIAL,
                    payment_date=debt_date,
                )
            )

        return saved_debt

    async def pay_full_debt(
        self,
        client_id: int,
        payment_date: str,
    ) -> tuple[int, ClientDebtSummary]:
        """Mijozning barcha mavjud qarzlarini to'liq yopadi.

        Qaytaradi: (to'langan_summa, yangilangan_mijoz_summary)
        """
        active_debts = await self._debts.get_active_by_client_id(client_id)
        if not active_debts:
            client = await self._clients.get_by_id(client_id)
            if client is None:
                raise ValueError("Mijoz topilmadi.")
            return 0, ClientDebtSummary(client=client, total_remaining_debt=0, active_debts_count=0)

        total_paid = 0
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
                        payment_type=PaymentType.FULL,
                        payment_date=payment_date,
                    )
                )
                total_paid += pay_amount

        client = await self._clients.get_by_id(client_id)
        if client is None:
            raise ValueError("Mijoz topilmadi.")

        summary = ClientDebtSummary(
            client=client,
            total_remaining_debt=0,
            active_debts_count=0,
        )
        return total_paid, summary

    async def pay_partial_debt(
        self,
        client_id: int,
        amount: int,
        payment_date: str,
    ) -> tuple[int, int, ClientDebtSummary]:
        """Mijozning qarzidan ma'lum miqdorni to'laydi (FIFO: eng eski qarzdan boshlab yopadi).

        Qaytaradi: (to'langan_summa, qolgan_jami_qarz, yangilangan_mijoz_summary)
        """
        if amount <= 0:
            raise ValueError("To'lov summasi 0 dan katta bo'lishi shart.")

        active_debts = await self._debts.get_active_by_client_id(client_id)
        total_remaining = sum(d.remaining_debt for d in active_debts)

        if total_remaining == 0:
            raise ValueError("Ushbu mijozda hozirda to'lanishi kerak bo'lgan faol qarz yo'q.")

        if amount > total_remaining:
            raise ValueError(
                f"To'lov summasi mavjud qarzdan ({format_money(total_remaining)}) "
                f"katta bo'lishi mumkin emas."
            )

        remaining_to_allocate = amount
        for debt in active_debts:
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

        summary = ClientDebtSummary(
            client=client,
            total_remaining_debt=new_total_remaining,
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

        total_product_price = sum(d.product_price for d in debts)
        total_exchange_price = sum(d.exchange_product_price for d in debts)
        total_given_money = sum(d.given_money for d in debts)
        total_original_debt = sum(d.original_debt for d in debts)

        # Qarz olingandan keyingi to'lovlar (INITIAL bo'lmaganlar)
        total_paid_after = sum(
            p.amount for p in payments if p.payment_type in (PaymentType.FULL, PaymentType.PARTIAL)
        )
        total_remaining_debt = sum(
            d.remaining_debt for d in debts if d.status == DebtStatus.ACTIVE
        )

        return ClientReport(
            client=client,
            debts=debts,
            payments=payments,
            total_product_price=total_product_price,
            total_exchange_price=total_exchange_price,
            total_given_money=total_given_money,
            total_original_debt=total_original_debt,
            total_paid_after=total_paid_after,
            total_remaining_debt=total_remaining_debt,
        )
