"""ClientService uchun testlar."""
from __future__ import annotations

import pytest

from bot.application.services.client_service import ClientService
from bot.application.services.debt_service import DebtService
from bot.infrastructure.database.repositories.client_repository import (
    SqliteClientRepository,
)
from bot.infrastructure.database.repositories.debt_repository import (
    SqliteDebtRepository,
)
from bot.infrastructure.database.repositories.payment_repository import (
    SqlitePaymentRepository,
)


@pytest.mark.asyncio
async def test_client_get_or_create(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
) -> None:
    service = ClientService(client_repo, debt_repo)

    # Yangi mijoz
    client1, is_new1 = await service.get_or_create("Aliyev Anvar", "+998901234567")
    assert is_new1 is True
    assert client1.id is not None
    assert client1.full_name == "Aliyev Anvar"

    # Mavjud mijoz (telefon orqali)
    client2, is_new2 = await service.get_or_create("Aliyev Anvar Boshqa", "+998901234567")
    assert is_new2 is False
    assert client2.id == client1.id

    # Mavjud mijoz (ism orqali)
    client3, is_new3 = await service.get_or_create("Aliyev Anvar", "+998999999999")
    assert is_new3 is False
    assert client3.id == client1.id


@pytest.mark.asyncio
async def test_get_or_create_empty_phone_does_not_link_strangers(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
) -> None:
    """Bo'sh telefonli ikki xil mijoz bir-biriga bog'lanmasligi kerak."""
    service = ClientService(client_repo, debt_repo)

    client1, is_new1 = await service.get_or_create("Aliyev Anvar", "")
    assert is_new1 is True

    client2, is_new2 = await service.get_or_create("Karimov Bobur", "")
    assert is_new2 is True
    assert client2.id != client1.id

    # Xuddi shu ism — allaqachon mavjud mijoz qaytadi
    client3, is_new3 = await service.get_or_create("Aliyev Anvar", "")
    assert is_new3 is False
    assert client3.id == client1.id


@pytest.mark.asyncio
async def test_alphabetical_summaries_and_debtors(
    client_repo: SqliteClientRepository,
    debt_repo: SqliteDebtRepository,
    payment_repo: SqlitePaymentRepository,
) -> None:
    client_service = ClientService(client_repo, debt_repo)
    debt_service = DebtService(client_repo, debt_repo, payment_repo)

    # 3 ta mijoz: Zohid, Anvar, Bekzod
    c_zohid, _ = await client_service.get_or_create("Zohidov Zohid", "+998903333333")
    c_anvar, _ = await client_service.get_or_create("Aliyev Anvar", "+998901111111")
    c_bekzod, _ = await client_service.get_or_create("Bekzod Karimov", "+998902222222")

    # Qarzlar: Anvar (1 000 000), Zohid (500 000), Bekzod (qarz yo'q)
    await debt_service.create_debt(c_anvar.id, "16.08.2026", "Shina", 1000000)  # type: ignore[arg-type]
    await debt_service.create_debt(c_zohid.id, "16.08.2026", "Moy", 500000)  # type: ignore[arg-type]

    # Barcha mijozlar alifbo tartibida
    all_summaries = await client_service.get_all_summaries()
    names = [s.client.full_name for s in all_summaries]
    assert names == ["Aliyev Anvar", "Bekzod Karimov", "Zohidov Zohid"]

    # Faqat qarzdorlar alifbo tartibida (Bekzod bo'lmasligi kerak)
    debtors = await client_service.get_debtor_summaries()
    debtor_names = [d.client.full_name for d in debtors]
    assert debtor_names == ["Aliyev Anvar", "Zohidov Zohid"]
    assert debtors[0].remaining_by_currency == {"UZS": 1000000}
    assert debtors[1].remaining_by_currency == {"UZS": 500000}
