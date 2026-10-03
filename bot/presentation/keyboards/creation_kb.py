"""Presentation qatlami: Qarz yaratish klaviaturalari."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from bot.application.common.formatters import clip_button_text, today_str
from bot.presentation.common.product_catalog import AKKUM_SIZES_AH, MONTHS, PRODUCT_TYPES

_BACK_CANCEL_ROW = [
    InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
    InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
]


def get_date_picker_keyboard() -> InlineKeyboardMarkup:
    """Sana kiritish: 'Bugun' tugmasi va kun (1–31) tugmalari."""
    today = today_str()
    days = [
        InlineKeyboardButton(text=str(d), callback_data=f"dday:{d}")
        for d in range(1, 32)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"📅 Bugun ({today})",
                    callback_data="create_date_today",
                )
            ],
            *[days[i:i + 7] for i in range(0, len(days), 7)],
            [
                InlineKeyboardButton(
                    text="❌ Bekor qilish",
                    callback_data="cancel_creation",
                )
            ],
        ]
    )


def get_month_keyboard() -> InlineKeyboardMarkup:
    """Oy tanlash: 'Yanvar (01)' ... 'Dekabr (12)'."""
    months = [
        InlineKeyboardButton(text=f"{name} ({i:02d})", callback_data=f"dmon:{i}")
        for i, name in enumerate(MONTHS, start=1)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[*[months[i:i + 3] for i in range(0, 12, 3)], _BACK_CANCEL_ROW]
    )


def get_year_keyboard(years: list[int]) -> InlineKeyboardMarkup:
    """Yil tanlash tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=str(y), callback_data=f"dyear:{y}") for y in years],
            _BACK_CANCEL_ROW,
        ]
    )


def get_numpad_keyboard(with_thousands: bool = False) -> InlineKeyboardMarkup:
    """Raqam klaviaturasi (son yoki narx kiritish uchun)."""
    def key(text: str, value: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(text=text, callback_data=f"np:{value}")

    rows = [[key(str(n), str(n)) for n in range(r, r + 3)] for r in (1, 4, 7)]
    rows.append([key("⬅️ O'chirish", "del"), key("0", "0"), key("🗑 Tozalash", "clr")])
    last = [key("✅ Tayyor", "ok")]
    if with_thousands:
        last.insert(0, key("000", "000"))
    rows.append(last)
    rows.append(_BACK_CANCEL_ROW)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def get_product_type_keyboard() -> InlineKeyboardMarkup:
    """Tovar turi: Shina / Diska / Akkumulyator."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text=label, callback_data=f"ptype:{key}")
                for key, label in PRODUCT_TYPES.items()
            ],
            _BACK_CANCEL_ROW,
        ]
    )


def get_brand_keyboard(brands: list[str]) -> InlineKeyboardMarkup:
    """Brend tanlash (indeks bo'yicha) va 'Boshqa' tugmasi."""
    buttons = [
        InlineKeyboardButton(text=b, callback_data=f"pbrand:{i}")
        for i, b in enumerate(brands)
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *[buttons[i:i + 3] for i in range(0, len(buttons), 3)],
            [InlineKeyboardButton(text="✍️ Boshqa (qo'lda yozish)", callback_data="pbrand:other")],
            _BACK_CANCEL_ROW,
        ]
    )


def get_akkum_size_keyboard() -> InlineKeyboardMarkup:
    """Akkumulyator razmeri (Ah) tugmalari."""
    buttons = [
        InlineKeyboardButton(text=f"{ah}Ah", callback_data=f"psize:{ah}")
        for ah in AKKUM_SIZES_AH
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[*[buttons[i:i + 4] for i in range(0, len(buttons), 4)], _BACK_CANCEL_ROW]
    )


def get_edit_products_keyboard(names: list[str]) -> InlineKeyboardMarkup:
    """Tahrirlash uchun tovarlar ro'yxati."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            *[
                [InlineKeyboardButton(
                    text=clip_button_text(f"✏️ {i}. {name}"),
                    callback_data=f"edit_prod:{i - 1}",
                )]
                for i, name in enumerate(names, start=1)
            ],
            [InlineKeyboardButton(text="🔙 Ortga", callback_data="edit_back")],
        ]
    )


def get_edit_product_actions_keyboard(index: int) -> InlineKeyboardMarkup:
    """Tanlangan tovar ustida amallar."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"edit_del:{index}"),
                InlineKeyboardButton(text="🔄 Qayta kiritish", callback_data=f"edit_redo:{index}"),
            ],
            [InlineKeyboardButton(text="🔙 Ortga", callback_data="edit_products")],
        ]
    )


def get_back_cancel_keyboard(show_back: bool = True) -> InlineKeyboardMarkup:
    """Ortga va Bekor qilish tugmalari."""
    buttons: list[InlineKeyboardButton] = []
    if show_back:
        buttons.append(
            InlineKeyboardButton(
                text="🔙 Ortga",
                callback_data="create_back",
            )
        )
    buttons.append(
        InlineKeyboardButton(
            text="❌ Bekor qilish",
            callback_data="cancel_creation",
        )
    )
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def get_phone_keyboard() -> InlineKeyboardMarkup:
    """Telefon raqami kiritish (ixtiyoriy, o'tkazib yuborish imkoni bilan) klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⏭ O'tkazib yuborish (Telefon yo'q)",
                    callback_data="skip_client_phone",
                )
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_product_currency_keyboard() -> InlineKeyboardMarkup:
    """Tovar valyutasi tanlash klaviaturasi (har tovar alohida)."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 So'm", callback_data="prodcur_uzs"),
                InlineKeyboardButton(text="$ Dollar", callback_data="prodcur_usd"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_exchange_currency_keyboard() -> InlineKeyboardMarkup:
    """Exchange tovari valyutasi tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 So'm", callback_data="excur_uzs"),
                InlineKeyboardButton(text="$ Dollar", callback_data="excur_usd"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_given_currency_keyboard() -> InlineKeyboardMarkup:
    """Berilgan pul valyutasi tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 So'm", callback_data="gcur_uzs"),
                InlineKeyboardButton(text="$ Dollar", callback_data="gcur_usd"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_exchange_choice_keyboard() -> InlineKeyboardMarkup:
    """Ayirboshlash (exchange) bor/yo'qligini tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data="exchange_yes"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="exchange_no"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_given_money_choice_keyboard() -> InlineKeyboardMarkup:
    """Dastlabki berilgan pul bor/yo'qligini tanlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💵 Pul berdi", callback_data="given_money_yes"),
                InlineKeyboardButton(text="❌ Pul bermadi", callback_data="given_money_no"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_more_products_keyboard() -> InlineKeyboardMarkup:
    """Yig'ma xabar klaviaturasi: yana tovar, tahrirlash, tasdiqlash."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="➕ Yana tovar qo'shish",
                    callback_data="more_products_yes",
                ),
            ],
            [
                InlineKeyboardButton(text="✏️ Tahrirlash", callback_data="edit_products"),
            ],
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash",
                    callback_data="more_products_no",
                ),
            ],
            [
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )


def get_creation_confirm_keyboard() -> InlineKeyboardMarkup:
    """Qarzni yakuniy tasdiqlash va saqlash klaviaturasi."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Tasdiqlash / Yaratish",
                    callback_data="confirm_create_debt",
                )
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="create_back"),
                InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_creation"),
            ],
        ]
    )
