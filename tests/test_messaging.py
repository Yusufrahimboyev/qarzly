"""Uzun Telegram xabarlarini bo'lish uchun testlar (M-11)."""
from __future__ import annotations

from bot.presentation.common.messaging import TELEGRAM_MESSAGE_LIMIT, split_message


def test_short_message_is_not_split() -> None:
    assert split_message("qisqa matn") == ["qisqa matn"]


def test_long_message_split_within_limit() -> None:
    text = "\n".join(f"{i}-qator " + "x" * 80 for i in range(300))
    chunks = split_message(text)

    assert len(chunks) > 1
    assert all(len(chunk) <= TELEGRAM_MESSAGE_LIMIT for chunk in chunks)
    # Ma'lumot yo'qolmaydi
    assert "\n".join(chunks) == text


def test_single_overlong_line_is_hard_split() -> None:
    text = "y" * (TELEGRAM_MESSAGE_LIMIT * 2 + 10)
    chunks = split_message(text)
    assert all(len(chunk) <= TELEGRAM_MESSAGE_LIMIT for chunk in chunks)
    assert "".join(chunks) == text
