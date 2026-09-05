"""Infrastructure qatlami: ClientRepository PostgreSQL implementatsiyasi."""
from __future__ import annotations

import logging

import asyncpg

from bot.domain.entities.client import Client
from bot.domain.repositories.client_repository import ClientRepository
from bot.infrastructure.database.repositories.executor import Executor

logger = logging.getLogger(__name__)

_SELECT_CLIENT_COLS = "id, full_name, phone, created_at, updated_at"

# `uq_clients_phone` indeksi mavjudligi. Eski bazada dublikat telefonlar
# sababli index qo'yilmagan bo'lishi mumkin — birinchi xatodan keyin barcha
# repository instansiyalari uchun o'chiriladi (har safar bekorga urinmasin).
_phone_upsert_supported = True


class PgClientRepository(ClientRepository):
    """ClientRepository ning asyncpg orqali amalga oshirilishi."""

    def __init__(self, executor: Executor) -> None:
        self._db = executor

    async def add(self, client: Client) -> Client:
        row = await self._db.fetchrow(
            f"""
            INSERT INTO clients (full_name, phone)
            VALUES ($1, $2)
            RETURNING {_SELECT_CLIENT_COLS}
            """,
            client.full_name,
            client.phone,
        )
        if row is None:
            raise RuntimeError("Mijoz yozuvi saqlanmadi.")
        return self._map_row(row)

    async def get_or_create_by_phone(self, client: Client) -> tuple[Client, bool]:
        """Telefon bo'yicha mijozni atomik ravishda topadi yoki yaratadi.

        `uq_clients_phone` unique index bilan birga ishlaydi: parallel ikki
        so'rov bir xil telefon bilan kelsa, ikkinchisi dublikat yaratmaydi,
        balki mavjud yozuvni oladi.

        Eski bazada (index hali qo'yilmagan, masalan dublikat telefonlar
        sababli) `ON CONFLICT` ishlamaydi — bunday holatda oddiy INSERT
        ishlatiladi, ya'ni funksiya baribir to'g'ri natija beradi.
        """
        global _phone_upsert_supported

        phone = client.phone.strip()
        if not phone:
            return await self.add(client), True

        existing = await self.find_by_phone(phone)
        if existing is not None:
            return existing, False

        if _phone_upsert_supported:
            try:
                row = await self._db.fetchrow(
                    f"""
                    INSERT INTO clients (full_name, phone)
                    VALUES ($1, $2)
                    ON CONFLICT (phone) WHERE phone <> '' DO NOTHING
                    RETURNING {_SELECT_CLIENT_COLS}
                    """,
                    client.full_name,
                    phone,
                )
            except asyncpg.exceptions.InvalidColumnReferenceError:
                # Unique index mavjud emas — keyingi chaqiruvlarda urinmaymiz.
                logger.warning(
                    "uq_clients_phone indeksi yo'q — telefon bo'yicha atomik "
                    "upsert o'chirildi. Dublikat telefonlarni tozalab, "
                    "migratsiyani qayta ishga tushiring."
                )
                _phone_upsert_supported = False
            else:
                if row is not None:
                    return self._map_row(row), True
                found = await self.find_by_phone(phone)
                if found is not None:
                    return found, False

        return await self.add(client), True

    async def get_by_id(self, client_id: int) -> Client | None:
        row = await self._db.fetchrow(
            f"SELECT {_SELECT_CLIENT_COLS} FROM clients WHERE id = $1",
            client_id,
        )
        if row is None:
            return None
        return self._map_row(row)

    async def find_by_phone(self, phone: str) -> Client | None:
        row = await self._db.fetchrow(
            f"""
            SELECT {_SELECT_CLIENT_COLS}
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
        row = await self._db.fetchrow(
            f"""
            SELECT {_SELECT_CLIENT_COLS}
            FROM clients
            WHERE LOWER(full_name) = LOWER($1)
            ORDER BY id ASC
            LIMIT 1
            """,
            full_name.strip(),
        )
        if row is None:
            return None
        return self._map_row(row)

    async def find_by_name_without_phone(self, full_name: str) -> Client | None:
        """Telefoni yo'q mijozlar orasidan ism bo'yicha topadi.

        Telefoni bor mijozlar ism bo'yicha birlashtirilmaydi — bir xil ismli
        ikki xil odam bitta yozuvga qo'shilib ketmasligi kerak.
        """
        row = await self._db.fetchrow(
            f"""
            SELECT {_SELECT_CLIENT_COLS}
            FROM clients
            WHERE LOWER(full_name) = LOWER($1) AND phone = ''
            ORDER BY id ASC
            LIMIT 1
            """,
            full_name.strip(),
        )
        if row is None:
            return None
        return self._map_row(row)

    async def get_all_alphabetical(self) -> list[Client]:
        rows = await self._db.fetch(
            f"""
            SELECT {_SELECT_CLIENT_COLS}
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
