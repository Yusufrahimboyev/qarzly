from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message

from bot.application.services.user_service import UserService
from bot.presentation.keyboards.start_kb import get_main_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user_service: UserService) -> None:
    tg_user = message.from_user
    if tg_user is not None:
        await user_service.register(
            telegram_id=tg_user.id,
            full_name=tg_user.full_name,
            username=tg_user.username,
        )

    first_name = tg_user.first_name if tg_user else "Foydalanuvchi"
    await message.answer(
        f"👋 <b>Salom, {first_name}!</b>\n\n"
        "Aiogram 3.x va Async SQLite bilan ishlaydigan botingiz tayyor!",
        reply_markup=get_main_keyboard(),
    )


@router.message(Command("help"))
@router.message(F.text == "ℹ️ Yordam")
async def cmd_help(message: Message) -> None:
    await message.answer(
        "🛠 <b>Yordam menyusi:</b>\n"
        "• /start — Botni qayta ishga tushirish\n"
        "• /help — Yordam xabari"
    )
