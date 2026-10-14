"""Domain entity: EditRecord.

Mijoz yoki qarz tahrirlanganda nima o'zgargani (eski → yangi qiymat), kim
va qachon o'zgartirgani. Mini App va botda "tahrirlangan" belgisi shu yozuvlar
asosida ko'rsatiladi.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class FieldChange:
    """Bitta maydon o'zgarishi (qiymatlar ko'rsatish uchun tayyor matn)."""

    field: str
    old: str
    new: str

    def to_dict(self) -> dict:
        return {"field": self.field, "old": self.old, "new": self.new}

    @classmethod
    def from_dict(cls, d: dict) -> FieldChange:
        return cls(
            field=str(d.get("field", "")),
            old=str(d.get("old", "")),
            new=str(d.get("new", "")),
        )


@dataclass(frozen=True, slots=True)
class EditRecord:
    """Bitta tahrir amali. `debt_id` bo'sh bo'lsa — mijoz ma'lumoti tahrirlangan."""

    client_id: int
    changes: tuple[FieldChange, ...]
    debt_id: int | None = None
    edited_by: int | None = None
    edited_by_name: str = ""
    edited_at: datetime | None = None
    id: int | None = None
