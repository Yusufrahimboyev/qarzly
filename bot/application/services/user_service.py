"""Application qatlami: UserService (use-case'lar).

Bu servis biznes-logikani o'z ichiga oladi va faqat `UserRepository`
abstraktsiyasiga tayanadi — u SQLite'mi, PostgreSQL'mi yoki soxta (test) repo'mi,
bilmaydi va bilishi shart emas. Handler'lar shu servis orqali ishlaydi.
"""
from __future__ import annotations

from bot.domain.entities.user import User
from bot.domain.repositories.user_repository import UserRepository


class UserService:
    """Foydalanuvchilar bilan bog'liq use-case'lar."""

    def __init__(self, users: UserRepository) -> None:
        self._users = users

    async def register(
        self,
        telegram_id: int,
        full_name: str,
        username: str | None = None,
    ) -> User:
        """Foydalanuvchini ro'yxatdan o'tkazadi (idempotent).

        Agar foydalanuvchi allaqachon mavjud bo'lsa — mavjudini qaytaradi,
        aks holda yangisini yaratib saqlaydi va saqlangan obyektni qaytaradi.
        """
        existing = await self._users.get_by_telegram_id(telegram_id)
        if existing is not None:
            return existing

        user = User(
            telegram_id=telegram_id,
            full_name=full_name,
            username=username,
        )
        await self._users.add(user)
        saved = await self._users.get_by_telegram_id(telegram_id)
        return saved if saved is not None else user

    async def get(self, telegram_id: int) -> User | None:
        """Telegram ID bo'yicha foydalanuvchini qaytaradi yoki None."""
        return await self._users.get_by_telegram_id(telegram_id)
