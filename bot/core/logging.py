"""Markazlashtirilgan logging sozlamasi.

`log_json=True` bo'lganda loglar structured JSON ko'rinishida yoziladi —
log agregatorlar (Render, Datadog, Loki) uchun qulay. AUDIT yozuvlarida
operatsiyani bajargan foydalanuvchi ID si (actor) ham bo'ladi.
"""
from __future__ import annotations

import json
import logging


class JsonFormatter(logging.Formatter):
    """Log yozuvini bitta qatorlik JSON obyektga aylantiradi."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        # Handler yoki middleware qo'shgan qo'shimcha maydonlar
        for key in ("actor_id", "request_id", "update_id", "correlation_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(level: str = "INFO", json_format: bool = False) -> None:
    """Ilova bo'ylab yagona log formatini o'rnatadi."""
    handler = logging.StreamHandler()
    if json_format:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)

    # Kutubxonalarning ortiqcha "shovqin"ini kamaytiramiz.
    logging.getLogger("asyncpg").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
