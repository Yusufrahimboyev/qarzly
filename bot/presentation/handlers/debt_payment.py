"""Presentation qatlami: Qarz to'lovi handler'lari."""
from __future__ import annotations

from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import format_money, parse_money
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.presentation.keyboards.main_menu_kb import get_main_menu_keyboard
from bot.presentation.keyboards.payment_kb import (
    get_debtors_list_keyboard,
    get_payment_back_cancel_keyboard,
    get_payment_type_keyboard,
)
from bot.presentation.states.debt_payment import DebtPaymentStates

router = Router()


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

    total_debt = sum(d.total_remaining_debt for d in debtors)
    text = (
        "💰 <b>QARZ TO'LOVI (Qarzdorlar ro'yxati):</b>\n\n"
        f"🔴 <b>Qarzdorlar soni:</b> {len(debtors)} nafar\n"
        f"💳 <b>Jami olinishi kerak:</b> <b>{format_money(total_debt)}</b>\n\n"
        "<i>To'lov qilayotgan mijozni tanlang:</i>"
    )
    await callback.message.edit_text(
        text,
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

    total_debt = sum(d.total_remaining_debt for d in debtors)
    text = (
        "💰 <b>QARZ TO'LOVI (Qarzdorlar ro'yxati):</b>\n\n"
        f"🔴 <b>Qarzdorlar soni:</b> {len(debtors)} nafar\n"
        f"💳 <b>Jami olinishi kerak:</b> <b>{format_money(total_debt)}</b>\n\n"
        "<i>To'lov qilayotgan mijozni tanlang:</i>"
    )
    await message.answer(
        text,
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

    total_debt = sum(d.total_remaining_debt for d in debtors)
    text = (
        "💰 <b>QARZ TO'LOVI (Qarzdorlar ro'yxati):</b>\n\n"
        f"🔴 <b>Qarzdorlar soni:</b> {len(debtors)} nafar\n"
        f"💳 <b>Jami olinishi kerak:</b> <b>{format_money(total_debt)}</b>\n\n"
        "<i>To'lov qilayotgan mijozni tanlang:</i>"
    )
    await callback.message.edit_text(
        text,
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

    # Mijozning umumiy qoldiq qarzini olish
    summaries = await client_service.get_debtor_summaries()
    client_summary = next((s for s in summaries if s.client.id == client_id), None)
    total_remaining = client_summary.total_remaining_debt if client_summary else 0

    if total_remaining <= 0:
        await callback.message.edit_text(
            f"👤 <b>{client.full_name}</b> ning hozirda qarzi yo'q (0 so'm)."
        )
        await callback.answer()
        return

    await state.clear()
    text = (
        f"👤 <b>QARZ TO'LOVI:</b> <b>{client.full_name}</b>\n"
        f"📞 <b>Telefon:</b> {client.phone}\n"
        f"💳 <b>Joriy qarzi:</b> <b>🔴 {format_money(total_remaining)}</b>\n\n"
        "<i>To'lov turini tanlang:</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_payment_type_keyboard(client_id, total_remaining),
    )
    await callback.answer()


# ==========================================
# 3. TO'LIQ TO'LASH
# ==========================================


@router.callback_query(F.data.startswith("pay_mode_full:"))
async def cb_pay_mode_full(
    callback: CallbackQuery,
    client_service: ClientService,
    debt_service: DebtService,
    settings: Settings,
    state: FSMContext,
) -> None:
    """Qarzni to'liq yopadi."""
    await state.clear()
    if callback.data is None or not isinstance(callback.message, Message):
        return

    client_id = int(callback.data.split(":")[1])
    today_str = datetime.now().strftime("%d.%m.%Y")

    try:
        total_paid, summary = await debt_service.pay_full_debt(
            client_id=client_id,
            payment_date=today_str,
        )

        success_text = (
            "✅ <b>TO'LOV MUVAFFAQIYATLI QABUL QILINDI!</b>\n\n"
            f"👤 <b>Mijoz:</b> {summary.client.full_name}\n"
            f"💰 <b>To'langan summa:</b> {format_money(total_paid)}\n"
            "💳 <b>Joriy qarzi:</b> <b>🟢 0 so'm (Qarzi to'liq yopildi)</b>"
        )
        await callback.message.edit_text(success_text)
        await callback.message.answer(
            "Asosiy menyu:",
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )
        await callback.answer("Qarz to'liq yopildi!", show_alert=False)

    except Exception as exc:
        await callback.message.edit_text(f"❌ <b>Xatolik yuz berdi:</b> {exc}")
        await callback.answer("Xatolik yuz berdi.", show_alert=True)


# ==========================================
# 4. QISMAN TO'LASH
# ==========================================


@router.callback_query(F.data.startswith("pay_mode_partial:"))
async def cb_pay_mode_partial(
    callback: CallbackQuery,
    client_service: ClientService,
    state: FSMContext,
) -> None:
    """Qisman to'lov uchun summani so'raydi."""
    if callback.data is None or not isinstance(callback.message, Message):
        return

    client_id = int(callback.data.split(":")[1])
    client = await client_service.get_by_id(client_id)
    if client is None:
        await callback.answer("Mijoz topilmadi.", show_alert=True)
        return

    summaries = await client_service.get_debtor_summaries()
    client_summary = next((s for s in summaries if s.client.id == client_id), None)
    total_remaining = client_summary.total_remaining_debt if client_summary else 0

    await state.set_state(DebtPaymentStates.waiting_partial_amount)
    await state.update_data(
        client_id=client_id,
        client_name=client.full_name,
        total_remaining=total_remaining,
    )

    text = (
        f"🟡 <b>QISMAN QARZ TO'LOVI</b>\n\n"
        f"👤 <b>Mijoz:</b> {client.full_name}\n"
        f"💳 <b>Joriy qarz:</b> <b>{format_money(total_remaining)}</b>\n\n"
        "💰 <b>Qancha summa to'ladi (so'mda)?</b>\n"
        "<i>Masalan: 500 000 yoki 500000</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=get_payment_back_cancel_keyboard(client_id),
    )
    await callback.answer()


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
            f"⚠️ <b>To'lov summasi ({format_money(amount)}) mavjud qarzdan "
            f"({format_money(total_remaining)}) katta bo'lishi mumkin emas!</b>\n\n"
            "Iltimos, qayta kiriting:",
            reply_markup=get_payment_back_cancel_keyboard(client_id),
        )
        return

    await state.clear()
    today_str = datetime.now().strftime("%d.%m.%Y")

    try:
        paid_amount, new_remaining, summary = await debt_service.pay_partial_debt(
            client_id=client_id,
            amount=amount,
            payment_date=today_str,
        )

        if new_remaining == 0:
            result_text = (
                "✅ <b>TO'LOV MUVAFFAQIYATLI QABUL QILINDI!</b>\n\n"
                f"👤 <b>{client_name}</b> {format_money(paid_amount)} to'ladi.\n"
                "💳 <b>Mijoz qarzini to'liq yopdi! Qoldiq qarz: 🟢 0 so'm.</b>"
            )
        else:
            result_text = (
                "✅ <b>TO'LOV MUVAFFAQIYATLI QABUL QILINDI!</b>\n\n"
                f"👤 <b>Mijoz:</b> {client_name}\n"
                f"💰 <b>To'langan summa:</b> {format_money(paid_amount)}\n"
                f"💳 <b>Qolgan qarz:</b> <b>🔴 {format_money(new_remaining)}</b>"
            )

        await message.answer(result_text)
        await message.answer(
            "Asosiy menyu:",
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )

    except Exception as exc:
        await message.answer(f"❌ <b>Xatolik yuz berdi:</b> {exc}")
