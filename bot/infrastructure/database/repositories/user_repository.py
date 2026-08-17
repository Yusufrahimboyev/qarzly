"""Infrastructure qatlami: UserRepository'ning PostgreSQL implementatsiyasi."""
from __future__ import annotations

import asyncpg

from bot.domain.entities.user import User
from bot.domain.repositories.user_repository import UserRepository


class PgUserRepository(UserRepository):
    """`UserRepository` abstraktsiyasining asyncpg orqali amalga oshirilishi.

    Umumiy ochiq hovuzni oladi (DI orqali) va domain `User` entity'siga
    xaritalaydi.
    """

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, user: User) -> None:
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO users (telegram_id, username, full_name)
                VALUES ($1, $2, $3)
                ON CONFLICT DO NOTHING
                """,
                user.telegram_id, user.username, user.full_name,
            )

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, telegram_id, username, full_name, created_at
                FROM users
                WHERE telegram_id = $1
                """,
                telegram_id,
            )

        if row is None:
            return None
        return self._map_row(row)

    @staticmethod
    def _map_row(row: asyncpg.Record) -> User:
        """PostgreSQL qatorini domain `User` entity'siga aylantiradi."""
        return User(
            id=row["id"],
            telegram_id=row["telegram_id"],
            username=row["username"],
            full_name=row["full_name"],
            created_at=row["created_at"],
        )
