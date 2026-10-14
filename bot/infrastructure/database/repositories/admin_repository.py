"""Infrastructure qatlami: AdminRepository PostgreSQL implementatsiyasi.

Jadval `public` sxemada: har bir filial boti o'z sxemasida ishlasa ham,
adminlar ro'yxati uchalasi uchun bitta.
"""
from __future__ import annotations

from bot.domain.entities.admin import Admin
from bot.domain.repositories.admin_repository import AdminRepository
from bot.infrastructure.database.repositories.executor import Executor


class PgAdminRepository(AdminRepository):
    """`public.bot_admins` jadvali bilan ishlaydi."""

    def __init__(self, executor: Executor) -> None:
        self._db = executor

    async def list(self) -> list[Admin]:
        rows = await self._db.fetch(
            "SELECT telegram_id, full_name, added_by, created_at"
            " FROM public.bot_admins ORDER BY created_at, telegram_id"
        )
        return [
            Admin(
                telegram_id=row["telegram_id"],
                full_name=row["full_name"] or "",
                added_by=row["added_by"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def add(self, admin: Admin) -> None:
        await self._db.execute(
            """
            INSERT INTO public.bot_admins (telegram_id, full_name, added_by)
            VALUES ($1, $2, $3)
            ON CONFLICT (telegram_id) DO UPDATE SET full_name = EXCLUDED.full_name
            """,
            admin.telegram_id,
            admin.full_name,
            admin.added_by,
        )

    async def remove(self, telegram_id: int) -> bool:
        result = await self._db.execute(
            "DELETE FROM public.bot_admins WHERE telegram_id = $1", telegram_id
        )
        return bool(result) and result.split()[-1] != "0"
