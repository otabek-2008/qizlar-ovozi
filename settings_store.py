"""Admin paneldan oʻzgartiriladigan sozlamalar.

Qiymatlar bazada (settings jadvali, "cfg:" prefiksi bilan) saqlanadi va ishga tushganda
hamda har oʻzgarishda `config` modulidagi qiymatlarni yangilaydi. .env dagi qiymatlar faqat
boshlangʻich (standart) qiymat boʻlib xizmat qiladi.
"""
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime

import config
import db

log = logging.getLogger(__name__)
PREFIX = "cfg:"


@dataclass
class Field:
    key: str
    title: str
    kind: str  # str | link | date | int | chat | bool | list | percent | color | ids
    hint: str = ""
    min_v: float | None = None
    max_v: float | None = None
    clearable: bool = False
    hidden: bool = False


FIELDS: dict[str, Field] = {f.key: f for f in [
    Field("MARATHON_NAME", "Marafon nomi", "str"),
    Field("MARATHON_START", "Boshlanish sanasi", "date",
          "Kun.Oy.Yil koʻrinishida, masalan: 01.12.2026\n"
          "Shu sanadan oldin olingan kurs sertifikatlari qabul qilinmaydi."),
    Field("REQUIRED_REFERRALS", "Kerakli takliflar soni", "int",
          "Necha doʻst taklif qilganda marafonga ruxsat beriladi. 0 — shartsiz.", 0, 100),
    Field("LESSONS_COUNT", "Darslar soni", "int", "", 1, 30),
    Field("DEFAULT_CODE_MINUTES", "Kod kiritish vaqti (daqiqa)", "int",
          "Davomat ochilganda kodni kiritish uchun beriladigan standart vaqt.", 1, 1440),
    Field("REQUIRE_REFERRALS_TO_ATTEND", "Davomat uchun taklif sharti", "bool"),
    Field("COURSES", "Kurslar roʻyxati", "list",
          "Har bir kurs nomini yangi qatorga yozing.\n"
          "⚠️ Sertifikatlar qabul qilina boshlagach kurslar tartibini oʻzgartirmang."),
    Field("REQUIRED_CHANNELS", "Majburiy kanallar", "channels",
          "Har bir kanalni yangi qatorga yozing: @kanal_nomi\n"
          "Yopiq kanal boʻlsa, yoniga taklif havolasini qoʻshing: -1001234567890 https://t.me/+XXXX\n"
          "⚠️ Botni har bir kanalga ADMIN qilib qoʻshing — aks holda obunani tekshira olmaydi.\n"
          "Majburiy obunani oʻchirish uchun «🗑 Tozalash» ni bosing.", clearable=True),
    Field("PLATFORM_NAME", "Platforma nomi", "str"),
    Field("PLATFORM_LINK", "Platforma havolasi", "link", "Masalan: https://example.uz", clearable=True),
    Field("REQUIRE_COURSES_FOR_CERT", "Sertifikat uchun kurslar sharti", "bool"),
    Field("CLUB_LINK", "Club havolasi", "link",
          "Yakuniy sertifikat bilan birga yuboriladigan club havolasi (masalan, yopiq kanal).", clearable=True),
    Field("ORGANIZER", "Tashkilotchi (sertifikatda)", "str"),
    Field("ADMIN_CHAT_ID", "Tekshiruv guruhi ID", "chat",
          "Kurs sertifikatlari shu guruhga tekshiruvga keladi. Eng oson yoʻli: botni guruhga qoʻshib, "
          "guruhda /set_review_group yozing. 0 — har bir adminga shaxsan.", clearable=True),
    Field("CERT_NAME_Y", "Shablonda ism joyi (yuqoridan, %)", "percent",
          "Masalan: 50 — rasm oʻrtasi, 40 — biroz yuqoriroq.", 5, 95),
    Field("CERT_NAME_COLOR", "Ism rangi", "color", "HEX rang, masalan: #2B1B24 yoki #B0185A"),
    Field("EXTRA_ADMINS", "Qoʻshimcha adminlar", "ids", hidden=True),
]}

SETTINGS_MENU = [k for k, f in FIELDS.items() if not f.hidden and not k.startswith("CERT_")]


# ---------------------------------------------------------------- parse / format
def parse(f: Field, text: str):
    t = text.strip()
    if f.clearable and t in ("-", "0", "yoʻq", "yo'q"):
        return 0 if f.kind == "chat" else ([] if f.kind == "channels" else "")
    if f.kind == "str":
        t = " ".join(t.split())
        if not 1 <= len(t) <= 200:
            raise ValueError("1–200 belgi boʻlishi kerak.")
        return t
    if f.kind == "link":
        if t.startswith("t.me/") or t.startswith("www."):
            t = "https://" + t
        if not re.match(r"^https?://\S+$", t):
            raise ValueError("Havola https:// bilan boshlanishi kerak.")
        return t
    if f.kind == "date":
        raw = t.replace("/", ".").replace("-", ".")
        try:
            return datetime.strptime(raw, "%d.%m.%Y").date()
        except ValueError:
            raise ValueError("Sana notoʻgʻri. Masalan: 01.12.2026") from None
    if f.kind in ("int", "chat"):
        try:
            v = int(t)
        except ValueError:
            raise ValueError("Butun son kiriting.") from None
        if f.min_v is not None and not f.min_v <= v <= f.max_v:
            raise ValueError(f"{int(f.min_v)} dan {int(f.max_v)} gacha son kiriting.")
        return v
    if f.kind == "channels":
        items = [" ".join(x.split()) for x in t.split("\n") if x.strip()]
        if not items or len(items) > 10:
            raise ValueError("1 dan 10 tagacha kanal yozing (har biri yangi qatorda).")
        return items
    if f.kind == "list":
        items = [" ".join(x.split()) for x in re.split(r"[\n;]", t)]
        items = [x for x in items if x]
        if not items:
            raise ValueError("Kamida bitta qiymat yozing.")
        if any(len(x) > 100 for x in items):
            raise ValueError("Har bir nom 100 belgidan oshmasin.")
        return items
    if f.kind == "percent":
        try:
            v = float(t.replace(",", ".").rstrip("%"))
        except ValueError:
            raise ValueError("Son kiriting, masalan: 50") from None
        if not f.min_v <= v <= f.max_v:
            raise ValueError(f"{int(f.min_v)} dan {int(f.max_v)} gacha son kiriting.")
        return v / 100
    if f.kind == "color":
        if not re.match(r"^#?[0-9a-fA-F]{6}$", t):
            raise ValueError("Rang #RRGGBB koʻrinishida boʻlsin, masalan: #B0185A")
        return "#" + t.lstrip("#").upper()
    if f.kind == "ids":
        return [int(x) for x in re.split(r"[,\s]+", t) if x]
    raise ValueError("Bu sozlamani matn bilan oʻzgartirib boʻlmaydi.")


def serialize(f: Field, v) -> str:
    if f.kind == "date":
        return v.isoformat()
    if f.kind == "bool":
        return "1" if v else "0"
    if f.kind in ("list", "channels"):
        return "\n".join(v)
    if f.kind == "ids":
        return ",".join(map(str, v))
    return str(v)


def deserialize(f: Field, s: str):
    if f.kind == "date":
        return date.fromisoformat(s)
    if f.kind in ("int", "chat"):
        return int(s)
    if f.kind == "bool":
        return s == "1"
    if f.kind in ("list", "channels"):
        return [x for x in s.split("\n") if x]
    if f.kind == "percent":
        return float(s)
    if f.kind == "ids":
        return [int(x) for x in s.split(",") if x]
    return s


def display(key: str) -> str:
    f = FIELDS[key]
    v = getattr(config, key)
    if f.kind == "date":
        return v.strftime("%d.%m.%Y")
    if f.kind == "bool":
        return "✅ ha" if v else "❌ yoʻq"
    if f.kind == "list":
        return "\n".join(f"   {i}. {x}" for i, x in enumerate(v, 1)) if v else "—"
    if f.kind == "channels":
        return "\n".join(f"   {i}. {x}" for i, x in enumerate(v, 1)) if v else "yoʻq (obuna shart emas)"
    if f.kind == "percent":
        return f"{round(v * 100)}%"
    if f.kind == "chat":
        return str(v) if v else "yoʻq (adminlarga shaxsan)"
    if f.kind == "ids":
        return ", ".join(map(str, v)) or "—"
    return str(v) if v not in ("", None) else "—"


# ---------------------------------------------------------------- saqlash
async def apply_all() -> None:
    for f in FIELDS.values():
        raw = await db.get_setting(PREFIX + f.key)
        if raw is None:
            continue
        try:
            setattr(config, f.key, deserialize(f, raw))
        except Exception:  # noqa: BLE001
            log.exception("Sozlama oʻqilmadi: %s=%r", f.key, raw)


async def set_value(key: str, value) -> None:
    f = FIELDS[key]
    await db.set_setting(PREFIX + key, serialize(f, value))
    setattr(config, key, value)
    if key == "LESSONS_COUNT":
        await db.ensure_lessons()
    if key == "REQUIRED_CHANNELS":
        import subscription
        subscription.reset_cache()


def all_admins() -> set[int]:
    return set(config.ADMIN_IDS) | set(config.EXTRA_ADMINS)


def is_admin(user_id: int) -> bool:
    return user_id in all_admins()
