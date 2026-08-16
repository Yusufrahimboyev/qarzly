"""Eski (product_quantity siz) bazani migratsiya qilish testi."""
from __future__ import annotations

from pathlib import Path

import aiosqlite
import pytest

from bot.infrastructure.database.connection import Database

# product_quantity ustuni YO'Q eski sxema
OLD_SCHEMA = """
CREATE TABLE clients (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name   TEXT NOT NULL,
    phone       TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE debts (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id              INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    debt_date              TEXT NOT NULL,
    product_name           TEXT NOT NULL,
    product_price          INTEGER NOT NULL,
    exchange_exists        INTEGER NOT NULL DEFAULT 0,
    exchange_product_name  TEXT,
    exchange_product_price INTEGER NOT NULL DEFAULT 0,
    given_money            INTEGER NOT NULL DEFAULT 0,
    original_debt          INTEGER NOT NULL,
    remaining_debt         INTEGER NOT NULL,
    status                 TEXT NOT NULL DEFAULT 'active',
    created_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at             TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


@pytest.mark.asyncio
async def test_old_database_gets_product_quantity_column(tmp_path: Path) -> None:
    db_path = tmp_path / "bot.db"

    # Eski formatdagi baza yaratamiz vaunga ma'lumot kiritamiz
    conn = await aiosqlite.connect(db_path)
    await conn.executescript(OLD_SCHEMA)
    await conn.execute(
        "INSERT INTO debts (client_id, debt_date, product_name, product_price,"
        " original_debt, remaining_debt, status)"
        " VALUES (1, '16.08.2026', 'Shina', 2500000, 2500000, 2500000, 'active')"
    )
    await conn.commit()
    await conn.close()

    # Database.connect() migratsiyani bajarishi kerak
    database = Database(db_path)
    await database.connect()
    try:
        async with database.connection.execute(
            "SELECT product_name, product_quantity, product_price, currency FROM debts"
        ) as cursor:
            rows = await cursor.fetchall()

        assert len(rows) == 1
        # Eski yozuvlar miqdori 1, valyutasi UZS deb belgilanadi, narxi o'zgarmaydi
        assert rows[0][0] == "Shina"
        assert rows[0][1] == 1
        assert rows[0][2] == 2500000
        assert rows[0][3] == "UZS"
    finally:
        await database.disconnect()
