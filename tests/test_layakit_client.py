"""LayaKitClient'ning HTTP kontrakti — lokal aiohttp server ustida."""
from __future__ import annotations

from typing import Any

import pytest
from aiohttp import web
from aiohttp.test_utils import TestServer

from bot.infrastructure.layakit.client import LayaKitClient, LayaKitError

TOKEN = "secret-token"


@pytest.fixture
async def gateway():
    received: dict[str, Any] = {}
    decide_response: dict[str, Any] = {
        "answers": {"pick": {"type": "choice", "choice": "Anvar", "answer_confidence": 0.91}},
        "routing": {"model": "multilingual"},
    }

    async def transcribe(request: web.Request) -> web.Response:
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return web.json_response({"detail": "invalid bearer token"}, status=401)
        received["audio"] = await request.read()
        received["content_type"] = request.content_type
        return web.json_response({"text": " Anvarga shina 500 ming so'm "})

    async def decide(request: web.Request) -> web.Response:
        received["decide"] = await request.json()
        return web.json_response(decide_response)

    app = web.Application()
    app.router.add_post("/v1/transcribe", transcribe)
    app.router.add_post("/v1/decide", decide)
    server = TestServer(app)
    await server.start_server()
    base = str(server.make_url("")).rstrip("/")
    yield base, received, decide_response
    await server.close()


def _client(base: str, token: str = TOKEN) -> LayaKitClient:
    return LayaKitClient(base, token, timeout_seconds=5)


async def test_transcribe_sends_audio_with_bearer(gateway) -> None:
    base, received, _ = gateway
    text = await _client(base).transcribe(b"OggS-audio")

    assert text == "Anvarga shina 500 ming so'm"
    assert received["audio"] == b"OggS-audio"
    assert received["content_type"] == "audio/ogg"


async def test_transcribe_rejects_bad_token(gateway) -> None:
    base, _, _ = gateway
    with pytest.raises(LayaKitError, match="401"):
        await _client(base, token="wrong").transcribe(b"x")


async def test_choose_sends_multilingual_choice_question(gateway) -> None:
    base, received, _ = gateway
    choice, confidence = await _client(base).choose(
        {"aytilgan_ism": "Anvar"}, "Qaysi mijoz?", ["Anvar", "Yangi mijoz"]
    )

    assert (choice, confidence) == ("Anvar", 0.91)
    assert received["decide"]["model"] == "multilingual"
    assert received["decide"]["questions"]["pick"] == {
        "type": "choice",
        "instructions": "Qaysi mijoz?",
        "choices": ["Anvar", "Yangi mijoz"],
    }


async def test_choose_rejects_choice_outside_list(gateway) -> None:
    base, _, decide_response = gateway
    decide_response["answers"]["pick"]["choice"] = "Boshqa odam"
    with pytest.raises(LayaKitError, match="ro'yxatda yo'q"):
        await _client(base).choose({}, "?", ["Anvar", "Yangi mijoz"])


async def test_unreachable_gateway_raises_layakit_error() -> None:
    client = LayaKitClient("http://127.0.0.1:9", TOKEN, 2)
    with pytest.raises(LayaKitError, match="aloqa yo'q"):
        await client.transcribe(b"x")
