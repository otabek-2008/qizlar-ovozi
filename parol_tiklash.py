"""Admin panel parolini oʻchiradi. Keyingi /admin da yangi parol oʻrnatiladi.
Faqat .env fayli (baza ulanishi) bor kompyuterdan ishlaydi — shuning uchun xavfsiz.
Supabase ulangan boʻlsa — Supabase'dagi parol, aks holda kompyuterdagi bazadagi parol oʻchiriladi."""
import asyncio
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import db  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


async def reset() -> None:
    await db.init()
    await db._exec("DELETE FROM settings WHERE key='admin_pw_hash'")
    await db.session_delete()  # hamma adminlar paneldan chiqariladi
    await db.close()


def main() -> None:
    where = "Supabase" if db.IS_PG else "kompyuterdagi baza"
    answer = input(f"Admin panel paroli oʻchirilsinmi? ({where}) (ha/yo'q): ").strip().lower()
    if answer not in ("ha", "h", "yes", "y"):
        print("Bekor qilindi.")
        return
    asyncio.run(reset())
    print("Parol oʻchirildi. Botda /admin yozing va yangi parol oʻrnating.")
    print("Bot ishlab turgan boʻlsa, uni qayta ishga tushiring (Render: Manual Deploy → Restart).")


if __name__ == "__main__":
    main()
