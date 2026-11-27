"""Admin panel parolini oʻchiradi. Keyingi /admin da yangi parol oʻrnatiladi.
Faqat bot oʻrnatilgan kompyuterdan ishlaydi — shuning uchun xavfsiz."""
import os
import sqlite3
import sys

from dotenv import load_dotenv

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
load_dotenv()
db_path = os.getenv("DB_PATH", "marathon.db")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

if not os.path.exists(db_path):
    print("Baza topilmadi — bot hali ishga tushirilmagan.")
    sys.exit(1)

answer = input("Admin panel paroli o'chirilsinmi? (ha/yo'q): ").strip().lower()
if answer not in ("ha", "h", "yes", "y"):
    print("Bekor qilindi.")
    sys.exit(0)

con = sqlite3.connect(db_path)
con.execute("DELETE FROM settings WHERE key='admin_pw_hash'")
con.commit()
con.close()
print("Parol o'chirildi. Botda /admin yozing va yangi parol o'rnating.")
print("Agar bot ishlab turgan bo'lsa, eski kirgan adminlar sessiyasi uni qayta ishga tushirguncha qoladi.")
