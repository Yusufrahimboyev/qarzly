"""Presentation qatlami: filialni almashtirish handler'lari."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.application.common.formatters import esc_html
from bot.core.config import Settings
from bot.i18n import _, all_variants
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
@router.message(F.text.in_(all_variants(BRANCH_BUTTON_TEXT)))
async def show_branches(
    message: Message,
    state: FSMContext,
    branch: Branch,
    branch_registry: BranchRegistry,
) -> None:
    """Filiallar ro'yxatini ko'rsatadi (joriysi belgilangan)."""
    await state.clear()
    await message.answer(
        _(
            "🏢 <b>Joriy filial:</b> {branch}\n\n"
            "Almashtirish uchun filialni tanlang. Har filialning ma'lumotlari "
            "alohida saqlanadi:",
            branch=esc_html(branch.title),
        ),
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
        await callback.answer(_("Noma'lum filial."), show_alert=True)
        return

    # Yarim qolgan qarz/to'lov jarayoni boshqa filialga o'tib ketmasligi uchun.
    await state.clear()
    await branch_preferences.set(callback.from_user.id, selected.code)

    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _("✅ <b>Filial almashtirildi:</b> {branch}", branch=esc_html(selected.title))
        )
        await callback.message.answer(
            _("🏢 Endi <b>{branch}</b> filiali bilan ishlaysiz.", branch=esc_html(selected.title)),
            reply_markup=get_main_menu_keyboard(settings.web_app_url),
        )
    await callback.answer()
