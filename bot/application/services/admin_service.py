"""Application qatlami: AdminService.

Botdan kim foydalana olishini hal qiladi. Ikki manba:
- `.env` dagi ADMIN_IDS — asosiy adminlar, o'chirib bo'lmaydi (hech kim
  hammani o'chirib, tizimdan qulflanib qolmasligi uchun);
- bazadagi qo'shilgan adminlar — uchala filial boti uchun bitta ro'yxat.

Ruxsat har xabarda tekshiriladi, shuning uchun bazadagi ro'yxat qisqa muddat
xotirada saqlanadi: boshqa botda qo'shilgan/o'chirilgan admin shu muddat
ichida kuchga kiradi.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterable

from bot.domain.entities.admin import Admin
from bot.domain.repositories.admin_repository import AdminRepository
from bot.i18n import _

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30.0
MAX_TELEGRAM_ID = 10**15


class AdminService:
    """Asosiy (.env) va qo'shilgan (baza) adminlarni boshqaradi."""

    def __init__(
        self,
        repository: AdminRepository,
        root_ids: Iterable[int],
        *,
        cache_ttl: float = CACHE_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._repo = repository
        self._root_ids = frozenset(root_ids)
        self._ttl = cache_ttl
        self._clock = clock
        self._cache: list[Admin] | None = None
        self._loaded_at = 0.0

    def is_root(self, telegram_id: int) -> bool:
        return telegram_id in self._root_ids

    async def _added(self) -> list[Admin]:
        if self._cache is not None and self._clock() - self._loaded_at < self._ttl:
            return self._cache
        try:
            self._cache = await self._repo.list()
            self._loaded_at = self._clock()
        except Exception:
            # Baza vaqtincha ishlamasa asosiy adminlar baribir kira oladi.
            logger.exception("Adminlar ro'yxatini bazadan o'qib bo'lmadi")
            if self._cache is None:
                return []
        return self._cache

    async def is_admin(self, telegram_id: int) -> bool:
        if telegram_id in self._root_ids:
            return True
        return any(a.telegram_id == telegram_id for a in await self._added())

    async def list_admins(self) -> list[Admin]:
        """Avval asosiy adminlar, keyin qo'shilganlar."""
        added = await self._added()
        names = {a.telegram_id: a.full_name for a in added}
        roots = [
            Admin(telegram_id=tid, full_name=names.get(tid, ""), is_root=True)
            for tid in sorted(self._root_ids)
        ]
        return roots + [a for a in added if a.telegram_id not in self._root_ids]

    async def add(
        self, telegram_id: int, full_name: str = "", added_by: int | None = None
    ) -> Admin:
        if not 0 < telegram_id < MAX_TELEGRAM_ID:
            raise ValueError(_("Telegram ID noto'g'ri."))
        if telegram_id in self._root_ids:
            raise ValueError(_("Bu foydalanuvchi allaqachon asosiy admin."))
        name = " ".join(full_name.split())[:80]
        admin = Admin(telegram_id=telegram_id, full_name=name, added_by=added_by)
        await self._repo.add(admin)
        self._cache = None
        logger.info("AUDIT admin_added telegram_id=%s by=%s", telegram_id, added_by)
        return admin

    async def remove(self, telegram_id: int, actor_id: int | None = None) -> None:
        if telegram_id in self._root_ids:
            raise ValueError(_("Asosiy adminni o'chirib bo'lmaydi (.env dagi ADMIN_IDS)."))
        if telegram_id == actor_id:
            raise ValueError(_("O'zingizni o'chira olmaysiz."))
        if not await self._repo.remove(telegram_id):
            raise ValueError(_("Bunday admin topilmadi."))
        self._cache = None
        logger.info("AUDIT admin_removed telegram_id=%s by=%s", telegram_id, actor_id)
