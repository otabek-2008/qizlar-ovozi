"""Supabase'dagi barcha maʼlumotlarni kompyuterga zaxira qilish.

Natija — "zaxira" papkasida:
  marathon_YYYY-MM-DD_HH-MM.db     — toʻliq baza (ishtirokchilar, davomat, sertifikatlar, sozlamalar, parol, shablon)
  ishtirokchilar_YYYY-MM-DD_HH-MM.csv — Excel'da ochiladigan roʻyxat
Oxirgi 60 ta nusxa saqlanadi (har 6 soatda — taxminan 15 kunlik).

Qoʻlda: zaxira_olish.bat. Avtomatik: Windows "Task Scheduler" (zaxira_jadval.bat bir marta).
Zaxiradan Supabase'ga qaytarish: python kochirish.py zaxira\\marathon_....db
"""
import asyncio
import csv
import glob
import os
import sqlite3
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import config  # noqa: E402
import db  # noqa: E402

ZDIR = os.path.join(HERE, "zaxira")
TABLES = ["users", "lessons", "attendance", "course_certs", "final_certs", "settings", "files"]
KEEP = 60


def log(msg: str) -> None:
    line = f"{datetime.now():%Y-%m-%d %H:%M}  {msg}"
    try:
        print(line)
    except Exception:  # noqa: BLE001 — pythonw (oynasiz) rejimida konsol yoʻq
        pass
    os.makedirs(ZDIR, exist_ok=True)
    with open(os.path.join(ZDIR, "zaxira.log"), "a", encoding="utf-8") as f:
        f.write(line + "\n")


async def backup() -> str:
    if not config.DATABASE_URL:
        raise SystemExit("DATABASE_URL yoʻq — avval supabase_ulash.bat ni ishga tushiring.")
    import asyncpg
    conn = await asyncpg.connect(config.DATABASE_URL, ssl="require", statement_cache_size=0, timeout=30)
    os.makedirs(ZDIR, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    path = os.path.join(ZDIR, f"marathon_{stamp}.db")
    tmp = path + ".tmp"
    if os.path.exists(tmp):
        os.remove(tmp)
    out = sqlite3.connect(tmp)
    out.executescript(db.SCHEMA_SQLITE + db.INDEXES)
    counts = {}
    try:
        for t in TABLES:
            rows = await conn.fetch(f"SELECT * FROM {t}")
            counts[t] = len(rows)
            if rows:
                cols = list(rows[0].keys())
                out.executemany(f"INSERT INTO {t}({','.join(cols)}) VALUES({','.join('?' * len(cols))})",
                                [tuple(r.values()) for r in rows])
        out.commit()
        users = await conn.fetch(
            "SELECT u.*, (SELECT COUNT(*) FROM users r WHERE r.referrer_id=u.tg_id) AS takliflar,"
            " (SELECT COUNT(*) FROM attendance a WHERE a.tg_id=u.tg_id) AS darslar"
            " FROM users u WHERE u.auto_admin=0 ORDER BY u.registered_at")
    finally:
        out.close()
        await conn.close()
    os.replace(tmp, path)

    csv_path = os.path.join(ZDIR, f"ishtirokchilar_{stamp}.csv")
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Telegram ID", "Username", "Ism", "Familiya", "Telefon", "Tugʻilgan sana", "Oʻqish/ish joyi",
                    "Kim taklif qilgan (ID)", "Roʻyxatdan oʻtgan (UTC)", "Ishtirok huquqi", "Takliflar", "Darslar"])
        for u in users:
            w.writerow([u["tg_id"], u["username"] or "", u["first_name"], u["last_name"], u["phone"],
                        u["birth_date"], u["study_place"] or "", u["referrer_id"] or "", u["registered_at"],
                        "ha" if u["eligible_at"] else "yoʻq", u["takliflar"], u["darslar"]])

    for pattern in ("marathon_*.db", "ishtirokchilar_*.csv"):  # eski nusxalarni tozalash
        for old in sorted(glob.glob(os.path.join(ZDIR, pattern)))[:-KEEP]:
            os.remove(old)
    summary = ", ".join(f"{t}: {n}" for t, n in counts.items())
    log(f"OK  {os.path.basename(path)}  ({summary})")
    return path


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    try:
        path = asyncio.run(backup())
    except SystemExit:
        raise
    except Exception as e:  # noqa: BLE001
        log(f"XATO  {e.__class__.__name__}: {e}")
        sys.exit(1)
    print(f"\nZaxira saqlandi: {path}")


if __name__ == "__main__":
    main()
