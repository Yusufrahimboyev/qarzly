"""Bot chatida foydalanuvchi tanlagan filialni saqlash (PostgreSQL).

Render qayta ishga tushganda tanlov yo'qolib, qarz jimgina boshqa filialga
yozilib qolmasligi uchun xotirada emas, bazada saqlanadi.
"""
from __future__ import annotations

from bot.infrastructure.database.repositories.executor import Executor


class BranchPreferenceStore:
    """`user_branch` jadvali bilan ishlaydi."""

    def __init__(self, executor: Executor) -> None:
        self._db = executor

    async def get(self, telegram_id: int) -> str | None:
        return await self._db.fetchval(
            "SELECT branch FROM user_branch WHERE telegram_id = $1", telegram_id
        )

    async def set(self, telegram_id: int, branch: str) -> None:
        await self._db.execute(
            """
            INSERT INTO user_branch (telegram_id, branch)
            VALUES ($1, $2)
            ON CONFLICT (telegram_id)
            DO UPDATE SET branch = EXCLUDED.branch, updated_at = NOW()
            """,
            telegram_id, branch,
        )
