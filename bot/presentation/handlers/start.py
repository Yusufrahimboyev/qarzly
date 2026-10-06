"""Presentation qatlami: /start, /help va asosiy menyu handler'lari."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import esc_html
from bot.application.services.user_service import UserService
from bot.core.config import Settings
from bot.i18n import _, all_variants
from bot.infrastructure.branches import Branch
from bot.presentation.keyboards.main_menu_kb import (
    BRANCH_BUTTON_TEXT,
    HELP_BUTTON_TEXT,
    SETTINGS_BUTTON_TEXT,
    get_main_menu_keyboard,
)

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    user_service: UserService,
    settings: Settings,
    state: FSMContext,
    branch: Branch,
) -> None:
    """Foydalanuvchini ro'yxatdan o'tkazadi va asosiy menyuni chiqaradi."""
    await state.clear()
    tg_user = message.from_user
    if tg_user is not None:
        await user_service.register(
            telegram_id=tg_user.id,
            full_name=tg_user.full_name,
            username=tg_user.username,
        )

    first_name = tg_user.first_name if tg_user else _("Foydalanuvchi")
    await message.answer(
        _(
            "👋 <b>Assalomu alaykum, {name}!</b>\n\n"
            "📖 <b>Qarz Daftar</b> botiga xush kelibsiz.\n"
            "🏢 <b>Filial:</b> {branch} (almashtirish: <b>{branch_button}</b>)\n"
            "Kerakli bo'limni tanlang:",
            name=esc_html(first_name),
            branch=esc_html(branch.title),
            branch_button=_(BRANCH_BUTTON_TEXT),
        ),
        reply_markup=get_main_menu_keyboard(settings.web_app_url),
    )


@router.message(Command("help"))
@router.message(F.text.in_(all_variants(HELP_BUTTON_TEXT)))
async def cmd_help(message: Message) -> None:
    """Yordam menyusini ko'rsatadi."""
    await message.answer(
        _(
            "🛠 <b>Qarz Daftar Boti — Yordam:</b>\n\n"
            "• <b>📋 Qarzlar jadvali</b> — Barcha mijozlar va qarzdorlar ro'yxati, "
            "to'liq qarz tarixi va hisobotlari.\n"
            "• <b>➕ Yaratish</b> — Yangi qarz yozuvi kiritish (tovar, "
            "exchange/ayirboshlash, berilgan pul va hisob-kitob).\n"
            "• <b>💰 Qarz to'lovi</b> — Mijozlarning qarzini to'liq yoki qisman yopish.\n\n"
            "• <b>{branch_button}</b> — Filialni almashtirish (har filialning "
            "ma'lumotlari alohida).\n"
            "• <b>{settings_button}</b> — Interfeys tili.\n"
            "• /start — Asosiy menyuni qayta ochish",
            branch_button=_(BRANCH_BUTTON_TEXT),
            settings_button=_(SETTINGS_BUTTON_TEXT),
        )
    )


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Hech qanday harakat bajarmaydigan indikator tugma."""
    await callback.answer()
