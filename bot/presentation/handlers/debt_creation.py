"""Presentation qatlami: Qarz yaratish (wizard) handler'lari.

Bir qarzda bir nechta tovar bo'lishi mumkin. Tovar kiritish sikli:
    tovar nomi → nechta → narxi → "Yana tovar?" → (takrorlanadi yoki keyingi)
Keyin: valyuta → exchange → berilgan pul → tasdiqlash.
"""
from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import (
    esc_html,
    format_money,
    format_money_map,
    is_valid_phone,
    normalize_phone,
    parse_date_input,
    parse_money,
    today_str,
)
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import DebtProduct
from bot.presentation.keyboards.creation_kb import (
    get_back_cancel_keyboard,
    get_creation_confirm_keyboard,
    get_date_picker_keyboard,
    get_exchange_choice_keyboard,
    get_exchange_currency_keyboard,
    get_given_currency_keyboard,
    get_given_money_choice_keyboard,
    get_more_products_keyboard,
    get_phone_keyboard,
    get_product_currency_keyboard,
)
from bot.presentation.keyboards.main_menu_kb import get_main_menu_keyboard
from bot.presentation.states.debt_creation import DebtCreationStates

router = Router()


# ==========================================
# 0. BEKOR QILISH VA ORTGA QAYTISH
# ==========================================


@router.callback_query(F.data.startswith("add_debt_for_client:"))
async def cb_add_debt_for_client(
    callback: CallbackQuery,
    state: FSMContext,
    client_service: ClientService,
) -> None:
    """Jadvaldan tanlangan mavjud mijozga yangi qarz qo'shishni boshlaydi.

    Ism va telefon allaqachon ma'lum — sanadan boshlab so'raladi,
    mijoz ma'lumotlari qayta so'ralmaydi (dublikat bo'lmaydi).
    """
    if callback.data is None or not isinstance(callback.message, Message):
        await callback.answer()
        return

    client_id_raw = callback.data.split(":", 1)[1]
    if not client_id_raw.isdigit():
        await callback.answer("Noto'g'ri so'rov.", show_alert=True)
        return

    client = await client_service.get_by_id(int(client_id_raw))
    if client is None:
        await callback.answer("Mijoz topilmadi.", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        client_name=client.full_name,
        client_phone=client.phone,
    )
    await state.set_state(DebtCreationStates.waiting_date)

    await callback.message.edit_text(
        "📝 <b>YANGI QARZ YARATISH</b>\n\n"
        f"👤 <b>Mijoz:</b> {client.full_name}\n"
        f"📞 <b>Telefon:</b> {client.phone}\n\n"
        "📅 <b>Qarzga olingan sanani kiriting:</b>\n\n"
        "<i>Masalan: 17.08.2026 yoki 'Bugun' tugmasini bosing</i>",
        reply_markup=get_date_picker_keyboard(),
    )
    await callback.answer()


@router.callback_query(F.data == "cancel_creation")
async def cb_cancel_creation(
    callback: CallbackQuery,
    state: FSMContext,
    settings: Settings,
) -> None:
    """Qarz yaratish jarayonini bekor qiladi."""
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.edit_text("❌ <b>Qarz yaratish bekor qilindi.</b>")
        await callback.message.answer(
            "Asosiy menyu:",
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )
    await callback.answer()


@router.callback_query(F.data == "create_back")
async def cb_create_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Oldingi bosqichga qaytaradi."""
    current_state = await state.get_state()
    data = await state.get_data()

    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    if current_state == DebtCreationStates.waiting_client_name:
        await state.set_state(DebtCreationStates.waiting_date)
        await callback.message.edit_text(
            "📅 <b>1-bosqich: Qarzga olingan sanani kiriting:</b>\n\n"
            "<i>Masalan: 16.08.2026 yoki 'Bugun' tugmasini bosing</i>",
            reply_markup=get_date_picker_keyboard(),
        )

    elif current_state == DebtCreationStates.waiting_client_phone:
        await state.set_state(DebtCreationStates.waiting_client_name)
        await callback.message.edit_text(
            "👤 <b>2-bosqich: Qarz oluvchining ism-familiyasini kiriting:</b>\n\n"
            "<i>Masalan: Aliyev Anvar</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

        if (
            data.get("client_name")
            and "client_phone" in data
            and not data.get("_manual_flow", True)
        ):
            # Mavjud mijozga qarz qo'shilmoqda — sanaga qaytamiz
            await state.set_state(DebtCreationStates.waiting_date)
            await callback.message.edit_text(
                "📅 <b>Qarzga olingan sanani kiriting:</b>\n\n"
                "<i>Masalan: 17.08.2026 yoki 'Bugun' tugmasini bosing</i>",
                reply_markup=get_date_picker_keyboard(),
            )
        else:
            await state.set_state(DebtCreationStates.waiting_client_phone)
            await callback.message.edit_text(
                "📞 <b>3-bosqich: Telefon raqamini kiriting (ixtiyoriy):</b>\n\n"
                "<i>Masalan: +998901234567 yoki 'O'tkazib yuborish'ni bosing:</i>",
                reply_markup=get_phone_keyboard(),
            )

    elif current_state == DebtCreationStates.waiting_product_quantity:
        await state.set_state(DebtCreationStates.waiting_product_name)
        product_num = _current_product_number(data) + 1
        await callback.message.edit_text(
            f"📦 <b>4-bosqich: {product_num}-tovar nomini kiriting:</b>\n\n"
            "<i>Masalan: Shina, Akkumulyator</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_product_price:
        await state.set_state(DebtCreationStates.waiting_product_quantity)
        await callback.message.edit_text(
            "🔢 <b>5-bosqich: Tovardan nechta olindi?</b>\n\n"
            "<i>Masalan: 2 — bitta bo'lsa 1 deb yozing</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_product_currency:
        await state.set_state(DebtCreationStates.waiting_product_price)
        await callback.message.edit_text(
            "💰 <b>Bitta tovar narxini kiriting:</b>\n\n"
            "<i>Masalan: 2 500 000 — jami summa o'zi hisoblanadi</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_more_products:
        # "Yana tovar?" dan ortga — oxirgi tovarni olib tashlash
        products = list(data.get("_products", []))
        if products:
            products.pop()
            await state.update_data(_products=products)
        await state.set_state(DebtCreationStates.waiting_product_price)
        await callback.message.edit_text(
            "💰 <b>Bitta tovar narxini kiriting:</b>\n\n"
            "<i>Masalan: 2 500 000 — jami summa o'zi hisoblanadi</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_exchange_choice:
        await state.set_state(DebtCreationStates.waiting_more_products)
        await callback.message.edit_text(
            "➕ <b>Yana tovar qo'shasizmi?</b>\n\n"
            "<i>Agar bir nechta turli tovar olgan bo'lsa, yana qo'shing.</i>",
            reply_markup=get_more_products_keyboard(),
        )

    elif current_state == DebtCreationStates.waiting_exchange_currency:
        await state.set_state(DebtCreationStates.waiting_exchange_choice)
        await callback.message.edit_text(
            "🔄 <b>Ayirboshlash (Exchange) tovari bormi?</b>",
            reply_markup=get_exchange_choice_keyboard(),
        )

    elif current_state == DebtCreationStates.waiting_exchange_name:
        await state.set_state(DebtCreationStates.waiting_exchange_currency)
        await callback.message.edit_text(
            "💱 <b>Ayirboshlash tovari qaysi valyutada?</b>\n\n"
            "<i>Exchange shu valyutadagi tovarlar qarzidan chegiriladi</i>",
            reply_markup=get_exchange_currency_keyboard(),
        )

    elif current_state == DebtCreationStates.waiting_exchange_price:
        await state.set_state(DebtCreationStates.waiting_exchange_name)
        await callback.message.edit_text(
            "📦 <b>Ayirboshlash tovari nomini kiriting:</b>\n\n"
            "<i>Masalan: Eski shina</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_given_money_choice:
        if data.get("exchange_exists", False):
            await state.set_state(DebtCreationStates.waiting_exchange_price)
            await callback.message.edit_text(
                "💰 <b>Ayirboshlash tovari narxini kiriting:</b>\n\n"
                "<i>Masalan: 800 000</i>",
                reply_markup=get_back_cancel_keyboard(show_back=True),
            )
        else:
            await state.set_state(DebtCreationStates.waiting_exchange_choice)
            await callback.message.edit_text(
                "🔄 <b>Ayirboshlash (Exchange) tovari bormi?</b>",
                reply_markup=get_exchange_choice_keyboard(),
            )

    elif current_state == DebtCreationStates.waiting_given_currency:
        await state.set_state(DebtCreationStates.waiting_given_money_choice)
        await callback.message.edit_text(
            "💵 <b>Qarzdan oldindan pul berildimi?</b>",
            reply_markup=get_given_money_choice_keyboard(),
        )

    elif current_state == DebtCreationStates.waiting_given_money_amount:
        await state.set_state(DebtCreationStates.waiting_given_currency)
        await callback.message.edit_text(
            "💱 <b>Berilgan pul qaysi valyutada?</b>\n\n"
            "<i>Shu valyutadagi tovarlar qarzidan chegiriladi</i>",
            reply_markup=get_given_currency_keyboard(),
        )

    elif current_state == DebtCreationStates.waiting_confirm:
        await state.set_state(DebtCreationStates.waiting_given_money_choice)
        await callback.message.edit_text(
            "💵 <b>Qarzdan oldindan pul berildimi?</b>",
            reply_markup=get_given_money_choice_keyboard(),
        )

    await callback.answer()


def _current_product_number(data: dict) -> int:
    """Hozirgi kiritilayotgan tovar tartib raqami (1-asosiy)."""
    return len(data.get("_products", []))


# ==========================================
# 1. BOSHLASH: SANA KIRITISH
# ==========================================


@router.message(F.text == "➕ Yaratish")
async def start_debt_creation(message: Message, state: FSMContext) -> None:
    """Qarz yaratish jarayonini boshlaydi."""
    await state.clear()
    await state.set_state(DebtCreationStates.waiting_date)
    await message.answer(
        "📝 <b>YANGI QARZ YARATISH</b>\n\n"
        "📅 <b>1-bosqich: Qarzga olingan sanani kiriting:</b>\n\n"
        "<i>Masalan: 16.08.2026 yoki 'Bugun' tugmasini bosing</i>",
        reply_markup=get_date_picker_keyboard(),
    )


@router.callback_query(DebtCreationStates.waiting_date, F.data == "create_date_today")
async def cb_date_today(callback: CallbackQuery, state: FSMContext) -> None:
    """Bugungi sanani qabul qiladi."""
    today = today_str()
    await state.update_data(debt_date=today)

    if isinstance(callback.message, Message):
        await _proceed_after_date(callback.message, state, today)
    await callback.answer()


async def _proceed_after_date(message: Message, state: FSMContext, date_str: str) -> None:
    """Sanadan keyingi bosqichga o'tadi.

    Mavjud mijozga qarz qo'shilayotgan bo'lsa (ism/telefon oldindan
    to'ldirilgan) — ularni qayta so'ramasdan to'var kiritishga o'tadi.
    """
    data = await state.get_data()

    if data.get("client_name") and data.get("client_phone"):
        client_name = data["client_name"]
        client_phone = data["client_phone"]
        await state.update_data(_products=[])
        await state.set_state(DebtCreationStates.waiting_product_name)
        await message.answer(
            f"📅 <b>Sana:</b> {date_str}\n"
            f"👤 <b>Mijoz:</b> {esc_html(client_name)} ({esc_html(client_phone)})\n\n"
            "📦 <b>Tovar (mahsulot) nomini kiriting:</b>\n\n"
            "<i>Masalan: Shina, Akkumulyator, Generator</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
    else:
        await state.set_state(DebtCreationStates.waiting_client_name)
        await message.answer(
            f"📅 <b>Sana:</b> {date_str}\n\n"
            "👤 <b>2-bosqich: Qarz oluvchining ism-familiyasini kiriting:</b>\n\n"
            "<i>Masalan: Aliyev Anvar</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )


@router.message(DebtCreationStates.waiting_date)
async def process_custom_date(message: Message, state: FSMContext) -> None:
    """Foydalanuvchi yozgan sanani tekshiradi."""
    if message.text is None:
        await message.answer("Iltimos, sanani matn ko'rinishida kiriting.")
        return

    parsed_date = parse_date_input(message.text)
    if parsed_date is None:
        await message.answer(
            "⚠️ <b>Noto'g'ri sana formati!</b>\n\n"
            "Iltimos, sanani <b>DD.MM.YYYY</b> ko'rinishida kiriting "
            "(masalan: <code>16.08.2026</code>) "
            "yoki quyidagi 'Bugun' tugmasini bosing:",
            reply_markup=get_date_picker_keyboard(),
        )
        return

    await state.update_data(debt_date=parsed_date)
    await _proceed_after_date(message, state, parsed_date)


# ==========================================
# 2. QARZ OLUVCHI: ISM VA TELEFON
# ==========================================


@router.message(DebtCreationStates.waiting_client_name)
async def process_client_name(message: Message, state: FSMContext) -> None:
    """Mijoz ism-familiyasini qabul qiladi."""
    name = (message.text or "").strip()
    if len(name) < 2:
        await message.answer(
            "⚠️ <b>Ism juda qisqa!</b>\n\n"
            "Iltimos, qarz oluvchining to'liq ism-familiyasini kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return
    if len(name) > 80:
        await message.answer(
            "⚠️ <b>Ism juda uzun!</b>\n\n"
            "Iltimos, 80 belgidan qisqa kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(client_name=name)
    await state.set_state(DebtCreationStates.waiting_client_phone)
    await message.answer(
        f"👤 <b>Qarz oluvchi:</b> {esc_html(name)}\n\n"
        "📞 <b>3-bosqich: Telefon raqamini kiriting (ixtiyoriy):</b>\n\n"
        "<i>Masalan: +998901234567 yoki telefon bo'lmasa 'O'tkazib yuborish' tugmasini bosing:</i>",
        reply_markup=get_phone_keyboard(),
    )


@router.callback_query(F.data == "skip_client_phone")
async def cb_skip_client_phone(callback: CallbackQuery, state: FSMContext) -> None:
    """Telefon raqami kiritishni o'tkazib yuboradi."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    await state.update_data(client_phone="")
    await state.update_data(_products=[])
    await state.set_state(DebtCreationStates.waiting_product_name)
    await callback.message.edit_text(
        "📞 <b>Telefon:</b> <i>Kiritilmadi</i>\n\n"
        "📦 <b>4-bosqich: Tovar (mahsulot) nomini kiriting:</b>\n\n"
        "<i>Masalan: Shina, Akkumulyator, Generator</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )
    await callback.answer()


@router.message(DebtCreationStates.waiting_client_phone)
async def process_client_phone(message: Message, state: FSMContext) -> None:
    """Telefon raqamini qabul qiladi yoki o'tkazib yuborishni qayta ishlaydi."""
    phone_raw = (message.text or "").strip()

    # O'tkazib yuborish so'zlari
    skip_keywords = ("-", "yo'q", "yoq", "skip", "otkazish", "o'tkazish", "none", "0")
    if phone_raw.lower() in skip_keywords:
        clean_phone = ""
    else:
        clean_phone = normalize_phone(phone_raw)
        if not is_valid_phone(clean_phone):
            await message.answer(
                "⚠️ <b>Noto'g'ri telefon raqami!</b>\n\n"
                "Iltimos, telefon raqamini to'g'ri formatda kiriting "
                "(masalan: <code>+998901234567</code>) yoki telefon bo'lmasa "
                "<b>'O'tkazib yuborish'</b> tugmasini bosing:",
                reply_markup=get_phone_keyboard(),
            )
            return

    await state.update_data(client_phone=clean_phone)
    # Tovarlar ro'yxatini bo'sh boshlaymiz
    await state.update_data(_products=[])
    await state.set_state(DebtCreationStates.waiting_product_name)
    phone_display = clean_phone if clean_phone else "<i>Kiritilmadi</i>"
    await message.answer(
        f"📞 <b>Telefon:</b> {phone_display}\n\n"
        "📦 <b>4-bosqich: Tovar (mahsulot) nomini kiriting:</b>\n\n"
        "<i>Masalan: Shina, Akkumulyator, Generator</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )


# ==========================================
# 3. TOVAR KIRITISH SIKLI (nom → nechta → narxi → yana?)
# ==========================================


@router.message(DebtCreationStates.waiting_product_name)
async def process_product_name(message: Message, state: FSMContext) -> None:
    """Tovar nomini qabul qiladi."""
    product = (message.text or "").strip()
    if not product:
        await message.answer(
            "⚠️ Tovar nomini kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return
    if len(product) > 80:
        await message.answer(
            "⚠️ <b>Tovar nomi juda uzun!</b>\n\n"
            "Iltimos, 80 belgidan qisqa kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(product_name=product)
    await state.set_state(DebtCreationStates.waiting_product_quantity)
    await message.answer(
        f"📦 <b>Tovar:</b> {esc_html(product)}\n\n"
        "🔢 <b>5-bosqich: Tovardan nechta olindi?</b>\n\n"
        "<i>Masalan: 2 — bitta bo'lsa 1 deb yozing</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )


@router.message(DebtCreationStates.waiting_product_quantity)
async def process_product_quantity(message: Message, state: FSMContext) -> None:
    """Tovar miqdorini (nechta) qabul qiladi."""
    quantity = parse_money(message.text or "")
    if quantity is None or quantity < 1:
        await message.answer(
            "⚠️ <b>Noto'g'ri miqdor!</b>\n\n"
            "Iltimos, 1 dan katta son kiriting (masalan: <code>2</code>):",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(product_quantity=quantity)
    await state.set_state(DebtCreationStates.waiting_product_price)
    await message.answer(
        f"🔢 <b>Miqdor:</b> {quantity} ta\n\n"
        "💰 <b>6-bosqich: Bitta tovar narxini kiriting:</b>\n\n"
        "<i>Masalan: 2 500 000 — jami summa o'zi hisoblanadi</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )


@router.message(DebtCreationStates.waiting_product_price)
async def process_product_price(message: Message, state: FSMContext) -> None:
    """Tovar narxini qabul qiladi va tovarni ro'yxatga qo'shib, 'Yana tovar?' deb so'raydi."""
    price = parse_money(message.text or "")
    if price is None or price <= 0:
        await message.answer(
            "⚠️ <b>Noto'g'ri narx!</b>\n\n"
            "Iltimos, faqat musbat son kiriting (masalan: <code>2 500 000</code>):",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(product_price=price)

    # Tovar valyutasi so'raladi — har bir tovar o'z valyutasida bo'ladi
    await state.set_state(DebtCreationStates.waiting_product_currency)
    await message.answer(
        "💰 <b>Narx qabul qilindi.</b>\n\n"
        "💱 <b>Bu tovar qaysi valyutada?</b>\n\n"
        "<i>Har bir tovar o'z valyutasida bo'lishi mumkin — so'm yoki dollar</i>",
        reply_markup=get_product_currency_keyboard(),
    )


@router.callback_query(DebtCreationStates.waiting_product_currency, F.data == "prodcur_uzs")
async def cb_prodcur_uzs(callback: CallbackQuery, state: FSMContext) -> None:
    """Tovar so'mda — tovarni ro'yxatga qo'shib 'Yana tovar?' deb so'raydi."""
    await _append_product_with_currency(callback, state, Currency.UZS)


@router.callback_query(DebtCreationStates.waiting_product_currency, F.data == "prodcur_usd")
async def cb_prodcur_usd(callback: CallbackQuery, state: FSMContext) -> None:
    """Tovar dollarda — tovarni ro'yxatga qo'shib 'Yana tovar?' deb so'raydi."""
    await _append_product_with_currency(callback, state, Currency.USD)


async def _append_product_with_currency(
    callback: CallbackQuery,
    state: FSMContext,
    currency: Currency,
) -> None:
    """Valyutasi tanlangan tovarni ro'yxatga qo'shib, 'Yana tovar?' so'raydi."""
    data = await state.get_data()
    product_name: str = data.get("product_name", "")
    quantity: int = data.get("product_quantity", 1)
    price: int = data.get("product_price", 0)

    products = list(data.get("_products", []))
    products.append(DebtProduct(
        name=product_name,
        quantity=quantity,
        price_per_unit=price,
        currency=currency.value,
    ))
    await state.update_data(_products=products)

    total_this = price * quantity
    if quantity > 1:
        added_line = (
            f"✅ <b>Qo'shildi:</b> {esc_html(product_name)} — {quantity} × "
            f"{format_money(price, currency)} = {format_money(total_this, currency)}\n\n"
        )
    else:
        added_line = (
            f"✅ <b>Qo'shildi:</b> {esc_html(product_name)} — "
            f"{format_money(price, currency)}\n\n"
        )

    await state.set_state(DebtCreationStates.waiting_more_products)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            added_line + "➕ <b>Yana tovar qo'shasizmi?</b>\n\n"
            "<i>Agar bir nechta turli tovar olgan bo'lsa, yana qo'shing.</i>",
            reply_markup=get_more_products_keyboard(),
        )
    await callback.answer()


@router.callback_query(DebtCreationStates.waiting_more_products, F.data == "more_products_yes")
async def cb_more_products_yes(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Yana tovar kiritish — siklni qayta boshlaydi."""
    data = await state.get_data()
    num = _current_product_number(data) + 1
    await state.set_state(DebtCreationStates.waiting_product_name)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"📦 <b>{num}-tovar nomini kiriting:</b>\n\n"
            "<i>Masalan: Shina, Akkumulyator</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
    await callback.answer()


@router.callback_query(DebtCreationStates.waiting_more_products, F.data == "more_products_no")
async def cb_more_products_no(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Tovarlar kiritish tugadi — exchange bosqichiga o'tadi."""
    await state.set_state(DebtCreationStates.waiting_exchange_choice)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🔄 <b>Ayirboshlash (Exchange) tovari bormi?</b>\n\n"
            "<i>Mijoz berilgan tovar evaziga boshqa tovar berdimi?</i>",
            reply_markup=get_exchange_choice_keyboard(),
        )
    await callback.answer()


# ==========================================
# 4. EXCHANGE (AYIRBOSHLASH)
# ==========================================


@router.callback_query(DebtCreationStates.waiting_exchange_choice, F.data == "exchange_no")
async def cb_exchange_no(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange yo'q bo'lsa to'g'ridan-to'g'ri berilgan pul bosqichiga o'tadi."""
    await state.update_data(
        exchange_exists=False,
        exchange_product_name=None,
        exchange_product_price=0,
    )
    await state.set_state(DebtCreationStates.waiting_given_money_choice)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🔄 <b>Exchange:</b> Yo'q\n\n"
            "💵 <b>Qarzdan oldindan pul berildimi?</b>\n\n"
            "<i>Mijoz tovar olingan paytda ma'lum bir summa to'ladimi?</i>",
            reply_markup=get_given_money_choice_keyboard(),
        )
    await callback.answer()


@router.callback_query(DebtCreationStates.waiting_exchange_choice, F.data == "exchange_yes")
async def cb_exchange_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange bor — avval valyutasi so'raladi."""
    await state.update_data(exchange_exists=True)
    await state.set_state(DebtCreationStates.waiting_exchange_currency)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🔄 <b>Exchange:</b> Ha\n\n"
            "💱 <b>Ayirboshlash tovari qaysi valyutada?</b>\n\n"
            "<i>Exchange shu valyutadagi tovarlar qarzidan chegiriladi</i>",
            reply_markup=get_exchange_currency_keyboard(),
        )
    await callback.answer()


@router.callback_query(DebtCreationStates.waiting_exchange_currency, F.data == "excur_uzs")
async def cb_excur_uzs(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange so'mda — nomini so'raydi."""
    await _apply_exchange_currency(callback, state, Currency.UZS)


@router.callback_query(DebtCreationStates.waiting_exchange_currency, F.data == "excur_usd")
async def cb_excur_usd(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange dollarda — nomini so'raydi."""
    await _apply_exchange_currency(callback, state, Currency.USD)


async def _apply_exchange_currency(
    callback: CallbackQuery,
    state: FSMContext,
    currency: Currency,
) -> None:
    """Exchange valyutasini saqlab, tovar nomini so'raydi."""
    await state.update_data(exchange_currency=currency.value)
    await state.set_state(DebtCreationStates.waiting_exchange_name)

    label = "So'm 💵" if currency == Currency.UZS else "Dollar $"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"💱 <b>Exchange valyutasi:</b> {label}\n\n"
            "📦 <b>Ayirboshlash tovari nomini kiriting:</b>\n\n"
            "<i>Masalan: Eski akkumulyator, Eski shina</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
    await callback.answer()


@router.message(DebtCreationStates.waiting_exchange_name)
async def process_exchange_name(message: Message, state: FSMContext) -> None:
    """Ayirboshlash tovari nomini qabul qiladi."""
    ex_name = (message.text or "").strip()
    if not ex_name:
        await message.answer(
            "⚠️ Ayirboshlash tovari nomini kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return
    if len(ex_name) > 80:
        await message.answer(
            "⚠️ <b>Nom juda uzun!</b>\n\nIltimos, 80 belgidan qisqa kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(exchange_product_name=ex_name)
    await state.set_state(DebtCreationStates.waiting_exchange_price)
    await message.answer(
        f"📦 <b>Ayirboshlash tovari:</b> {esc_html(ex_name)}\n\n"
        "💰 <b>Ayirboshlash tovari narxini kiriting:</b>\n\n"
        "<i>Masalan: 800 000</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )


@router.message(DebtCreationStates.waiting_exchange_price)
async def process_exchange_price(message: Message, state: FSMContext) -> None:
    """Ayirboshlash tovari narxini tekshiradi (o'z valyutasidagi jami bilan)."""
    ex_price = parse_money(message.text or "")
    data = await state.get_data()
    currency = Currency(data.get("exchange_currency", Currency.UZS.value))
    products = _get_products(data)
    total_in_currency = sum(
        p.total_price for p in products if p.currency == currency.value
    )

    if ex_price is None or ex_price < 0:
        await message.answer(
            "⚠️ <b>Noto'g'ri narx!</b>\n\n"
            "Iltimos, son kiriting (masalan: <code>800 000</code>):",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    if ex_price > total_in_currency:
        await message.answer(
            f"⚠️ <b>Exchange narxi ({format_money(ex_price, currency)}) "
            f"{currency.value} valyutasidagi tovarlar jami narxidan "
            f"({format_money(total_in_currency, currency)}) "
            f"katta bo'lishi mumkin emas!</b>\n\n"
            "Iltimos, qayta kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(exchange_product_price=ex_price)
    await state.set_state(DebtCreationStates.waiting_given_money_choice)
    ex_price_str = format_money(ex_price, currency)
    await message.answer(
        f"💰 <b>Exchange narxi:</b> {ex_price_str}\n\n"
        "💵 <b>Qarzdan oldindan pul berildimi?</b>\n\n"
        "<i>Mijoz tovar olingan paytda qarzidan ma'lum summa to'ladimi?</i>",
        reply_markup=get_given_money_choice_keyboard(),
    )


# ==========================================
# 5. BERILGAN PUL VA HISOB-KITOB
# ==========================================


@router.callback_query(DebtCreationStates.waiting_given_money_choice, F.data == "given_money_no")
async def cb_given_money_no(callback: CallbackQuery, state: FSMContext) -> None:
    """Oldindan pul berilmagan holat — preview ko'rsatadi."""
    await state.update_data(given_money=0)
    await state.set_state(DebtCreationStates.waiting_confirm)

    data = await state.get_data()
    preview_text = _render_preview(data)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            preview_text,
            reply_markup=get_creation_confirm_keyboard(),
        )
    await callback.answer()


@router.callback_query(DebtCreationStates.waiting_given_money_choice, F.data == "given_money_yes")
async def cb_given_money_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """Oldindan berilgan pul — avval valyutasi so'raladi."""
    await state.set_state(DebtCreationStates.waiting_given_currency)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "💵 <b>Pul berdi</b> tanlandi.\n\n"
            "💱 <b>Berilgan pul qaysi valyutada?</b>\n\n"
            "<i>Shu valyutadagi tovarlar qarzidan chegiriladi</i>",
            reply_markup=get_given_currency_keyboard(),
        )
    await callback.answer()


@router.callback_query(DebtCreationStates.waiting_given_currency, F.data == "gcur_uzs")
async def cb_gcur_uzs(callback: CallbackQuery, state: FSMContext) -> None:
    """Berilgan pul so'mda — summani so'raydi."""
    await _apply_given_currency(callback, state, Currency.UZS)


@router.callback_query(DebtCreationStates.waiting_given_currency, F.data == "gcur_usd")
async def cb_gcur_usd(callback: CallbackQuery, state: FSMContext) -> None:
    """Berilgan pul dollarda — summani so'raydi."""
    await _apply_given_currency(callback, state, Currency.USD)


async def _apply_given_currency(
    callback: CallbackQuery,
    state: FSMContext,
    currency: Currency,
) -> None:
    """Berilgan pul valyutasini saqlab, summani so'raydi."""
    await state.update_data(given_currency=currency.value)
    await state.set_state(DebtCreationStates.waiting_given_money_amount)

    label = "So'm 💵" if currency == Currency.UZS else "Dollar $"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"💱 <b>Valyuta:</b> {label}\n\n"
            "💰 <b>Qarzdan qancha pul berildi?</b>\n\n"
            "<i>Masalan: 200 000</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
    await callback.answer()


@router.message(DebtCreationStates.waiting_given_money_amount)
async def process_given_money_amount(message: Message, state: FSMContext) -> None:
    """Berilgan pul summasini tekshiradi (o'z valyutasidagi chegaralar bilan)."""
    amount = parse_money(message.text or "")
    data = await state.get_data()
    currency = Currency(data.get("given_currency", Currency.UZS.value))
    products = _get_products(data)
    total_in_currency = sum(
        p.total_price for p in products if p.currency == currency.value
    )
    exchange_currency = Currency(data.get("exchange_currency", Currency.UZS.value))
    exchange_price: int = (
        data.get("exchange_product_price", 0)
        if data.get("exchange_exists", False) and exchange_currency == currency
        else 0
    )
    max_allowable = total_in_currency - exchange_price

    if amount is None or amount < 0:
        await message.answer(
            "⚠️ <b>Noto'g'ri summa!</b>\n\n"
            "Iltimos, son kiriting (masalan: <code>200 000</code>):",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    if amount > max_allowable:
        amount_str = format_money(amount, currency)
        allowable_str = format_money(max_allowable, currency)
        await message.answer(
            f"⚠️ <b>Berilgan pul ({amount_str}) {currency.value} valyutasidagi "
            f"tovar narxi va exchange ayirmasidan ({allowable_str}) "
            f"katta bo'lishi mumkin emas!</b>\n\n"
            "Iltimos, qayta kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(given_money=amount)
    await state.set_state(DebtCreationStates.waiting_confirm)

    full_data = await state.get_data()
    preview_text = _render_preview(full_data)

    await message.answer(
        preview_text,
        reply_markup=get_creation_confirm_keyboard(),
    )


# ==========================================
# 7. YAKUNIY TASDIQLASH VA SAQLASH
# ==========================================


@router.callback_query(DebtCreationStates.waiting_confirm, F.data == "confirm_create_debt")
async def cb_confirm_create_debt(
    callback: CallbackQuery,
    state: FSMContext,
    client_service: ClientService,
    debt_service: DebtService,
    settings: Settings,
) -> None:
    """Barcha ma'lumotlarni tekshirib, ma'lumotlar bazasiga saqlaydi."""
    data = await state.get_data()
    await state.clear()

    debt_date: str = data["debt_date"]
    client_name: str = data["client_name"]
    client_phone: str = data["client_phone"]
    products = _get_products(data)
    exchange_exists: bool = data.get("exchange_exists", False)
    exchange_product_name: str | None = data.get("exchange_product_name")
    exchange_product_price: int = data.get("exchange_product_price", 0)
    exchange_currency = Currency(data.get("exchange_currency", Currency.UZS.value))
    given_money: int = data.get("given_money", 0)
    given_currency = Currency(data.get("given_currency", Currency.UZS.value))

    try:
        client, is_new = await client_service.get_or_create(
            full_name=client_name,
            phone=client_phone,
        )

        if client.id is None:
            raise RuntimeError("Mijoz ID si aniqlanmadi.")

        saved_debts = await debt_service.create_debts(
            client_id=client.id,
            debt_date=debt_date,
            products=products,
            exchange_exists=exchange_exists,
            exchange_product_name=exchange_product_name,
            exchange_product_price=exchange_product_price,
            exchange_currency=exchange_currency,
            given_money=given_money,
            given_currency=given_currency,
        )

        # Valyutalar bo'yicha jami narxlar
        totals: dict[str, int] = {}
        for p in products:
            totals[p.currency] = totals.get(p.currency, 0) + p.total_price

        success_lines = [
            "✅ <b>QARZ MUVAFFAQIYATLI SAQLANDI!</b>\n",
            f"👤 <b>Mijoz:</b> {esc_html(client.full_name)} ({esc_html(client.phone)})",
            f"📅 <b>Sana:</b> {debt_date}",
        ]

        # Har bir tovarni o'z valyutasida ko'rsatamiz
        for p in products:
            p_cur = Currency(p.currency)
            if p.quantity > 1:
                success_lines.append(
                    f"📦 <b>{esc_html(p.name)}</b> — {p.quantity} × "
                    f"{format_money(p.price_per_unit, p_cur)} = "
                    f"{format_money(p.total_price, p_cur)}"
                )
            else:
                success_lines.append(
                    f"📦 <b>{esc_html(p.name)}</b> — {format_money(p.price_per_unit, p_cur)}"
                )

        success_lines.append(
            f"💰 <b>Jami narxi:</b> {format_money_map(totals)}"
        )

        if exchange_exists:
            success_lines.append(
                f"🔄 <b>Exchange:</b> {esc_html(exchange_product_name or '')} "
                f"({format_money(exchange_product_price, exchange_currency)})"
            )
        if given_money > 0:
            success_lines.append(
                f"💵 <b>Boshlang'ich to'lov:</b> "
                f"{format_money(given_money, given_currency)}"
            )

        remaining_map: dict[str, int] = {}
        for d in saved_debts:
            remaining_map[d.currency.value] = (
                remaining_map.get(d.currency.value, 0) + d.remaining_debt
            )
        success_lines.append(
            f"💳 <b>Hisoblangan qarz:</b> <b>{format_money_map(remaining_map)}</b>\n"
        )
        if len(saved_debts) > 1:
            success_lines.append(
                f"<i>{len(saved_debts)} ta valyutada alohida qarz yozuvlari yaratildi.</i>"
            )
        success_lines.append("<i>Ma'lumotlar 'Qarzlar jadvali' ga qo'shildi.</i>")

        if isinstance(callback.message, Message):
            await callback.message.edit_text("\n".join(success_lines))
            await callback.message.answer(
                "Asosiy menyu:",
                reply_markup=get_main_menu_keyboard(settings.web_app_url),
            )
        await callback.answer("Saqlandi!", show_alert=False)

    except Exception as exc:
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                f"❌ <b>Xatolik yuz berdi:</b> {esc_html(str(exc))}",
            )
        await callback.answer("Xatolik yuz berdi.", show_alert=True)


# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================


def _get_products(data: dict[str, Any]) -> list[DebtProduct]:
    """State dan tovarlar ro'yxatini olish."""
    raw = data.get("_products", [])
    if isinstance(raw, list):
        return [p if isinstance(p, DebtProduct) else DebtProduct(**p) for p in raw]
    return []


def _render_preview(data: dict[str, Any]) -> str:
    """Kiritilgan qarz ma'lumotlarining chiroyli preview ko'rinishi.

    Har bir tovar o'z valyutasida ko'rsatiladi; jami summalar valyutalar
    bo'yicha alohida yig'iladi.
    """
    debt_date = data.get("debt_date", "-")
    client_name = data.get("client_name", "-")
    client_phone = data.get("client_phone", "-")
    exchange_exists = data.get("exchange_exists", False)
    exchange_product_name = data.get("exchange_product_name")
    exchange_product_price: int = data.get("exchange_product_price", 0)
    exchange_currency = Currency(data.get("exchange_currency", Currency.UZS.value))
    given_money: int = data.get("given_money", 0)
    given_currency = Currency(data.get("given_currency", Currency.UZS.value))

    products = _get_products(data)

    # Valyutalar bo'yicha jami narxlar
    totals: dict[str, int] = {}
    for p in products:
        totals[p.currency] = totals.get(p.currency, 0) + p.total_price

    # Har bir valyutada chegirmalarni hisoblab, qoldiqni topamiz
    remaining: dict[str, int] = dict(totals)
    if exchange_exists and exchange_product_price > 0:
        cur = exchange_currency.value
        remaining[cur] = max(0, remaining.get(cur, 0) - exchange_product_price)
    if given_money > 0:
        cur = given_currency.value
        remaining[cur] = max(0, remaining.get(cur, 0) - given_money)

    lines = [
        "📋 <b>QARZ MA'LUMOTLARI (TASDIQLASH):</b>\n",
        f"📅 <b>Sana:</b> {debt_date}",
        f"👤 <b>Qarz oluvchi:</b> {esc_html(client_name)}",
        f"📞 <b>Telefon:</b> {esc_html(client_phone)}",
        "━━━━━━━━━━ <b>TOVARLAR:</b> ━━━━━━━━━━",
    ]

    for idx, p in enumerate(products, start=1):
        p_cur = Currency(p.currency)
        if p.quantity > 1:
            lines.append(
                f"  {idx}. 📦 <b>{esc_html(p.name)}</b> — {p.quantity} × "
                f"{format_money(p.price_per_unit, p_cur)} = "
                f"{format_money(p.total_price, p_cur)}"
            )
        else:
            lines.append(
                f"  {idx}. 📦 <b>{esc_html(p.name)}</b> — "
                f"{format_money(p.price_per_unit, p_cur)}"
            )

    lines.append(f"\n💰 <b>Tovarlar jami narxi:</b> {format_money_map(totals)}")

    if exchange_exists:
        lines.append(
            f"🔄 <b>Exchange tovar:</b> {esc_html(exchange_product_name or 'Tovar')} "
            f"({format_money(exchange_product_price, exchange_currency)})"
        )
    else:
        lines.append("🔄 <b>Exchange tovar:</b> Yo'q")

    if given_money > 0:
        lines.append(
            f"💵 <b>Berilgan pul:</b> {format_money(given_money, given_currency)}"
        )
    else:
        lines.append("💵 <b>Berilgan pul:</b> 0 (bermadi)")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"💳 <b>HISOBLANGAN QARZ:</b> "
        f"<b>{format_money_map(remaining)}</b>\n"
    )
    lines.append("<i>Ma'lumotlar to'g'ri bo'lsa, 'Tasdiqlash' tugmasini bosing:</i>")

    return "\n".join(lines)
