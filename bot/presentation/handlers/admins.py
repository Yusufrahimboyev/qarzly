"""Presentation qatlami: Sozlamalar → Adminlar (qo'shish va o'chirish).

Ro'yxat uchala filial boti uchun bitta: shu yerda qo'shilgan admin Nukus va
Lassa botlariga ham kiradi. `.env` dagi asosiy adminlarni o'chirib bo'lmaydi.
"""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.application.common.formatters import esc_html
from bot.application.services.admin_service import AdminService
from bot.domain.entities.admin import Admin
from bot.i18n import _
from bot.presentation.states.admins import AdminStates

router = Router()


def _label(admin: Admin) -> str:
    return f"{admin.full_name} ({admin.telegram_id})" if admin.full_name else str(admin.telegram_id)


def _list_view(admins: list[Admin], me: int) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        _("👥 <b>Adminlar</b>"),
        _("Ro'yxat uchala filial boti uchun umumiy."),
        "",
    ]
    for admin in admins:
        mark = "👑" if admin.is_root else "👤"
        you = _(" (siz)") if admin.telegram_id == me else ""
        lines.append(f"{mark} {esc_html(_label(admin))}{you}")
    lines += ["", _("👑 — asosiy admin (.env), o'chirib bo'lmaydi.")]

    rows = [
        [InlineKeyboardButton(
            text=f"❌ {_label(a)}"[:60], callback_data=f"admins:del:{a.telegram_id}"
        )]
        for a in admins
        if not a.is_root and a.telegram_id != me
    ]
    rows.append([InlineKeyboardButton(text=_("➕ Admin qo'shish"), callback_data="admins:add")])
    return "\n".join(lines), InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_list(message: Message, admin_service: AdminService, me: int, *, edit: bool) -> None:
    text, keyboard = _list_view(await admin_service.list_admins(), me)
    if edit:
        await message.edit_text(text, reply_markup=keyboard)
    else:
        await message.answer(text, reply_markup=keyboard)


@router.callback_query(F.data == "admins:list")
async def cb_admins_list(
    callback: CallbackQuery, state: FSMContext, admin_service: AdminService
) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await _show_list(callback.message, admin_service, callback.from_user.id, edit=True)
    await callback.answer()


@router.callback_query(F.data == "admins:add")
async def cb_admins_add(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.waiting_id)
    if isinstance(callback.message, Message):
        await callback.message.answer(_(
            "➕ Yangi adminning <b>Telegram ID</b> sini yuboring.\n"
            "Xohlasangiz, ID dan keyin ismini ham yozing: <code>123456789 Ali</code>\n\n"
            "ID ni bilish uchun u odam @userinfobot ga /start yozsin."
        ))
    await callback.answer()


@router.message(AdminStates.waiting_id, F.text.regexp(r"^\s*\d+"))
async def msg_admin_id(
    message: Message, state: FSMContext, admin_service: AdminService
) -> None:
    raw_id, _sep, name = (message.text or "").strip().partition(" ")
    me = message.from_user.id if message.from_user else 0
    try:
        await admin_service.add(int(raw_id), name, added_by=me)
    except ValueError as exc:
        await message.answer(f"⚠️ {esc_html(str(exc))}")
        return
    await state.clear()
    await message.answer(_(
        "✅ Admin qo'shildi: <code>{id}</code>. Endi u Mangit, Nukus va Lassa "
        "botlaridan foydalana oladi (30 soniyagacha kechikishi mumkin).",
        id=raw_id,
    ))
    await _show_list(message, admin_service, me, edit=False)


@router.callback_query(F.data.startswith("admins:del:"))
async def cb_admins_delete(callback: CallbackQuery) -> None:
    telegram_id = (callback.data or "").rsplit(":", 1)[1]
    if isinstance(callback.message, Message):
        await callback.message.edit_text(
            _(
                "❓ <code>{id}</code> adminlikdan o'chirilsinmi? "
                "U uchala botdan ham chiqariladi.",
                id=telegram_id,
            ),
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text=_("✅ Ha, o'chirish"), callback_data=f"admins:delok:{telegram_id}"
                ),
                InlineKeyboardButton(text=_("↩️ Bekor qilish"), callback_data="admins:list"),
            ]]),
        )
    await callback.answer()


@router.callback_query(F.data.startswith("admins:delok:"))
async def cb_admins_delete_confirm(
    callback: CallbackQuery, admin_service: AdminService
) -> None:
    raw_id = (callback.data or "").rsplit(":", 1)[1]
    try:
        await admin_service.remove(int(raw_id), actor_id=callback.from_user.id)
    except ValueError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if isinstance(callback.message, Message):
        await _show_list(callback.message, admin_service, callback.from_user.id, edit=True)
    await callback.answer(_("Admin o'chirildi."))
