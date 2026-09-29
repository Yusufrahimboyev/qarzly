"""Application qatlami: VoiceDebtService.

Ovozli xabar → matn (ASR) → qarz qoralamasi → mavjud mijozga moslash (Laya).
Saqlash bu yerda emas: natija qarz yaratish ustasiga beriladi va admin
tasdiqlagandan keyingina bazaga yoziladi.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from typing import Any, Protocol

from bot.application.common.voice_parser import VoiceDebtDraft, parse_voice_debt
from bot.application.services.client_service import ClientService
from bot.domain.entities.client import Client

logger = logging.getLogger(__name__)

NEW_CLIENT_CHOICE = "Yangi mijoz"
MIN_MATCH_CONFIDENCE = 0.7
_MAX_CANDIDATES = 10
_MIN_NAME_SIMILARITY = 0.75


class LayaGateway(Protocol):
    async def transcribe(self, audio: bytes, content_type: str = ...) -> str: ...

    async def choose(
        self, state: dict[str, Any], instructions: str, choices: list[str]
    ) -> tuple[str, float]: ...


@dataclass(frozen=True, slots=True)
class VoiceDebt:
    draft: VoiceDebtDraft
    client_name: str
    client_phone: str
    is_existing_client: bool
    # Tanlanmagan, lekin ismi o'xshash mijozlar — admin tugma bilan almashtirishi uchun
    similar_clients: list[Client] = field(default_factory=list)


class VoiceDebtService:
    """Ovozli xabardan qarz qoralamasini tayyorlaydi."""

    def __init__(self, laya: LayaGateway, client_service: ClientService) -> None:
        self._laya = laya
        self._clients = client_service

    async def transcribe(self, audio: bytes) -> str:
        return await self._laya.transcribe(audio)

    async def prepare(self, transcript: str) -> VoiceDebt:
        """Transkriptni qoralamaga aylantiradi va mijozni aniqlaydi.

        Raises:
            VoiceParseError: majburiy maydonlar topilmasa.
        """
        draft = parse_voice_debt(transcript)
        candidates = _similar_clients(
            draft.client_name, await self._clients.get_all_clients()
        )
        client = await self._match_client(draft.client_name, transcript, candidates)
        similar = [c for c in candidates if c is not client]
        if client is None:
            return VoiceDebt(draft, draft.client_name, "", False, similar)
        return VoiceDebt(draft, client.full_name, client.phone, True, similar)

    async def _match_client(
        self, spoken_name: str, transcript: str, candidates: list[Client]
    ) -> Client | None:
        """Aytilgan ismga o'xshash mijozlardan Laya bittasini tanlaydi.

        Laya ishonchi past bo'lsa yoki xizmat ishlamasa — yangi mijoz (None).
        """
        if not candidates:
            return None

        labels = {client_label(c): c for c in candidates}
        try:
            choice, confidence = await self._laya.choose(
                state={"aytilgan_ism": spoken_name, "transkript": transcript},
                instructions=(
                    "Aytilgan ism qaysi mavjud mijozga tegishli? "
                    f"Hech biriga mos kelmasa '{NEW_CLIENT_CHOICE}' ni tanlang."
                ),
                choices=[*labels, NEW_CLIENT_CHOICE],
            )
        except Exception:
            logger.exception("Laya mijozni tanlay olmadi — yangi mijoz deb olinadi")
            return None

        if choice == NEW_CLIENT_CHOICE or confidence < MIN_MATCH_CONFIDENCE:
            return None
        return labels.get(choice)


def _similar_clients(spoken_name: str, clients: list[Client]) -> list[Client]:
    """Ismi aytilgan ismga o'xshash mijozlar (eng o'xshashi birinchi)."""
    spoken = spoken_name.lower()
    spoken_first = spoken.split()[0] if spoken else ""

    def score(client: Client) -> float:
        name = client.full_name.lower()
        first = name.split()[0] if name else ""
        return max(
            SequenceMatcher(None, spoken, name).ratio(),
            SequenceMatcher(None, spoken_first, first).ratio(),
        )

    scored = sorted(((score(c), c) for c in clients), key=lambda item: -item[0])
    return [c for s, c in scored if s >= _MIN_NAME_SIMILARITY][:_MAX_CANDIDATES]


def client_label(client: Client) -> str:
    return f"{client.full_name} ({client.phone})" if client.phone else client.full_name
