"""Kompyuterdagi SQLite bazadan (marathon.db) Supabase'ga maʼlumotlarni koʻchirish.

Qayta ishga tushirish xavfsiz: mavjud yozuvlar takrorlanmaydi.
"""
import asyncio
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import config  # noqa: E402
import db  # noqa: E402

TABLES = ["users", "lessons", "attendance", "course_certs", "final_certs", "settings", "files"]
UPSERT_KEYS = {"lessons": "num", "settings": "key", "files": "name"}  # bularda bazadagi qiymat yangilanadi


async def migrate(sqlite_path: str) -> None:
    if not db.IS_PG:
        raise SystemExit("DATABASE_URL koʻrsatilmagan — avval supabase_ulash.bat ni ishga tushiring.")
    if not os.path.exists(sqlite_path):
        print("Kompyuterda eski baza yoʻq — koʻchiradigan narsa yoʻq.")
        return
    src = sqlite3.connect(sqlite_path)
    src.row_factory = sqlite3.Row
    existing = {r[0] for r in src.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    await db.init()
    for table in TABLES:
        if table not in existing:
            continue
        rows = src.execute(f"SELECT * FROM {table}").fetchall()
        if not rows:
            print(f"  {table:13} — boʻsh")
            continue
        cols = list(rows[0].keys())
        marks = ",".join("?" * len(cols))
        key = UPSERT_KEYS.get(table)
        if key:
            updates = ", ".join(f"{c}=excluded.{c}" for c in cols if c != key)
            conflict = f"ON CONFLICT({key}) DO UPDATE SET {updates}"
        else:
            conflict = "ON CONFLICT DO NOTHING"
        added = 0
        for r in rows:
            values = tuple(bytes(v) if isinstance(v, memoryview) else v for v in r)
            added += await db._exec(f"INSERT INTO {table}({','.join(cols)}) VALUES({marks}) {conflict}", values)
        print(f"  {table:13} — {len(rows)} ta yozuv ({added} ta yangi/yangilangan)")
    # avtomatik raqamlar (sertifikat seriyasi) davom etishi uchun
    for table in ("course_certs", "final_certs"):
        await db._exec(f"SELECT setval(pg_get_serial_sequence('{table}', 'id'),"
                       f" COALESCE((SELECT MAX(id) FROM {table}), 0) + 1, false)")
    await db.close()
    src.close()


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    print("Maʼlumotlar Supabase'ga koʻchirilmoqda...")
    asyncio.run(migrate(config.DB_PATH))
    print("Tayyor.")


if __name__ == "__main__":
    main()
