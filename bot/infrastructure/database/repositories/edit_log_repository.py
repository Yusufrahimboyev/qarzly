"""Infrastructure qatlami: EditLogRepository PostgreSQL implementatsiyasi."""
from __future__ import annotations

import json

import asyncpg

from bot.domain.entities.edit import EditRecord, FieldChange
from bot.domain.repositories.edit_log_repository import EditLogRepository
from bot.infrastructure.database.repositories.executor import Executor

_SELECT_COLS = "id, client_id, debt_id, changes_json, edited_by, edited_by_name, edited_at"


class PgEditLogRepository(EditLogRepository):
    """`edit_log` jadvali bilan ishlaydi."""

    def __init__(self, executor: Executor) -> None:
        self._db = executor

    async def add(self, record: EditRecord) -> EditRecord:
        row = await self._db.fetchrow(
            f"""
            INSERT INTO edit_log (client_id, debt_id, changes_json, edited_by, edited_by_name)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING {_SELECT_COLS}
            """,
            record.client_id,
            record.debt_id,
            json.dumps([c.to_dict() for c in record.changes], ensure_ascii=False),
            record.edited_by,
            record.edited_by_name,
        )
        if row is None:
            raise RuntimeError("Tahrir yozuvi saqlanmadi.")
        return self._map_row(row)

    async def get_by_client_id(self, client_id: int) -> list[EditRecord]:
        rows = await self._db.fetch(
            f"SELECT {_SELECT_COLS} FROM edit_log WHERE client_id = $1"
            " ORDER BY edited_at DESC, id DESC",
            client_id,
        )
        return [self._map_row(row) for row in rows]

    @staticmethod
    def _map_row(row: asyncpg.Record) -> EditRecord:
        try:
            raw = json.loads(row["changes_json"] or "[]")
        except ValueError:
            raw = []
        return EditRecord(
            id=row["id"],
            client_id=row["client_id"],
            debt_id=row["debt_id"],
            changes=tuple(FieldChange.from_dict(c) for c in raw if isinstance(c, dict)),
            edited_by=row["edited_by"],
            edited_by_name=row["edited_by_name"] or "",
            edited_at=row["edited_at"],
        )
