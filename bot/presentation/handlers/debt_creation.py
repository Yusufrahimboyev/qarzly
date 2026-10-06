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
from bot.i18n import N_, _, all_variants
from bot.infrastructure.branches import Branch
from bot.presentation.common.product_catalog import (
    BRANDS,
    PRODUCT_TYPES,
    akkum_sizes,
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
    get_exchange_more_keyboard,
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
from bot.presentation.keyboards.main_menu_kb import CREATE_BUTTON_TEXT, get_main_menu_keyboard
from bot.presentation.states.debt_creation import DebtCreationStates

router = Router()

S = DebtCreationStates
Prompt = tuple[str, InlineKeyboardMarkup]


# ==========================================
# BOSQICH XABARLARI (oldinga va ortga bir xil matn)
# ==========================================


def _date_prompt(data: dict[str, Any]) -> Prompt:
    header = (
        _("🏢 <b>Filial:</b> {branch}", branch=esc_html(data["branch_title"])) + "\n\n"
        if data.get("branch_title")
        else ""
    )
    return (
        header + _(
            "📅 <b>Qarzga olingan kunni tanlang:</b>\n\n"
            "<i>Keyin oy va yil so'raladi. Bugun bo'lsa 'Bugun' tugmasini bosing</i>"
        ),
        get_date_picker_keyboard(),
    )


def _month_prompt(data: dict[str, Any]) -> Prompt:
    return (
        _("📅 <b>Kun:</b> {day}\n\n🗓 <b>Oyni tanlang:</b>", day=data["_date_day"]),
        get_month_keyboard(),
    )


def _year_prompt(data: dict[str, Any]) -> Prompt:
    year = today().year
    return (
        _(
            "📅 <b>Sana:</b> {date}\n\n🗓 <b>Yilni tanlang:</b>",
            date=f"{data['_date_day']:02d}.{data['_date_month']:02d}",
        ),
        get_year_keyboard([year, year + 1]),
    )


def _name_prompt(_data: dict[str, Any]) -> Prompt:
    return (
        _("👤 <b>Qarz oluvchining ismini kiriting:</b>\n\n<i>Masalan: Aliyev Anvar</i>"),
        get_back_cancel_keyboard(show_back=True),
    )


def _phone_prompt(_data: dict[str, Any]) -> Prompt:
    return (
        _(
            "📞 <b>Telefon raqamini kiriting:</b>\n\n"
            "<i>Masalan: +998901234567 yoki telefon bo'lmasa "
            "'O'tkazib yuborish' tugmasini bosing:</i>"
        ),
        get_phone_keyboard(),
    )


def _type_prompt(data: dict[str, Any]) -> Prompt:
    num = len(data.get("_products", [])) + 1
    text = (
        _("📦 <b>Tovar turini tanlang:</b>") if num == 1
        else _("📦 <b>{num}-tovar turini tanlang:</b>", num=num)
    )
    return text, get_product_type_keyboard()


def _brand_prompt(data: dict[str, Any]) -> Prompt:
    type_key = data["product_type"]
    header = _("📦 <b>Tovar:</b> {name}", name=_(PRODUCT_TYPES[type_key])) + "\n\n"
    if data.get("_brand_manual"):
        return (
            header + _("✍️ <b>Brend nomini yozing:</b>"),
            get_back_cancel_keyboard(show_back=True),
        )
    return header + _("🏷 <b>Brendini tanlang:</b>"), get_brand_keyboard(BRANDS[type_key])


def _size_prompt(data: dict[str, Any]) -> Prompt:
    type_key = data["product_type"]
    header = _(
        "📦 <b>Tovar:</b> {name}",
        name=f"{_(PRODUCT_TYPES[type_key])} {esc_html(data['product_brand'])}",
    ) + "\n\n"
    if type_key == "akkum":
        return (
            header + _("🔋 <b>Razmerini tanlang:</b>"),
            get_akkum_size_keyboard(akkum_sizes(data["product_brand"])),
        )
    example = "R16 malibu" if type_key == "diska" else "205/65R15"
    return (
        header + _("📏 <b>Razmerini kiriting:</b>\n\n<i>Masalan: {example}</i>", example=example),
        get_back_cancel_keyboard(show_back=True),
    )


def _entered(value: str) -> str:
    return _("Kiritildi: <b>{value}</b>", value=value)


def _quantity_prompt(data: dict[str, Any]) -> Prompt:
    return (
        _("📦 <b>Tovar:</b> {name}", name=esc_html(data["product_name"])) + "\n\n"
        + _("🔢 <b>Tovar sonini kiriting:</b>") + "\n\n"
        + _entered(data.get("_np") or "—"),
        get_numpad_keyboard(),
    )


def _item_header(icon_text: str, name: str, quantity: int) -> str:
    return _(icon_text, name=esc_html(name)) + " — " + _("{count} ta", count=quantity) + "\n\n"


def _currency_prompt(data: dict[str, Any]) -> Prompt:
    return (
        _item_header("📦 <b>Tovar:</b> {name}", data["product_name"], data["product_quantity"])
        + _("💱 <b>Valyutani tanlang:</b>"),
        get_product_currency_keyboard(),
    )


def _price_prompt(data: dict[str, Any]) -> Prompt:
    currency = Currency(data["product_currency"])
    raw = data.get("_np")
    return (
        _item_header("📦 <b>Tovar:</b> {name}", data["product_name"], data["product_quantity"])
        + _("💰 <b>1 dona tovar narxini kiriting:</b>") + "\n\n"
        + _entered(format_money(int(raw), currency) if raw else "—"),
        get_numpad_keyboard(with_thousands=True),
    )


def _product_line(p: DebtProduct, icon: str = "📦") -> str:
    if p.quantity > 1:
        return (
            f"{icon} <b>{esc_html(p.name)}</b> — {p.quantity} × "
            f"{format_money(p.price_per_unit, p.currency)} = "
            f"{format_money(p.total_price, p.currency)}"
        )
    return f"{icon} <b>{esc_html(p.name)}</b> — {format_money(p.price_per_unit, p.currency)}"


def _totals(items: list[DebtProduct]) -> dict[str, int]:
    """Valyutalar bo'yicha jami narxlar."""
    totals: dict[str, int] = {}
    for p in items:
        totals[p.currency.value] = totals.get(p.currency.value, 0) + p.total_price
    return totals


def _summary_lines(data: dict[str, Any]) -> list[str]:
    """Mijoz ma'lumotlari va tovarlar ro'yxati (yig'ma xabarlar uchun)."""
    products = _get_products(data)
    lines = []
    if data.get("branch_title"):
        lines.append(_("🏢 <b>Filial:</b> {branch}", branch=esc_html(data["branch_title"])))
    lines.append(_("👤 <b>Qarz oluvchi:</b> {name}", name=esc_html(data.get("client_name", "-"))))
    if data.get("client_phone"):
        lines.append(_("📞 <b>Telefon:</b> {phone}", phone=esc_html(data["client_phone"])))
    lines.append(_("📅 <b>Sana:</b> {date}", date=data.get("debt_date", "-")))
    lines.append(_("━━━━━━━━ <b>TOVARLAR:</b> ━━━━━━━━"))
    lines.extend(f"{i}. {_product_line(p)}" for i, p in enumerate(products, start=1))
    lines.append("\n" + _("💰 <b>Jami:</b> {total}", total=format_money_map(_totals(products))))
    return lines


def _summary_prompt(data: dict[str, Any]) -> Prompt:
    """Shu paytgacha kiritilgan barcha ma'lumotlar bitta xabarda."""
    return "\n".join(_summary_lines(data)), get_more_products_keyboard()


def _exchange_choice_prompt(_data: dict[str, Any]) -> Prompt:
    return (
        _(
            "🔄 <b>Ayirboshlash (Exchange) tovari bormi?</b>\n\n"
            "<i>Mijoz berilgan tovar evaziga boshqa tovar berdimi?</i>"
        ),
        get_exchange_choice_keyboard(),
    )


def _ex_name_prompt(data: dict[str, Any]) -> Prompt:
    num = len(data.get("_exchanges", [])) + 1
    title = (
        _("🔄 <b>Ayirboshlash tovari nomini kiriting:</b>") if num == 1
        else _("🔄 <b>{num}-ayirboshlash tovari nomini kiriting:</b>", num=num)
    )
    return (
        title + "\n\n" + _("<i>Masalan: Eski shina R16, Eski akkumulyator</i>"),
        get_back_cancel_keyboard(show_back=True),
    )


def _ex_quantity_prompt(data: dict[str, Any]) -> Prompt:
    return (
        _("🔄 <b>Exchange:</b> {name}", name=esc_html(data["ex_name"])) + "\n\n"
        + _("🔢 <b>Sonini kiriting:</b>") + "\n\n"
        + _entered(data.get("_np") or "—"),
        get_numpad_keyboard(),
    )


def _ex_currency_prompt(data: dict[str, Any]) -> Prompt:
    return (
        _item_header("🔄 <b>Exchange:</b> {name}", data["ex_name"], data["ex_quantity"])
        + _(
            "💱 <b>Valyutani tanlang:</b>\n\n"
            "<i>Exchange shu valyutadagi tovarlar qarzidan chegiriladi</i>"
        ),
        get_exchange_currency_keyboard(),
    )


def _ex_price_prompt(data: dict[str, Any]) -> Prompt:
    currency = Currency(data["ex_currency"])
    raw = data.get("_np")
    return (
        _item_header("🔄 <b>Exchange:</b> {name}", data["ex_name"], data["ex_quantity"])
        + _("💰 <b>1 dona narxini kiriting:</b>") + "\n\n"
        + _entered(format_money(int(raw), currency) if raw else "—"),
        get_numpad_keyboard(with_thousands=True),
    )


def _ex_summary_prompt(data: dict[str, Any]) -> Prompt:
    """Tovarlar va exchange'lar bitta xabarda."""
    exchanges = _get_exchanges(data)
    lines = _summary_lines(data)
    lines.append(_("━━━━━━━━ <b>EXCHANGE:</b> ━━━━━━━━"))
    lines.extend(
        f"{i}. {_product_line(e, icon='🔄')}" for i, e in enumerate(exchanges, start=1)
    )
    lines.append("\n" + _(
        "🔄 <b>Exchange jami:</b> {total}", total=format_money_map(_totals(exchanges))
    ))
    return "\n".join(lines), get_exchange_more_keyboard()


def _given_choice_prompt(_data: dict[str, Any]) -> Prompt:
    return (
        _(
            "💵 <b>Qarzdan oldindan pul berildimi?</b>\n\n"
            "<i>Mijoz tovar olingan paytda ma'lum bir summa to'ladimi?</i>"
        ),
        get_given_money_choice_keyboard(),
    )


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
    S.waiting_exchange_choice.state: _exchange_choice_prompt,
    S.waiting_exchange_name.state: _ex_name_prompt,
    S.waiting_exchange_quantity.state: _ex_quantity_prompt,
    S.waiting_exchange_currency.state: _ex_currency_prompt,
    S.waiting_exchange_price.state: _ex_price_prompt,
    S.waiting_exchange_more.state: _ex_summary_prompt,
    S.waiting_given_money_choice.state: _given_choice_prompt,
}

# Raqam klaviaturasi ishlaydigan holatlar
_GIVEN_CURRENCY_TEXT = N_(
    "💱 <b>Berilgan pul qaysi valyutada?</b>\n\n"
    "<i>Shu valyutadagi tovarlar qarzidan chegiriladi</i>"
)

_NUMPAD_STATES = (
    S.waiting_product_quantity.state,
    S.waiting_product_price.state,
    S.waiting_exchange_quantity.state,
    S.waiting_exchange_price.state,
)


def _previous_state(current: str | None, data: dict[str, Any]) -> str | None:
    """'Ortga' tugmasi manzili (berilgan pul summasidan tashqari)."""
    if current == S.waiting_product_type.state:
        if data.get("_products"):
            return S.waiting_more_products.state
        if data.get("_existing_client"):
            return S.waiting_date.state
        return S.waiting_client_phone.state
    if current in (S.waiting_exchange_name.state, S.waiting_given_money_choice.state):
        if data.get("_exchanges"):
            return S.waiting_exchange_more.state
        return S.waiting_exchange_choice.state
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
        S.waiting_exchange_quantity.state: S.waiting_exchange_name.state,
        S.waiting_exchange_currency.state: S.waiting_exchange_quantity.state,
        S.waiting_exchange_price.state: S.waiting_exchange_currency.state,
        S.waiting_given_currency.state: S.waiting_given_money_choice.state,
        S.waiting_confirm.state: S.waiting_given_money_choice.state,
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
        await callback.answer(_("Noto'g'ri so'rov."), show_alert=True)
        return

    client = await client_service.get_by_id(int(client_id_raw))
    if client is None:
        await callback.answer(_("Mijoz topilmadi."), show_alert=True)
        return

    await state.clear()
    await state.update_data(
        branch_title=branch.title,
        client_name=client.full_name,
        client_phone=client.phone,
        _existing_client=True,
    )
    await state.set_state(S.waiting_date)

    text, markup = _date_prompt({})
    await callback.message.edit_text(
        _(
            "📝 <b>YANGI QARZ YARATISH</b>\n\n"
            "👤 <b>Mijoz:</b> {name}\n"
            "📞 <b>Telefon:</b> {phone}",
            name=esc_html(client.full_name),
            phone=esc_html(client.phone),
        ) + "\n\n" + text,
        reply_markup=markup,
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
        await callback.message.edit_text(_("❌ <b>Qarz yaratish bekor qilindi.</b>"))
        await callback.message.answer(
            _("Asosiy menyu:"),
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
        if previous in _NUMPAD_STATES:
            await state.update_data(_np="")
            data["_np"] = ""
        await state.set_state(previous)
        text, markup = _PROMPTS[previous](data)
        await callback.message.edit_text(text, reply_markup=markup)

    elif current_state == DebtCreationStates.waiting_given_money_amount:
        await state.set_state(DebtCreationStates.waiting_given_currency)
        await callback.message.edit_text(
            _(_GIVEN_CURRENCY_TEXT),
            reply_markup=get_given_currency_keyboard(),
        )

    await callback.answer()


# ==========================================
# 1. BOSHLASH: SANA (kun → oy → yil)
# ==========================================


@router.message(F.text.in_(all_variants(CREATE_BUTTON_TEXT)))
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
        await callback.answer(_("⚠️ Bunday sana yo'q. Kunni qayta tanlang."), show_alert=True)
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
            _("📅 <b>Sana:</b> {date}", date=date_str) + "\n"
            + _(
                "👤 <b>Mijoz:</b> {name}",
                name=f"{esc_html(client_name)} ({esc_html(client_phone)})",
            )
            + "\n\n" + text,
            reply_markup=markup,
        )
    else:
        await state.set_state(S.waiting_client_name)
        text, markup = _name_prompt(data)
        await message.answer(
            _("📅 <b>Sana:</b> {date}", date=date_str) + "\n\n" + text, reply_markup=markup
        )


@router.message(S.waiting_date)
async def process_custom_date(message: Message, state: FSMContext) -> None:
    """Foydalanuvchi yozgan sanani tekshiradi."""
    if message.text is None:
        await message.answer(_("Iltimos, sanani matn ko'rinishida kiriting."))
        return

    parsed_date = parse_date_input(message.text)
    if parsed_date is None:
        await message.answer(
            _(
                "⚠️ <b>Noto'g'ri sana formati!</b>\n\n"
                "Iltimos, sanani <b>DD.MM.YYYY</b> ko'rinishida kiriting "
                "(masalan: <code>16.08.2026</code>) "
                "yoki quyidagi tugmalardan tanlang:"
            ),
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
            _(
                "⚠️ <b>Ism juda qisqa!</b>\n\n"
                "Iltimos, qarz oluvchining to'liq ism-familiyasini kiriting:"
            ),
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return
    if len(name) > 80:
        await message.answer(
            _("⚠️ <b>Ism juda uzun!</b>\n\nIltimos, 80 belgidan qisqa kiriting:"),
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    await state.update_data(client_name=name)
    await state.set_state(S.waiting_client_phone)
    text, markup = _phone_prompt({})
    await message.answer(
        _("👤 <b>Qarz oluvchi:</b> {name}", name=esc_html(name)) + "\n\n" + text,
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
        _("📞 <b>Telefon:</b> {phone}", phone=_("<i>Kiritilmadi</i>")) + "\n\n" + text,
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
                _(
                    "⚠️ <b>Noto'g'ri telefon raqami!</b>\n\n"
                    "Iltimos, telefon raqamini to'g'ri formatda kiriting "
                    "(masalan: <code>+998901234567</code>) yoki telefon bo'lmasa "
                    "<b>'O'tkazib yuborish'</b> tugmasini bosing:"
                ),
                reply_markup=get_phone_keyboard(),
            )
            return

    # Tovarlar ro'yxatini bo'sh boshlaymiz
    await state.update_data(client_phone=clean_phone, _products=[])
    await _start_product(state)
    phone_display = clean_phone if clean_phone else _("<i>Kiritilmadi</i>")
    text, markup = _type_prompt({})
    await message.answer(
        _("📞 <b>Telefon:</b> {phone}", phone=phone_display) + "\n\n" + text,
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
            _("⚠️ Brend nomini 30 belgigacha kiriting:"),
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
    raw = (callback.data or "").split(":", 1)[1]
    sizes = akkum_sizes((await state.get_data())["product_brand"])
    if not raw.isdigit() or int(raw) >= len(sizes):
        await callback.answer()
        return
    text, markup = await _accept_size(state, sizes[int(raw)])
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


@router.callback_query(StateFilter(*_NUMPAD_STATES), F.data.startswith("np:"))
async def cb_numpad(callback: CallbackQuery, state: FSMContext) -> None:
    """Raqam klaviaturasi: raqam qo'shish, o'chirish, tozalash, tayyor."""
    key = (callback.data or "").split(":", 1)[1]
    current_state = await state.get_state()
    data = await state.get_data()
    value: str = data.get("_np", "")

    if key == "ok":
        result = await _ACCEPT[current_state or ""](state, int(value) if value else 0)
        if isinstance(result, str):
            await callback.answer(result, show_alert=True)
            return
        if isinstance(callback.message, Message):
            await callback.message.edit_text(result[0], reply_markup=result[1])
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


_INVALID_NUMBER = N_("⚠️ Noto'g'ri qiymat. Musbat son kiriting.")


async def _accept_quantity(state: FSMContext, quantity: int) -> Prompt | str:
    """Tovar sonini saqlab, valyutani so'raydi. Noto'g'ri bo'lsa xato matni."""
    if not 1 <= quantity <= MAX_QUANTITY:
        return _(_INVALID_NUMBER)
    await state.update_data(product_quantity=quantity)
    await state.set_state(S.waiting_product_currency)
    return _currency_prompt(await state.get_data())


async def _accept_price(state: FSMContext, price: int) -> Prompt | str:
    """Narxni saqlab, tovarni ro'yxatga qo'shadi. Noto'g'ri bo'lsa xato matni."""
    if not 0 < price <= MAX_MONEY:
        return _(_INVALID_NUMBER)
    await state.update_data(product_price=price)
    data = await state.get_data()
    return await _append_product(state, Currency(data["product_currency"]))


async def _accept_ex_quantity(state: FSMContext, quantity: int) -> Prompt | str:
    """Exchange sonini saqlab, valyutani so'raydi."""
    if not 1 <= quantity <= MAX_QUANTITY:
        return _(_INVALID_NUMBER)
    await state.update_data(ex_quantity=quantity)
    await state.set_state(S.waiting_exchange_currency)
    return _ex_currency_prompt(await state.get_data())


async def _accept_ex_price(state: FSMContext, price: int) -> Prompt | str:
    """Exchange narxini tekshirib, ro'yxatga qo'shadi.

    Shu valyutadagi barcha exchange'lar jami tovarlar jamidan oshmasligi kerak.
    """
    if not 0 < price <= MAX_MONEY:
        return _(_INVALID_NUMBER)
    data = await state.get_data()
    currency = Currency(data["ex_currency"])
    item = DebtProduct(
        name=data["ex_name"],
        quantity=data["ex_quantity"],
        price_per_unit=price,
        currency=currency,
    )
    exchanges = _get_exchanges(data)
    replace_index = data.get("_ex_replace_index")
    if replace_index is not None and 0 <= replace_index < len(exchanges):
        exchanges[replace_index] = item
    else:
        exchanges.append(item)

    limit = _totals(_get_products(data)).get(currency.value, 0)
    total = _totals(exchanges).get(currency.value, 0)
    if total > limit:
        return (
            _(
                "⚠️ Exchange jami ({total}) shu valyutadagi tovarlar jamidan ({limit}) "
                "oshmasligi kerak.",
                total=format_money(total, currency),
                limit=format_money(limit, currency),
            )
        )

    await state.update_data(_exchanges=exchanges, _ex_replace_index=None)
    await state.set_state(S.waiting_exchange_more)
    return _ex_summary_prompt(await state.get_data())


_ACCEPT = {
    S.waiting_product_quantity.state: _accept_quantity,
    S.waiting_product_price.state: _accept_price,
    S.waiting_exchange_quantity.state: _accept_ex_quantity,
    S.waiting_exchange_price.state: _accept_ex_price,
}


@router.message(StateFilter(*_NUMPAD_STATES))
async def process_numpad_text(message: Message, state: FSMContext) -> None:
    """Son yoki narx klaviatura o'rniga matn bilan yozilganda."""
    current_state = await state.get_state() or ""
    result = await _ACCEPT[current_state](state, parse_money(message.text or "") or 0)
    if isinstance(result, str):
        text, markup = _PROMPTS[current_state](await state.get_data())
        await message.answer(f"{result}\n\n{text}", reply_markup=markup)
        return
    await message.answer(result[0], reply_markup=result[1])


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
        text, markup = _exchange_choice_prompt({})
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


# ==========================================
# 3.1. TOVARLARNI TAHRIRLASH
# ==========================================


# Tahrirlash tovarlar ("edit_*") va exchange'lar ("exedit_*") uchun umumiy.
# prefix → (ro'yxat kaliti, qayta kiritish indeksi kaliti, ikonka)
_EDIT_TARGETS = {
    "edit": ("_products", "_replace_index", "📦"),
    "exedit": ("_exchanges", "_ex_replace_index", "🔄"),
}
_EDIT_STATES = StateFilter(S.waiting_more_products, S.waiting_exchange_more)


def _edit_prefix(callback: CallbackQuery) -> str:
    return (callback.data or "").split("_", 1)[0]


def _edit_summary(prefix: str, data: dict[str, Any]) -> Prompt:
    return _summary_prompt(data) if prefix == "edit" else _ex_summary_prompt(data)


def _edit_items(prefix: str, data: dict[str, Any]) -> list[DebtProduct]:
    return _get_products(data) if prefix == "edit" else _get_exchanges(data)


@router.callback_query(_EDIT_STATES, F.data.in_({"edit_products", "exedit_products"}))
async def cb_edit_products(callback: CallbackQuery, state: FSMContext) -> None:
    """Tahrirlash uchun ro'yxatni ko'rsatadi."""
    prefix = _edit_prefix(callback)
    items = _edit_items(prefix, await state.get_data())
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("✏️ <b>Qaysi birini tahrirlaysiz?</b>"),
            reply_markup=get_edit_products_keyboard([p.name for p in items], prefix),
        )
    await callback.answer()


@router.callback_query(_EDIT_STATES, F.data.in_({"edit_back", "exedit_back"}))
async def cb_edit_back(callback: CallbackQuery, state: FSMContext) -> None:
    """Tahrirlashdan yig'ma xabarga qaytadi."""
    if isinstance(callback.message, Message):
        text, markup = _edit_summary(_edit_prefix(callback), await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def _edit_index(callback: CallbackQuery, state: FSMContext) -> int | None:
    """Callback'dagi indeksni tekshiradi."""
    raw = (callback.data or "").split(":", 1)[1]
    list_key = _EDIT_TARGETS[_edit_prefix(callback)][0]
    items = (await state.get_data()).get(list_key, [])
    if not raw.isdigit() or int(raw) >= len(items):
        await callback.answer(_("Topilmadi."), show_alert=True)
        return None
    return int(raw)


@router.callback_query(_EDIT_STATES, F.data.startswith(("edit_prod:", "exedit_prod:")))
async def cb_edit_product(callback: CallbackQuery, state: FSMContext) -> None:
    """Tanlangan element uchun amallarni ko'rsatadi."""
    index = await _edit_index(callback, state)
    if index is None:
        return
    prefix = _edit_prefix(callback)
    item = _edit_items(prefix, await state.get_data())[index]
    if isinstance(callback.message, Message):
        line = _product_line(item, icon=_EDIT_TARGETS[prefix][2])
        await callback.message.edit_text(
            f"✏️ {index + 1}. {line}\n\n" + _("<b>Nima qilamiz?</b>"),
            reply_markup=get_edit_product_actions_keyboard(index, prefix),
        )
    await callback.answer()


@router.callback_query(_EDIT_STATES, F.data.startswith(("edit_del:", "exedit_del:")))
async def cb_edit_delete(callback: CallbackQuery, state: FSMContext) -> None:
    """O'chiradi; ro'yxat bo'shab qolsa — tovar turi yoki 'Exchange bormi?' so'raladi."""
    index = await _edit_index(callback, state)
    if index is None:
        return
    prefix = _edit_prefix(callback)
    list_key = _EDIT_TARGETS[prefix][0]
    items = list((await state.get_data())[list_key])
    items.pop(index)
    await state.update_data(**{list_key: items})

    if items:
        text, markup = _edit_summary(prefix, await state.get_data())
    elif prefix == "edit":
        await _start_product(state)
        text, markup = _type_prompt(await state.get_data())
    else:
        await state.set_state(S.waiting_exchange_choice)
        text, markup = _exchange_choice_prompt({})
    if isinstance(callback.message, Message):
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer(_("O'chirildi"))


@router.callback_query(_EDIT_STATES, F.data.startswith(("edit_redo:", "exedit_redo:")))
async def cb_edit_redo(callback: CallbackQuery, state: FSMContext) -> None:
    """Qayta kiritish — yangi qiymat shu o'ringa yoziladi."""
    index = await _edit_index(callback, state)
    if index is None:
        return
    prefix = _edit_prefix(callback)
    if prefix == "edit":
        await _start_product(state)
        text, markup = _type_prompt({})
    else:
        await _start_exchange(state)
        text, markup = _ex_name_prompt({})
    await state.update_data(**{_EDIT_TARGETS[prefix][1]: index})
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("🔄 <b>{num}-qator qayta kiritilmoqda</b>", num=index + 1) + "\n\n" + text,
            reply_markup=markup,
        )
    await callback.answer()


# ==========================================
# 4. EXCHANGE (AYIRBOSHLASH)
# ==========================================


@router.callback_query(S.waiting_exchange_choice, F.data == "exchange_no")
async def cb_exchange_no(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange yo'q bo'lsa to'g'ridan-to'g'ri berilgan pul bosqichiga o'tadi."""
    await state.update_data(_exchanges=[])
    await state.set_state(S.waiting_given_money_choice)

    if isinstance(callback.message, Message):
        text, markup = _given_choice_prompt({})
        await callback.message.edit_text(
            _("🔄 <b>Exchange:</b> Yo'q") + "\n\n" + text, reply_markup=markup
        )
    await callback.answer()


@router.callback_query(S.waiting_exchange_choice, F.data == "exchange_yes")
async def cb_exchange_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange bor — birinchi exchange tovari nomini so'raydi."""
    await state.update_data(_exchanges=[])
    await _start_exchange(state)

    if isinstance(callback.message, Message):
        text, markup = _ex_name_prompt({})
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


async def _start_exchange(state: FSMContext) -> None:
    """Yangi exchange tovarini kiritishni boshlaydi."""
    await state.update_data(ex_name=None, ex_quantity=None, ex_currency=None,
                            _ex_replace_index=None)
    await state.set_state(S.waiting_exchange_name)


@router.message(S.waiting_exchange_name)
async def process_exchange_name(message: Message, state: FSMContext) -> None:
    """Exchange tovari nomini qabul qiladi va sonini so'raydi."""
    ex_name = (message.text or "").strip()
    if not ex_name or len(ex_name) > 80:
        text, markup = _ex_name_prompt(await state.get_data())
        await message.answer(
            _("⚠️ Nomni 80 belgigacha kiriting.") + "\n\n" + text, reply_markup=markup
        )
        return

    await state.update_data(ex_name=ex_name, _np="")
    await state.set_state(S.waiting_exchange_quantity)
    text, markup = _ex_quantity_prompt(await state.get_data())
    await message.answer(text, reply_markup=markup)


@router.callback_query(S.waiting_exchange_currency, F.data.in_({"excur_uzs", "excur_usd"}))
async def cb_exchange_currency(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange valyutasi tanlandi — 1 dona narxini so'raydi."""
    currency = Currency.UZS if callback.data == "excur_uzs" else Currency.USD
    await state.update_data(ex_currency=currency.value, _np="")
    await state.set_state(S.waiting_exchange_price)
    if isinstance(callback.message, Message):
        text, markup = _ex_price_prompt(await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(S.waiting_exchange_more, F.data == "exchange_more_yes")
async def cb_exchange_more_yes(callback: CallbackQuery, state: FSMContext) -> None:
    """Yana exchange tovari qo'shish."""
    await _start_exchange(state)
    if isinstance(callback.message, Message):
        text, markup = _ex_name_prompt(await state.get_data())
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(S.waiting_exchange_more, F.data == "exchange_done")
async def cb_exchange_done(callback: CallbackQuery, state: FSMContext) -> None:
    """Exchange'lar tayyor — berilgan pul bosqichiga o'tadi."""
    await state.set_state(S.waiting_given_money_choice)
    if isinstance(callback.message, Message):
        text, markup = _given_choice_prompt({})
        await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


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
            _("💵 <b>Pul berdi</b> tanlandi.") + "\n\n" + _(_GIVEN_CURRENCY_TEXT),
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

    label = _("So'm 💵") if currency == Currency.UZS else _("Dollar $")
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _(
                "💱 <b>Valyuta:</b> {label}\n\n"
                "💰 <b>Qarzdan qancha pul berildi?</b>\n\n"
                "<i>Masalan: 200 000</i>",
                label=label,
            ),
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
    exchange_price = _totals(_get_exchanges(data)).get(currency.value, 0)
    max_allowable = total_in_currency - exchange_price

    if amount is None or amount < 0:
        await message.answer(
            _(
                "⚠️ <b>Noto'g'ri summa!</b>\n\n"
                "Iltimos, son kiriting (masalan: <code>200 000</code>):"
            ),
            reply_markup=get_back_cancel_keyboard(show_back=True),
        )
        return

    if amount > max_allowable:
        amount_str = format_money(amount, currency)
        allowable_str = format_money(max_allowable, currency)
        await message.answer(
            _(
                "⚠️ <b>Berilgan pul ({amount}) {currency} valyutasidagi "
                "tovar narxi va exchange ayirmasidan ({allowed}) "
                "katta bo'lishi mumkin emas!</b>\n\n"
                "Iltimos, qayta kiriting:",
                amount=amount_str,
                currency=currency.value,
                allowed=allowable_str,
            ),
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
    exchanges = _get_exchanges(data)
    given_money: int = data.get("given_money", 0)
    given_currency = Currency(data.get("given_currency", Currency.UZS.value))

    try:
        client, is_new = await client_service.get_or_create(
            full_name=client_name,
            phone=client_phone,
        )

        if client.id is None:
            raise RuntimeError(_("Mijoz ID si aniqlanmadi."))

        saved_debts = await debt_service.create_debts(
            client_id=client.id,
            debt_date=debt_date,
            products=products,
            given_money=given_money,
            given_currency=given_currency,
            exchanges=exchanges,
        )

        # Valyutalar bo'yicha jami narxlar
        totals: dict[str, int] = {}
        for p in products:
            totals[p.currency.value] = (
                totals.get(p.currency.value, 0) + p.total_price
            )

        success_lines = [
            _("✅ <b>QARZ MUVAFFAQIYATLI SAQLANDI!</b>") + "\n",
            _(
                "👤 <b>Mijoz:</b> {name}",
                name=f"{esc_html(client.full_name)} ({esc_html(client.phone)})",
            ),
            _("📅 <b>Sana:</b> {date}", date=debt_date),
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
            _("💰 <b>Jami narxi:</b> {total}", total=format_money_map(totals))
        )

        success_lines.extend(_product_line(e, icon="🔄") for e in exchanges)
        if given_money > 0:
            success_lines.append(
                _(
                    "💵 <b>Boshlang'ich to'lov:</b> {amount}",
                    amount=format_money(given_money, given_currency),
                )
            )

        remaining_map: dict[str, int] = {}
        for d in saved_debts:
            remaining_map[d.currency.value] = (
                remaining_map.get(d.currency.value, 0) + d.remaining_debt
            )
        success_lines.append(
            _("💳 <b>Hisoblangan qarz:</b> <b>{debt}</b>", debt=format_money_map(remaining_map))
            + "\n"
        )
        if len(saved_debts) > 1:
            success_lines.append(
                _(
                    "<i>{count} ta valyutada alohida qarz yozuvlari yaratildi.</i>",
                    count=len(saved_debts),
                )
            )
        success_lines.append(_("<i>Ma'lumotlar 'Qarzlar jadvali' ga qo'shildi.</i>"))

        if isinstance(callback.message, Message):
            await callback.message.edit_text("\n".join(success_lines))
            await callback.message.answer(
                _("Asosiy menyu:"),
                reply_markup=get_main_menu_keyboard(settings.web_app_url),
            )
        await callback.answer(_("Saqlandi!"), show_alert=False)

    except Exception as exc:
        if isinstance(callback.message, Message):
            await callback.message.edit_text(
                _("❌ <b>Xatolik yuz berdi:</b> {error}", error=esc_html(str(exc))),
            )
        await callback.answer(_("Xatolik yuz berdi."), show_alert=True)


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


def _get_exchanges(data: dict[str, Any]) -> list[DebtProduct]:
    """State dan exchange tovarlari ro'yxatini olish."""
    return [
        e if isinstance(e, DebtProduct) else DebtProduct.from_dict(e)
        for e in data.get("_exchanges", [])
    ]


def _render_preview(data: dict[str, Any]) -> str:
    """Kiritilgan qarz ma'lumotlarining chiroyli preview ko'rinishi.

    Har bir tovar o'z valyutasida ko'rsatiladi; jami summalar valyutalar
    bo'yicha alohida yig'iladi.
    """
    debt_date = data.get("debt_date", "-")
    client_name = data.get("client_name", "-")
    client_phone = data.get("client_phone", "-")
    exchanges = _get_exchanges(data)
    given_money: int = data.get("given_money", 0)
    given_currency = Currency(data.get("given_currency", Currency.UZS.value))

    products = _get_products(data)

    # Valyutalar bo'yicha jami narxlar
    totals: dict[str, int] = {}
    for p in products:
        totals[p.currency.value] = totals.get(p.currency.value, 0) + p.total_price

    # Har bir valyutada chegirmalarni hisoblab, qoldiqni topamiz
    remaining: dict[str, int] = dict(totals)
    for cur, amount in _totals(exchanges).items():
        remaining[cur] = max(0, remaining.get(cur, 0) - amount)
    if given_money > 0:
        cur = given_currency.value
        remaining[cur] = max(0, remaining.get(cur, 0) - given_money)

    lines = [
        _("📋 <b>QARZ MA'LUMOTLARI (TASDIQLASH):</b>") + "\n",
        _("📅 <b>Sana:</b> {date}", date=debt_date),
        _("👤 <b>Qarz oluvchi:</b> {name}", name=esc_html(client_name)),
        _("📞 <b>Telefon:</b> {phone}", phone=esc_html(client_phone)),
        _("━━━━━━━━ <b>TOVARLAR:</b> ━━━━━━━━"),
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

    lines.append("\n" + _("💰 <b>Tovarlar jami narxi:</b> {total}", total=format_money_map(totals)))

    if exchanges:
        lines.append(_("🔄 <b>Exchange:</b>"))
        lines.extend(f"  {i}. {_product_line(e, icon='🔄')}"
                     for i, e in enumerate(exchanges, start=1))
    else:
        lines.append(_("🔄 <b>Exchange tovar:</b> Yo'q"))

    if given_money > 0:
        lines.append(
            _("💵 <b>Berilgan pul:</b> {amount}", amount=format_money(given_money, given_currency))
        )
    else:
        lines.append(_("💵 <b>Berilgan pul:</b> 0 (bermadi)"))

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append(
        _("💳 <b>HISOBLANGAN QARZ:</b> <b>{debt}</b>", debt=format_money_map(remaining)) + "\n"
    )
    lines.append(_("<i>Ma'lumotlar to'g'ri bo'lsa, 'Tasdiqlash' tugmasini bosing:</i>"))

    return "\n".join(lines)
