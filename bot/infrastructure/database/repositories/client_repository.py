"""Infrastructure qatlami: ClientRepository PostgreSQL implementatsiyasi."""
from __future__ import annotations

import asyncpg

from bot.domain.entities.client import Client
from bot.domain.repositories.client_repository import ClientRepository


class PgClientRepository(ClientRepository):
    """ClientRepository ning asyncpg orqali amalga oshirilishi."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def add(self, client: Client) -> Client:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO clients (full_name, phone)
                VALUES ($1, $2)
                RETURNING id
                """,
                client.full_name,
                client.phone,
            )
            client_id = row["id"] if row else None
            if client_id is None:
                raise RuntimeError("Mijozni saqlashda ID olinmadi.")
            return await self.get_by_id(client_id)  # type: ignore[return-value]

    async def get_by_id(self, client_id: int) -> Client | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, full_name, phone, created_at, updated_at
                FROM clients
                WHERE id = $1
                """,
                client_id,
            )

        if row is None:
            return None
        return self._map_row(row)

    async def find_by_phone(self, phone: str) -> Client | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, full_name, phone, created_at, updated_at
                FROM clients
                WHERE phone = $1
                LIMIT 1
                """,
                phone.strip(),
            )

        if row is None:
            return None
        return self._map_row(row)

    async def find_by_name(self, full_name: str) -> Client | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, full_name, phone, created_at, updated_at
                FROM clients
                WHERE LOWER(full_name) = LOWER($1)
                LIMIT 1
                """,
                full_name.strip(),
            )

        if row is None:
            return None
        return self._map_row(row)

    async def get_all_alphabetical(self) -> list[Client]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, full_name, phone, created_at, updated_at
                FROM clients
                ORDER BY LOWER(full_name) ASC
                """
            )

        return [self._map_row(row) for row in rows]

    @staticmethod
    def _map_row(row: asyncpg.Record) -> Client:
        return Client(
            id=row["id"],
            full_name=row["full_name"],
            phone=row["phone"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
