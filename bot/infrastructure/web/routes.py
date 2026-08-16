"""Infrastructure qatlami: aiohttp web route'lari.

Mini App (index sahifa), health check va statik fayllar uchun route'lar.
Health check Render.com kabi platformalarda xizmatni "tirik" ushlab turishga
yordam beradi.
"""
from __future__ import annotations

from pathlib import Path

from aiohttp import web

# template/web/ papkasiga ishora qiladi (bu fayldan uch pog'ona yuqorida).
_WEB_DIR = Path(__file__).resolve().parents[3] / "web"
_TEMPLATES_DIR = _WEB_DIR / "templates"
_STATIC_DIR = _WEB_DIR / "static"


async def health_check(request: web.Request) -> web.Response:
    """Xizmat holatini qaytaradi (monitoring / keep-alive uchun)."""
    return web.json_response({"status": "ok", "service": "Telegram Bot & WebApp"})


async def index_handler(request: web.Request) -> web.StreamResponse:
    """Mini App bosh sahifasini (index.html) qaytaradi."""
    index_path = _TEMPLATES_DIR / "index.html"
    if index_path.exists():
        return web.FileResponse(index_path)
    return web.Response(
        text="<h1>WebApp Index Template</h1>",
        content_type="text/html",
    )


def setup_routes(app: web.Application) -> None:
    """Route'larni aiohttp ilovasiga ro'yxatga oladi."""
    app.router.add_get("/", index_handler)
    app.router.add_get("/health", health_check)

    if _STATIC_DIR.exists():
        app.router.add_static("/static/", _STATIC_DIR, name="static")
