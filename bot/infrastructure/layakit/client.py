"""Infrastructure qatlami: LayaKit gateway HTTP klienti.

Ikki vazifa:
- `transcribe` — ovozli xabarni `/v1/transcribe` (GigaAM ASR) orqali matnga o'giradi;
- `choose` — Laya `/v1/decide` ga `choice` savolini yuboradi.

Tashqi API'ning shakli (URL, payload, javob) faqat shu faylda — servis
qatlami faqat `str` va `(tanlov, ishonch)` bilan ishlaydi.
"""
from __future__ import annotations

from typing import Any

import aiohttp


class LayaKitError(RuntimeError):
    """LayaKit bilan aloqa yoki javob formati xatosi."""


class LayaKitClient:
    """LayaKit gateway va ASR endpointi uchun asinxron klient."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout_seconds: int = 120,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = {"Authorization": f"Bearer {token}"}
        self._timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def transcribe(self, audio: bytes, content_type: str = "audio/ogg") -> str:
        """Audio baytlarni matnga o'giradi (body — raw audio, javob `{"text": ...}`)."""
        data = await self._post(
            f"{self._base_url}/v1/transcribe",
            data=audio,
            headers={"Content-Type": content_type},
        )
        text = data.get("text")
        if not isinstance(text, str):
            raise LayaKitError("ASR javobida 'text' maydoni yo'q.")
        return text.strip()

    async def choose(
        self,
        state: dict[str, Any],
        instructions: str,
        choices: list[str],
    ) -> tuple[str, float]:
        """Laya'dan variantlardan birini tanlashni so'raydi.

        Qaytaradi: (tanlangan variant, answer_confidence).
        """
        payload = {
            "model": "multilingual",
            "state": state,
            "questions": {
                "pick": {
                    "type": "choice",
                    "instructions": instructions,
                    # Laya variantlarni `criteria` da kutadi (`choices` → 422)
                    "criteria": choices,
                }
            },
        }
        data = await self._post(f"{self._base_url}/v1/decide", json=payload)
        try:
            answer = data["answers"]["pick"]
            choice = answer["choice"]
            confidence = float(answer.get("answer_confidence", 0.0))
        except (KeyError, TypeError, ValueError) as exc:
            raise LayaKitError(f"Laya javobi kutilgan formatda emas: {data!r}") from exc
        if choice not in choices:
            raise LayaKitError(f"Laya ro'yxatda yo'q variant qaytardi: {choice!r}")
        return choice, confidence

    async def _post(self, url: str, **kwargs: Any) -> dict[str, Any]:
        try:
            async with aiohttp.ClientSession(
                timeout=self._timeout, headers=self._headers
            ) as session:
                async with session.post(url, **kwargs) as response:
                    if response.status >= 400:
                        raise LayaKitError(f"{url} → HTTP {response.status}")
                    data = await response.json()
        except (aiohttp.ClientError, TimeoutError) as exc:
            raise LayaKitError(f"{url} bilan aloqa yo'q: {type(exc).__name__}") from exc
        if not isinstance(data, dict):
            raise LayaKitError("LayaKit javobi JSON obyekt emas.")
        return data
