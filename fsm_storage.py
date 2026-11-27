"""FSM holatini (roʻyxatdan oʻtish qadamlari, admin kiritayotgan qiymatlar) bazada saqlash.

Render bepul tarifida bot uxlab qolib, qayta ishga tushadi — xotiradagi holat yoʻqolmasligi uchun.
"""
import json
from typing import Any, Mapping

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

import db


def _key(key: StorageKey) -> str:
    return f"{key.bot_id}:{key.chat_id}:{key.user_id}:{key.thread_id or 0}:{key.destiny}"


class DbStorage(BaseStorage):
    async def set_state(self, key: StorageKey, state=None) -> None:
        value = state.state if isinstance(state, State) else state
        await db.fsm_set_state(_key(key), value)

    async def get_state(self, key: StorageKey) -> str | None:
        row = await db.fsm_get(_key(key))
        return row["state"] if row else None

    async def set_data(self, key: StorageKey, data: Mapping[str, Any]) -> None:
        await db.fsm_set_data(_key(key), json.dumps(dict(data), ensure_ascii=False))

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        row = await db.fsm_get(_key(key))
        return json.loads(row["data"]) if row and row["data"] else {}

    async def close(self) -> None:
        pass
