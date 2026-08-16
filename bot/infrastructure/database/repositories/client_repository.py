"""Infrastructure qatlami: ClientRepository SQLite implementatsiyasi."""
from __future__ import annotations

from datetime import datetime

import aiosqlite

from bot.domain.entities.client import Client
from bot.domain.repositories.client_repository import ClientRepository


class SqliteClientRepository(ClientRepository):
    """ClientRepository ning aiosqlite orqali amalga oshirilishi."""

    def __init__(self, connection: aiosqlite.Connection) -> None:
        self._connection = connection

    async def add(self, client: Client) -> Client:
        cursor = await self._connection.execute(
            """
            INSERT INTO clients (full_name, phone)
            VALUES (?, ?)
            """,
            (client.full_name, client.phone),
        )
        await self._connection.commit()
        client_id = cursor.lastrowid
        return await self.get_by_id(client_id)  # type: ignore[return-value]

    async def get_by_id(self, client_id: int) -> Client | None:
        async with self._connection.execute(
            """
            SELECT id, full_name, phone, created_at, updated_at
            FROM clients
            WHERE id = ?
            """,
            (client_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return self._map_row(row)

    async def find_by_phone(self, phone: str) -> Client | None:
        async with self._connection.execute(
            """
            SELECT id, full_name, phone, created_at, updated_at
            FROM clients
            WHERE phone = ?
            LIMIT 1
            """,
            (phone.strip(),),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return self._map_row(row)

    async def find_by_name(self, full_name: str) -> Client | None:
        async with self._connection.execute(
            """
            SELECT id, full_name, phone, created_at, updated_at
            FROM clients
            WHERE full_name = ? COLLATE NOCASE
            LIMIT 1
            """,
            (full_name.strip(),),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None
        return self._map_row(row)

    async def get_all_alphabetical(self) -> list[Client]:
        async with self._connection.execute(
            """
            SELECT id, full_name, phone, created_at, updated_at
            FROM clients
            ORDER BY full_name COLLATE NOCASE ASC
            """
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._map_row(row) for row in rows]

    @staticmethod
    def _map_row(row: aiosqlite.Row) -> Client:
        created_at_raw = row["created_at"]
        updated_at_raw = row["updated_at"]

        created_at = None
        if created_at_raw:
            try:
                created_at = datetime.fromisoformat(str(created_at_raw))
            except Exception:
                created_at = None

        updated_at = None
        if updated_at_raw:
            try:
                updated_at = datetime.fromisoformat(str(updated_at_raw))
            except Exception:
                updated_at = None

        return Client(
            id=row["id"],
            full_name=row["full_name"],
            phone=row["phone"],
            created_at=created_at,
            updated_at=updated_at,
        )
