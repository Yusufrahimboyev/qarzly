"""Presentation qatlami: /start, /help va asosiy menyu handler'lari."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import esc_html
from bot.application.services.user_service import UserService
from bot.core.config import Settings
from bot.presentation.keyboards.main_menu_kb import get_main_menu_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    user_service: UserService,
    settings: Settings,
    state: FSMContext,
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

    first_name = tg_user.first_name if tg_user else "Foydalanuvchi"
    await message.answer(
        f"👋 <b>Assalomu alaykum, {esc_html(first_name)}!</b>\n\n"
        "📖 <b>Qarz Daftar</b> botiga xush kelibsiz.\n"
        "Kerakli bo'limni tanlang:",
        reply_markup=get_main_menu_keyboard(settings.web_app_url),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(message: Message) -> None:
    """Yordam menyusini ko'rsatadi."""
    await message.answer(
        "🛠 <b>Qarz Daftar Boti — Yordam:</b>\n\n"
        "• <b>📋 Qarzlar jadvali</b> — Barcha mijozlar va qarzdorlar ro'yxati, "
        "to'liq qarz tarixi va hisobotlari.\n"
        "• <b>➕ Yaratish</b> — Yangi qarz yozuvi kiritish (tovar, "
        "exchange/ayirboshlash, berilgan pul va hisob-kitob).\n"
        "• <b>💰 Qarz to'lovi</b> — Mijozlarning qarzini to'liq yoki qisman yopish.\n\n"
        "• /start — Asosiy menyuni qayta ochish"
    )


@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    """Hech qanday harakat bajarmaydigan indikator tugma."""
    await callback.answer()
