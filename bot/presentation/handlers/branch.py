"""Presentation qatlami: filialni almashtirish handler'lari."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import esc_html
from bot.core.config import Settings
from bot.infrastructure.branches import Branch, BranchRegistry
from bot.infrastructure.database.repositories.branch_preference_repository import (
    BranchPreferenceStore,
)
from bot.presentation.keyboards.main_menu_kb import (
    BRANCH_BUTTON_TEXT,
    get_branch_keyboard,
    get_main_menu_keyboard,
)

router = Router()


@router.message(Command("branch"))
@router.message(F.text == BRANCH_BUTTON_TEXT)
async def show_branches(
    message: Message,
    state: FSMContext,
    branch: Branch,
    branch_registry: BranchRegistry,
) -> None:
    """Filiallar ro'yxatini ko'rsatadi (joriysi belgilangan)."""
    await state.clear()
    await message.answer(
        f"🏢 <b>Joriy filial:</b> {esc_html(branch.title)}\n\n"
        "Almashtirish uchun filialni tanlang. Har filialning ma'lumotlari "
        "alohida saqlanadi:",
        reply_markup=get_branch_keyboard(
            [(b.code, b.title) for b in branch_registry], branch.code
        ),
    )


@router.callback_query(F.data.startswith("branch:"))
async def cb_select_branch(
    callback: CallbackQuery,
    state: FSMContext,
    branch_registry: BranchRegistry,
    branch_preferences: BranchPreferenceStore,
    settings: Settings,
) -> None:
    """Tanlangan filialni saqlaydi va jarayonlarni (FSM) tozalaydi."""
    selected = branch_registry.get((callback.data or "").split(":", 1)[1])
    if selected is None:
        await callback.answer("Noma'lum filial.", show_alert=True)
        return

    # Yarim qolgan qarz/to'lov jarayoni boshqa filialga o'tib ketmasligi uchun.
    await state.clear()
    await branch_preferences.set(callback.from_user.id, selected.code)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            f"✅ <b>Filial almashtirildi:</b> {esc_html(selected.title)}"
        )
        await callback.message.answer(
            f"🏢 Endi <b>{esc_html(selected.title)}</b> filiali bilan ishlaysiz.",
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )
    await callback.answer()
