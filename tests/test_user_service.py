from __future__ import annotations

import pytest

from bot.application.services.user_service import UserService
from tests.conftest import FakeUserRepository


@pytest.mark.asyncio
async def test_register_yangi_foydalanuvchi(fake_repo: FakeUserRepository) -> None:
    service = UserService(fake_repo)

    user = await service.register(telegram_id=1, full_name="Ali", username="ali")

    assert user.telegram_id == 1
    assert user.full_name == "Ali"
    assert await fake_repo.get_by_telegram_id(1) is not None


@pytest.mark.asyncio
async def test_register_idempotent(fake_repo: FakeUserRepository) -> None:
    service = UserService(fake_repo)

    first = await service.register(telegram_id=1, full_name="Ali")
    second = await service.register(telegram_id=1, full_name="Boshqa ism")

    assert first == second
    assert first.full_name == "Ali"


@pytest.mark.asyncio
async def test_get_mavjud_emas(fake_repo: FakeUserRepository) -> None:
    service = UserService(fake_repo)
    assert await service.get(telegram_id=999) is None
