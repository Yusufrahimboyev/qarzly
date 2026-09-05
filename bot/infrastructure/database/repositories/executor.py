"""SQL bajaruvchi abstraktsiyasi: pool yoki tranzaksiya connection'i.

asyncpg'da `Pool` ham, `Connection` ham bir xil `fetch/fetchrow/execute`
interfeysiga ega. Repository'lar aynan shu interfeysga tayanadi:

- oddiy o'qish so'rovlarida pool beriladi (avtomatik acquire/release);
- bir nechta yozuvni atomik bajarish kerak bo'lganda Unit of Work bitta
  tranzaksiya connection'ini beradi.

Shu sababli repository ichida hech qachon `pool.acquire()` chaqirilmaydi —
ilgari `add()` connection ushlab turib `get_by_id()` orqali yana bitta
connection so'rar va yuqori parallel yukda pool deadlock'iga olib kelardi.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg

Executor = Any
"""asyncpg.Pool yoki asyncpg.Connection (ikkalasi bir xil interfeysga ega)."""


def is_pool(db: Executor) -> bool:
    """Berilgan executor pool ekanini aniqlaydi."""
    return isinstance(db, asyncpg.Pool) or hasattr(db, "acquire")


@asynccontextmanager
async def transaction_scope(db: Executor) -> AsyncIterator[Any]:
    """Tranzaksiya konteksti.

    Pool berilgan bo'lsa yangi connection olinadi; mavjud tranzaksiya
    connection'i berilgan bo'lsa, u savepoint sifatida ichma-ich ishlatiladi.
    """
    if is_pool(db):
        async with db.acquire() as conn:
            async with conn.transaction():
                yield conn
    else:
        async with db.transaction():
            yield db
