"""Infrastructure qatlami: UserRepository'ning SQLite implementatsiyasi."""
from __future__ import annotations

import aiosqlite

from bot.domain.entities.user import User
from bot.domain.repositories.user_repository import UserRepository


class SqliteUserRepository(UserRepository):
    """`UserRepository` abstraktsiyasining aiosqlite orqali amalga oshirilishi.

    Umumiy ochiq ulanishni oladi (DI orqali) va domain `User` entity'siga
    xaritalaydi.
    """

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self._connection = connection

    async def add(self, user: User) -> None:
        await self._connection.execute(
            """
            INSERT OR IGNORE INTO users (telegram_id, username, full_name)
            VALUES (?, ?, ?)
            """,
            (user.telegram_id, user.username, user.full_name),
        )
        await self._connection.commit()

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        async with self._connection.execute(
            """
            SELECT id, telegram_id, username, full_name, created_at
            FROM users
            WHERE telegram_id = ?
            """,
            (telegram_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return self._map_row(row)

    @staticmethod
    def _map_row(row: aiosqlite.Row) -> User:
        """SQLite qatorini domain `User` entity'siga aylantiradi."""
        return User(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            full_name=row["full_name"],
            created_at=row["created_at"],
        )
