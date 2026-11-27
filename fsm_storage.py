"""FSM holatini (roʻyxatdan oʻtish qadamlari, admin kiritayotgan qiymatlar) bazada saqlash.

Render bepul tarifida bot uxlab qolib, qayta ishga tushadi — xotiradagi holat yoʻqolmasligi uchun.
Tezlik uchun holat xotirada ham saqlanadi: oʻqish bazaga bormaydi (faqat birinchi marta),
yozish esa faqat qiymat oʻzgarganda va bitta soʻrov bilan bajariladi.
"""
import json
from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

import db

_MAX_CACHE = 20000


def _key(key: StorageKey) -> str:
    return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id or 0}:{key.destiny}"


class DbStorage(BaseStorage):
    def __init__(self) -> None:
        self._cache: dict[str, tuple[str | None, str]] = {}   # key -> (state, data JSON)

    async def _load(self, k: str) -> tuple[str | None, str]:
        hit = self._cache.get(k)
        if hit is None:
            row = await db.fsm_get(k)
            hit = (row["state"], row["data"] or "{}") if row else (None, "{}")
            if len(self._cache) >= _MAX_CACHE:
                self._cache.clear()
            self._cache[k] = hit
        return hit

    async def _save(self, k: str, state: str | None, data: str) -> None:
        if self._cache.get(k) == (state, data):
            return
        await db.fsm_put(k, state, data)
        self._cache[k] = (state, data)

    async def set_state(self, key: StorageKey, state=None) -> None:
        value = state.state if isinstance(state, State) else state
        k = _key(key)
        _, data = await self._load(k)
        await self._save(k, value, data)

    async def get_state(self, key: StorageKey) -> str | None:
        return (await self._load(_key(key)))[0]

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        k = _key(key)
        state, _ = await self._load(k)
        await self._save(k, state, json.dumps(dict(data), ensure_ascii=False))

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        return json.loads((await self._load(_key(key)))[1])

    async def close(self) -> None:
        pass
