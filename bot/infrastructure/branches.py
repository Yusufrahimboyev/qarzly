"""Filiallar konteyneri: har filial o'z bazasi va servislari bilan.

Servis va repository'lar "bitta baza" uchun yozilgan va o'zgarmagan — filialga
bo'lish faqat ularni ulash qatlamida: har filial uchun alohida `Database`
(pool), repo'lar va servislar yaratilib, shu yerda yig'iladi.
"""
from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.application.services.user_service import UserService
from bot.application.services.voice_debt_service import VoiceDebtService
from bot.infrastructure.database.repositories.idempotency_repository import (
    IdempotencyStore,
)


@dataclass(frozen=True, slots=True)
class Branch:
    """Bitta filial: o'z bazasi va shu bazaga ulangan servislar."""

    code: str
    title: str
    client_service: ClientService
    debt_service: DebtService
    user_service: UserService
    database: Any = None
    idempotency_store: IdempotencyStore | None = None
    voice_debt_service: VoiceDebtService | None = None


class BranchRegistry:
    """Filiallarni kod bo'yicha topish (tartib saqlanadi)."""

    def __init__(self, branches: list[Branch], default: str) -> None:
        if not branches:
            raise ValueError("Kamida bitta filial kerak.")
        self._branches = {branch.code: branch for branch in branches}
        if default not in self._branches:
            raise ValueError(f"Asosiy filial ({default}) ro'yxatda yo'q.")
        self._default = default

    @property
    def default(self) -> Branch:
        return self._branches[self._default]

    def get(self, code: str | None) -> Branch | None:
        """Kod bo'yicha filial; noma'lum kod uchun None."""
        return self._branches.get(code or "")

    def __iter__(self) -> Iterator[Branch]:
        return iter(self._branches.values())

    def __len__(self) -> int:
        return len(self._branches)
