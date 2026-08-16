"""Presentation qatlami: Qarz to'lovi handler'lari (valyutalar bo'yicha)."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import (
    aggregate_remaining,
    esc_html,
    format_money,
    format_money_map,
    parse_money,
    today_str,
)
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.domain.entities.currency import Currency
from bot.presentation.keyboards.main_menu_kb import get_main_menu_keyboard
from bot.presentation.keyboards.payment_kb import (
    get_debtors_list_keyboard,
    get_payment_back_cancel_keyboard,
    get_payment_currency_keyboard,
    get_payment_type_keyboard,
)
from bot.presentation.states.debt_payment import DebtPaymentStates

router = Router()


def _debtors_header(debtors) -> str:
    total_debt = aggregate_remaining(debtors)
    return (
        "💰 <b>QARZ TO'LOVI (Qarzdorlar ro'yxati):</b>\n\n"
        f"🔴 <b>Qarzdorlar soni:</b> {len(debtors)} nafar\n"
        f"💳 <b>Jami olinishi kerak:</b> <b>{format_money_map(total_debt)}</b>\n\n"
        "<i>To'lov qilayotgan mijozni tanlang:</i>"
    )


# ==========================================
# 0. BEKOR QILISH VA ORTGA
# ==========================================


@router.callback_query(F.data == "cancel_payment")
async def cb_cancel_payment(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    """To'lov jarayonini bekor qiladi."""
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("❌ <b>To'lov jarayoni bekor qilindi.</b>")
        await callback.message.answer(
            "Asosiy menyu:",
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )
    await callback.answer()


@router.callback_query(F.data == "back_to_pay_debtors")
async def cb_back_to_pay_debtors(
    callback: CallbackQuery,
    client_service: ClientService,
    state: FSMContext,
) -> None:
    """Qarzdorlar ro'yxatiga qaytadi."""
    await state.clear()
    debtors = await client_service.get_debtor_summaries()

    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    if not debtors:
        await callback.message.edit_text(
            "🎉 <b>Hozirda hech kimda qarz yo'q! Barcha qarzlar yopilgan.</b>"
        )
        await callback.answer()
        return

    await callback.message.edit_text(
        _debtors_header(debtors),
        reply_markup=get_debtors_list_keyboard(debtors, page=1),
    )
    await callback.answer()


# ==========================================
# 1. QARZ TO'LOVI MENYUSI
# ==========================================


@router.message(F.text == "💰 Qarz to'lovi")
async def show_debtors_payment_list(
    message: Message,
    client_service: ClientService,
    state: FSMContext,
) -> None:
    """Qarz to'lash uchun barcha qarzdorlar ro'yxatini ko'rsatadi."""
    await state.clear()
    debtors = await client_service.get_debtor_summaries()

    if not debtors:
        await message.answer(
            "🎉 <b>Hozirda hech kimda qarz yo'q! Barcha qarzlar to'liq yopilgan.</b>\n\n"
            "Yangi qarz kiritish uchun <b>➕ Yaratish</b> tugmasini bosing."
        )
        return

    await message.answer(
        _debtors_header(debtors),
        reply_markup=get_debtors_list_keyboard(debtors, page=1),
    )


@router.callback_query(F.data.startswith("pay_page:"))
async def cb_pay_page(
    callback: CallbackQuery,
    client_service: ClientService,
) -> None:
    """To'lov qarzdorlari sahifasini almashtiradi."""
    if callback.data is None or not isinstance(callback.message, Message):
        return

    page = int(callback.data.split(":")[1])
    debtors = await client_service.get_debtor_summaries()
    if not debtors:
        await callback.answer("Qarzdorlar mavjud emas.", show_alert=True)
        return

    await callback.message.edit_text(
        _debtors_header(debtors),
        reply_markup=get_debtors_list_keyboard(debtors, page=page),
    )
    await callback.answer()


# ==========================================
# 2. QARZDORNI TANLASH VA TO'LOV TURINI KO'RSATISH
# ==========================================


@router.callback_query(F.data.startswith("select_pay_client:"))
async def cb_select_pay_client(
    callback: CallbackQuery,
    client_service: ClientService,
    state: FSMContext,
) -> None:
    """Tanlangan qarzdorning ma'lumotlarini va to'lov variantlarini ko'rsatadi."""
    if callback.data is None or not isinstance(callback.message, Message):
        return

    client_id = int(callback.data.split(":")[1])
    client = await client_service.get_by_id(client_id)
    if client is None:
        await callback.answer("Mijoz topilmadi.", show_alert=True)
        return

    # Mijozning valyutalar bo'yicha qoldiq qarzini olish
    summaries = await client_service.get_debtor_summaries()
    client_summary = next((s for s in summaries if s.client.id == client_id), None)
    remaining_map = client_summary.remaining_by_currency if client_summary else {}

    if not any(amount > 0 for amount in remaining_map.values()):
        await callback.message.edit_text(
            f"👤 <b>{esc_html(client.full_name)}</b> ning hozirda qarzi yo'q (0)."
        )
        await callback.answer()
        return

    await state.clear()
    text = (
        f"👤 <b>QARZ TO'LOVI:</b> <b>{esc_html(client.full_name)}</b>\n"
        f"📞 <b>Telefon:</b> {esc_html(client.phone)}\n"
        f"💳 <b>Joriy qarzi:</b> <b>🔴 {format_money_map(remaining_map)}</b>\n\n"
        "<i>To'lov turini tanlang:</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_payment_type_keyboard(client_id, remaining_map),
    )
    await callback.answer()


# ==========================================
# 3. TO'LIQ TO'LASH
# ==========================================


@router.callback_query(F.data.startswith("pay_mode_full:"))
async def cb_pay_mode_full(
    callback: CallbackQuery,
    debt_service: DebtService,
    settings: Settings,
    state: FSMContext,
) -> None:
    """Qarzni to'liq yopadi (barcha valyutalarda)."""
    await state.clear()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    client_id = int(callback.data.split(":")[1])
    today = today_str()

    try:
        paid_map, summary = await debt_service.pay_full_debt(
            client_id=client_id,
            payment_date=today,
        )

        success_text = (
            "✅ <b>TO'LOV MUVAFFAQIYATLI QABUL QILINDI!</b>\n\n"
            f"👤 <b>Mijoz:</b> {esc_html(summary.client.full_name)}\n"
            f"💰 <b>To'langan summa:</b> {format_money_map(paid_map)}\n"
            "💳 <b>Joriy qarzi:</b> <b>🟢 0 (Qarzi to'liq yopildi)</b>"
        )
        await callback.message.edit_text(success_text)
        await callback.message.answer(
            "Asosiy menyu:",
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )
        await callback.answer("Qarz to'liq yopildi!", show_alert=False)

    except Exception as exc:
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                f"❌ <b>Xatolik yuz berdi:</b> {esc_html(str(exc))}"
            )
        await callback.answer("Xatolik yuz berdi.", show_alert=True)


# ==========================================
# 4. QISMAN TO'LASH (valyuta tanlash bilan)
# ==========================================


@router.callback_query(F.data.startswith("pay_mode_partial:"))
async def cb_pay_mode_partial(
    callback: CallbackQuery,
    client_service: ClientService,
    state: FSMContext,
) -> None:
    """Qisman to'lov uchun valyuta tanlaydi (bitta bo'lsa darhol summani so'raydi)."""
    if callback.data is None or not isinstance(callback.message, Message):
        return

    client_id = int(callback.data.split(":")[1])
    client = await client_service.get_by_id(client_id)
    if client is None:
        await callback.answer("Mijoz topilmadi.", show_alert=True)
        return

    summaries = await client_service.get_debtor_summaries()
    client_summary = next((s for s in summaries if s.client.id == client_id), None)
    remaining_map = client_summary.remaining_by_currency if client_summary else {}
    owed = [
        Currency(cur)
        for cur in (Currency.UZS.value, Currency.USD.value)
        if remaining_map.get(cur, 0) > 0
    ]

    if len(owed) > 1:
        # Ikki valyutada ham qarzi bor — avval qaysi valyutada to'layotganini so'raymiz
        await callback.message.edit_text(
            "🟡 <b>QISMAN QARZ TO'LOVI</b>\n\n"
            f"👤 <b>Mijoz:</b> {esc_html(client.full_name)}\n"
            f"💳 <b>Joriy qarzi:</b> <b>{format_money_map(remaining_map)}</b>\n\n"
            "<i>Qaysi valyutada to'lov qilmoqchisiz?</i>",
            reply_markup=get_payment_currency_keyboard(client_id, owed),
        )
        await callback.answer()
        return

    if not owed:
        await callback.message.edit_text(
            f"👤 <b>{esc_html(client.full_name)}</b> ning hozirda qarzi yo'q."
        )
        await callback.answer()
        return

    await _ask_partial_amount(
        callback.message,
        state,
        client.full_name,
        client_id,
        owed[0],
        remaining_map.get(owed[0].value, 0),
        remaining_map,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("pay_currency:"))
async def cb_pay_currency(
    callback: CallbackQuery,
    client_service: ClientService,
    state: FSMContext,
) -> None:
    """Qisman to'lov valyutasi tanlandi — summani so'raydi."""
    if callback.data is None or not isinstance(callback.message, Message):
        return

    parts = callback.data.split(":")
    client_id = int(parts[1])
    currency = Currency(parts[2])

    client = await client_service.get_by_id(client_id)
    if client is None:
        await callback.answer("Mijoz topilmadi.", show_alert=True)
        return

    summaries = await client_service.get_debtor_summaries()
    client_summary = next((s for s in summaries if s.client.id == client_id), None)
    remaining_map = client_summary.remaining_by_currency if client_summary else {}

    await _ask_partial_amount(
        callback.message,
        state,
        client.full_name,
        client_id,
        currency,
        remaining_map.get(currency.value, 0),
        remaining_map,
    )
    await callback.answer()


async def _ask_partial_amount(
    message: Message,
    state: FSMContext,
    client_name: str,
    client_id: int,
    currency: Currency,
    total_in_currency: int,
    remaining_map: dict[str, int],
) -> None:
    """Qisman to'lov summasini so'raydi va holatni saqlaydi."""
    await state.set_state(DebtPaymentStates.waiting_partial_amount)
    await state.update_data(
        client_id=client_id,
        client_name=client_name,
        currency=currency.value,
        total_remaining=total_in_currency,
    )
    currency_label = "So'mda" if currency == Currency.UZS else "Dollarda"
    example = "500 000" if currency == Currency.UZS else "200"
    text = (
        f"🟡 <b>QISMAN QARZ TO'LOVI</b>\n\n"
        f"👤 <b>Mijoz:</b> {esc_html(client_name)}\n"
        f"💳 <b>Joriy qarzi:</b> <b>{format_money_map(remaining_map)}</b>\n\n"
        f"💰 <b>{currency_label} qancha summa to'ladi?</b>\n"
        f"<i>Masalan: {example}</i>"
    )
    await message.edit_text(
        text,
        reply_markup=get_payment_back_cancel_keyboard(client_id),
    )


@router.message(DebtPaymentStates.waiting_partial_amount)
async def process_partial_amount(
    message: Message,
    debt_service: DebtService,
    settings: Settings,
    state: FSMContext,
) -> None:
    """Qisman to'lov summasini tekshiradi va to'lovni amalga oshiradi."""
    amount = parse_money(message.text or "")
    data = await state.get_data()
    client_id: int = data.get("client_id", 0)
    client_name: str = data.get("client_name", "Mijoz")
    currency = Currency(data.get("currency", Currency.UZS.value))
    total_remaining: int = data.get("total_remaining", 0)

    if amount is None or amount <= 0:
        await message.answer(
            "⚠️ <b>Noto'g'ri summa!</b>\n\n"
            "Iltimos, musbat son kiriting (masalan: <code>500 000</code>):",
            reply_markup=get_payment_back_cancel_keyboard(client_id),
        )
        return

    if amount > total_remaining:
        await message.answer(
            f"⚠️ <b>To'lov summasi ({format_money(amount, currency)}) mavjud qarzdan "
            f"({format_money(total_remaining, currency)}) katta bo'lishi mumkin emas!</b>\n\n"
            "Iltimos, qayta kiriting:",
            reply_markup=get_payment_back_cancel_keyboard(client_id),
        )
        return

    await state.clear()
    today = today_str()

    try:
        paid_amount, new_remaining, summary = await debt_service.pay_partial_debt(
            client_id=client_id,
            amount=amount,
            payment_date=today,
            currency=currency,
        )

        if not summary.has_debt:
            result_text = (
                "✅ <b>TO'LOV MUVAFFAQIYATLI QABUL QILINDI!</b>\n\n"
                f"👤 <b>{esc_html(client_name)}</b> "
                f"{format_money(paid_amount, currency)} to'ladi.\n"
                "💳 <b>Mijoz qarzini to'liq yopdi! Qoldiq qarz: 🟢 0.</b>"
            )
        else:
            result_text = (
                "✅ <b>TO'LOV MUVAFFAQIYATLI QABUL QILINDI!</b>\n\n"
                f"👤 <b>Mijoz:</b> {esc_html(client_name)}\n"
                f"💰 <b>To'langan summa:</b> {format_money(paid_amount, currency)}\n"
                "💳 <b>Qolgan qarz:</b> <b>🔴 "
                f"{format_money_map(summary.remaining_by_currency)}</b>"
            )

        await message.answer(result_text)
        await message.answer(
            "Asosiy menyu:",
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )

    except Exception as exc:
        await message.answer(f"❌ <b>Xatolik yuz berdi:</b> {esc_html(str(exc))}")
