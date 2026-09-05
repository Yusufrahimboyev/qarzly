"""Versiyalangan ma'lumotlar bazasi migratsiyalari.

Har bir migratsiya bir marta bajariladi va `schema_migrations` jadvalida
qayd etiladi. Avvalgi yondashuv (har startupda `ALTER TABLE ...` ni try/except
ichida jimgina bajarish) xatolarni yashirar va ilova "muvaffaqiyatli ulandim"
deb davom etaverardi. Endi:

- har bir qadam alohida tranzaksiyada bajariladi;
- majburiy qadamdagi xato ilovani darhol to'xtatadi (fail-fast);
- ixtiyoriy qadam (masalan mavjud dublikatlar sababli qo'yib bo'lmaydigan
  unique index) aniq ERROR log bilan qayd etiladi va keyingi startupda
  qayta uriniladi;
- bir vaqtda bir nechta instansiya ishga tushsa, advisory lock ularni
  ketma-ketlashtiradi.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import asyncpg

from bot.infrastructure.database.schema import CREATE_UNIQUE_CLIENTS_PHONE

logger = logging.getLogger(__name__)

# Migratsiyalarni bir vaqtda faqat bitta instansiya bajarishi uchun
# tranzaksiya darajasidagi advisory lock kaliti.
MIGRATION_LOCK_KEY = 815_042_026

CREATE_MIGRATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
"""


@dataclass(frozen=True, slots=True)
class Migration:
    """Bitta versiyalangan migratsiya qadami."""

    version: str
    description: str
    statements: tuple[str, ...]
    # Ixtiyoriy qadam mavjud ma'lumotlar sababli bajarilmasligi mumkin —
    # bunda ilova to'xtamaydi, lekin ERROR log yoziladi va qayd etilmaydi.
    required: bool = True


# --- 001: eski INTEGER ustunlarni BIGINT ga o'tkazish -----------------------
_BIGINT_COLUMNS = (
    ("debts", "product_quantity"),
    ("debts", "product_price"),
    ("debts", "exchange_product_price"),
    ("debts", "given_money"),
    ("debts", "original_debt"),
    ("debts", "remaining_debt"),
    ("payments", "amount"),
)

_BIGINT_STATEMENTS = tuple(
    f"""
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = '{table}'
              AND column_name = '{column}'
              AND data_type <> 'bigint'
        ) THEN
            ALTER TABLE {table} ALTER COLUMN {column} TYPE BIGINT;
        END IF;
    END $$;
    """
    for table, column in _BIGINT_COLUMNS
)


# --- 002: TEXT sanalarni DATE ga o'tkazish ---------------------------------
_DATE_COLUMNS = (
    ("debts", "debt_date"),
    ("payments", "payment_date"),
    ("trash", "debt_date"),
)


def _date_guard_sql(table: str, column: str) -> str:
    """Konvertatsiyadan oldin barcha qiymatlar haqiqiy sana ekanini tekshiradi.

    Ikki bosqichli tekshiruv:

    1. format — qiymat aynan `DD.MM.YYYY` shabloniga mos kelishi kerak;
    2. round-trip — `to_char(to_date(x))` aynan `x` ni qaytarishi kerak.

    Ikkinchisi shart: `TO_DATE('31.02.2026', 'DD.MM.YYYY')` xato bermaydi,
    balki sanani jimgina `03.03.2026` ga surib yuboradi. Faqat shablon
    tekshirilganda bunday yozuv sezilmay konvertatsiya qilinib, moliyaviy
    tarix buzilardi.
    """
    pattern = "^[0-9]{2}[.][0-9]{2}[.][0-9]{4}$"
    count_sql = f"SELECT COUNT(*) FROM {table} WHERE {column} !~ ''{pattern}''"
    roundtrip_sql = (
        f"SELECT COUNT(*) FROM {table}"
        f" WHERE to_char(to_date({column}, ''DD.MM.YYYY''), ''DD.MM.YYYY'') <> {column}"
    )
    alter_sql = (
        f"ALTER TABLE {table} ALTER COLUMN {column} TYPE DATE"
        f" USING TO_DATE({column}, ''DD.MM.YYYY'')"
    )
    format_message = (
        f"{table}.{column}: % ta yozuv DD.MM.YYYY formatida emas;"
        " DATE ga o''tkazishdan oldin qo''lda tuzating"
    )
    invalid_message = (
        f"{table}.{column}: mavjud bo''lmagan sana bor (masalan 31.02.2026);"
        " DATE ga o''tkazishdan oldin qo''lda tuzating"
    )
    shifted_message = (
        f"{table}.{column}: % ta yozuv haqiqiy sana emas (to_date qiymatni"
        " o''zgartirib yuboradi); DATE ga o''tkazishdan oldin qo''lda tuzating"
    )
    return f"""
    DO $$
    DECLARE
        bad_count BIGINT;
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = '{table}'
              AND column_name = '{column}'
              AND data_type = 'text'
        ) THEN
            EXECUTE '{count_sql}' INTO bad_count;

            IF bad_count > 0 THEN
                RAISE EXCEPTION '{format_message}', bad_count;
            END IF;

            BEGIN
                EXECUTE '{roundtrip_sql}' INTO bad_count;
            EXCEPTION
                WHEN others THEN
                    RAISE EXCEPTION '{invalid_message}';
            END;

            IF bad_count > 0 THEN
                RAISE EXCEPTION '{shifted_message}', bad_count;
            END IF;

            EXECUTE '{alter_sql}';
        END IF;
    END $$;
    """


# --- 003: moliyaviy invariantlar uchun CHECK constraintlar ------------------
def _add_check_sql(table: str, name: str, expression: str) -> str:
    """Mavjud jadvalga CHECK qo'shadi (eski qatorlarni bloklamaslik uchun NOT VALID)."""
    return f"""
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM pg_constraint WHERE conname = '{name}'
        ) THEN
            ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({expression}) NOT VALID;
        END IF;
    END $$;
    """


MIGRATIONS: tuple[Migration, ...] = (
    Migration(
        version="001_bigint_columns",
        description="Eski INTEGER pul ustunlarini BIGINT ga o'tkazish",
        statements=_BIGINT_STATEMENTS,
    ),
    Migration(
        version="002_date_columns",
        description="debt_date / payment_date ustunlarini TEXT dan DATE ga o'tkazish",
        statements=tuple(
            _date_guard_sql(table, column) for table, column in _DATE_COLUMNS
        ),
    ),
    Migration(
        version="003_money_check_constraints",
        description="Manfiy summa va noto'g'ri qoldiqdan himoya qiluvchi CHECK'lar",
        statements=(
            _add_check_sql(
                "debts",
                "chk_debts_amounts_non_negative",
                "product_price >= 0 AND exchange_product_price >= 0"
                " AND given_money >= 0 AND original_debt >= 0"
                " AND remaining_debt >= 0 AND product_quantity >= 0",
            ),
            _add_check_sql(
                "debts",
                "chk_debts_remaining_le_original",
                "remaining_debt <= original_debt",
            ),
            _add_check_sql("payments", "chk_payments_amount_non_negative", "amount >= 0"),
        ),
    ),
    Migration(
        version="004_trash_actor_columns",
        description="Korzina arxiviga o'chirgan foydalanuvchi (actor) ustuni",
        statements=(
            "ALTER TABLE trash ADD COLUMN IF NOT EXISTS deleted_by BIGINT;",
        ),
    ),
    Migration(
        version="005_clients_phone_unique",
        description="Telefon raqami bo'yicha unique index (mijoz identity'si)",
        statements=(CREATE_UNIQUE_CLIENTS_PHONE,),
        # Mavjud bazada dublikat telefonlar bo'lsa index qo'yilmaydi — bu
        # deploy'ni to'xtatmasligi kerak, ammo ERROR log bilan ko'rinadi.
        required=False,
    ),
)


async def _applied_versions(conn: asyncpg.Connection) -> set[str]:
    rows = await conn.fetch("SELECT version FROM schema_migrations")
    return {str(row["version"]) for row in rows}


async def run_migrations(pool: asyncpg.Pool) -> list[str]:
    """Qo'llanilmagan migratsiyalarni bajaradi va ularning versiyalarini qaytaradi.

    Butun jarayon bitta tranzaksiya ichida ketadi va `pg_advisory_xact_lock`
    bilan qulflanadi. Transaction-mode pooler (Supabase 6543-port) sessiyani
    statementlar orasida saqlamaydi — shuning uchun sessiya darajasidagi
    advisory lock emas, aynan tranzaksiya darajasidagi lock ishlatiladi.

    Har bir migratsiya o'z savepoint'ida bajariladi: ixtiyoriy qadamdagi xato
    faqat o'sha qadamni bekor qiladi, qolganlarini emas.
    """
    applied_now: list[str] = []

    async with pool.acquire() as conn:
        await conn.execute(CREATE_MIGRATIONS_TABLE)

        async with conn.transaction():
            # Bir vaqtda ishga tushgan instansiyalar bir-birini kutadi;
            # lock tranzaksiya tugashi bilan avtomatik bo'shaydi.
            await conn.execute("SELECT pg_advisory_xact_lock($1)", MIGRATION_LOCK_KEY)

            already = await _applied_versions(conn)

            for migration in MIGRATIONS:
                if migration.version in already:
                    continue
                try:
                    # Ichki transaction() — SAVEPOINT: xato bo'lsa faqat shu
                    # qadam bekor qilinadi.
                    async with conn.transaction():
                        for statement in migration.statements:
                            await conn.execute(statement)
                        await conn.execute(
                            "INSERT INTO schema_migrations (version) VALUES ($1)"
                            " ON CONFLICT (version) DO NOTHING",
                            migration.version,
                        )
                except Exception:
                    if migration.required:
                        logger.error(
                            "Migratsiya bajarilmadi: %s (%s)",
                            migration.version,
                            migration.description,
                        )
                        raise
                    logger.error(
                        "Ixtiyoriy migratsiya bajarilmadi: %s (%s). "
                        "Ma'lumotlarni tekshiring — keyingi startupda qayta uriniladi.",
                        migration.version,
                        migration.description,
                        exc_info=True,
                    )
                    continue

                applied_now.append(migration.version)
                logger.info(
                    "Migratsiya qo'llandi: %s — %s",
                    migration.version,
                    migration.description,
                )

    if not applied_now:
        logger.info("Migratsiyalar allaqachon eng so'nggi holatda.")
    return applied_now
