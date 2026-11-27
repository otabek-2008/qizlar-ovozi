"""Admin panel paroli: xeshlash, sessiyalar va notoʻgʻri urinishlarni cheklash."""
import hashlib
import hmac
import os
import time

import db

PW_KEY = "admin_pw_hash"
MIN_LENGTH = 6
SESSION_HOURS = 12      # paroldan keyin panel shuncha vaqt ochiq turadi
MAX_FAILS = 5           # shuncha notoʻgʻri urinishdan keyin...
LOCK_MINUTES = 15       # ...shuncha daqiqaga bloklanadi

_sessions: dict[int, float] = {}
_fails: dict[int, int] = {}
_locked_until: dict[int, float] = {}


def _hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"{salt.hex()}${digest.hex()}"


async def has_password() -> bool:
    return bool(await db.get_setting(PW_KEY))


async def set_password(password: str) -> None:
    await db.set_setting(PW_KEY, _hash(password))


async def check_password(password: str) -> bool:
    stored = await db.get_setting(PW_KEY)
    if not stored or "$" not in stored:
        return False
    salt_hex, _ = stored.split("$", 1)
    return hmac.compare_digest(_hash(password, bytes.fromhex(salt_hex)), stored)


async def load_sessions() -> None:
    """Bot qayta ishga tushganda (masalan, Render uygʻotganda) kirgan adminlar chiqib ketmasin."""
    _sessions.clear()
    _sessions.update(await db.sessions_all())


def logged_in(user_id: int) -> bool:
    return _sessions.get(user_id, 0) > time.time()


async def login(user_id: int) -> None:
    _sessions[user_id] = time.time() + SESSION_HOURS * 3600
    _fails.pop(user_id, None)
    await db.session_set(user_id, _sessions[user_id])


async def logout(user_id: int) -> None:
    _sessions.pop(user_id, None)
    await db.session_delete(user_id)


async def logout_all() -> None:
    _sessions.clear()
    await db.session_delete()


def locked_minutes(user_id: int) -> int:
    left = _locked_until.get(user_id, 0) - time.time()
    return int(left // 60) + 1 if left > 0 else 0


def register_fail(user_id: int) -> int:
    """Qolgan urinishlar sonini qaytaradi (0 — bloklandi)."""
    _fails[user_id] = _fails.get(user_id, 0) + 1
    if _fails[user_id] >= MAX_FAILS:
        _fails.pop(user_id, None)
        _locked_until[user_id] = time.time() + LOCK_MINUTES * 60
        return 0
    return MAX_FAILS - _fails[user_id]
