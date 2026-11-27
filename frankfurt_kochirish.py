"""Supabase bazasini yangi loyihaga (Frankfurt, eu-central-1) koʻchirish — bot tezroq ishlashi uchun.

Ishga tushirish: frankfurt_kochirish.bat ni ikki marta bosing.
1) eski bazadan zaxira olinadi (zaxira papkasiga);
2) zaxira yangi bazaga koʻchiriladi;
3) .env dagi DATABASE_URL yangisiga almashtiriladi (eskisi DATABASE_URL_OLD da qoladi);
4) yangi manzil buferga nusxalanadi — uni Render'ga qoʻyasiz;
5) Render'da almashtirgach — oxirgi sinxronlash (oraliqda yozilganlar ham oʻtadi).
"""
import asyncio
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, HERE)

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

from dotenv import dotenv_values  # noqa: E402

from sozlash import write_env  # noqa: E402
from supabase_ulash import ask_url, check  # noqa: E402


def to_clipboard(text: str) -> bool:
    try:
        subprocess.run("clip", input=text.encode("utf-16-le"), check=True, shell=True)
        return True
    except Exception:  # noqa: BLE001
        return False


def host_of(url: str) -> str:
    from urllib.parse import urlsplit
    return urlsplit(url).hostname or ""


async def copy(old: str, new: str) -> None:
    import zaxira
    import kochirish
    path = await zaxira.backup(old)
    print(f"  Eski bazadan zaxira olindi: {os.path.basename(path)}")
    await kochirish.migrate(path)


def main() -> bool:
    print("=" * 60)
    print("  Supabase'ni Frankfurt'ga koʻchirish")
    print("=" * 60 + "\n")
    env = dotenv_values(os.path.join(HERE, ".env"))
    old = (env.get("DATABASE_URL") or "").strip()
    if not old:
        print("  ! .env da hozirgi DATABASE_URL yoʻq.")
        return False
    print(f"  Hozirgi baza: {host_of(old)}\n")
    print("YANGI (Frankfurt) loyihaning manzilini kiriting.")
    while True:
        new = ask_url()
        if host_of(new) == host_of(old) and new.split("@")[0] == old.split("@")[0]:
            print("  ! Bu hozirgi bazaning oʻzi. Yangi loyihaning manzilini kiriting.\n")
            continue
        if "eu-central-1" not in host_of(new):
            ans = input(f"  ! Bu manzil Frankfurt emas ({host_of(new)}). Baribir davom etamizmi? (ha/yo'q) [yo'q]: ")
            if ans.strip().lower() not in ("ha", "h", "y", "yes"):
                continue
        error = asyncio.run(check(new))
        if error:
            print("  !", error, "\n")
            continue
        break

    os.environ["DATABASE_URL"] = new          # db va config yangi bazani ishlatadi
    os.environ["DB_SCHEMA"] = ""
    print("1/2. Maʼlumotlar koʻchirilmoqda...")
    asyncio.run(copy(old, new))
    write_env({"DATABASE_URL": new, "DATABASE_URL_OLD": old})
    print("  .env yangilandi (eski manzil DATABASE_URL_OLD da saqlandi).\n")

    copied = to_clipboard(new)
    print("=" * 60)
    print("  Endi Render'da:")
    print("   1) xizmatingiz → Environment → DATABASE_URL → Edit")
    print("   2) eski qiymatni oʻchirib, " + ("Ctrl+V bilan yangisini qoʻying (buferda)" if copied
                                             else ".env dagi yangi DATABASE_URL ni qoʻying"))
    print("   3) Save Changes — bot 2–3 daqiqada qayta ishga tushadi")
    print("=" * 60)
    input("\nRender'da saqlab, 3 daqiqa kutgach Enter bosing (oxirgi sinxronlash)... ")
    print("\n2/2. Oxirgi sinxronlash (oraliqda yozilganlar)...")
    asyncio.run(copy(old, new))
    print("\n" + "=" * 60)
    print("  TAYYOR! Bot endi Frankfurt'dagi bazada ishlaydi.")
    print("  Eski loyihani 1 hafta saqlab turing, hammasi joyida boʻlsa —")
    print("  Supabase'da uni oʻchirishingiz (yoki Pause qilishingiz) mumkin.")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        ok = main()
    except (KeyboardInterrupt, EOFError):
        print("\nBekor qilindi.")
        ok = False
    except Exception as e:  # noqa: BLE001
        print(f"\n  ! Xato: {e.__class__.__name__}: {e}")
        ok = False
    sys.exit(0 if ok else 1)
