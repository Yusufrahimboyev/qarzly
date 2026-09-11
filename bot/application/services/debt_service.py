"""Application qatlami: DebtService.

Qarzlar hisob-kitobi, yaratish, to'liq va qisman to'lovlar (FIFO), hisobotlar
generatsiyasi. Har bir qarz o'z valyutasida (so'm yoki dollar) saqlanadi —
summalar valyutalar bo'yicha aralashtirilmaydi. Bir qarzda bir nechta tovar
bo'lishi mumkin.

Har bir yozuv operatsiyasi (qarz yaratish, to'liq va qisman to'lov) bitta
Unit of Work — ya'ni bitta DB tranzaksiyasi — ichida bajariladi. Qarz qatorlari
to'lov davomida `FOR UPDATE` bilan qulflanadi, shuning uchun parallel so'rovlar
bir xil qarzni ikki marta yopa olmaydi.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date

from bot.application.common.formatters import format_money, to_date
from bot.application.common.period_report import build_period_report
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import (
    MAX_MONEY,
    MAX_PRODUCTS_PER_DEBT,
    Debt,
    DebtProduct,
    DebtStatus,
    build_summary_name,
)
from bot.domain.entities.payment import Payment, PaymentType
from bot.domain.entities.period_report import PeriodReport
from bot.domain.entities.report import ClientDebtSummary, ClientReport
from bot.domain.repositories.client_repository import ClientRepository
from bot.domain.repositories.debt_repository import DebtRepository
from bot.domain.repositories.payment_repository import PaymentRepository
from bot.domain.repositories.unit_of_work import (
    NonTransactionalUnitOfWork,
    UnitOfWork,
    UnitOfWorkFactory,
)

logger = logging.getLogger(__name__)


def _sum_by(items, attr: str) -> dict[str, int]:
    """Obyektlar ro'yxatidagi maydonni valyuta bo'yicha yig'adi."""
    totals: dict[str, int] = {}
    for item in items:
        currency = str(item.currency)
        totals[currency] = totals.get(currency, 0) + getattr(item, attr)
    return totals


@dataclass(frozen=True, slots=True)
class _DebtPlan:
    """Hisoblab va validatsiyadan o'tkazib bo'lingan, ammo hali saqlanmagan qarz.

    Barcha guruhlar avval to'liq tekshiriladi, keyin bitta tranzaksiyada
    yoziladi — shu sababli "birinchi valyuta saqlanib, ikkinchisi xato bilan
    qolishi" holati bo'lmaydi.
    """

    debt: Debt
    initial_payment: Payment | None


class DebtService:
    """Qarzlar va to'lovlar biznes-mantiq servisi."""

    def __init__(
        self,
        clients: ClientRepository,
        debts: DebtRepository,
        payments: PaymentRepository,
        uow_factory: UnitOfWorkFactory | None = None,
    ) -> None:
        self._clients = clients
        self._debts = debts
        self._payments = payments
        self._uow_factory: UnitOfWorkFactory = uow_factory or (
            lambda: NonTransactionalUnitOfWork(clients, debts, payments)
        )

    def _unit_of_work(self) -> UnitOfWork:
        return self._uow_factory()

    # ------------------------------------------------------------------
    # Qarz yaratish
    # ------------------------------------------------------------------

    @staticmethod
    def _plan_debt(
        client_id: int,
        debt_date: date,
        products: list[DebtProduct],
        currency: Currency,
        exchange_exists: bool,
        exchange_product_name: str | None,
        exchange_product_price: int,
        given_money: int,
    ) -> _DebtPlan:
        """Qarzni hisoblaydi va invariantlarni tekshiradi (I/O siz).

        Hech qanday DB amali bajarilmaydi — shu sababli bir nechta qarzni
        avval to'liq tekshirib, keyin bitta tranzaksiyada saqlash mumkin.
        """
        if not isinstance(currency, Currency):
            raise ValueError("Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak).")
        if not products:
            raise ValueError("Kamida bitta tovar kiritilishi shart.")
        if len(products) > MAX_PRODUCTS_PER_DEBT:
            raise ValueError(
                f"Bitta qarzda {MAX_PRODUCTS_PER_DEBT} tadan ko'p tovar bo'lishi mumkin emas."
            )

        for product in products:
            product.validate()
            if product.currency != currency:
                raise ValueError(
                    "Tovar valyutasi qarz valyutasiga mos emas "
                    f"({product.currency.value} != {currency.value})."
                )

        total_product_price = sum(p.total_price for p in products)
        total_quantity = sum(p.quantity for p in products)
        summary_name = build_summary_name(products)

        if total_product_price <= 0:
            raise ValueError("Tovarlar jami narxi 0 dan katta bo'lishi shart.")
        if total_product_price > MAX_MONEY:
            raise ValueError("Tovarlar jami narxi ruxsat etilgan chegaradan katta.")

        actual_exchange_price = exchange_product_price if exchange_exists else 0
        actual_exchange_name = exchange_product_name if exchange_exists else None

        if actual_exchange_price < 0 or given_money < 0:
            raise ValueError(
                "Exchange narxi yoki berilgan pul manfiy bo'lishi mumkin emas."
            )
        if actual_exchange_price > MAX_MONEY or given_money > MAX_MONEY:
            raise ValueError("Summa ruxsat etilgan chegaradan katta.")

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
            product_name=summary_name,
            product_quantity=total_quantity,
            product_price=total_product_price,
            currency=currency,
            exchange_exists=exchange_exists,
            exchange_product_name=actual_exchange_name,
            exchange_product_price=actual_exchange_price,
            given_money=given_money,
            original_debt=original_debt,
            remaining_debt=remaining_debt,
            products=tuple(products),
            status=status,
        )

        initial_payment: Payment | None = None
        if given_money > 0:
            initial_payment = Payment(
                client_id=client_id,
                amount=given_money,
                currency=currency,
                payment_type=PaymentType.INITIAL,
                payment_date=debt_date,
            )

        return _DebtPlan(debt=debt, initial_payment=initial_payment)

    @staticmethod
    async def _save_plans(uow: UnitOfWork, plans: list[_DebtPlan]) -> list[Debt]:
        """Tayyor rejalarni bitta tranzaksiya ichida saqlaydi."""
        saved: list[Debt] = []
        for plan in plans:
            debt = await uow.debts.add(plan.debt)
            saved.append(debt)
            if plan.initial_payment is not None and debt.id is not None:
                payment = plan.initial_payment
                await uow.payments.add(
                    Payment(
                        client_id=payment.client_id,
                        debt_id=debt.id,
                        amount=payment.amount,
                        currency=payment.currency,
                        payment_type=payment.payment_type,
                        payment_date=payment.payment_date,
                    )
                )
        return saved

    async def create_debt(
        self,
        client_id: int,
        debt_date: str | date,
        products: list[DebtProduct] | None = None,
        product_name: str = "",
        product_price: int = 0,
        product_quantity: int = 1,
        currency: Currency = Currency.UZS,
        exchange_exists: bool = False,
        exchange_product_name: str | None = None,
        exchange_product_price: int = 0,
        given_money: int = 0,
    ) -> Debt:
        """Yangi qarz yozuvini hisoblab bazaga kiritadi.

        Agar `products` berilgan bo'lsa, jami narx va miqdor tovarlar ro'yxatidan
        hisoblanadi. Aks holda eski single-product parametrlar ishlatiladi
        (bot va eski API uchun).

        Qarz va unga tegishli dastlabki to'lov bitta tranzaksiyada saqlanadi.
        """
        parsed_date = to_date(debt_date)

        if products:
            final_products = list(products)
        else:
            # Single-product rejim (eski bot/API): tovar valyutasi qarz
            # valyutasi bilan bir xil bo'lishi shart.
            if product_price <= 0:
                raise ValueError("Tovar narxi 0 dan katta bo'lishi shart.")
            if product_quantity < 1:
                raise ValueError(
                    "Miqdor (nechta) 1 dan kichik bo'lishi mumkin emas."
                )
            final_products = [
                DebtProduct(
                    name=product_name.strip(),
                    quantity=product_quantity,
                    price_per_unit=product_price,
                    currency=currency,
                )
            ]

        plan = self._plan_debt(
            client_id=client_id,
            debt_date=parsed_date,
            products=final_products,
            currency=currency,
            exchange_exists=exchange_exists,
            exchange_product_name=exchange_product_name,
            exchange_product_price=exchange_product_price,
            given_money=given_money,
        )

        async with self._unit_of_work() as uow:
            saved = await self._save_plans(uow, [plan])

        saved_debt = saved[0]
        logger.info(
            "AUDIT debt_created client_id=%s debt_id=%s currency=%s "
            "total=%s exchange=%s given=%s original=%s date=%s",
            client_id,
            saved_debt.id,
            currency.value,
            saved_debt.product_price,
            saved_debt.exchange_product_price,
            given_money,
            saved_debt.original_debt,
            parsed_date.isoformat(),
        )
        return saved_debt

    async def create_debts(
        self,
        client_id: int,
        debt_date: str | date,
        products: list[DebtProduct],
        exchange_exists: bool = False,
        exchange_product_name: str | None = None,
        exchange_product_price: int = 0,
        exchange_currency: Currency = Currency.UZS,
        given_money: int = 0,
        given_currency: Currency = Currency.UZS,
    ) -> list[Debt]:
        """Aralash valyutadagi tovarlardan qarzlar yaratadi.

        Har bir tovarning o'z valyutasi bo'lishi mumkin — tovarlar valyuta
        bo'yicha guruhlanadi va har bir valyuta uchun alohida qarz yozuvi
        yaratiladi. Exchange va berilgan pul faqat o'z valyutasidagi
        guruhdan chegiriladi.

        Barcha guruhlar avval to'liq tekshiriladi va faqat shundan keyin
        bitta tranzaksiyada saqlanadi.

        Qaytaradi: yaratilgan qarzlar ro'yxati (valyutalar bo'yicha).
        """
        if not products:
            raise ValueError("Kamida bitta tovar kiritilishi shart.")
        if len(products) > MAX_PRODUCTS_PER_DEBT:
            raise ValueError(
                f"Bir vaqtda {MAX_PRODUCTS_PER_DEBT} tadan ko'p tovar kiritib bo'lmaydi."
            )

        parsed_date = to_date(debt_date)

        # Tovarlarni valyuta bo'yicha guruhlaymiz
        groups: dict[Currency, list[DebtProduct]] = {}
        for p in products:
            try:
                cur = Currency(p.currency)
            except ValueError as exc:
                raise ValueError(
                    f"Tovar valyutasi noto'g'ri: {p.currency} "
                    "(UZS yoki USD bo'lishi kerak)."
                ) from exc
            groups.setdefault(cur, []).append(p)

        # Exchange yoki berilgan pul mos valyutadagi tovarsiz qolmasligi kerak —
        # aks holda chegirma jimgina e'tiborsiz qolardi.
        if exchange_exists and exchange_product_price > 0 and exchange_currency not in groups:
            raise ValueError(
                f"Exchange {exchange_currency.value} valyutasida, ammo shu "
                "valyutadagi tovar kiritilmagan."
            )
        if given_money > 0 and given_currency not in groups:
            raise ValueError(
                f"Berilgan pul {given_currency.value} valyutasida, ammo shu "
                "valyutadagi tovar kiritilmagan."
            )

        plans: list[_DebtPlan] = []
        for cur, group in groups.items():
            group_exchange_exists = exchange_exists and cur == exchange_currency
            group_exchange_price = (
                exchange_product_price if group_exchange_exists else 0
            )
            group_exchange_name = (
                exchange_product_name if group_exchange_exists else None
            )
            group_given = given_money if cur == given_currency else 0

            plans.append(
                self._plan_debt(
                    client_id=client_id,
                    debt_date=parsed_date,
                    products=group,
                    currency=cur,
                    exchange_exists=group_exchange_exists,
                    exchange_product_name=group_exchange_name,
                    exchange_product_price=group_exchange_price,
                    given_money=group_given,
                )
            )

        async with self._unit_of_work() as uow:
            created = await self._save_plans(uow, plans)

        logger.info(
            "AUDIT debts_created_multi client_id=%s debts=%s date=%s",
            client_id,
            [(d.id, d.currency.value, d.remaining_debt) for d in created],
            parsed_date.isoformat(),
        )
        return created

    # ------------------------------------------------------------------
    # To'lovlar
    # ------------------------------------------------------------------

    async def pay_full_debt(
        self,
        client_id: int,
        payment_date: str | date,
    ) -> tuple[dict[str, int], ClientDebtSummary]:
        """Mijozning barcha mavjud qarzlarini (barcha valyutalarda) to'liq yopadi.

        Qaytaradi: (valyutalar_bo'yicha_to'langan_summa, yangilangan_summary)
        """
        parsed_date = to_date(payment_date)

        async with self._unit_of_work() as uow:
            client = await uow.clients.get_by_id(client_id)
            if client is None:
                raise ValueError("Mijoz topilmadi.")

            active_debts = await uow.debts.get_active_by_client_id(
                client_id, for_update=True
            )
            if not active_debts:
                return {}, ClientDebtSummary(client=client)

            paid_by_currency: dict[str, int] = {}
            for debt in active_debts:
                if debt.id is None:
                    continue
                pay_amount = debt.remaining_debt
                if pay_amount <= 0:
                    continue

                await uow.debts.update_remaining_debt(
                    debt_id=debt.id,
                    remaining_debt=0,
                    status=DebtStatus.PAID,
                )
                await uow.payments.add(
                    Payment(
                        client_id=client_id,
                        debt_id=debt.id,
                        amount=pay_amount,
                        currency=debt.currency,
                        payment_type=PaymentType.FULL,
                        payment_date=parsed_date,
                    )
                )
                key = debt.currency.value
                paid_by_currency[key] = paid_by_currency.get(key, 0) + pay_amount

        logger.info(
            "AUDIT payment_full client_id=%s paid=%s date=%s",
            client_id,
            paid_by_currency,
            parsed_date.isoformat(),
        )
        return paid_by_currency, ClientDebtSummary(client=client)

    async def pay_partial_debt(
        self,
        client_id: int,
        amount: int,
        payment_date: str | date,
        currency: Currency = Currency.UZS,
    ) -> tuple[int, int, ClientDebtSummary]:
        """Mijozning tanlangan valyutadagi qarzidan ma'lum miqdorni to'laydi.

        FIFO: shu valyutadagi eng eski qarzdan boshlab yopadi. Boshqa
        valyutadagi qarzlarga ta'sir qilmaydi.

        Qaytaradi: (to'langan_summa, shu_valyutadagi_qolgan, summary)
        """
        if amount <= 0:
            raise ValueError("To'lov summasi 0 dan katta bo'lishi shart.")
        if amount > MAX_MONEY:
            raise ValueError("To'lov summasi ruxsat etilgan chegaradan katta.")
        if not isinstance(currency, Currency):
            raise ValueError("Valyuta noto'g'ri (UZS yoki USD bo'lishi kerak).")

        parsed_date = to_date(payment_date)

        async with self._unit_of_work() as uow:
            client = await uow.clients.get_by_id(client_id)
            if client is None:
                raise ValueError("Mijoz topilmadi.")

            active_debts = await uow.debts.get_active_by_client_id(
                client_id, for_update=True
            )
            currency_debts = [d for d in active_debts if d.currency == currency]
            total_remaining = sum(d.remaining_debt for d in currency_debts)

            if total_remaining == 0:
                currency_label = (
                    "so'mda" if currency == Currency.UZS else "dollarda"
                )
                raise ValueError(
                    f"Ushbu mijozda {currency_label} to'lanishi kerak"
                    " bo'lgan faol qarz yo'q."
                )

            if amount > total_remaining:
                raise ValueError(
                    f"To'lov summasi mavjud qarzdan "
                    f"({format_money(total_remaining, currency)}) "
                    f"katta bo'lishi mumkin emas."
                )

            remaining_to_allocate = amount
            for debt in currency_debts:
                if debt.id is None or remaining_to_allocate <= 0:
                    break

                pay_for_this = min(remaining_to_allocate, debt.remaining_debt)
                new_remaining = debt.remaining_debt - pay_for_this
                new_status = (
                    DebtStatus.PAID if new_remaining == 0 else DebtStatus.ACTIVE
                )

                await uow.debts.update_remaining_debt(
                    debt_id=debt.id,
                    remaining_debt=new_remaining,
                    status=new_status,
                )

                p_type = (
                    PaymentType.FULL
                    if (new_remaining == 0 and pay_for_this == debt.remaining_debt)
                    else PaymentType.PARTIAL
                )

                await uow.payments.add(
                    Payment(
                        client_id=client_id,
                        debt_id=debt.id,
                        amount=pay_for_this,
                        currency=debt.currency,
                        payment_type=p_type,
                        payment_date=parsed_date,
                    )
                )

                remaining_to_allocate -= pay_for_this

            new_total_remaining = total_remaining - amount
            new_active_debts = await uow.debts.get_active_by_client_id(client_id)

        remaining_map = _sum_by(new_active_debts, "remaining_debt")
        summary = ClientDebtSummary(
            client=client,
            remaining_by_currency={
                cur: v for cur, v in remaining_map.items() if v > 0
            },
            active_debts_count=len(new_active_debts),
        )

        logger.info(
            "AUDIT payment_partial client_id=%s amount=%s currency=%s "
            "new_remaining=%s date=%s",
            client_id,
            amount,
            currency.value,
            new_total_remaining,
            parsed_date.isoformat(),
        )
        return amount, new_total_remaining, summary

    # ------------------------------------------------------------------
    # Hisobotlar
    # ------------------------------------------------------------------

    async def get_client_report(self, client_id: int) -> ClientReport:
        """Mijozning barcha qarz va to'lovlari bo'yicha to'liq hisoboti."""
        client = await self._clients.get_by_id(client_id)
        if client is None:
            raise ValueError("Mijoz topilmadi.")

        debts = await self._debts.get_all_by_client_id(client_id)
        all_payments = await self._payments.get_by_client_id(client_id)

        # Korzinadagi qarzlar hisobotda ko'rsatilmaydi — ularning to'lovlari
        # ham jamiga qo'shilmasligi kerak, aks holda "to'langan" summa
        # ko'rsatilgan qarzlarga mos kelmay qolardi.
        visible_debt_ids = {d.id for d in debts if d.id is not None}
        payments = [
            p
            for p in all_payments
            if p.debt_id is None or p.debt_id in visible_debt_ids
        ]

        paid_after = [
            p
            for p in payments
            if p.payment_type in (PaymentType.FULL, PaymentType.PARTIAL)
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

    async def get_period_report(self, date_from: date, date_to: date) -> PeriodReport:
        """Sana oralig'i bo'yicha umumiy hisobotni yig'adi (Excel eksporti uchun).

        Ikkala chegara ham oraliqqa kiradi. Hisob-kitob `build_period_report`
        sof funksiyasida — bu metod faqat kerakli ma'lumotni o'qiydi.
        """
        if date_from > date_to:
            raise ValueError(
                "Boshlanish sanasi tugash sanasidan keyin bo'lishi mumkin emas."
            )

        return build_period_report(
            date_from=date_from,
            date_to=date_to,
            debts=await self._debts.get_by_date_range(date_from, date_to),
            payments=await self._payments.get_by_date_range(date_from, date_to),
            clients=await self._clients.get_all_alphabetical(),
            opening_given=await self._debts.sum_original_before(date_from),
            opening_repaid=await self._payments.sum_repayments_before(date_from),
            active_totals=await self._debts.get_active_totals(),
        )

    # ------------------------------------------------------------------
    # Korzina (Trash) va Yopilgan qarzlar operatsiyalari
    # ------------------------------------------------------------------

    async def get_all_paid(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Debt]:
        """Yopilgan (paid) qarzlarni sahifalab qaytaradi."""
        return await self._debts.get_all_paid(limit=limit, offset=offset)

    async def get_all_trashed(
        self,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[Debt]:
        """Korzinaga yuborilgan (trashed) qarzlarni sahifalab qaytaradi."""
        return await self._debts.get_all_trashed(limit=limit, offset=offset)

    async def move_to_trash(self, debt_ids: list[int], actor_id: int | None = None) -> int:
        """Yopilgan qarzlarni korzinaga ko'chiradi."""
        moved = await self._debts.move_to_trash(debt_ids)
        logger.info(
            "AUDIT trash_move actor_id=%s debt_ids=%s moved=%s",
            actor_id,
            debt_ids,
            moved,
        )
        return moved

    async def restore_from_trash(
        self,
        debt_ids: list[int],
        actor_id: int | None = None,
    ) -> int:
        """Korzinadagi qarzlarni yopilganga qaytaradi."""
        restored = await self._debts.restore_from_trash(debt_ids)
        logger.info(
            "AUDIT trash_restore actor_id=%s debt_ids=%s restored=%s",
            actor_id,
            debt_ids,
            restored,
        )
        return restored

    async def purge_trash(self, actor_id: int | None = None) -> int:
        """Korzinani butunlay tozalaydi (to'lov tarixi arxivga ko'chiriladi)."""
        deleted = await self._debts.purge_trash(actor_id=actor_id)
        logger.info(
            "AUDIT trash_purge actor_id=%s deleted=%s",
            actor_id,
            deleted,
        )
        return deleted
