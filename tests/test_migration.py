"""PostgreSQL DDL sxemasi, migratsiyalar va DTO'lar uchun testlar."""
from __future__ import annotations

from bot.infrastructure.database.migrations import MIGRATIONS
from bot.infrastructure.database.schema import SCHEMA
from bot.infrastructure.web.routes import CreateDebtDTO, MakePaymentDTO


def test_schema_ddl_contains_all_required_tables() -> None:
    """Sxemada barcha asosiy jadvallar va indekslar mavjudligini tekshiradi."""
    joined_schema = "\n".join(SCHEMA)

    assert "CREATE TABLE IF NOT EXISTS users" in joined_schema
    assert "CREATE TABLE IF NOT EXISTS clients" in joined_schema
    assert "CREATE TABLE IF NOT EXISTS debts" in joined_schema
    assert "CREATE TABLE IF NOT EXISTS payments" in joined_schema
    assert "CREATE TABLE IF NOT EXISTS trash_payments" in joined_schema
    assert "CREATE TABLE IF NOT EXISTS idempotency_keys" in joined_schema

    # BIGINT qo'llanilganligini tekshirish
    assert "product_price          BIGINT" in joined_schema
    assert "remaining_debt         BIGINT" in joined_schema
    assert "amount       BIGINT" in joined_schema

    # Indekslar
    assert "idx_clients_full_name" in joined_schema
    assert "idx_debts_client_id" in joined_schema
    assert "idx_payments_client_id" in joined_schema
    # FIFO uchun composite indeks
    assert "idx_debts_client_fifo" in joined_schema


def test_schema_uses_date_columns_for_dates() -> None:
    """Sanalar TEXT emas, DATE bo'lishi kerak (C-03)."""
    joined_schema = "\n".join(SCHEMA)

    assert "debt_date              DATE NOT NULL" in joined_schema
    assert "payment_date DATE NOT NULL" in joined_schema
    assert "debt_date       DATE NOT NULL" in joined_schema
    assert "debt_date              TEXT" not in joined_schema
    assert "payment_date TEXT" not in joined_schema


def test_schema_has_money_check_constraints() -> None:
    """Manfiy summa va qoldiq > asl qarz holatlari DB darajasida bloklanadi."""
    joined_schema = "\n".join(SCHEMA)

    assert "chk_debts_amounts_non_negative" in joined_schema
    assert "chk_debts_remaining_le_original" in joined_schema


def test_migration_versions_are_unique_and_ordered() -> None:
    versions = [m.version for m in MIGRATIONS]
    assert versions == sorted(versions)
    assert len(versions) == len(set(versions))
    assert all(m.statements for m in MIGRATIONS)


def test_date_migration_guards_bad_values() -> None:
    """Sana migratsiyasi noto'g'ri qiymatlarda fail-fast bo'lishi kerak (M-09)."""
    date_migration = next(m for m in MIGRATIONS if m.version == "002_date_columns")
    sql = "\n".join(date_migration.statements)

    assert "RAISE EXCEPTION" in sql
    assert "TO_DATE" in sql
    # Faqat shablon emas, round-trip ham tekshiriladi: TO_DATE('31.02.2026')
    # xato bermay, sanani jimgina surib yuboradi.
    assert "to_char(to_date(" in sql
    assert date_migration.required is True


def test_create_debt_dto_validation() -> None:
    """CreateDebtDTO validatsiyasi."""
    valid_data = {
        "client_name": "Toshmat",
        "client_phone": "+998901234567",
        "products": [
            {"name": "Shina", "quantity": 2, "price_per_unit": 500000, "currency": "UZS"}
        ],
    }
    dto = CreateDebtDTO.model_validate(valid_data)
    assert dto.client_name == "Toshmat"
    assert len(dto.products or []) == 1


def test_create_debt_dto_strips_whitespace() -> None:
    """Nomlar avval tozalanadi, keyin uzunlik tekshiriladi (M-03)."""
    import pytest
    from pydantic import ValidationError

    dto = CreateDebtDTO.model_validate({"client_name": "  Toshmat  "})
    assert dto.client_name == "Toshmat"

    with pytest.raises(ValidationError):
        CreateDebtDTO.model_validate({"client_name": "   "})


def test_payment_dto_validation() -> None:
    """MakePaymentDTO validatsiyasi."""
    valid_data = {
        "client_id": 5,
        "payment_type": "partial",
        "amount": 250000,
        "currency": "UZS",
    }
    dto = MakePaymentDTO.model_validate(valid_data)
    assert dto.client_id == 5
    assert dto.amount == 250000


def test_payment_dto_rejects_unknown_field() -> None:
    """Noto'g'ri yozilgan maydon jimgina e'tiborsiz qolmasligi kerak."""
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        MakePaymentDTO.model_validate({"client_id": 5, "mode": "full"})
