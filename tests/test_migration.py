"""PostgreSQL DDL sxemasi va DTO'lar uchun testlar."""
from __future__ import annotations

from bot.infrastructure.database.schema import SCHEMA
from bot.infrastructure.web.routes import CreateDebtDTO, MakePaymentDTO


def test_schema_ddl_contains_all_required_tables() -> None:
    """Sxemada barcha 4 ta asosiy jadval va indekslar mavjudligini tekshiradi."""
    joined_schema = "\n".join(SCHEMA)

    assert "CREATE TABLE IF NOT EXISTS users" in joined_schema
    assert "CREATE TABLE IF NOT EXISTS clients" in joined_schema
    assert "CREATE TABLE IF NOT EXISTS debts" in joined_schema
    assert "CREATE TABLE IF NOT EXISTS payments" in joined_schema

    # BIGINT qo'llanilganligini tekshirish
    assert "product_price          BIGINT" in joined_schema
    assert "remaining_debt         BIGINT" in joined_schema
    assert "amount       BIGINT" in joined_schema

    # Indekslar
    assert "idx_clients_full_name" in joined_schema
    assert "idx_debts_client_id" in joined_schema
    assert "idx_payments_client_id" in joined_schema


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
