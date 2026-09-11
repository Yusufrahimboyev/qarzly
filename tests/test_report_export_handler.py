"""Excel hisobot FSM oqimi uchun testlar.

Handler'lar to'g'ridan-to'g'ri chaqiriladi (Telegram'siz): Message o'rniga
faqat kerakli metodlarni (`answer`, `answer_document`) yozib boruvchi stub
ishlatiladi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message

from bot.application.common.formatters import today
from bot.application.services.debt_service import DebtService
from bot.domain.entities.client import Client
from bot.domain.entities.debt import DebtProduct
from bot.presentation.handlers.report_export import (
    cb_export_date_today,
    process_end_date,
    process_start_date,
)
from bot.presentation.states.report_export import ReportExportStates


@dataclass
class SentDocument:
    filename: str
    content: bytes
    caption: str


class StubMessage(Message):
    """Haqiqiy `Message`, lekin yuborish o'rniga chaqiruvlarni yozib boradi.

    Handler'lar `isinstance(..., Message)` tekshiruvidan o'tishi uchun aynan
    `Message` vorisi bo'lishi shart.
    """

    def model_post_init(self, context: object) -> None:
        super().model_post_init(context)
        object.__setattr__(self, "_answers", [])
        object.__setattr__(self, "_documents", [])

    @classmethod
    def build(cls, text: str = "") -> StubMessage:
        return cls(
            message_id=1,
            date=datetime.now(),
            chat=Chat(id=1, type="private"),
            text=text,
        )

    async def answer(self, text: str, **_kwargs) -> StubMessage:
        self._answers.append(text)
        return self

    async def answer_document(self, document, caption: str = "", **_kwargs) -> None:
        self._documents.append(
            SentDocument(
                filename=document.filename,
                content=document.data,
                caption=caption,
            )
        )

    async def edit_text(self, text: str, **_kwargs) -> StubMessage:
        self._answers.append(text)
        return self

    async def delete(self) -> None:
        return None

    @property
    def answers(self) -> list[str]:
        return self._answers

    @property
    def documents(self) -> list[SentDocument]:
        return self._documents

    @property
    def last_answer(self) -> str:
        return self._answers[-1] if self._answers else ""


@dataclass
class StubCallback:
    """`answer()` va `message` maydoni bo'lgan minimal CallbackQuery."""

    message: StubMessage
    answered: bool = False

    async def answer(self, *_args, **_kwargs) -> None:
        self.answered = True


@pytest.fixture
def state() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=1, chat_id=1, user_id=1),
    )


@pytest.fixture
def service(client_repo, debt_repo, payment_repo) -> DebtService:
    return DebtService(client_repo, debt_repo, payment_repo)


# ==========================================
# Boshlanish sanasi
# ==========================================


async def test_invalid_start_date_keeps_state(state):
    await state.set_state(ReportExportStates.waiting_start_date)
    message = StubMessage.build(text="kecha")

    await process_start_date(message, state)

    assert "format" in message.last_answer.lower()
    assert await state.get_state() == ReportExportStates.waiting_start_date.state


async def test_future_start_date_is_rejected(state):
    await state.set_state(ReportExportStates.waiting_start_date)
    tomorrow = today() + timedelta(days=1)
    message = StubMessage.build(text=tomorrow.strftime("%d.%m.%Y"))

    await process_start_date(message, state)

    assert "bugundan keyin" in message.last_answer
    assert await state.get_state() == ReportExportStates.waiting_start_date.state


async def test_valid_start_date_moves_to_end_date(state):
    await state.set_state(ReportExportStates.waiting_start_date)
    message = StubMessage.build(text="01.01.2026")

    await process_start_date(message, state)

    assert await state.get_state() == ReportExportStates.waiting_end_date.state
    assert (await state.get_data())["date_from"] == "2026-01-01"
    assert "Tugash sanasini kiriting" in message.last_answer


# ==========================================
# Tugash sanasi — asosiy talab
# ==========================================


async def test_future_end_date_is_rejected(state, service):
    await state.set_state(ReportExportStates.waiting_end_date)
    await state.update_data(date_from="2026-01-01")
    tomorrow = today() + timedelta(days=1)
    message = StubMessage.build(text=tomorrow.strftime("%d.%m.%Y"))

    await process_end_date(message, state, service)

    assert "bugundan keyin" in message.last_answer
    assert not message.documents
    # Foydalanuvchi hali ham tugash sanasini kiritish bosqichida.
    assert await state.get_state() == ReportExportStates.waiting_end_date.state


async def test_end_date_today_is_accepted(state, service):
    await state.set_state(ReportExportStates.waiting_end_date)
    await state.update_data(date_from="2026-01-01")
    message = StubMessage.build(text=today().strftime("%d.%m.%Y"))

    await process_end_date(message, state, service)

    assert len(message.documents) == 1
    assert await state.get_state() is None


async def test_end_date_before_start_is_rejected(state, service):
    await state.set_state(ReportExportStates.waiting_end_date)
    await state.update_data(date_from="2026-05-10")
    message = StubMessage.build(text="01.05.2026")

    await process_end_date(message, state, service)

    assert "Boshlanish sanasi" in message.last_answer
    assert not message.documents


async def test_expired_session_asks_to_restart(state, service):
    await state.set_state(ReportExportStates.waiting_end_date)
    message = StubMessage.build(text="01.06.2026")

    await process_end_date(message, state, service)

    assert "Sessiya eskirgan" in message.last_answer
    assert await state.get_state() is None


# ==========================================
# Fayl mazmuni
# ==========================================


async def test_generated_file_covers_inclusive_range(
    state,
    service,
    client_repo,
):
    client = await client_repo.add(Client(full_name="Akmal", phone="+998901234567"))
    assert client.id is not None
    for debt_date in (date(2026, 1, 1), date(2026, 1, 31), date(2026, 2, 1)):
        await service.create_debt(
            client_id=client.id,
            debt_date=debt_date,
            products=[DebtProduct(name="Moy", price_per_unit=100_000)],
        )

    await state.set_state(ReportExportStates.waiting_end_date)
    await state.update_data(date_from="2026-01-01")
    message = StubMessage.build(text="31.01.2026")

    await process_end_date(message, state, service)

    (document,) = message.documents
    assert document.filename == "qarz-hisobot_01.01.2026_31.01.2026.xlsx"
    assert document.content[:2] == b"PK"  # .xlsx — zip konteyner

    # Chegara sanalari kiradi: 01.01 va 31.01 — 2 ta qarz, 01.02 kirmaydi.
    assert "200 000 so'm" in document.caption
    assert "Qarz yozuvlari:</b> 2 ta" in document.caption


async def test_today_button_generates_report(state, service):
    """"📅 Bugun" tugmasi tugash sanasini bugun qilib belgilaydi."""
    await state.set_state(ReportExportStates.waiting_end_date)
    await state.update_data(date_from="2026-01-01")
    callback = StubCallback(message=StubMessage.build())

    await cb_export_date_today(callback, state, service)

    assert callback.answered
    (document,) = callback.message.documents
    assert document.filename.endswith(f"{today():%d.%m.%Y}.xlsx")
    assert await state.get_state() is None
