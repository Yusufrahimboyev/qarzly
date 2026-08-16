from __future__ import annotations

import pytest

from bot.domain.entities.user import User
from bot.domain.repositories.user_repository import UserRepository


class FakeUserRepository(UserRepository):
    def __init__(self) -> None:
        self._store: dict[int, User] = {}

    async def add(self, user: User) -> None:
        self._store.setdefault(user.telegram_id, user)

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        return self._store.get(telegram_id)


@pytest.fixture
def fake_repo() -> FakeUserRepository:
    return FakeUserRepository()
