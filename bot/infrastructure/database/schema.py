"""Ma'lumotlar bazasi jadval sxemasi (DDL).

Sxema shu yerda bir joyda saqlanadi — kelgusida migratsiyalar qo'shilsa
ham shu modul kengaytiriladi.
"""

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_id INTEGER UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT NOT NULL,
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

# Barcha DDL iboralari ketma-ketligi. init() shu ro'yxat bo'yicha yuradi.
SCHEMA: tuple[str, ...] = (CREATE_USERS_TABLE,)
