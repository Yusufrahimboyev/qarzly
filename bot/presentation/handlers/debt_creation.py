"""Presentation qatlami: Qarz yaratish (wizard) handler'lari."""
from __future__ import annotations

from typing import Any

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import (
    format_money,
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
from bot.presentation.keyboards.creation_kb import (
    get_back_cancel_keyboard,
    get_creation_confirm_keyboard,
    get_currency_choice_keyboard,
    get_date_picker_keyboard,
    get_exchange_choice_keyboard,
    get_given_money_choice_keyboard,
)
from bot.presentation.keyboards.main_menu_kb import get_main_menu_keyboard
from bot.presentation.states.debt_creation import DebtCreationStates

router = Router()


# ==========================================
# 0. BEKOR QILISH VA ORTGA QAYTISH
# ==========================================


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

    elif current_state == DebtCreationStates.waiting_product_name:
        await state.set_state(DebtCreationStates.waiting_client_phone)
        await callback.message.edit_text(
            "📞 <b>3-bosqich: Telefon raqamini kiriting:</b>\n\n"
            "<i>Masalan: +998901234567</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_product_quantity:
        await state.set_state(DebtCreationStates.waiting_product_name)
        await callback.message.edit_text(
            "📦 <b>4-bosqich: Tovar (mahsulot) nomini kiriting:</b>\n\n"
            "<i>Masalan: Shina, Akkumulyator</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_product_price:
        await state.set_state(DebtCreationStates.waiting_product_quantity)
        await callback.message.edit_text(
            "🔢 <b>5-bosqich: Tovardan nechta olindi?</b>\n\n"
            "<i>Masalan: 2</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_currency:
        await state.set_state(DebtCreationStates.waiting_product_price)
        await callback.message.edit_text(
            "💰 <b>6-bosqich: Bitta tovar narxini kiriting:</b>\n\n"
            "<i>Masalan: 2 500 000</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )

    elif current_state == DebtCreationStates.waiting_exchange_choice:
        await state.set_state(DebtCreationStates.waiting_currency)
        await callback.message.edit_text(
            "💱 <b>7-bosqich: Qarz qaysi valyutada?</b>\n\n"
            "<i>So'm yoki dollar tanlang</i>",
            reply_markup=get_currency_choice_keyboard(),
        )

    elif current_state == DebtCreationStates.waiting_exchange_name:
        await state.set_state(DebtCreationStates.waiting_exchange_choice)
        await callback.message.edit_text(
            "🔄 <b>8-bosqich: Ayirboshlash (Exchange) tovari bormi?</b>",
            reply_markup=get_exchange_choice_keyboard(),
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
                "💰 <b>Ayirboshlash tovari narxini kiriting (so'mda):</b>\n\n"
                "<i>Masalan: 800 000</i>",
                reply_markup=get_back_cancel_keyboard(show_back=True),
            )
        else:
            await state.set_state(DebtCreationStates.waiting_exchange_choice)
            await callback.message.edit_text(
                "🔄 <b>8-bosqich: Ayirboshlash (Exchange) tovari bormi?</b>",
                reply_markup=get_exchange_choice_keyboard(),
            )

    elif current_state == DebtCreationStates.waiting_given_money_amount:
        await state.set_state(DebtCreationStates.waiting_given_money_choice)
        await callback.message.edit_text(
            "💵 <b>9-bosqich: Qarzdan oldindan pul berildimi?</b>",
            reply_markup=get_given_money_choice_keyboard(),
        )

    elif current_state == DebtCreationStates.waiting_confirm:
        await state.set_state(DebtCreationStates.waiting_given_money_choice)
        await callback.message.edit_text(
            "💵 <b>9-bosqich: Qarzdan oldindan pul berildimi?</b>",
            reply_markup=get_given_money_choice_keyboard(),
        )

    await callback.answer()


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
    await state.set_state(DebtCreationStates.waiting_client_name)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"📅 <b>Sana:</b> {today}\n\n"
            "👤 <b>2-bosqich: Qarz oluvchining ism-familiyasini kiriting:</b>\n\n"
            "<i>Masalan: Aliyev Anvar</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
    await callback.answer()


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
            "Iltimos, sanani <b>DD.MM.YYYY</b> ko'rinishida kiriting (masalan: <code>16.08.2026</code>) "
            "yoki quyidagi 'Bugun' tugmasini bosing:",
            reply_markup=get_date_picker_keyboard(),
        )
        return

    await state.update_data(debt_date=parsed_date)
    await state.set_state(DebtCreationStates.waiting_client_name)
    await message.answer(
        f"📅 <b>Sana:</b> {parsed_date}\n\n"
        "👤 <b>2-bosqich: Qarz oluvchining ism-familiyasini kiriting:</b>\n\n"
        "<i>Masalan: Aliyev Anvar</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )


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

    await state.update_data(client_name=name)
    await state.set_state(DebtCreationStates.waiting_client_phone)
    await message.answer(
        f"👤 <b>Qarz oluvchi:</b> {name}\n\n"
        "📞 <b>3-bosqich: Telefon raqamini kiriting:</b>\n\n"
        "<i>Masalan: +998901234567 yoki 901234567</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )


@router.message(DebtCreationStates.waiting_client_phone)
async def process_client_phone(message: Message, state: FSMContext) -> None:
    """Telefon raqamini qabul qiladi."""
    phone_raw = (message.text or "").strip()
    clean_phone = normalize_phone(phone_raw)

    if not is_valid_phone(clean_phone):
        await message.answer(
            "⚠️ <b>Noto'g'ri telefon raqami!</b>\n\n"
            "Iltimos, telefon raqamini to'g'ri formatda kiriting (masalan: <code>+998901234567</code>):",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(client_phone=clean_phone)
    await state.set_state(DebtCreationStates.waiting_product_name)
    await message.answer(
        f"📞 <b>Telefon:</b> {clean_phone}\n\n"
        "📦 <b>4-bosqich: Tovar (mahsulot) nomini kiriting:</b>\n\n"
        "<i>Masalan: Shina, Akkumulyator, Generator</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )


# ==========================================
# 3. TOVAR NOMI VA NARXI
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

    await state.update_data(product_name=product)
    await state.set_state(DebtCreationStates.waiting_product_quantity)
    await message.answer(
        f"📦 <b>Tovar:</b> {product}\n\n"
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
    """Tovar narxini (bitta dona narxini) tekshiradi va qabul qiladi."""
    price = parse_money(message.text or "")
    if price is None or price <= 0:
        await message.answer(
            "⚠️ <b>Noto'g'ri narx!</b>\n\n"
            "Iltimos, faqat musbat son kiriting (masalan: <code>2 500 000</code>):",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    data = await state.get_data()
    quantity: int = data.get("product_quantity", 1)
    total_price = price * quantity

    await state.update_data(product_price=price)
    await state.set_state(DebtCreationStates.waiting_currency)
    if quantity > 1:
        price_line = (
            f"💰 <b>Tovar narxi:</b> {quantity} × {format_money(price)} = "
            f"<b>{format_money(total_price)}</b>\n\n"
        )
    else:
        price_line = f"💰 <b>Tovar narxi:</b> {format_money(price)}\n\n"
    await message.answer(
        price_line
        + "💱 <b>7-bosqich: Qarz qaysi valyutada?</b>\n\n"
        "<i>So'm yoki dollar tanlang</i>",
        reply_markup=get_currency_choice_keyboard(),
    )


@router.callback_query(DebtCreationStates.waiting_currency, F.data == "currency_uzs")
async def cb_currency_uzs(callback: CallbackQuery, state: FSMContext) -> None:
    """So'm valyutasi tanlandi."""
    await _apply_currency(callback, state, Currency.UZS)


@router.callback_query(DebtCreationStates.waiting_currency, F.data == "currency_usd")
async def cb_currency_usd(callback: CallbackQuery, state: FSMContext) -> None:
    """Dollar valyutasi tanlandi."""
    await _apply_currency(callback, state, Currency.USD)


async def _apply_currency(callback: CallbackQuery, state: FSMContext, currency: Currency) -> None:
    """Valyutani saqlab, exchange bosqichiga o'tadi."""
    await state.update_data(currency=currency.value)
    await state.set_state(DebtCreationStates.waiting_exchange_choice)

    label = "So'm 💵" if currency == Currency.UZS else "Dollar $"
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"💱 <b>Valyuta:</b> {label}\n\n"
            "🔄 <b>8-bosqich: Ayirboshlash (Exchange) tovari bormi?</b>\n\n"
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
            "💵 <b>9-bosqich: Qarzdan oldindan pul berildimi?</b>\n\n"
            "<i>Mijoz tovar olingan paytda ma'lum bir summa to'ladimi?</i>",
            reply_markup=get_given_money_choice_keyboard(),
        )
    await callback.answer()


@router.callback_query(DebtCreationStates.waiting_exchange_choice, F.data == "exchange_yes")
async def cb_exchange_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange bor bo'lsa tovar nomini so'raydi."""
    await state.update_data(exchange_exists=True)
    await state.set_state(DebtCreationStates.waiting_exchange_name)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🔄 <b>Exchange:</b> Ha\n\n"
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

    await state.update_data(exchange_product_name=ex_name)
    await state.set_state(DebtCreationStates.waiting_exchange_price)
    await message.answer(
        f"📦 <b>Ayirboshlash tovari:</b> {ex_name}\n\n"
        "💰 <b>Ayirboshlash tovari narxini kiriting (so'mda):</b>\n\n"
        "<i>Masalan: 800 000</i>",
        reply_markup=get_back_cancel_keyboard(show_back=True),
    )


@router.message(DebtCreationStates.waiting_exchange_price)
async def process_exchange_price(message: Message, state: FSMContext) -> None:
    """Ayirboshlash tovari narxini tekshiradi."""
    ex_price = parse_money(message.text or "")
    data = await state.get_data()
    product_price: int = data.get("product_price", 0)
    quantity: int = data.get("product_quantity", 1)
    currency = Currency(data.get("currency", Currency.UZS.value))
    total_price = product_price * quantity

    if ex_price is None or ex_price < 0:
        await message.answer(
            "⚠️ <b>Noto'g'ri narx!</b>\n\n"
            "Iltimos, son kiriting (masalan: <code>800 000</code>):",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    if ex_price > total_price:
        await message.answer(
            f"⚠️ <b>Exchange narxi ({format_money(ex_price, currency)}) tovarlar jami narxidan "
            f"({format_money(total_price, currency)}) katta bo'lishi mumkin emas!</b>\n\n"
            "Iltimos, qayta kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(exchange_product_price=ex_price)
    await state.set_state(DebtCreationStates.waiting_given_money_choice)
    ex_price_str = format_money(ex_price, currency)
    await message.answer(
        f"💰 <b>Exchange narxi:</b> {ex_price_str}\n\n"
        "💵 <b>9-bosqich: Qarzdan oldindan pul berildimi?</b>\n\n"
        "<i>Mijoz tovar olingan paytda qarzidan ma'lum summa to'ladimi?</i>",
        reply_markup=get_given_money_choice_keyboard(),
    )


# ==========================================
# 5. BERILGAN PUL VA HISOB-KITOB
# ==========================================


@router.callback_query(DebtCreationStates.waiting_given_money_choice, F.data == "given_money_no")
async def cb_given_money_no(callback: CallbackQuery, state: FSMContext) -> None:
    """Oldindan pul berilmagan holat."""
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
    """Oldindan berilgan pul summasini so'raydi."""
    await state.set_state(DebtCreationStates.waiting_given_money_amount)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "💵 <b>Pul berdi</b> tanlandi.\n\n"
            "💰 <b>Qarzdan qancha pul berildi (so'mda)?</b>\n\n"
            "<i>Masalan: 200 000</i>",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
    await callback.answer()


@router.message(DebtCreationStates.waiting_given_money_amount)
async def process_given_money_amount(message: Message, state: FSMContext) -> None:
    """Berilgan pul summasini tekshiradi."""
    amount = parse_money(message.text or "")
    data = await state.get_data()
    product_price: int = data.get("product_price", 0)
    quantity: int = data.get("product_quantity", 1)
    currency = Currency(data.get("currency", Currency.UZS.value))
    exchange_price: int = data.get("exchange_product_price", 0)
    max_allowable = product_price * quantity - exchange_price

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
            f"⚠️ <b>Berilgan pul ({amount_str}) tovar narxi va exchange ayirmasidan "
            f"({allowable_str}) katta bo'lishi mumkin emas!</b>\n\n"
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
# 6. YAKUNIY TASDIQLASH VA SAQLASH
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
    product_name: str = data["product_name"]
    product_price: int = data["product_price"]
    product_quantity: int = data.get("product_quantity", 1)
    currency = Currency(data.get("currency", Currency.UZS.value))
    exchange_exists: bool = data.get("exchange_exists", False)
    exchange_product_name: str | None = data.get("exchange_product_name")
    exchange_product_price: int = data.get("exchange_product_price", 0)
    given_money: int = data.get("given_money", 0)

    try:
        # 1. Mijozni olish yoki yaratish
        client, is_new = await client_service.get_or_create(
            full_name=client_name,
            phone=client_phone,
        )

        if client.id is None:
            raise RuntimeError("Mijoz ID si aniqlanmadi.")

        # 2. Qarz yozuvini yaratish
        saved_debt = await debt_service.create_debt(
            client_id=client.id,
            debt_date=debt_date,
            product_name=product_name,
            product_price=product_price,
            product_quantity=product_quantity,
            currency=currency,
            exchange_exists=exchange_exists,
            exchange_product_name=exchange_product_name,
            exchange_product_price=exchange_product_price,
            given_money=given_money,
        )

        success_text = (
            "✅ <b>QARZ MUVAFFAQIYATLI SAQLANDI!</b>\n\n"
            f"👤 <b>Mijoz:</b> {client.full_name} ({client.phone})\n"
            f"📅 <b>Sana:</b> {debt_date}\n"
            f"📦 <b>Tovar:</b> {product_name} — {product_quantity} ta\n"
            f"💰 <b>Jami narxi:</b> {format_money(saved_debt.product_price, currency)}\n"
        )
        if exchange_exists:
            success_text += (
                f"🔄 <b>Exchange:</b> {exchange_product_name} "
                f"({format_money(exchange_product_price, currency)})\n"
            )
        if given_money > 0:
            success_text += (
                f"💵 <b>Boshlang'ich to'lov:</b> {format_money(given_money, currency)}\n"
            )

        final_debt_str = format_money(saved_debt.remaining_debt, currency)
        success_text += (
            f"💳 <b>Hisoblangan qarz:</b> <b>{final_debt_str}</b>\n\n"
            "<i>Ma'lumotlar 'Qarzlar jadvali' ga qo'shildi.</i>"
        )

        if isinstance(callback.message, Message):
            await callback.message.edit_text(success_text)
            await callback.message.answer(
                "Asosiy menyu:",
                reply_markup=get_main_menu_keyboard(settings.web_app_url),
            )
        await callback.answer("Saqlandi!", show_alert=False)

    except Exception as exc:
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                f"❌ <b>Xatolik yuz berdi:</b> {exc}",
            )
        await callback.answer("Xatolik yuz berdi.", show_alert=True)


def _render_preview(data: dict[str, Any]) -> str:
    """Kiritilgan qarz ma'lumotlarining chiroyli preview ko'rinishi."""
    debt_date = data.get("debt_date", "-")
    client_name = data.get("client_name", "-")
    client_phone = data.get("client_phone", "-")
    product_name = data.get("product_name", "-")
    product_price: int = data.get("product_price", 0)
    quantity: int = data.get("product_quantity", 1)
    currency = Currency(data.get("currency", Currency.UZS.value))
    exchange_exists = data.get("exchange_exists", False)
    exchange_product_name = data.get("exchange_product_name")
    exchange_product_price: int = data.get("exchange_product_price", 0)
    given_money: int = data.get("given_money", 0)

    total_price = product_price * quantity
    calculated_debt = total_price - exchange_product_price - given_money

    currency_label = "So'm" if currency == Currency.UZS else "Dollar"

    lines = [
        "📋 <b>QARZ MA'LUMOTLARI (TASDIQLASH):</b>\n",
        f"📅 <b>Sana:</b> {debt_date}",
        f"👤 <b>Qarz oluvchi:</b> {client_name}",
        f"📞 <b>Telefon:</b> {client_phone}",
        f"📦 <b>Tovar:</b> {product_name} — {quantity} ta",
        f"💰 <b>Tovarlar narxi:</b> {quantity} × {format_money(product_price, currency)} = "
        f"{format_money(total_price, currency)}",
        f"💱 <b>Valyuta:</b> {currency_label}",
    ]

    if exchange_exists:
        lines.append(
            f"🔄 <b>Exchange tovar:</b> {exchange_product_name or 'Tovar'} "
            f"({format_money(exchange_product_price, currency)})"
        )
    else:
        lines.append("🔄 <b>Exchange tovar:</b> Yo'q")

    if given_money > 0:
        lines.append(f"💵 <b>Berilgan pul:</b> {format_money(given_money, currency)}")
    else:
        lines.append("💵 <b>Berilgan pul:</b> 0 (bermadi)")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        f"💳 <b>HISOBLANGAN QARZ:</b> <b>{format_money(calculated_debt, currency)}</b>\n"
    )
    lines.append("<i>Ma'lumotlar to'g'ri bo'lsa, 'Tasdiqlash' tugmasini bosing:</i>")

    return "\n".join(lines)
