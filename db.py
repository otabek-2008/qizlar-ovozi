"""Maʼlumotlar bazasi.

DATABASE_URL berilgan boʻlsa — PostgreSQL (Supabase), aks holda — mahalliy SQLite fayl (DB_PATH).
SQL bir xil yoziladi ("?" belgilari bilan); PostgreSQL uchun avtomatik $1, $2... ga oʻgiriladi.
"""
import re
from datetime import datetime, timezone

import config

IS_PG = bool(config.DATABASE_URL)
_pool = None   # asyncpg pool (PostgreSQL)
_db = None     # aiosqlite connection (SQLite)

TABLES = ["users", "lessons", "attendance", "course_certs", "final_certs", "settings", "fsm", "files",
          "admin_sessions"]

SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users(
    tg_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
    phone TEXT NOT NULL, birth_date TEXT NOT NULL, study_place TEXT, referrer_id INTEGER,
    registered_at TEXT NOT NULL, eligible_at TEXT, auto_admin INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS lessons(num INTEGER PRIMARY KEY, title TEXT, code TEXT, opens_at TEXT, closes_at TEXT);
CREATE TABLE IF NOT EXISTS attendance(
    tg_id INTEGER NOT NULL, lesson_num INTEGER NOT NULL, marked_at TEXT NOT NULL, PRIMARY KEY(tg_id, lesson_num)
);
CREATE TABLE IF NOT EXISTS course_certs(
    id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL, course_idx INTEGER NOT NULL,
    file_id TEXT NOT NULL, file_unique_id TEXT NOT NULL, file_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', reject_reason TEXT, submitted_at TEXT NOT NULL,
    reviewed_at TEXT, reviewed_by INTEGER
);
CREATE TABLE IF NOT EXISTS final_certs(
    id INTEGER PRIMARY KEY AUTOINCREMENT, tg_id INTEGER NOT NULL UNIQUE, issued_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS fsm(key TEXT PRIMARY KEY, state TEXT, data TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS files(name TEXT PRIMARY KEY, data BLOB NOT NULL);
CREATE TABLE IF NOT EXISTS admin_sessions(user_id INTEGER PRIMARY KEY, expires REAL NOT NULL);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users(
    tg_id BIGINT PRIMARY KEY, username TEXT, first_name TEXT NOT NULL, last_name TEXT NOT NULL,
    phone TEXT NOT NULL, birth_date TEXT NOT NULL, study_place TEXT, referrer_id BIGINT,
    registered_at TEXT NOT NULL, eligible_at TEXT, auto_admin INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS lessons(num INTEGER PRIMARY KEY, title TEXT, code TEXT, opens_at TEXT, closes_at TEXT);
CREATE TABLE IF NOT EXISTS attendance(
    tg_id BIGINT NOT NULL, lesson_num INTEGER NOT NULL, marked_at TEXT NOT NULL, PRIMARY KEY(tg_id, lesson_num)
);
CREATE TABLE IF NOT EXISTS course_certs(
    id BIGSERIAL PRIMARY KEY, tg_id BIGINT NOT NULL, course_idx INTEGER NOT NULL,
    file_id TEXT NOT NULL, file_unique_id TEXT NOT NULL, file_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending', reject_reason TEXT, submitted_at TEXT NOT NULL,
    reviewed_at TEXT, reviewed_by BIGINT
);
CREATE TABLE IF NOT EXISTS final_certs(
    id BIGSERIAL PRIMARY KEY, tg_id BIGINT NOT NULL UNIQUE, issued_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS fsm(key TEXT PRIMARY KEY, state TEXT, data TEXT NOT NULL DEFAULT '{}');
CREATE TABLE IF NOT EXISTS files(name TEXT PRIMARY KEY, data BYTEA NOT NULL);
CREATE TABLE IF NOT EXISTS admin_sessions(user_id BIGINT PRIMARY KEY, expires DOUBLE PRECISION NOT NULL);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_users_ref ON users(referrer_id);
CREATE INDEX IF NOT EXISTS idx_users_phone ON users(phone);
CREATE INDEX IF NOT EXISTS idx_cc_user ON course_certs(tg_id);
CREATE INDEX IF NOT EXISTS idx_cc_file ON course_certs(file_unique_id);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def to_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def _pg(sql: str) -> str:
    n = 0

    def repl(_):
        nonlocal n
        n += 1
        return f"${n}"
    return re.sub(r"\?", repl, sql)


def _statements(script: str) -> list[str]:
    return [s.strip() for s in script.split(";") if s.strip()]


# ---------------------------------------------------------------- ulanish
async def init() -> None:
    global _pool, _db
    if IS_PG:
        import asyncpg
        dsn = config.DATABASE_URL
        local = any(h in dsn for h in ("@localhost", "@127.0.0.1"))
        server_settings = {"search_path": config.DB_SCHEMA} if config.DB_SCHEMA else None
        _pool = await asyncpg.create_pool(
            dsn, min_size=1, max_size=5, statement_cache_size=0,  # Supabase pooler bilan mos
            ssl=None if local else "require", server_settings=server_settings, command_timeout=60,
        )
        async with _pool.acquire() as c:
            if config.DB_SCHEMA:
                await c.execute(f'CREATE SCHEMA IF NOT EXISTS "{config.DB_SCHEMA}"')
            for stmt in _statements(SCHEMA_PG) + _statements(INDEXES):
                await c.execute(stmt)
            await c.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS auto_admin INTEGER NOT NULL DEFAULT 0")
            # Supabase API (anon kalit) orqali jadvallarni oʻqib boʻlmasin — faqat bot (toʻgʻridan-toʻgʻri ulanish)
            for t in TABLES:
                await c.execute(f"ALTER TABLE {t} ENABLE ROW LEVEL SECURITY")
    else:
        import aiosqlite
        _db = await aiosqlite.connect(config.DB_PATH)
        _db.row_factory = aiosqlite.Row
        await _db.execute("PRAGMA journal_mode=WAL")
        await _db.executescript(SCHEMA_SQLITE + INDEXES)
        cols = {r[1] for r in await _all("PRAGMA table_info(users)")}
        if "auto_admin" not in cols:
            await _db.execute("ALTER TABLE users ADD COLUMN auto_admin INTEGER NOT NULL DEFAULT 0")
        await _db.commit()
    await ensure_lessons()


async def close() -> None:
    if _pool:
        await _pool.close()
    if _db:
        await _db.close()


async def _one(sql: str, args: tuple = ()):
    if IS_PG:
        async with _pool.acquire() as c:
            return await c.fetchrow(_pg(sql), *args)
    async with _db.execute(sql, args) as cur:
        return await cur.fetchone()


async def _all(sql: str, args: tuple = ()):
    if IS_PG:
        async with _pool.acquire() as c:
            return await c.fetch(_pg(sql), *args)
    async with _db.execute(sql, args) as cur:
        return await cur.fetchall()


async def _exec(sql: str, args: tuple = ()) -> int:
    """Buyruqni bajaradi va oʻzgargan qatorlar sonini qaytaradi."""
    if IS_PG:
        async with _pool.acquire() as c:
            status = await c.execute(_pg(sql), *args)
        last = status.split()[-1] if status else "0"
        return int(last) if last.isdigit() else 0
    cur = await _db.execute(sql, args)
    await _db.commit()
    return cur.rowcount


async def _count(sql: str, args: tuple = ()) -> int:
    row = await _one(sql, args)
    return int(row[0] or 0) if row else 0


def _agg(expr: str, sep: str, order: str) -> str:
    """Qatorlarni bitta matnga yigʻish (SQLite va PostgreSQL uchun)."""
    if IS_PG:
        return f"string_agg(({expr})::text, '{sep}' ORDER BY {order})"
    return f"group_concat({expr}, '{sep}')"


async def ensure_lessons() -> None:
    for n in range(1, config.LESSONS_COUNT + 1):
        await _exec("INSERT INTO lessons(num, title) VALUES(?, ?) ON CONFLICT DO NOTHING", (n, f"{n}-dars"))


# ---------------------------------------------------------------- users
async def get_user(tg_id: int):
    return await _one("SELECT * FROM users WHERE tg_id=?", (tg_id,))


async def find_user(query: str):
    q = query.strip().lstrip("@")
    if q.lstrip("+").isdigit():
        row = await _one("SELECT * FROM users WHERE tg_id=?", (int(q.lstrip("+")),))
        if row:
            return row
        return await _one("SELECT * FROM users WHERE phone=?", ("+" + q.lstrip("+"),))
    return await _one("SELECT * FROM users WHERE lower(username)=lower(?)", (q,))


async def add_user(tg_id, username, first_name, last_name, phone, birth_date, study_place, referrer_id) -> bool:
    return await _exec(
        "INSERT INTO users(tg_id, username, first_name, last_name, phone, birth_date,"
        " study_place, referrer_id, registered_at) VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT DO NOTHING",
        (tg_id, username, first_name, last_name, phone, birth_date, study_place, referrer_id, now_iso()),
    ) == 1


async def ensure_admin_profile(tg_id: int, username, first_name: str, last_name: str):
    """Roʻyxatdan oʻtmagan admin davomat/sertifikatdan foydalanishi uchun Telegram ismi bilan profil."""
    now = now_iso()
    await _exec(
        "INSERT INTO users(tg_id, username, first_name, last_name, phone, birth_date, study_place,"
        " referrer_id, registered_at, eligible_at, auto_admin) VALUES(?,?,?,?,'—','—','Admin',NULL,?,?,1)"
        " ON CONFLICT DO NOTHING",
        (tg_id, username, first_name, last_name, now, now),
    )
    return await get_user(tg_id)


async def delete_auto_admin(tg_id: int) -> None:
    """Admin oʻzi roʻyxatdan oʻtganda avtomatik profil haqiqiysi bilan almashtiriladi."""
    await _exec("DELETE FROM users WHERE tg_id=? AND auto_admin=1", (tg_id,))


EDITABLE_FIELDS = {"first_name", "last_name", "phone", "birth_date", "study_place"}


async def update_user_field(tg_id: int, field: str, value: str) -> None:
    if field not in EDITABLE_FIELDS:
        raise ValueError(field)
    await _exec(f"UPDATE users SET {field}=? WHERE tg_id=?", (value, tg_id))


async def unset_eligible(tg_id: int) -> None:
    await _exec("UPDATE users SET eligible_at=NULL WHERE tg_id=?", (tg_id,))


async def unmark_attendance(tg_id: int, lesson_num: int) -> None:
    await _exec("DELETE FROM attendance WHERE tg_id=? AND lesson_num=?", (tg_id, lesson_num))


async def delete_user(tg_id: int) -> bool:
    """Ishtirokchini va unga tegishli barcha maʼlumotlarni (davomat, sertifikatlar) oʻchiradi."""
    for sql in ("DELETE FROM attendance WHERE tg_id=?",
                "DELETE FROM course_certs WHERE tg_id=?",
                "DELETE FROM final_certs WHERE tg_id=?",
                "UPDATE users SET referrer_id=NULL WHERE referrer_id=?"):
        await _exec(sql, (tg_id,))
    return await _exec("DELETE FROM users WHERE tg_id=?", (tg_id,)) == 1


async def phone_taken(phone: str, tg_id: int) -> bool:
    return await _count("SELECT COUNT(*) FROM users WHERE phone=? AND tg_id<>?", (phone, tg_id)) > 0


async def referral_count(tg_id: int) -> int:
    return await _count("SELECT COUNT(*) FROM users WHERE referrer_id=?", (tg_id,))


LIST_FILTERS = {
    "all": "u.auto_admin=0",
    "elig": "u.auto_admin=0 AND u.eligible_at IS NOT NULL",
    "new": "u.auto_admin=0 AND u.eligible_at IS NULL",
}


async def list_users(filter_key: str, offset: int, limit: int):
    """Ishtirokchilar roʻyxati (eng yangilari birinchi) + takliflar va davomat soni."""
    where = LIST_FILTERS.get(filter_key, LIST_FILTERS["all"])
    return await _all(
        "SELECT u.*,"
        " (SELECT COUNT(*) FROM users r WHERE r.referrer_id=u.tg_id) AS refs,"
        " (SELECT COUNT(*) FROM attendance a WHERE a.tg_id=u.tg_id AND a.lesson_num<=?) AS att"
        f" FROM users u WHERE {where} ORDER BY u.registered_at DESC, u.tg_id DESC LIMIT ? OFFSET ?",
        (config.LESSONS_COUNT, limit, offset),
    )


async def count_users(filter_key: str) -> int:
    where = LIST_FILTERS.get(filter_key, LIST_FILTERS["all"])
    return await _count(f"SELECT COUNT(*) FROM users u WHERE {where}")


async def get_invitees(tg_id: int):
    """Shu odam taklif qilgan barcha ishtirokchilar (roʻyxatdan oʻtish tartibida)."""
    return await _all("SELECT * FROM users WHERE referrer_id=? ORDER BY registered_at", (tg_id,))


async def set_eligible(tg_id: int) -> bool:
    """True qaytaradi, agar foydalanuvchi aynan hozir ruxsat olgan boʻlsa."""
    return await _exec("UPDATE users SET eligible_at=? WHERE tg_id=? AND eligible_at IS NULL",
                       (now_iso(), tg_id)) == 1


async def top_referrers(limit: int):
    return await _all(
        "SELECT u.tg_id, u.first_name, u.last_name, u.username, u.phone,"
        " COUNT(r.tg_id) AS cnt, MAX(r.registered_at) AS last_at"
        " FROM users u JOIN users r ON r.referrer_id = u.tg_id"
        " GROUP BY u.tg_id ORDER BY cnt DESC, last_at ASC LIMIT ?",
        (limit,),
    )


async def user_rank(tg_id: int) -> int | None:
    mine = await referral_count(tg_id)
    if mine == 0:
        return None
    better = await _count(
        "SELECT COUNT(*) FROM (SELECT referrer_id FROM users WHERE referrer_id IS NOT NULL"
        " GROUP BY referrer_id HAVING COUNT(*) > ?) AS t",
        (mine,),
    )
    return better + 1


async def all_user_ids(only_eligible: bool = False, participants_only: bool = False) -> list[int]:
    where = []
    if only_eligible:
        where.append("eligible_at IS NOT NULL")
    if participants_only:
        where.append("auto_admin=0")
    sql = "SELECT tg_id FROM users" + (" WHERE " + " AND ".join(where) if where else "")
    return [r[0] for r in await _all(sql)]


async def export_rows():
    invitees = _agg("r2.first_name || ' ' || r2.last_name", ", ", "r2.registered_at")
    att_list = _agg("a2.lesson_num", ",", "a2.lesson_num")
    return await _all(
        "SELECT u.*,"
        " (SELECT p.first_name || ' ' || p.last_name FROM users p WHERE p.tg_id=u.referrer_id) AS ref_name,"
        " (SELECT p.phone FROM users p WHERE p.tg_id=u.referrer_id) AS ref_phone,"
        f" (SELECT {invitees} FROM (SELECT * FROM users r3 WHERE r3.referrer_id=u.tg_id"
        "    ORDER BY r3.registered_at) AS r2) AS invitees,"
        " (SELECT COUNT(*) FROM users r WHERE r.referrer_id=u.tg_id) AS refs,"
        " (SELECT COUNT(*) FROM attendance a WHERE a.tg_id=u.tg_id) AS att,"
        f" (SELECT {att_list} FROM (SELECT * FROM attendance a3 WHERE a3.tg_id=u.tg_id"
        "    ORDER BY a3.lesson_num) AS a2) AS att_list,"
        " (SELECT COUNT(DISTINCT course_idx) FROM course_certs c WHERE c.tg_id=u.tg_id"
        "    AND c.status='approved') AS courses,"
        " (SELECT id FROM final_certs f WHERE f.tg_id=u.tg_id) AS final_id"
        " FROM users u WHERE u.auto_admin=0 ORDER BY refs DESC, u.registered_at ASC"
    )


# ---------------------------------------------------------------- lessons
async def get_lessons():
    return await _all("SELECT * FROM lessons WHERE num<=? ORDER BY num", (config.LESSONS_COUNT,))


async def get_lesson(num: int):
    return await _one("SELECT * FROM lessons WHERE num=?", (num,))


async def open_lesson(num: int, code: str, opens_at: str, closes_at: str) -> None:
    await _exec("UPDATE lessons SET code=?, opens_at=?, closes_at=? WHERE num=?", (code, opens_at, closes_at, num))


async def close_lesson(num: int) -> None:
    await _exec("UPDATE lessons SET closes_at=? WHERE num=?", (now_iso(), num))


async def set_lesson_title(num: int, title: str) -> None:
    await _exec("UPDATE lessons SET title=? WHERE num=?", (title, num))


async def open_lessons():
    now = now_iso()
    return await _all(
        "SELECT * FROM lessons WHERE opens_at<=? AND closes_at>? AND num<=? ORDER BY num",
        (now, now, config.LESSONS_COUNT),
    )


# ---------------------------------------------------------------- attendance
async def mark_attendance(tg_id: int, lesson_num: int) -> bool:
    return await _exec(
        "INSERT INTO attendance(tg_id, lesson_num, marked_at) VALUES(?,?,?) ON CONFLICT DO NOTHING",
        (tg_id, lesson_num, now_iso()),
    ) == 1


async def attendance_count(tg_id: int) -> int:
    return await _count(
        "SELECT COUNT(*) FROM attendance WHERE tg_id=? AND lesson_num<=?", (tg_id, config.LESSONS_COUNT)
    )


async def user_attendance(tg_id: int) -> set[int]:
    return {r[0] for r in await _all("SELECT lesson_num FROM attendance WHERE tg_id=?", (tg_id,))}


async def users_with_full_attendance() -> list[int]:
    rows = await _all(
        "SELECT tg_id FROM attendance WHERE lesson_num<=? GROUP BY tg_id HAVING COUNT(*)>=?",
        (config.LESSONS_COUNT, config.LESSONS_COUNT),
    )
    return [r[0] for r in rows]


# ---------------------------------------------------------------- course certificates
async def course_status(tg_id: int) -> dict[int, str]:
    """Har bir kurs uchun eng yaxshi holat: approved > pending > rejected."""
    priority = {"approved": 3, "pending": 2, "rejected": 1}
    result: dict[int, str] = {}
    for r in await _all("SELECT course_idx, status FROM course_certs WHERE tg_id=?", (tg_id,)):
        cur = result.get(r["course_idx"])
        if cur is None or priority[r["status"]] > priority[cur]:
            result[r["course_idx"]] = r["status"]
    return result


async def file_used(file_unique_id: str) -> bool:
    return await _count(
        "SELECT COUNT(*) FROM course_certs WHERE file_unique_id=? AND status<>'rejected'", (file_unique_id,)
    ) > 0


async def add_course_cert(tg_id, course_idx, file_id, file_unique_id, file_type) -> int:
    row = await _one(
        "INSERT INTO course_certs(tg_id, course_idx, file_id, file_unique_id, file_type, submitted_at)"
        " VALUES(?,?,?,?,?,?) RETURNING id",
        (tg_id, course_idx, file_id, file_unique_id, file_type, now_iso()),
    )
    if not IS_PG:
        await _db.commit()
    return row[0]


async def get_course_cert(cert_id: int):
    return await _one("SELECT * FROM course_certs WHERE id=?", (cert_id,))


async def review_course_cert(cert_id: int, status: str, reason: str | None, admin_id: int) -> bool:
    return await _exec(
        "UPDATE course_certs SET status=?, reject_reason=?, reviewed_at=?, reviewed_by=?"
        " WHERE id=? AND status='pending'",
        (status, reason, now_iso(), admin_id, cert_id),
    ) == 1


async def approved_course_count(tg_id: int) -> int:
    return await _count(
        "SELECT COUNT(DISTINCT course_idx) FROM course_certs WHERE tg_id=? AND status='approved' AND course_idx<?",
        (tg_id, len(config.COURSES)),
    )


async def count_pending() -> int:
    return await _count("SELECT COUNT(*) FROM course_certs WHERE status='pending'")


async def pending_certs(limit: int):
    return await _all("SELECT * FROM course_certs WHERE status='pending' ORDER BY id LIMIT ?", (limit,))


# ---------------------------------------------------------------- final certificates
async def get_final(tg_id: int):
    return await _one("SELECT * FROM final_certs WHERE tg_id=?", (tg_id,))


async def create_final(tg_id: int) -> bool:
    return await _exec("INSERT INTO final_certs(tg_id, issued_at) VALUES(?,?) ON CONFLICT DO NOTHING",
                       (tg_id, now_iso())) == 1


# ---------------------------------------------------------------- settings
async def get_setting(key: str, default: str | None = None) -> str | None:
    row = await _one("SELECT value FROM settings WHERE key=?", (key,))
    return row[0] if row else default


async def set_setting(key: str, value: str) -> None:
    await _exec("INSERT INTO settings(key, value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value))


# ---------------------------------------------------------------- FSM holati (roʻyxatdan oʻtish qadamlari va h.k.)
async def fsm_get(key: str):
    return await _one("SELECT state, data FROM fsm WHERE key=?", (key,))


async def fsm_set_state(key: str, state: str | None) -> None:
    await _exec("INSERT INTO fsm(key, state, data) VALUES(?,?,'{}')"
                " ON CONFLICT(key) DO UPDATE SET state=excluded.state", (key, state))
    await _exec("DELETE FROM fsm WHERE key=? AND state IS NULL AND data='{}'", (key,))


async def fsm_set_data(key: str, data: str) -> None:
    await _exec("INSERT INTO fsm(key, state, data) VALUES(?,NULL,?)"
                " ON CONFLICT(key) DO UPDATE SET data=excluded.data", (key, data))
    await _exec("DELETE FROM fsm WHERE key=? AND state IS NULL AND data='{}'", (key,))


# ---------------------------------------------------------------- fayllar (sertifikat shabloni)
async def file_get(name: str) -> bytes | None:
    row = await _one("SELECT data FROM files WHERE name=?", (name,))
    return bytes(row[0]) if row else None


async def file_set(name: str, data: bytes) -> None:
    await _exec("INSERT INTO files(name, data) VALUES(?,?) ON CONFLICT(name) DO UPDATE SET data=excluded.data",
                (name, data))


async def file_delete(name: str) -> None:
    await _exec("DELETE FROM files WHERE name=?", (name,))


# ---------------------------------------------------------------- admin sessiyalari
async def sessions_all() -> dict[int, float]:
    return {int(r[0]): float(r[1]) for r in await _all("SELECT user_id, expires FROM admin_sessions")}


async def session_set(user_id: int, expires: float) -> None:
    await _exec("INSERT INTO admin_sessions(user_id, expires) VALUES(?,?)"
                " ON CONFLICT(user_id) DO UPDATE SET expires=excluded.expires", (user_id, expires))


async def session_delete(user_id: int | None = None) -> None:
    if user_id is None:
        await _exec("DELETE FROM admin_sessions")
    else:
        await _exec("DELETE FROM admin_sessions WHERE user_id=?", (user_id,))


# ---------------------------------------------------------------- statistics
async def stats(today_start_iso: str) -> dict:
    n = config.LESSONS_COUNT
    s = {
        "users": await _count("SELECT COUNT(*) FROM users WHERE auto_admin=0"),
        "today": await _count("SELECT COUNT(*) FROM users WHERE auto_admin=0 AND registered_at>=?",
                              (today_start_iso,)),
        "eligible": await _count("SELECT COUNT(*) FROM users WHERE auto_admin=0 AND eligible_at IS NOT NULL"),
        "invited": await _count("SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL"),
        "inviters": await _count("SELECT COUNT(DISTINCT referrer_id) FROM users WHERE referrer_id IS NOT NULL"),
        "any_lesson": await _count("SELECT COUNT(DISTINCT tg_id) FROM attendance WHERE lesson_num<=?", (n,)),
        "all_lessons": len(await users_with_full_attendance()),
        "courses_done": await _count(
            "SELECT COUNT(*) FROM (SELECT tg_id FROM course_certs WHERE status='approved' AND course_idx<?"
            " GROUP BY tg_id HAVING COUNT(DISTINCT course_idx)>=?) AS t",
            (len(config.COURSES), len(config.COURSES)),
        ),
        "finals": await _count("SELECT COUNT(*) FROM final_certs"),
    }
    s["lessons"] = {r[0]: r[1] for r in await _all(
        "SELECT lesson_num, COUNT(*) FROM attendance GROUP BY lesson_num")}
    s["certs"] = {r[0]: r[1] for r in await _all("SELECT status, COUNT(*) FROM course_certs GROUP BY status")}
    return s
