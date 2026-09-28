"""Ovozli xabar → qarz yaratish ustasi → tasdiqlash → bazaga yozish oqimi."""
from __future__ import annotations

import io
from datetime import datetime

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Voice
from pydantic import SecretStr

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.voice_debt_service import VoiceDebtService
from bot.core.config import Settings
from bot.domain.entities.currency import Currency
from bot.presentation.handlers.debt_creation import (
    cb_confirm_create_debt,
    cb_exchange_no,
    cb_given_money_no,
    cb_more_products_no,
    cb_prodcur_usd,
)
from bot.presentation.handlers.voice_debt import MAX_VOICE_SECONDS, process_voice_debt
from bot.presentation.states.debt_creation import DebtCreationStates
from tests.test_report_export_handler import StubCallback, StubMessage
from tests.test_voice_debt_service import FakeLaya


class StubBot:
    async def download(self, file) -> io.BytesIO:
        return io.BytesIO(file.file_id.encode())


def voice_message(transcript: str, duration: int = 5) -> StubMessage:
    """FakeLaya audio baytlarini matn sifatida qaytaradi — file_id = transkript."""
    return StubMessage(
        message_id=1,
        date=datetime.now(),
        chat=Chat(id=1, type="private"),
        voice=Voice(file_id=transcript, file_unique_id="u", duration=duration),
    )


@pytest.fixture
def state() -> FSMContext:
    return FSMContext(storage=MemoryStorage(), key=StorageKey(bot_id=1, chat_id=1, user_id=1))


@pytest.fixture
def services(client_repo, debt_repo, payment_repo):
    clients = ClientService(client_repo, debt_repo)
    debts = DebtService(clients=client_repo, debts=debt_repo, payments=payment_repo)
    return clients, debts, VoiceDebtService(FakeLaya(), clients)


@pytest.fixture
def settings() -> Settings:
    return Settings(bot_token=SecretStr("1:x"), admin_ids=[1], database_url=SecretStr("pg://x"))


async def test_voice_to_saved_debt(state, services, settings, debt_repo) -> None:
    clients, debts, voice = services
    message = voice_message("Anvarga ikkita shina besh yuz ming so'mdan")

    await process_voice_debt(message, state, StubBot(), voice)

    assert "Qo'shildi" in message.last_answer
    assert await state.get_state() == DebtCreationStates.waiting_more_products.state

    # Qolgan qadamlar mavjud usta orqali: tovar yo'q → exchange yo'q → pul yo'q → tasdiq
    await cb_more_products_no(StubCallback(message), state)
    await cb_exchange_no(StubCallback(message), state)
    await cb_given_money_no(StubCallback(message), state)
    await cb_confirm_create_debt(StubCallback(message), state, clients, debts, settings)

    assert "MUVAFFAQIYATLI SAQLANDI" in message.answers[-2]
    [client] = await clients.get_all_clients()
    [debt] = await debt_repo.get_all_by_client_id(client.id)
    assert client.full_name == "Anvar"
    assert (debt.remaining_debt, debt.currency) == (1_000_000, Currency.UZS)


async def test_unknown_currency_asks_with_existing_keyboard(state, services) -> None:
    _, _, voice = services
    message = voice_message("Alisherga akkumulyator 120")

    await process_voice_debt(message, state, StubBot(), voice)
    assert await state.get_state() == DebtCreationStates.waiting_product_currency.state

    await cb_prodcur_usd(StubCallback(message), state)

    [product] = (await state.get_data())["_products"]
    assert (product.name, product.price_per_unit, product.currency) == (
        "Akkumulyator", 120, Currency.USD,
    )


async def test_unparseable_voice_shows_transcript_and_keeps_idle(state, services) -> None:
    _, _, voice = services
    message = voice_message("salom qalaysiz")

    await process_voice_debt(message, state, StubBot(), voice)

    assert "salom qalaysiz" in message.last_answer
    assert "Aniqlanmadi" in message.last_answer
    assert await state.get_state() is None


async def test_rejects_long_voice_and_disabled_feature(state, services) -> None:
    _, _, voice = services
    long_message = voice_message("x", duration=MAX_VOICE_SECONDS + 1)
    await process_voice_debt(long_message, state, StubBot(), voice)
    assert "soniyadan" in long_message.last_answer

    disabled = voice_message("x")
    await process_voice_debt(disabled, state, StubBot(), None)
    assert "sozlanmagan" in disabled.last_answer
