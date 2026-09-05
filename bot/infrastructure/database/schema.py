"""Ma'lumotlar bazasi jadval sxemasi (PostgreSQL DDL).

Barcha pul summalari va miqdorlar BIGINT formatida saqlanadi — bu
katta summalar (milliard so'mlar) bilan ishlaganda integer overflow xavfini
to'liq bartaraf etadi.

Sanalar `DATE` turida saqlanadi: matn sifatida saqlangan sana "DD.MM.YYYY"
tartibida noto'g'ri saralanib, FIFO to'lov taqsimotini buzardi.
"""
from __future__ import annotations

CREATE_USERS_TABLE = """
CREATE TABLE IF NOT EXISTS users (
    id          BIGSERIAL PRIMARY KEY,
    telegram_id BIGINT UNIQUE NOT NULL,
    username    TEXT,
    full_name   TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_CLIENTS_TABLE = """
CREATE TABLE IF NOT EXISTS clients (
    id          BIGSERIAL PRIMARY KEY,
    full_name   TEXT NOT NULL,
    phone       TEXT NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);
"""

CREATE_DEBTS_TABLE = """
CREATE TABLE IF NOT EXISTS debts (
    id                     BIGSERIAL PRIMARY KEY,
    client_id              BIGINT NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    debt_date              DATE NOT NULL,
    product_name           TEXT NOT NULL,
    product_quantity       BIGINT NOT NULL DEFAULT 1,
    product_price          BIGINT NOT NULL,
    currency               TEXT NOT NULL DEFAULT 'UZS' CHECK(currency IN ('UZS', 'USD')),
    exchange_exists        INTEGER NOT NULL DEFAULT 0,
    exchange_product_name  TEXT,
    exchange_product_price BIGINT NOT NULL DEFAULT 0,
    given_money            BIGINT NOT NULL DEFAULT 0,
    original_debt          BIGINT NOT NULL,
    remaining_debt         BIGINT NOT NULL,
    products_json          TEXT NOT NULL DEFAULT '[]',
    status                 TEXT NOT NULL DEFAULT 'active'
                               CHECK(status IN ('active', 'paid', 'trashed')),
    created_at             TIMESTAMPTZ DEFAULT NOW(),
    updated_at             TIMESTAMPTZ DEFAULT NOW(),
    CONSTRAINT chk_debts_amounts_non_negative CHECK (
        product_price >= 0
        AND exchange_product_price >= 0
        AND given_money >= 0
        AND original_debt >= 0
        AND remaining_debt >= 0
        AND product_quantity >= 0
    ),
    CONSTRAINT chk_debts_remaining_le_original CHECK (remaining_debt <= original_debt)
);
"""

CREATE_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS payments (
    id           BIGSERIAL PRIMARY KEY,
    client_id    BIGINT NOT NULL REFERENCES clients(id) ON DELETE RESTRICT,
    debt_id      BIGINT REFERENCES debts(id) ON DELETE RESTRICT,
    amount       BIGINT NOT NULL CHECK (amount >= 0),
    currency     TEXT NOT NULL DEFAULT 'UZS' CHECK(currency IN ('UZS', 'USD')),
    payment_type TEXT NOT NULL CHECK(payment_type IN ('full', 'partial', 'initial')),
    payment_date DATE NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);
"""

# Korzinaga ko'chirilgan va butunlay o'chirilgan qarzlarning arxivi.
# Bu jadval faqat statistika uchun saqlanadi — hech qachon o'zgartirilmaydi.
CREATE_TRASH_TABLE = """
CREATE TABLE IF NOT EXISTS trash (
    id              BIGSERIAL PRIMARY KEY,
    original_id     BIGINT NOT NULL,
    client_id       BIGINT NOT NULL,
    client_name     TEXT NOT NULL,
    product_name    TEXT NOT NULL,
    product_price   BIGINT NOT NULL,
    original_debt   BIGINT NOT NULL,
    remaining_debt  BIGINT NOT NULL,
    currency        TEXT NOT NULL DEFAULT 'UZS',
    debt_date       DATE NOT NULL,
    status_before   TEXT NOT NULL,
    products_json   TEXT NOT NULL DEFAULT '[]',
    deleted_by      BIGINT,
    deleted_at      TIMESTAMPTZ DEFAULT NOW()
);
"""

# To'lov tarixi moliyaviy audit trail — korzina tozalanganda ham
# yo'qotilmaydi, balki shu arxivga ko'chiriladi (append-only).
CREATE_TRASH_PAYMENTS_TABLE = """
CREATE TABLE IF NOT EXISTS trash_payments (
    id               BIGSERIAL PRIMARY KEY,
    original_id      BIGINT NOT NULL,
    original_debt_id BIGINT,
    client_id        BIGINT NOT NULL,
    amount           BIGINT NOT NULL,
    currency         TEXT NOT NULL DEFAULT 'UZS',
    payment_type     TEXT NOT NULL,
    payment_date     DATE NOT NULL,
    paid_created_at  TIMESTAMPTZ,
    deleted_by       BIGINT,
    deleted_at       TIMESTAMPTZ DEFAULT NOW()
);
"""

# Idempotency: bir xil so'rov (tarmoq retry, ikki marta bosish) ikkinchi
# marta yozuv yaratmasligi uchun kalit va javob shu yerda saqlanadi.
CREATE_IDEMPOTENCY_TABLE = """
CREATE TABLE IF NOT EXISTS idempotency_keys (
    id            BIGSERIAL PRIMARY KEY,
    scope         TEXT NOT NULL,
    idem_key      TEXT NOT NULL,
    actor_id      BIGINT,
    response_json TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (scope, idem_key)
);
"""

CREATE_INDEX_CLIENTS_NAME = (
    "CREATE INDEX IF NOT EXISTS idx_clients_full_name ON clients(LOWER(full_name));"
)
CREATE_INDEX_CLIENTS_PHONE = (
    "CREATE INDEX IF NOT EXISTS idx_clients_phone ON clients(phone);"
)
# Telefon — mijozning asosiy identity'si: bir raqam faqat bitta mijozga tegishli.
# Telefonsiz yozuvlar (bo'sh matn) chegaraga tushmaydi.
CREATE_UNIQUE_CLIENTS_PHONE = (
    "CREATE UNIQUE INDEX IF NOT EXISTS uq_clients_phone"
    " ON clients(phone) WHERE phone <> '';"
)
CREATE_INDEX_DEBTS_CLIENT = (
    "CREATE INDEX IF NOT EXISTS idx_debts_client_id ON debts(client_id);"
)
CREATE_INDEX_DEBTS_STATUS = (
    "CREATE INDEX IF NOT EXISTS idx_debts_status ON debts(status);"
)
# Asosiy access pattern: mijozning statusi bo'yicha filtrlangan qarzlari,
# FIFO tartibida (sana, id).
CREATE_INDEX_DEBTS_FIFO = (
    "CREATE INDEX IF NOT EXISTS idx_debts_client_fifo"
    " ON debts(client_id, status, debt_date, id);"
)
CREATE_INDEX_PAYMENTS_CLIENT = (
    "CREATE INDEX IF NOT EXISTS idx_payments_client_id ON payments(client_id);"
)
CREATE_INDEX_PAYMENTS_DEBT = (
    "CREATE INDEX IF NOT EXISTS idx_payments_debt_id ON payments(debt_id);"
)
CREATE_INDEX_TRASH_CLIENT = (
    "CREATE INDEX IF NOT EXISTS idx_trash_client_id ON trash(client_id);"
)
CREATE_INDEX_TRASH_ORIGINAL = (
    "CREATE INDEX IF NOT EXISTS idx_trash_original_id ON trash(original_id);"
)
CREATE_INDEX_TRASH_PAYMENTS_CLIENT = (
    "CREATE INDEX IF NOT EXISTS idx_trash_payments_client_id"
    " ON trash_payments(client_id);"
)
CREATE_INDEX_IDEMPOTENCY_CREATED = (
    "CREATE INDEX IF NOT EXISTS idx_idempotency_created_at"
    " ON idempotency_keys(created_at);"
)

# Barcha DDL iboralari ketma-ketligi. Migration runner shu ro'yxat bo'yicha
# yuradi (faqat "yangi baza" holati uchun; mavjud bazalar migrations.py dagi
# versiyalangan qadamlar bilan yangilanadi).
SCHEMA: tuple[str, ...] = (
    CREATE_USERS_TABLE,
    CREATE_CLIENTS_TABLE,
    CREATE_DEBTS_TABLE,
    CREATE_PAYMENTS_TABLE,
    CREATE_TRASH_TABLE,
    CREATE_TRASH_PAYMENTS_TABLE,
    CREATE_IDEMPOTENCY_TABLE,
    CREATE_INDEX_CLIENTS_NAME,
    CREATE_INDEX_CLIENTS_PHONE,
    CREATE_INDEX_DEBTS_CLIENT,
    CREATE_INDEX_DEBTS_STATUS,
    CREATE_INDEX_DEBTS_FIFO,
    CREATE_INDEX_PAYMENTS_CLIENT,
    CREATE_INDEX_PAYMENTS_DEBT,
    CREATE_INDEX_TRASH_CLIENT,
    CREATE_INDEX_TRASH_ORIGINAL,
    CREATE_INDEX_TRASH_PAYMENTS_CLIENT,
    CREATE_INDEX_IDEMPOTENCY_CREATED,
)
