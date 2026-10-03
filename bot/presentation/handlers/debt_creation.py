"""Presentation qatlami: Qarz yaratish (wizard) handler'lari.

Bir qarzda bir nechta tovar bo'lishi mumkin. Tovar kiritish sikli:
    tur → brend → razmer → soni → valyuta → narxi → yig'ma xabar
    (yana tovar / tahrirlash / tasdiqlash)
Keyin: exchange → berilgan pul → tasdiqlash.
"""
from __future__ import annotations

from datetime import date
from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

from bot.application.common.formatters import (
    esc_html,
    format_date,
    format_money,
    format_money_map,
    is_valid_phone,
    normalize_phone,
    parse_date_input,
    parse_money,
    today,
    today_str,
)
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.domain.entities.currency import Currency
from bot.domain.entities.debt import MAX_MONEY, MAX_QUANTITY, DebtProduct
from bot.infrastructure.branches import Branch
from bot.presentation.common.product_catalog import (
    BRANDS,
    PRODUCT_TYPES,
    build_product_name,
)
from bot.presentation.keyboards.creation_kb import (
    get_akkum_size_keyboard,
    get_back_cancel_keyboard,
    get_brand_keyboard,
    get_creation_confirm_keyboard,
    get_date_picker_keyboard,
    get_edit_product_actions_keyboard,
    get_edit_products_keyboard,
    get_exchange_choice_keyboard,
    get_exchange_currency_keyboard,
    get_given_currency_keyboard,
    get_given_money_choice_keyboard,
    get_month_keyboard,
    get_more_products_keyboard,
    get_numpad_keyboard,
    get_phone_keyboard,
    get_product_currency_keyboard,
    get_product_type_keyboard,
    get_year_keyboard,
)
from bot.presentation.keyboards.main_menu_kb import get_main_menu_keyboard
from bot.presentation.states.debt_creation import DebtCreationStates

router = Router()

S = DebtCreationStates
Prompt = tuple[str, InlineKeyboardMarkup]


# ==========================================
# BOSQICH XABARLARI (oldinga va ortga bir xil matn)
# ==========================================


def _date_prompt(data: dict[str, Any]) -> Prompt:
    header = (
        f"🏢 <b>Filial:</b> {esc_html(data['branch_title'])}\n\n"
        if data.get("branch_title")
        else ""
    )
    return (
        header + "📅 <b>Qarzga olingan kunni tanlang:</b>\n\n"
        "<i>Keyin oy va yil so'raladi. Bugun bo'lsa 'Bugun' tugmasini bosing</i>",
        get_date_picker_keyboard(),
    )


def _month_prompt(data: dict[str, Any]) -> Prompt:
    return (
        f"📅 <b>Kun:</b> {data['_date_day']}\n\n🗓 <b>Oyni tanlang:</b>",
        get_month_keyboard(),
    )


def _year_prompt(data: dict[str, Any]) -> Prompt:
    year = today().year
    return (
        f"📅 <b>Sana:</b> {data['_date_day']:02d}.{data['_date_month']:02d}\n\n"
        "🗓 <b>Yilni tanlang:</b>",
        get_year_keyboard([year, year + 1]),
    )


def _name_prompt(_data: dict[str, Any]) -> Prompt:
    return (
        "👤 <b>Qarz oluvchining ismini kiriting:</b>\n\n"
        "<i>Masalan: Aliyev Anvar</i>",
        get_back_cancel_keyboard(show_back=True),
    )


def _phone_prompt(_data: dict[str, Any]) -> Prompt:
    return (
        "📞 <b>Telefon raqamini kiriting:</b>\n\n"
        "<i>Masalan: +998901234567 yoki telefon bo'lmasa 'O'tkazib yuborish' tugmasini bosing:</i>",
        get_phone_keyboard(),
    )


def _type_prompt(data: dict[str, Any]) -> Prompt:
    num = len(data.get("_products", [])) + 1
    title = "Tovar turini tanlang" if num == 1 else f"{num}-tovar turini tanlang"
    return f"📦 <b>{title}:</b>", get_product_type_keyboard()


def _brand_prompt(data: dict[str, Any]) -> Prompt:
    type_key = data["product_type"]
    header = f"📦 <b>Tovar:</b> {PRODUCT_TYPES[type_key]}\n\n"
    if data.get("_brand_manual"):
        return (
            header + "✍️ <b>Brend nomini yozing:</b>",
            get_back_cancel_keyboard(show_back=True),
        )
    return header + "🏷 <b>Brendini tanlang:</b>", get_brand_keyboard(BRANDS[type_key])


def _size_prompt(data: dict[str, Any]) -> Prompt:
    type_key = data["product_type"]
    header = (
        f"📦 <b>Tovar:</b> {PRODUCT_TYPES[type_key]} "
        f"{esc_html(data['product_brand'])}\n\n"
    )
    if type_key == "akkum":
        return header + "🔋 <b>Razmerini tanlang:</b>", get_akkum_size_keyboard()
    example = "R16 malibu" if type_key == "diska" else "R16"
    return (
        header + f"📏 <b>Razmerini kiriting:</b>\n\n<i>Masalan: {example}</i>",
        get_back_cancel_keyboard(show_back=True),
    )


def _quantity_prompt(data: dict[str, Any]) -> Prompt:
    value = data.get("_np") or "—"
    return (
        f"📦 <b>Tovar:</b> {esc_html(data['product_name'])}\n\n"
        "🔢 <b>Tovar sonini kiriting:</b>\n\n"
        f"Kiritildi: <b>{value}</b>",
        get_numpad_keyboard(),
    )


def _currency_prompt(data: dict[str, Any]) -> Prompt:
    return (
        f"📦 <b>Tovar:</b> {esc_html(data['product_name'])} — "
        f"{data['product_quantity']} ta\n\n"
        "💱 <b>Valyutani tanlang:</b>",
        get_product_currency_keyboard(),
    )


def _price_prompt(data: dict[str, Any]) -> Prompt:
    currency = Currency(data["product_currency"])
    raw = data.get("_np")
    value = format_money(int(raw), currency) if raw else "—"
    return (
        f"📦 <b>Tovar:</b> {esc_html(data['product_name'])} — "
        f"{data['product_quantity']} ta\n\n"
        "💰 <b>1 dona tovar narxini kiriting:</b>\n\n"
        f"Kiritildi: <b>{value}</b>",
        get_numpad_keyboard(with_thousands=True),
    )


def _product_line(p: DebtProduct) -> str:
    if p.quantity > 1:
        return (
            f"📦 <b>{esc_html(p.name)}</b> — {p.quantity} × "
            f"{format_money(p.price_per_unit, p.currency)} = "
            f"{format_money(p.total_price, p.currency)}"
        )
    return f"📦 <b>{esc_html(p.name)}</b> — {format_money(p.price_per_unit, p.currency)}"


def _summary_prompt(data: dict[str, Any]) -> Prompt:
    """Shu paytgacha kiritilgan barcha ma'lumotlar bitta xabarda."""
    products = _get_products(data)
    totals: dict[str, int] = {}
    for p in products:
        totals[p.currency.value] = totals.get(p.currency.value, 0) + p.total_price

    lines = []
    if data.get("branch_title"):
        lines.append(f"🏢 <b>Filial:</b> {esc_html(data['branch_title'])}")
    lines.append(f"👤 <b>Qarz oluvchi:</b> {esc_html(data.get('client_name', '-'))}")
    if data.get("client_phone"):
        lines.append(f"📞 <b>Telefon:</b> {esc_html(data['client_phone'])}")
    lines.append(f"📅 <b>Sana:</b> {data.get('debt_date', '-')}")
    lines.append("━━━━━━━━ <b>TOVARLAR:</b> ━━━━━━━━")
    lines.extend(f"{i}. {_product_line(p)}" for i, p in enumerate(products, start=1))
    lines.append(f"\n💰 <b>Jami:</b> {format_money_map(totals)}")
    return "\n".join(lines), get_more_products_keyboard()


_PROMPTS = {
    S.waiting_date.state: _date_prompt,
    S.waiting_date_month.state: _month_prompt,
    S.waiting_date_year.state: _year_prompt,
    S.waiting_client_name.state: _name_prompt,
    S.waiting_client_phone.state: _phone_prompt,
    S.waiting_product_type.state: _type_prompt,
    S.waiting_product_brand.state: _brand_prompt,
    S.waiting_product_size.state: _size_prompt,
    S.waiting_product_quantity.state: _quantity_prompt,
    S.waiting_product_currency.state: _currency_prompt,
    S.waiting_product_price.state: _price_prompt,
    S.waiting_more_products.state: _summary_prompt,
}


def _previous_state(current: str | None, data: dict[str, Any]) -> str | None:
    """Tovar kiritishgacha bo'lgan bosqichlar uchun 'Ortga' manzili."""
    if current == S.waiting_product_type.state:
        if data.get("_products"):
            return S.waiting_more_products.state
        if data.get("_existing_client"):
            return S.waiting_date.state
        return S.waiting_client_phone.state
    return {
        S.waiting_date_month.state: S.waiting_date.state,
        S.waiting_date_year.state: S.waiting_date_month.state,
        S.waiting_client_name.state: S.waiting_date.state,
        S.waiting_client_phone.state: S.waiting_client_name.state,
        S.waiting_product_brand.state: S.waiting_product_type.state,
        S.waiting_product_size.state: S.waiting_product_brand.state,
        S.waiting_product_quantity.state: S.waiting_product_size.state,
        S.waiting_product_currency.state: S.waiting_product_quantity.state,
        S.waiting_product_price.state: S.waiting_product_currency.state,
        S.waiting_exchange_choice.state: S.waiting_more_products.state,
    }.get(current or "")


# ==========================================
# 0. BEKOR QILISH VA ORTGA QAYTISH
# ==========================================


@router.callback_query(F.data.startswith("add_debt_for_client:"))
async def cb_add_debt_for_client(
    callback: CallbackQuery,
    state: FSMContext,
    client_service: ClientService,
    branch: Branch,
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
        branch_title=branch.title,
        client_name=client.full_name,
        client_phone=client.phone,
        _existing_client=True,
    )
    await state.set_state(S.waiting_date)

    await callback.message.edit_text(
        "📝 <b>YANGI QARZ YARATISH</b>\n\n"
        f"👤 <b>Mijoz:</b> {client.full_name}\n"
        f"📞 <b>Telefon:</b> {client.phone}\n\n"
        "📅 <b>Qarzga olingan kunni tanlang:</b>\n\n"
        "<i>Keyin oy va yil so'raladi. Bugun bo'lsa 'Bugun' tugmasini bosing</i>",
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

    if current_state == S.waiting_product_brand.state and data.get("_brand_manual"):
        # Qo'lda yozishdan brend tugmalariga qaytish
        await state.update_data(_brand_manual=False)
        data["_brand_manual"] = False
        text, markup = _brand_prompt(data)
        await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()
        return

    previous = _previous_state(current_state, data)
    if previous is not None:
        if previous in (S.waiting_product_quantity.state, S.waiting_product_price.state):
            await state.update_data(_np="")
            data["_np"] = ""
        await state.set_state(previous)
        text, markup = _PROMPTS[previous](data)
        await callback.message.edit_text(text, reply_markup=markup)

    elif current_state == S.waiting_exchange_currency:
        await state.set_state(S.waiting_exchange_choice)
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


# ==========================================
# 1. BOSHLASH: SANA (kun → oy → yil)
# ==========================================


@router.message(F.text == "➕ Yaratish")
async def start_debt_creation(
    message: Message, state: FSMContext, branch: Branch
) -> None:
    """Qarz yaratish jarayonini boshlaydi."""
    await state.clear()
    await state.update_data(branch_title=branch.title)
    await state.set_state(S.waiting_date)
    text, markup = _date_prompt({"branch_title": branch.title})
    await message.answer(text, reply_markup=markup)


@router.callback_query(S.waiting_date, F.data == "create_date_today")
async def cb_date_today(callback: CallbackQuery, state: FSMContext) -> None:
    """Bugungi sanani qabul qiladi."""
    today_value = today_str()
    await state.update_data(debt_date=today_value)

    if isinstance(callback.message, Message):
        await _proceed_after_date(callback.message, state, today_value)
    await callback.answer()


@router.callback_query(S.waiting_date, F.data.startswith("dday:"))
async def cb_date_day(callback: CallbackQuery, state: FSMContext) -> None:
    """Kun tanlandi — oyni so'raydi."""
    await state.update_data(_date_day=int((callback.data or "").split(":", 1)[1]))
    await state.set_state(S.waiting_date_month)
    if isinstance(callback.message, Message):
        text, markup = _month_prompt(await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(S.waiting_date_month, F.data.startswith("dmon:"))
async def cb_date_month(callback: CallbackQuery, state: FSMContext) -> None:
    """Oy tanlandi — yilni so'raydi."""
    await state.update_data(_date_month=int((callback.data or "").split(":", 1)[1]))
    await state.set_state(S.waiting_date_year)
    if isinstance(callback.message, Message):
        text, markup = _year_prompt(await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(S.waiting_date_year, F.data.startswith("dyear:"))
async def cb_date_year(callback: CallbackQuery, state: FSMContext) -> None:
    """Yil tanlandi — sanani tekshirib, keyingi bosqichga o'tadi."""
    data = await state.get_data()
    year = int((callback.data or "").split(":", 1)[1])
    try:
        chosen = date(year, data["_date_month"], data["_date_day"])
    except ValueError:
        # Masalan 31.02 — bunday sana yo'q, kunni qayta tanlatamiz
        await state.set_state(S.waiting_date)
        if isinstance(callback.message, Message):
            text, markup = _date_prompt(data)
            await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer("⚠️ Bunday sana yo'q. Kunni qayta tanlang.", show_alert=True)
        return

    debt_date = format_date(chosen)
    await state.update_data(debt_date=debt_date)
    if isinstance(callback.message, Message):
        await _proceed_after_date(callback.message, state, debt_date)
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
        await _start_product(state)
        text, markup = _type_prompt({})
        await message.answer(
            f"📅 <b>Sana:</b> {date_str}\n"
            f"👤 <b>Mijoz:</b> {esc_html(client_name)} ({esc_html(client_phone)})\n\n"
            + text,
            reply_markup=markup,
        )
    else:
        await state.set_state(S.waiting_client_name)
        text, markup = _name_prompt(data)
        await message.answer(f"📅 <b>Sana:</b> {date_str}\n\n" + text, reply_markup=markup)


@router.message(S.waiting_date)
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
            "yoki quyidagi tugmalardan tanlang:",
            reply_markup=get_date_picker_keyboard(),
        )
        return

    await state.update_data(debt_date=parsed_date)
    await _proceed_after_date(message, state, parsed_date)


# ==========================================
# 2. QARZ OLUVCHI: ISM VA TELEFON
# ==========================================


@router.message(S.waiting_client_name)
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
    await state.set_state(S.waiting_client_phone)
    text, markup = _phone_prompt({})
    await message.answer(
        f"👤 <b>Qarz oluvchi:</b> {esc_html(name)}\n\n" + text,
        reply_markup=markup,
    )


@router.callback_query(F.data == "skip_client_phone")
async def cb_skip_client_phone(callback: CallbackQuery, state: FSMContext) -> None:
    """Telefon raqami kiritishni o'tkazib yuboradi."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    await state.update_data(client_phone="", _products=[])
    await _start_product(state)
    text, markup = _type_prompt({})
    await callback.message.edit_text(
        "📞 <b>Telefon:</b> <i>Kiritilmadi</i>\n\n" + text,
        reply_markup=markup,
    )
    await callback.answer()


@router.message(S.waiting_client_phone)
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

    # Tovarlar ro'yxatini bo'sh boshlaymiz
    await state.update_data(client_phone=clean_phone, _products=[])
    await _start_product(state)
    phone_display = clean_phone if clean_phone else "<i>Kiritilmadi</i>"
    text, markup = _type_prompt({})
    await message.answer(
        f"📞 <b>Telefon:</b> {phone_display}\n\n" + text,
        reply_markup=markup,
    )


# ==========================================
# 3. TOVAR KIRITISH SIKLI
#    tur → brend → razmer → soni → valyuta → narxi → yig'ma xabar
# ==========================================


async def _start_product(state: FSMContext) -> None:
    """Yangi tovar kiritishni boshlaydi (oldingi tovar maydonlarini tozalaydi)."""
    await state.update_data(
        product_type=None,
        product_brand=None,
        product_name=None,
        product_price=None,
        _brand_manual=False,
        _replace_index=None,
    )
    await state.set_state(S.waiting_product_type)


@router.callback_query(S.waiting_product_type, F.data.startswith("ptype:"))
async def cb_product_type(callback: CallbackQuery, state: FSMContext) -> None:
    """Tovar turi tanlandi — brendni so'raydi."""
    type_key = (callback.data or "").split(":", 1)[1]
    if type_key not in PRODUCT_TYPES:
        await callback.answer()
        return
    await state.update_data(product_type=type_key, _brand_manual=False)
    await state.set_state(S.waiting_product_brand)
    if isinstance(callback.message, Message):
        text, markup = _brand_prompt(await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(S.waiting_product_brand, F.data.startswith("pbrand:"))
async def cb_product_brand(callback: CallbackQuery, state: FSMContext) -> None:
    """Brend tanlandi (yoki 'Boshqa' — qo'lda yozish so'raladi)."""
    choice = (callback.data or "").split(":", 1)[1]
    data = await state.get_data()
    brands = BRANDS[data["product_type"]]

    if choice == "other":
        await state.update_data(_brand_manual=True)
        data["_brand_manual"] = True
        if isinstance(callback.message, Message):
            text, markup = _brand_prompt(data)
            await callback.message.edit_text(text, reply_markup=markup)
        await callback.answer()
        return

    if not choice.isdigit() or int(choice) >= len(brands):
        await callback.answer()
        return

    await state.update_data(product_brand=brands[int(choice)])
    await state.set_state(S.waiting_product_size)
    if isinstance(callback.message, Message):
        text, markup = _size_prompt(await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.message(S.waiting_product_brand)
async def process_product_brand(message: Message, state: FSMContext) -> None:
    """Qo'lda yozilgan brend nomini qabul qiladi."""
    brand = (message.text or "").strip()
    if not brand or len(brand) > 30:
        await message.answer(
            "⚠️ Brend nomini 30 belgigacha kiriting:",
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(product_brand=brand, _brand_manual=False)
    await state.set_state(S.waiting_product_size)
    text, markup = _size_prompt(await state.get_data())
    await message.answer(text, reply_markup=markup)


@router.callback_query(S.waiting_product_size, F.data.startswith("psize:"))
async def cb_akkum_size(callback: CallbackQuery, state: FSMContext) -> None:
    """Akkumulyator razmeri tugma orqali tanlandi."""
    size = f"{(callback.data or '').split(':', 1)[1]}Ah"
    text, markup = await _accept_size(state, size)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.message(S.waiting_product_size)
async def process_product_size(message: Message, state: FSMContext) -> None:
    """Shina/diska razmerini qo'lda qabul qiladi."""
    data = await state.get_data()
    size = (message.text or "").strip()
    if data.get("product_type") == "akkum" or not size or len(size) > 30:
        text, markup = _size_prompt(data)
        await message.answer("⚠️ " + text, reply_markup=markup)
        return

    text, markup = await _accept_size(state, size)
    await message.answer(text, reply_markup=markup)


async def _accept_size(state: FSMContext, size: str) -> Prompt:
    """Razmerdan keyin tovar nomini yig'ib, sonini so'raydi."""
    data = await state.get_data()
    name = build_product_name(data["product_type"], data["product_brand"], size)
    await state.update_data(product_name=name, _np="")
    await state.set_state(S.waiting_product_quantity)
    return _quantity_prompt(await state.get_data())


@router.callback_query(
    StateFilter(S.waiting_product_quantity, S.waiting_product_price),
    F.data.startswith("np:"),
)
async def cb_numpad(callback: CallbackQuery, state: FSMContext) -> None:
    """Raqam klaviaturasi: raqam qo'shish, o'chirish, tozalash, tayyor."""
    key = (callback.data or "").split(":", 1)[1]
    current_state = await state.get_state()
    data = await state.get_data()
    value: str = data.get("_np", "")

    if key == "ok":
        amount = int(value) if value else 0
        if current_state == S.waiting_product_quantity.state:
            prompt = await _accept_quantity(state, amount)
        else:
            prompt = await _accept_price(state, amount)
        if prompt is None:
            await callback.answer("⚠️ Noto'g'ri qiymat. Musbat son kiriting.", show_alert=True)
            return
        if isinstance(callback.message, Message):
            await callback.message.edit_text(prompt[0], reply_markup=prompt[1])
        await callback.answer()
        return

    if key == "del":
        new_value = value[:-1]
    elif key == "clr":
        new_value = ""
    else:
        new_value = (value + key).lstrip("0")
    if len(new_value) > 15:
        new_value = value

    if new_value != value:
        await state.update_data(_np=new_value)
        data["_np"] = new_value
        if isinstance(callback.message, Message) and current_state is not None:
            text, markup = _PROMPTS[current_state](data)
            await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def _accept_quantity(state: FSMContext, quantity: int) -> Prompt | None:
    """Tovar sonini saqlab, valyutani so'raydi. Noto'g'ri bo'lsa None."""
    if not 1 <= quantity <= MAX_QUANTITY:
        return None
    await state.update_data(product_quantity=quantity)
    await state.set_state(S.waiting_product_currency)
    return _currency_prompt(await state.get_data())


async def _accept_price(state: FSMContext, price: int) -> Prompt | None:
    """Narxni saqlab, tovarni ro'yxatga qo'shadi. Noto'g'ri bo'lsa None."""
    if not 0 < price <= MAX_MONEY:
        return None
    await state.update_data(product_price=price)
    data = await state.get_data()
    return await _append_product(state, Currency(data["product_currency"]))


@router.message(S.waiting_product_quantity)
async def process_product_quantity(message: Message, state: FSMContext) -> None:
    """Tovar sonini matn sifatida qabul qiladi."""
    prompt = await _accept_quantity(state, parse_money(message.text or "") or 0)
    if prompt is None:
        text, markup = _quantity_prompt(await state.get_data())
        await message.answer("⚠️ <b>Noto'g'ri miqdor!</b>\n\n" + text, reply_markup=markup)
        return
    await message.answer(prompt[0], reply_markup=prompt[1])


@router.message(S.waiting_product_price)
async def process_product_price(message: Message, state: FSMContext) -> None:
    """Tovar narxini matn sifatida qabul qiladi."""
    prompt = await _accept_price(state, parse_money(message.text or "") or 0)
    if prompt is None:
        text, markup = _price_prompt(await state.get_data())
        await message.answer("⚠️ <b>Noto'g'ri narx!</b>\n\n" + text, reply_markup=markup)
        return
    await message.answer(prompt[0], reply_markup=prompt[1])


@router.callback_query(S.waiting_product_currency, F.data == "prodcur_uzs")
async def cb_prodcur_uzs(callback: CallbackQuery, state: FSMContext) -> None:
    """Tovar so'mda."""
    await _choose_product_currency(callback, state, Currency.UZS)


@router.callback_query(S.waiting_product_currency, F.data == "prodcur_usd")
async def cb_prodcur_usd(callback: CallbackQuery, state: FSMContext) -> None:
    """Tovar dollarda."""
    await _choose_product_currency(callback, state, Currency.USD)


async def _choose_product_currency(
    callback: CallbackQuery,
    state: FSMContext,
    currency: Currency,
) -> None:
    """Valyuta tanlandi — narxni so'raydi.

    Ovozli xabardan kelgan qoralamada narx allaqachon ma'lum — tovar
    to'g'ridan-to'g'ri ro'yxatga qo'shiladi.
    """
    data = await state.get_data()
    if data.get("product_price"):
        text, markup = await _append_product(state, currency)
    else:
        await state.update_data(product_currency=currency.value, _np="")
        await state.set_state(S.waiting_product_price)
        text, markup = _price_prompt(await state.get_data())

    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def _append_product(state: FSMContext, currency: Currency) -> Prompt:
    """Tovarni ro'yxatga qo'shadi (tahrirlashda — o'z o'rniga) va yig'ma xabarni qaytaradi."""
    data = await state.get_data()
    product = DebtProduct(
        name=data.get("product_name", ""),
        quantity=data.get("product_quantity", 1),
        price_per_unit=data.get("product_price", 0),
        currency=currency,
    )
    products = list(data.get("_products", []))
    replace_index = data.get("_replace_index")
    if replace_index is not None and 0 <= replace_index < len(products):
        products[replace_index] = product
    else:
        products.append(product)

    await state.update_data(_products=products, _replace_index=None)
    await state.set_state(S.waiting_more_products)
    return _summary_prompt(await state.get_data())


@router.callback_query(S.waiting_more_products, F.data == "more_products_yes")
async def cb_more_products_yes(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Yana tovar kiritish — siklni qayta boshlaydi."""
    await _start_product(state)

    if isinstance(callback.message, Message):
        text, markup = _type_prompt(await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(S.waiting_more_products, F.data == "more_products_no")
async def cb_more_products_no(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Tovarlar tasdiqlandi — exchange bosqichiga o'tadi."""
    await state.set_state(S.waiting_exchange_choice)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "🔄 <b>Ayirboshlash (Exchange) tovari bormi?</b>\n\n"
            "<i>Mijoz berilgan tovar evaziga boshqa tovar berdimi?</i>",
            reply_markup=get_exchange_choice_keyboard(),
        )
    await callback.answer()


# ==========================================
# 3.1. TOVARLARNI TAHRIRLASH
# ==========================================


@router.callback_query(S.waiting_more_products, F.data == "edit_products")
async def cb_edit_products(callback: CallbackQuery, state: FSMContext) -> None:
    """Tahrirlash uchun tovarlar ro'yxatini ko'rsatadi."""
    products = _get_products(await state.get_data())
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            "✏️ <b>Qaysi tovarni tahrirlaysiz?</b>",
            reply_markup=get_edit_products_keyboard([p.name for p in products]),
        )
    await callback.answer()


@router.callback_query(S.waiting_more_products, F.data == "edit_back")
async def cb_edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Tahrirlashdan yig'ma xabarga qaytadi."""
    if isinstance(callback.message, Message):
        text, markup = _summary_prompt(await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def _edit_index(callback: CallbackQuery, state: FSMContext) -> int | None:
    """Callback'dagi tovar indeksini tekshiradi."""
    raw = (callback.data or "").split(":", 1)[1]
    products = (await state.get_data()).get("_products", [])
    if not raw.isdigit() or int(raw) >= len(products):
        await callback.answer("Tovar topilmadi.", show_alert=True)
        return None
    return int(raw)


@router.callback_query(S.waiting_more_products, F.data.startswith("edit_prod:"))
async def cb_edit_product(callback: CallbackQuery, state: FSMContext) -> None:
    """Tanlangan tovar uchun amallarni ko'rsatadi."""
    index = await _edit_index(callback, state)
    if index is None:
        return
    product = _get_products(await state.get_data())[index]
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"✏️ {index + 1}. {_product_line(product)}\n\n<b>Nima qilamiz?</b>",
            reply_markup=get_edit_product_actions_keyboard(index),
        )
    await callback.answer()


@router.callback_query(S.waiting_more_products, F.data.startswith("edit_del:"))
async def cb_edit_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """Tovarni o'chiradi; ro'yxat bo'shab qolsa yangi tovar so'raladi."""
    index = await _edit_index(callback, state)
    if index is None:
        return
    products = list((await state.get_data())["_products"])
    products.pop(index)
    await state.update_data(_products=products)

    if products:
        text, markup = _summary_prompt(await state.get_data())
    else:
        await _start_product(state)
        text, markup = _type_prompt(await state.get_data())
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer("O'chirildi")


@router.callback_query(S.waiting_more_products, F.data.startswith("edit_redo:"))
async def cb_edit_redo(callback: CallbackQuery, state: FSMContext) -> None:
    """Tovarni qayta kiritish — yangi tovar shu o'ringa yoziladi."""
    index = await _edit_index(callback, state)
    if index is None:
        return
    await _start_product(state)
    await state.update_data(_replace_index=index)
    if isinstance(callback.message, Message):
        text, markup = _type_prompt({})
        await callback.message.edit_text(
            f"🔄 <b>{index + 1}-tovar qayta kiritilmoqda</b>\n\n" + text,
            reply_markup=markup,
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
        p.total_price for p in products if p.currency == currency
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
        p.total_price for p in products if p.currency == currency
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
            totals[p.currency.value] = (
                totals.get(p.currency.value, 0) + p.total_price
            )

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
        return [
            p if isinstance(p, DebtProduct) else DebtProduct.from_dict(p)
            for p in raw
        ]
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
        totals[p.currency.value] = totals.get(p.currency.value, 0) + p.total_price

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
