"""AdminService: asosiy va qo'shilgan adminlar, botlar orasida umumiy ro'yxat."""
from __future__ import annotations

import pytest

from bot.application.services.admin_service import AdminService
from tests.conftest import FakeAdminRepository

ROOT = 111


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


async def test_root_is_always_admin_and_stranger_is_not() -> None:
    service = AdminService(FakeAdminRepository(), [ROOT])
    assert await service.is_admin(ROOT)
    assert not await service.is_admin(999)


async def test_admin_added_in_one_bot_reaches_other_bot_after_cache_ttl() -> None:
    shared = FakeAdminRepository()  # bitta baza jadvali
    clock = Clock()
    mangit = AdminService(shared, [ROOT], cache_ttl=30, clock=clock)
    nukus = AdminService(shared, [ROOT], cache_ttl=30, clock=clock)
    assert not await nukus.is_admin(555)  # nukus ro'yxatni keshladi

    await mangit.add(555, "Ali", added_by=ROOT)
    assert await mangit.is_admin(555)  # qo'shgan bot darhol biladi

    clock.now = 31
    assert await nukus.is_admin(555)

    await nukus.remove(555, actor_id=ROOT)
    clock.now = 62
    assert not await mangit.is_admin(555)


async def test_cache_avoids_db_query_per_message() -> None:
    repo = FakeAdminRepository()
    service = AdminService(repo, [ROOT], clock=Clock())
    for _ in range(5):
        await service.is_admin(999)
    assert repo.list_calls == 1


async def test_root_cannot_be_removed_or_re_added() -> None:
    service = AdminService(FakeAdminRepository(), [ROOT])
    with pytest.raises(ValueError, match="Asosiy adminni"):
        await service.remove(ROOT, actor_id=555)
    with pytest.raises(ValueError, match="asosiy admin"):
        await service.add(ROOT)


async def test_cannot_remove_self_or_unknown() -> None:
    service = AdminService(FakeAdminRepository(), [ROOT])
    await service.add(555)
    with pytest.raises(ValueError, match="O'zingizni"):
        await service.remove(555, actor_id=555)
    with pytest.raises(ValueError, match="topilmadi"):
        await service.remove(777, actor_id=ROOT)


async def test_invalid_id_rejected() -> None:
    service = AdminService(FakeAdminRepository(), [ROOT])
    with pytest.raises(ValueError):
        await service.add(0)


async def test_list_puts_roots_first() -> None:
    service = AdminService(FakeAdminRepository(), [ROOT])
    await service.add(555, "  Ali   Valiyev ")
    admins = await service.list_admins()
    assert [(a.telegram_id, a.is_root, a.full_name) for a in admins] == [
        (ROOT, True, ""),
        (555, False, "Ali Valiyev"),
    ]
