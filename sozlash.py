"""Bot tokeni va admin ID'ni .env fayliga yozadigan yordamchi dastur.

Ishga tushirish: sozlash.bat ni ikki marta bosing (yoki: python sozlash.py)
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass


def api(token: str, method: str, **params):
    url = f"https://api.telegram.org/bot{token}/{method}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def read_env() -> list[str]:
    if not os.path.exists(ENV_PATH):
        return []
    with open(ENV_PATH, encoding="utf-8-sig") as f:
        return f.read().splitlines()


def write_env(values: dict[str, str]) -> None:
    lines = read_env()
    done = set()
    for i, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if key in values and not line.lstrip().startswith("#"):
            lines[i] = f"{key}={values[key]}"
            done.add(key)
    for key, value in values.items():
        if key not in done:
            lines.append(f"{key}={value}")
    with open(ENV_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def ask_token() -> tuple[str, str]:
    print("1-QADAM. Bot tokeni")
    print("  Telegram'da @BotFather ga /newbot yozing, bot nomi va username bering.")
    print("  U bergan tokenni (1234567890:AAF... ko'rinishida) shu yerga qo'ying.")
    print("  (Windows terminalida qo'yish: sichqonchaning o'ng tugmasi)\n")
    while True:
        token = input("Token: ").strip().strip('"').strip("'")
        if ":" not in token:
            print("  ! Bu tokenga o'xshamaydi. Qaytadan urinib ko'ring.\n")
            continue
        try:
            me = api(token, "getMe")["result"]
            print(f"  OK! Bot topildi: @{me['username']} ({me['first_name']})\n")
            return token, me["username"]
        except urllib.error.HTTPError:
            print("  ! Token noto'g'ri. @BotFather dagi tokenni to'liq nusxalang.\n")
        except urllib.error.URLError:
            print("  ! Telegram'ga ulanib bo'lmadi. Internetni tekshiring.\n")


def find_senders(token: str) -> tuple[dict[int, str], int | None]:
    try:
        api(token, "deleteWebhook")
        updates = api(token, "getUpdates", timeout=0)["result"]
    except (urllib.error.URLError, KeyError):
        return {}, None
    senders: dict[int, str] = {}
    last = None
    for upd in updates:
        last = upd["update_id"]
        msg = upd.get("message") or upd.get("edited_message")
        if msg and msg.get("chat", {}).get("type") == "private":
            u = msg["from"]
            name = " ".join(x for x in (u.get("first_name"), u.get("last_name")) if x)
            if u.get("username"):
                name += f" (@{u['username']})"
            senders[u["id"]] = name
    return senders, last


def ask_admins(token: str, username: str) -> list[int]:
    print("2-QADAM. Admin(lar)")
    print(f"  Telefoningizda https://t.me/{username} ni oching, START bosing")
    print("  va istalgan xabar yozing (masalan: salom).")
    print("  Boshqa adminlar ham shunday qilsin.\n")
    while True:
        input("Yozib bo'lgach, Enter bosing...")
        senders, last = find_senders(token)
        if not senders:
            print("  ! Hali hech kim yozmadi. Botga xabar yozib, yana Enter bosing.")
            manual = input("  (yoki ID raqamini o'zingiz biling — yozing, bo'lmasa Enter): ").strip()
            ids = [int(x) for x in manual.replace(" ", "").split(",") if x.lstrip("-").isdigit()]
            if ids:
                return ids
            continue
        items = list(senders.items())
        print("\n  Botga yozganlar:")
        for i, (uid, name) in enumerate(items, 1):
            print(f"   {i}) {name} — ID {uid}")
        choice = input("\nQaysilari admin bo'ladi? Raqamini yozing (bir nechta bo'lsa vergul bilan) [1]: ").strip()
        try:
            nums = [int(x) for x in (choice or "1").replace(" ", "").split(",") if x]
            ids = [items[n - 1][0] for n in nums if 1 <= n <= len(items)]
        except ValueError:
            ids = []
        if not ids:
            print("  ! Noto'g'ri tanlov.\n")
            continue
        if last is not None:  # bu xabarlarga bot keyin javob berib yurmasin
            try:
                api(token, "getUpdates", offset=last + 1, timeout=0)
            except urllib.error.URLError:
                pass
        return ids


def main() -> None:
    print("=" * 56)
    print("  'Qizlar ovozi' boti — boshlang'ich sozlash")
    print("=" * 56 + "\n")
    current = {l.split("=", 1)[0]: l.split("=", 1)[1] for l in read_env() if "=" in l and not l.startswith("#")}
    if current.get("BOT_TOKEN", "").count(":") == 1 and "your-token" not in current.get("BOT_TOKEN", ""):
        again = input(".env da token allaqachon bor. Qaytadan sozlaymizmi? (ha/yo'q) [yo'q]: ").strip().lower()
        if again not in ("ha", "h", "yes", "y"):
            return True

    token, username = ask_token()
    admins = ask_admins(token, username)
    write_env({"BOT_TOKEN": token, "ADMIN_IDS": ",".join(map(str, admins))})
    print("\n" + "=" * 56)
    print("  TAYYOR! .env fayli saqlandi.")
    print(f"  Bot: @{username}   Adminlar: {', '.join(map(str, admins))}")
    print("  Qolgan sozlamalar (sana, kurslar, darslar...) botda: /admin")
    print("=" * 56)
    return True


if __name__ == "__main__":
    try:
        ok = main()
    except (KeyboardInterrupt, EOFError):
        print("\nBekor qilindi.")
        ok = False
    sys.exit(0 if ok else 1)
