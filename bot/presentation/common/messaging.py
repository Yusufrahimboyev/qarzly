"""Telegram xabarlari bilan ishlash yordamchilari.

Telegram bitta xabarda 4096 belgidan ko'pini qabul qilmaydi. Uzun mijoz
hisobotlari shu chegaradan oshib ketib, xabar umuman yuborilmay qolardi.
"""
from __future__ import annotations

TELEGRAM_MESSAGE_LIMIT = 4096


def split_message(text: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    """Uzun matnni qator chegaralari bo'yicha bo'laklarga ajratadi.

    HTML teglari qator ichida yopilgani uchun qatorlar bo'yicha bo'lish
    xavfsiz: hech bir teg ikki bo'lak orasida ochiq qolmaydi.
    """
    if len(text) <= limit:
        return [text]

    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for line in text.split("\n"):
        # Bitta qatorning o'zi chegaradan uzun bo'lsa — majburan kesamiz.
        while len(line) > limit:
            if current:
                chunks.append("\n".join(current))
                current, current_len = [], 0
            chunks.append(line[:limit])
            line = line[limit:]

        extra = len(line) + (1 if current else 0)
        if current_len + extra > limit:
            chunks.append("\n".join(current))
            current, current_len = [line], len(line)
        else:
            current.append(line)
            current_len += extra

    if current:
        chunks.append("\n".join(current))
    return chunks
