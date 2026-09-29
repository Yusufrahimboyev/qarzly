"""VoiceDebtService uchun testlar (fake Laya gateway bilan)."""
from __future__ import annotations

from typing import Any

import pytest

from bot.application.services.client_service import ClientService
from bot.application.services.voice_debt_service import (
    NEW_CLIENT_CHOICE,
    VoiceDebtService,
)
from tests.conftest import FakeClientRepository, FakeDebtRepository


class FakeLaya:
    def __init__(self, answer: tuple[str, float] | Exception = ("", 0.0)) -> None:
        self.answer = answer
        self.calls: list[list[str]] = []

    async def transcribe(self, audio: bytes, content_type: str = "audio/ogg") -> str:
        return audio.decode()

    async def choose(
        self, state: dict[str, Any], instructions: str, choices: list[str]
    ) -> tuple[str, float]:
        self.calls.append(choices)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture
async def client_service(
    client_repo: FakeClientRepository, debt_repo: FakeDebtRepository
) -> ClientService:
    service = ClientService(client_repo, debt_repo)
    await service.get_or_create("Anvar Aliyev", "+998901234567")
    await service.get_or_create("Anvar Karimov", "")
    await service.get_or_create("Bekzod", "")
    return service


async def test_laya_picks_existing_client(client_service: ClientService) -> None:
    laya = FakeLaya(("Anvar Aliyev (+998901234567)", 0.93))
    result = await VoiceDebtService(laya, client_service).prepare(
        "Anvarga ikkita shina 500 ming so'm"
    )

    assert result.is_existing_client
    assert (result.client_name, result.client_phone) == ("Anvar Aliyev", "+998901234567")
    # Ikkinchi Anvar ham bor — admin ogohlantiriladi
    assert [c.full_name for c in result.similar_clients] == ["Anvar Karimov"]
    # Faqat o'xshash mijozlar va "Yangi mijoz" varianti yuboriladi
    assert set(laya.calls[0]) == {
        "Anvar Aliyev (+998901234567)", "Anvar Karimov", NEW_CLIENT_CHOICE,
    }


@pytest.mark.parametrize(
    "answer",
    [
        ("Anvar Aliyev (+998901234567)", 0.4),  # ishonch past
        (NEW_CLIENT_CHOICE, 0.99),
        RuntimeError("Laya is unavailable"),
    ],
)
async def test_falls_back_to_new_client(
    client_service: ClientService, answer: tuple[str, float] | Exception
) -> None:
    result = await VoiceDebtService(FakeLaya(answer), client_service).prepare(
        "Anvarga shina 500 ming so'm"
    )

    assert not result.is_existing_client
    assert (result.client_name, result.client_phone) == ("Anvar", "")


async def test_skips_laya_when_no_similar_client(client_service: ClientService) -> None:
    laya = FakeLaya()
    result = await VoiceDebtService(laya, client_service).prepare("Zafarga disk 100 dollar")

    assert laya.calls == []
    assert result.client_name == "Zafar"
    assert result.similar_clients == []
    assert result.draft.price_per_unit == 100
