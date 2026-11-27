"""Supabase bazasini ulash: ulanish manzilini tekshiradi, .env ga yozadi, eski maʼlumotlarni koʻchiradi.

Ishga tushirish: supabase_ulash.bat ni ikki marta bosing.
"""
import asyncio
import os
import sys
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from sozlash import read_env, write_env  # noqa: E402


def ask_url() -> str:
    print("Supabase'da: loyihangiz → yuqoridagi «Connect» tugmasi → «Session pooler» boʻlimi")
    print("(Render IPv4 ishlatadi, shuning uchun aynan Session pooler kerak).")
    print("U yerdagi URI ni nusxalang. U shunday koʻrinishda boʻladi:")
    print("  postgresql://postgres.xxxx:[YOUR-PASSWORD]@aws-0-eu-central-1.pooler.supabase.com:5432/postgres\n")
    while True:
        url = input("URI (oʻng tugma bilan qoʻying, keyin Enter): ").strip().strip('"').strip("'")
        if not url.startswith(("postgresql://", "postgres://")):
            print("  ! Bu postgresql:// bilan boshlanishi kerak. Qaytadan urinib koʻring.\n")
            continue
        if "[YOUR-PASSWORD]" in url:
            pw = input("Supabase baza parolingiz (loyiha yaratilganda oʻylab topgansiz): ").strip()
            url = url.replace("[YOUR-PASSWORD]", urllib.parse.quote(pw, safe=""))
        return url


async def check(url: str) -> str | None:
    import asyncpg
    try:
        conn = await asyncpg.connect(url, ssl="require", statement_cache_size=0, timeout=20)
        version = await conn.fetchval("SHOW server_version")
        await conn.close()
        print(f"  OK! Supabase'ga ulandi (PostgreSQL {version})\n")
        return None
    except asyncpg.InvalidPasswordError:
        return "Parol notoʻgʻri. Supabase → Project Settings → Database → «Reset database password»."
    except (OSError, asyncio.TimeoutError) as e:
        return f"Serverga ulanib boʻlmadi ({e.__class__.__name__}). Session pooler URI ekanini va internetni tekshiring."
    except Exception as e:  # noqa: BLE001
        return f"Xato: {e}"


def main() -> bool:
    print("=" * 60)
    print("  Supabase bazasini ulash")
    print("=" * 60 + "\n")
    current = {l.split("=", 1)[0]: l.split("=", 1)[1] for l in read_env() if "=" in l and not l.startswith("#")}
    if current.get("DATABASE_URL"):
        again = input(".env da Supabase manzili allaqachon bor. Qaytadan kiritamizmi? (ha/yo'q) [yo'q]: ")
        if again.strip().lower() not in ("ha", "h", "y", "yes"):
            url = current["DATABASE_URL"]
            error = asyncio.run(check(url))
            if error:
                print("  !", error)
                return False
        else:
            url = None
    else:
        url = None
    while url is None:
        candidate = ask_url()
        error = asyncio.run(check(candidate))
        if error:
            print("  !", error, "\n")
            continue
        url = candidate
    write_env({"DATABASE_URL": url})
    print("  .env fayliga saqlandi.\n")

    if os.path.exists(os.path.join(HERE, "marathon.db")):
        ans = input("Kompyuterdagi bazadagi maʼlumotlarni (sozlamalar, parol, ishtirokchilar) Supabase'ga "
                    "koʻchiramizmi? (ha/yo'q) [ha]: ").strip().lower()
        if ans in ("", "ha", "h", "y", "yes"):
            os.environ["DATABASE_URL"] = url
            import kochirish
            asyncio.run(kochirish.migrate(os.path.join(HERE, "marathon.db")))
            print("  Koʻchirildi.\n")
    print("=" * 60)
    print("  TAYYOR! Endi bot maʼlumotlarni Supabase'da saqlaydi.")
    print("  Render'ga joylashda shu DATABASE_URL ni Render saytiga kiritasiz")
    print("  (uni .env faylidan nusxalab olasiz).")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        ok = main()
    except (KeyboardInterrupt, EOFError):
        print("\nBekor qilindi.")
        ok = False
    sys.exit(0 if ok else 1)
