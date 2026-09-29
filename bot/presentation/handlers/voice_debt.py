"""Presentation qatlami: ovozli xabar orqali qarz qo'shish.

Admin botga ovozli xabar yuboradi ("Anvarga ikkita shina besh yuz ming
so'mdan") → matnga o'giriladi → tovar qarz yaratish ustasiga qo'shiladi.
Keyingi qadamlar (yana tovar, exchange, berilgan pul, tasdiqlash) mavjud
usta orqali davom etadi — hech narsa tasdiqsiz saqlanmaydi.
"""
from __future__ import annotations

import logging

from aiogram import Bot, F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.application.common.formatters import (
    clip_button_text,
    esc_html,
    format_money,
    today_str,
)
from bot.application.common.voice_parser import VoiceParseError
from bot.application.services.client_service import ClientService
from bot.application.services.voice_debt_service import VoiceDebtService, client_label
from bot.domain.entities.debt import DebtProduct
from bot.presentation.keyboards.creation_kb import (
    get_more_products_keyboard,
    get_product_currency_keyboard,
)
from bot.presentation.states.debt_creation import DebtCreationStates

logger = logging.getLogger(__name__)

router = Router()

MAX_VOICE_SECONDS = 60
_MAX_SWITCH_BUTTONS = 3

_USAGE_HINT = (
    "<i>Masalan: «Anvarga ikkita shina besh yuz ming so'mdan» yoki "
    "«Alisherga akkumulyator 120 dollar»</i>"
)


@router.message(StateFilter(None), F.voice)
async def process_voice_debt(
    message: Message,
    state: FSMContext,
    bot: Bot,
    voice_debt_service: VoiceDebtService | None,
) -> None:
    """Ovozli xabardan qarz qoralamasini tayyorlab, ustaga uzatadi."""
    if voice_debt_service is None:
        await message.answer("🎙 Ovozli xabar orqali qarz qo'shish sozlanmagan.")
        return
    if message.voice is None:
        return
    if message.voice.duration > MAX_VOICE_SECONDS:
        await message.answer(
            f"⚠️ Ovozli xabar {MAX_VOICE_SECONDS} soniyadan oshmasligi kerak."
        )
        return

    status = await message.answer("🎙 Ovozli xabar tahlil qilinmoqda...")

    try:
        audio = await bot.download(message.voice)
        if audio is None:
            raise RuntimeError("Ovozli xabarni yuklab bo'lmadi.")
        transcript = await voice_debt_service.transcribe(audio.read())
    except Exception:
        logger.exception("Ovozli xabarni matnga o'girishda xatolik")
        await status.edit_text(
            "❌ <b>Ovozni matnga o'girib bo'lmadi.</b>\n\n"
            "Keyinroq urinib ko'ring yoki '➕ Yaratish' orqali qo'lda kiriting."
        )
        return

    heard = f"🎙 <b>Eshitildi:</b> «{esc_html(transcript)}»\n\n"
    try:
        voice_debt = await voice_debt_service.prepare(transcript)
    except VoiceParseError as exc:
        await status.edit_text(f"{heard}⚠️ <b>{esc_html(exc)}</b>\n\n{_USAGE_HINT}")
        return

    draft = voice_debt.draft
    client_line = (
        f"👤 <b>Mijoz:</b> {esc_html(voice_debt.client_name)}"
        + (f" ({esc_html(voice_debt.client_phone)})" if voice_debt.client_phone else "")
        + (" — <i>mavjud mijoz</i>" if voice_debt.is_existing_client else " — <i>yangi mijoz</i>")
        + "\n"
    )
    similar = voice_debt.similar_clients[:_MAX_SWITCH_BUTTONS]
    if similar:
        client_line += "⚠️ <i>O'xshash mijozlar ham bor — to'g'risi boshqa bo'lsa, tanlang.</i>\n"
    switch_rows = [
        [
            InlineKeyboardButton(
                text=clip_button_text(f"👤 {client_label(c)}"),
                callback_data=f"voice_client:{c.id}",
            )
        ]
        for c in similar
    ]

    await state.clear()
    await state.update_data(
        debt_date=today_str(),
        client_name=voice_debt.client_name,
        client_phone=voice_debt.client_phone,
        _products=[],
        product_name=draft.product_name,
        product_quantity=draft.quantity,
        product_price=draft.price_per_unit,
    )

    if draft.currency is None:
        price = f"{draft.price_per_unit:,}".replace(",", " ")
        await state.set_state(DebtCreationStates.waiting_product_currency)
        await status.edit_text(
            f"{heard}{client_line}"
            f"📦 <b>Tovar:</b> {esc_html(draft.product_name)} — "
            f"{draft.quantity} × {price}\n\n"
            "💱 <b>Narx qaysi valyutada?</b>",
            reply_markup=_with_rows(switch_rows, get_product_currency_keyboard()),
        )
        return

    product = DebtProduct(
        name=draft.product_name,
        quantity=draft.quantity,
        price_per_unit=draft.price_per_unit,
        currency=draft.currency,
    )
    await state.update_data(_products=[product])
    await state.set_state(DebtCreationStates.waiting_more_products)
    await status.edit_text(
        f"{heard}{client_line}"
        f"✅ <b>Qo'shildi:</b> {esc_html(product.name)} — {product.quantity} × "
        f"{format_money(product.price_per_unit, product.currency)} = "
        f"{format_money(product.total_price, product.currency)}\n\n"
        "➕ <b>Yana tovar qo'shasizmi?</b>",
        reply_markup=_with_rows(switch_rows, get_more_products_keyboard()),
    )


@router.callback_query(
    StateFilter(
        DebtCreationStates.waiting_more_products,
        DebtCreationStates.waiting_product_currency,
    ),
    F.data.startswith("voice_client:"),
)
async def cb_voice_switch_client(
    callback: CallbackQuery,
    state: FSMContext,
    client_service: ClientService,
) -> None:
    """Ovozdan aniqlangan mijozni o'xshash mavjud mijozga almashtiradi."""
    client_id_raw = (callback.data or "").split(":", 1)[1]
    client = (
        await client_service.get_by_id(int(client_id_raw))
        if client_id_raw.isdigit()
        else None
    )
    if client is None:
        await callback.answer("Mijoz topilmadi.", show_alert=True)
        return

    await state.update_data(client_name=client.full_name, client_phone=client.phone)
    if isinstance(callback.message, Message):
        waiting_currency = (
            await state.get_state() == DebtCreationStates.waiting_product_currency.state
        )
        await callback.message.edit_reply_markup(
            reply_markup=get_product_currency_keyboard()
            if waiting_currency
            else get_more_products_keyboard()
        )
        await callback.message.answer(
            f"👤 <b>Mijoz o'zgartirildi:</b> {esc_html(client_label(client))}"
        )
    await callback.answer()


def _with_rows(
    rows: list[list[InlineKeyboardButton]], keyboard: InlineKeyboardMarkup
) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[*rows, *keyboard.inline_keyboard])
