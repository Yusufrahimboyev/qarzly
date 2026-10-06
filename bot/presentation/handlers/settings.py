"""Presentation qatlami: sozlamalar (interfeys tili).

Til bot va Mini App uchun umumiy — `user_settings` jadvalida saqlanadi.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.core.config import Settings
from bot.i18n import LANGUAGES, _, all_variants, get_language, set_language
from bot.infrastructure.database.repositories.language_repository import LanguageStore
from bot.presentation.keyboards.main_menu_kb import SETTINGS_BUTTON_TEXT, get_main_menu_keyboard

router = Router()


def _language_keyboard(current: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(
                text=f"✅ {title}" if code == current else title,
                callback_data=f"lang:{code}",
            )]
            for code, title in LANGUAGES.items()
        ]
    )


@router.message(Command("settings"))
@router.message(F.text.in_(all_variants(SETTINGS_BUTTON_TEXT)))
async def show_settings(message: Message, state: FSMContext) -> None:
    """Sozlamalar: til tanlash."""
    await state.clear()
    await message.answer(
        _("⚙️ <b>Sozlamalar</b>\n\n🌐 Interfeys tilini tanlang:"),
        reply_markup=_language_keyboard(get_language()),
    )


@router.callback_query(F.data.startswith("lang:"))
async def cb_select_language(
    callback: CallbackQuery,
    language_store: LanguageStore,
    settings: Settings,
) -> None:
    """Tanlangan tilni saqlaydi va menyuni shu tilda qayta chiqaradi."""
    language = (callback.data or "").split(":", 1)[1]
    if language not in LANGUAGES:
        await callback.answer()
        return

    await language_store.set(callback.from_user.id, language)
    set_language(language)
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("✅ <b>Til o'zgartirildi:</b> {language}", language=LANGUAGES[language])
        )
        await callback.message.answer(
            _("Asosiy menyu:"),
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )
    await callback.answer()
