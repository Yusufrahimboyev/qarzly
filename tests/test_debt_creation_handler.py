"""Qarz yaratish ustasi: tugmali sana, tovar katalogi, raqam klaviaturasi, tahrirlash."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from pydantic import SecretStr

from bot.application.common.formatters import today
from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.core.config import Settings
from bot.domain.entities.currency import Currency
from bot.presentation.common.product_catalog import akkum_sizes, build_product_name
from bot.presentation.handlers.debt_creation import (
    cb_akkum_size,
    cb_confirm_create_debt,
    cb_create_back,
    cb_date_day,
    cb_date_month,
    cb_date_year,
    cb_edit_delete,
    cb_edit_redo,
    cb_exchange_no,
    cb_given_money_no,
    cb_more_products_no,
    cb_numpad,
    cb_prodcur_usd,
    cb_product_brand,
    cb_product_type,
    cb_skip_client_phone,
    process_client_name,
    process_product_size,
    start_debt_creation,
)
from bot.presentation.states.debt_creation import DebtCreationStates as S
from tests.test_report_export_handler import StubCallback
from tests.test_voice_debt_handler import VoiceStubMessage


@pytest.fixture
def state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))


def msg(text: str = "") -> VoiceStubMessage:
    return VoiceStubMessage.build(text)


async def press(message: VoiceStubMessage, handler, state: FSMContext, data: str) -> StubCallback:
    callback = StubCallback(message, data=data)
    await handler(callback, state)
    return callback


async def type_number(message, state, digits: str) -> None:
    for key in digits:
        await press(message, cb_numpad, state, f"np:{key}")
    await press(message, cb_numpad, state, "np:ok")


async def fill_until_summary(state: FSMContext) -> VoiceStubMessage:
    """Sana → ism → telefonsiz → Akkumulyator Jazz 60L но × 2 × 120 $."""
    start = msg()
    await start_debt_creation(start, state, SimpleNamespace(title="Mangit"))
    assert "Filial:</b> Mangit" in start.last_answer
    assert "YANGI QARZ" not in start.last_answer and "bosqich" not in start.last_answer

    m = msg()
    year = today().year
    await press(m, cb_date_day, state, "dday:5")
    assert "Yanvar (01)" in [b.text for row in m._markup.inline_keyboard for b in row]
    await press(m, cb_date_month, state, "dmon:3")
    assert m.button_data[:2] == [f"dyear:{year}", f"dyear:{year + 1}"]
    await press(m, cb_date_year, state, f"dyear:{year}")
    assert (await state.get_data())["debt_date"] == f"05.03.{year}"
    assert "ismini kiriting" in m.last_answer

    await process_client_name(msg("Anvar"), state)
    await press(m, cb_skip_client_phone, state, "skip_client_phone")
    await press(m, cb_product_type, state, "ptype:akkum")
    assert m.button_data[:4] == ["pbrand:0", "pbrand:1", "pbrand:2", "pbrand:3"]
    await press(m, cb_product_brand, state, "pbrand:0")
    assert m.button_data[5] == "psize:5"  # Jazz: 6-razmer = "60L но"
    await press(m, cb_akkum_size, state, "psize:5")
    await type_number(m, state, "2")
    await press(m, cb_prodcur_usd, state, "prodcur_usd")
    assert await state.get_state() == S.waiting_product_price.state
    await type_number(m, state, "120")
    return m


async def test_full_flow_saves_debt(state, client_repo, debt_repo, payment_repo) -> None:
    m = await fill_until_summary(state)

    summary = m.last_answer
    assert "Filial:</b> Mangit" in summary
    assert "Qarz oluvchi:</b> Anvar" in summary
    assert "Akkumulyator Jazz 60L но" in summary
    assert "2 × 120 $ = 240 $" in summary
    assert m.button_data == [
        "more_products_yes", "edit_products", "more_products_no", "cancel_creation",
    ]

    clients = ClientService(client_repo, debt_repo)
    debts = DebtService(clients=client_repo, debts=debt_repo, payments=payment_repo)
    settings = Settings(bot_token=SecretStr("1:x"), admin_ids=[1], database_url=SecretStr("pg://x"))
    await press(m, cb_more_products_no, state, "more_products_no")
    await press(m, cb_exchange_no, state, "exchange_no")
    await press(m, cb_given_money_no, state, "given_money_no")
    await cb_confirm_create_debt(StubCallback(m), state, clients, debts, settings)

    [client] = await clients.get_all_clients()
    [debt] = await debt_repo.get_all_by_client_id(client.id)
    assert (debt.remaining_debt, debt.currency) == (240, Currency.USD)


async def test_numpad_edits_and_rejects_zero(state) -> None:
    await state.set_state(S.waiting_product_quantity)
    await state.update_data(product_name="Shina Kumho R16", _np="")
    m = msg()

    for key in ("0", "4", "5", "del", "000"):
        await press(m, cb_numpad, state, f"np:{key}")
    assert (await state.get_data())["_np"] == "4000"
    await press(m, cb_numpad, state, "np:clr")
    callback = await press(m, cb_numpad, state, "np:ok")

    assert "Noto'g'ri" in callback.alert
    assert await state.get_state() == S.waiting_product_quantity.state


async def test_impossible_date_returns_to_day(state) -> None:
    await state.set_state(S.waiting_date)
    m = msg()
    await press(m, cb_date_day, state, "dday:31")
    await press(m, cb_date_month, state, "dmon:2")
    callback = await press(m, cb_date_year, state, f"dyear:{today().year}")

    assert "Bunday sana yo'q" in callback.alert
    assert await state.get_state() == S.waiting_date.state


async def test_back_from_year_goes_to_month(state) -> None:
    await state.set_state(S.waiting_date)
    m = msg()
    await press(m, cb_date_day, state, "dday:1")
    await press(m, cb_date_month, state, "dmon:1")
    await press(m, cb_create_back, state, "create_back")

    assert await state.get_state() == S.waiting_date_month.state
    assert "Oyni tanlang" in m.last_answer


async def test_edit_redo_replaces_in_place_and_delete(state) -> None:
    m = await fill_until_summary(state)

    await press(m, cb_edit_redo, state, "edit_redo:0")
    await press(m, cb_product_type, state, "ptype:shina")
    await press(m, cb_product_brand, state, "pbrand:2")
    await process_product_size(msg("R16"), state)
    await type_number(m, state, "4")
    await press(m, cb_prodcur_usd, state, "prodcur_usd")
    await type_number(m, state, "50")

    [product] = (await state.get_data())["_products"]
    assert (product.name, product.quantity, product.price_per_unit) == ("Shina Kumho R16", 4, 50)

    await press(m, cb_edit_delete, state, "edit_del:0")
    assert (await state.get_data())["_products"] == []
    assert await state.get_state() == S.waiting_product_type.state


def test_build_product_name() -> None:
    assert build_product_name("shina", "Kumho", "R16") == "Shina Kumho R16"
    assert build_product_name("diska", "Qo'qon diska", "R15") == "Qo'qon diska R15"
    assert build_product_name("diska", "Литий диска", "R17") == "Литий диска R17"
    assert build_product_name("akkum", "Jazz", "60L но") == "Akkumulyator Jazz 60L но"


def test_akkum_sizes_per_brand() -> None:
    assert akkum_sizes("Atlant") == [
        "60/45L сз", "60/45R сз", "90/77L сз", "132/105 ач", "190/150 ач",
    ]
    assert akkum_sizes("Wolter") == ["60R ач"]
    assert akkum_sizes("Qaynar") == akkum_sizes("Jazz")  # vaqtincha
    assert akkum_sizes("Boshqa brend")[0] == "35Ah"  # qo'lda yozilgan — umumiy
