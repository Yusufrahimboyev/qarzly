"""Ma'lumotlar bazasi jadval sxemasi (DDL).

Sxema shu yerda bir joyda saqlanadi — kelgusida migratsiyalar qo'shilsa
ham shu modul kengaytiriladi.
"""

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id          SERIAL PRIMARY KEY,
    telegram_id INTEGER UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_CLIENTS_TABLE = """
CREATE TABLE IF NOT EXISTS clients (
    id          SERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    phone       TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_DEBTS_TABLE = """
CREATE TABLE IF NOT EXISTS debts (
    id                     SERIAL PRIMARY KEY,
    client_id              INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    debt_date              TEXT NOT NULL,
    product_name           TEXT NOT NULL,
    product_quantity       INTEGER NOT NULL DEFAULT 1,
    product_price          INTEGER NOT NULL,
    currency               TEXT NOT NULL DEFAULT 'UZS' CHECK(currency IN ('UZS', 'USD')),
    exchange_exists        INTEGER NOT NULL DEFAULT 0,
    exchange_product_name  TEXT,
    exchange_product_price INTEGER NOT NULL DEFAULT 0,
    given_money            INTEGER NOT NULL DEFAULT 0,
    original_debt          INTEGER NOT NULL,
    remaining_debt         INTEGER NOT NULL,
    products_json          TEXT NOT NULL DEFAULT '[]',
    status                 TEXT NOT NULL DEFAULT 'active' CHECK(status IN ('active', 'paid')),
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS payments (
    id           SERIAL PRIMARY KEY,
    client_id    INTEGER NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    debt_id      INTEGER REFERENCES debts(id) ON DELETE RESTRICT,
    amount       INTEGER NOT NULL,
    currency     TEXT NOT NULL DEFAULT 'UZS' CHECK(currency IN ('UZS', 'USD')),
    payment_type TEXT NOT NULL CHECK(payment_type IN ('full', 'partial', 'initial')),
    payment_date TEXT NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_INDEX_CLIENTS_NAME = "CREATE INDEX IF NOT EXISTS idx_clients_full_name ON clients(LOWER(full_name));"
CREATE_INDEX_CLIENTS_PHONE = "CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);"
CREATE_INDEX_DEBTS_CLIENT = "CREATE INDEX IF NOT EXISTS idx_debts_client_id ON debts(client_id);"
CREATE_INDEX_DEBTS_STATUS = "CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);"
CREATE_INDEX_PAYMENTS_CLIENT = "CREATE INDEX IF NOT EXISTS idx_payments_client_id ON payments(client_id);"
CREATE_INDEX_PAYMENTS_DEBT = "CREATE INDEX IF NOT EXISTS idx_payments_debt_id ON payments(debt_id);"

# Barcha DDL iboralari ketma-ketligi. init() shu ro'yxat bo'yicha yuradi.
SCHEMA: tuple[str, ...] = (
    CREATE_USERS_TABLE,
    CREATE_CLIENTS_TABLE,
    CREATE_DEBTS_TABLE,
    CREATE_PAYMENTS_TABLE,
    CREATE_INDEX_CLIENTS_NAME,
    CREATE_INDEX_CLIENTS_PHONE,
    CREATE_INDEX_DEBTS_CLIENT,
    CREATE_INDEX_DEBTS_STATUS,
    CREATE_INDEX_PAYMENTS_CLIENT,
    CREATE_INDEX_PAYMENTS_DEBT,
)
