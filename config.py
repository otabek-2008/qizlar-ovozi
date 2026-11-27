import os
from datetime import date
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "ha")


def _int_list(value: str) -> list[int]:
    return [int(x) for x in value.replace(" ", "").split(",") if x]


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_IDS = set(_int_list(os.getenv("ADMIN_IDS", "")))
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID") or 0)
EXTRA_ADMINS: list[int] = []  # admin paneldan qo'shiladi

# Quyidagilar faqat boshlang'ich qiymatlar — ularni bot ichidagi Admin paneldan o'zgartirasiz.

MARATHON_NAME = os.getenv("MARATHON_NAME", "Qizlar ovozi")
MARATHON_START = date.fromisoformat(os.getenv("MARATHON_START", "2026-12-01"))
TZ = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tashkent"))
REQUIRED_REFERRALS = int(os.getenv("REQUIRED_REFERRALS", "5"))
LESSONS_COUNT = int(os.getenv("LESSONS_COUNT", "5"))
DEFAULT_CODE_MINUTES = int(os.getenv("DEFAULT_CODE_MINUTES", "10"))
REQUIRE_REFERRALS_TO_ATTEND = _bool("REQUIRE_REFERRALS_TO_ATTEND", "true")

COURSES = [c.strip() for c in os.getenv("COURSES", "1-kurs;2-kurs;3-kurs").split(";") if c.strip()]
PLATFORM_NAME = os.getenv("PLATFORM_NAME", "Qizlar akademiyasi")
PLATFORM_LINK = os.getenv("PLATFORM_LINK", "")
REQUIRE_COURSES_FOR_CERT = _bool("REQUIRE_COURSES_FOR_CERT", "true")

CERT_TEMPLATE = os.getenv("CERT_TEMPLATE", "templates/certificate.png")
CERT_NAME_X = float(os.getenv("CERT_NAME_X", "0.5"))
CERT_NAME_Y = float(os.getenv("CERT_NAME_Y", "0.5"))
CERT_NAME_COLOR = os.getenv("CERT_NAME_COLOR", "#2B1B24")
CERT_DRAW_SERIAL = _bool("CERT_DRAW_SERIAL", "true")
ORGANIZER = os.getenv("ORGANIZER", "Qizlar ovozi jamoasi")
FONT_PATH = os.getenv("FONT_PATH", "")
FONT_PATH_REGULAR = os.getenv("FONT_PATH_REGULAR", "")
CLUB_LINK = os.getenv("CLUB_LINK", "").strip()

# Majburiy obuna kanallari (roʻyxatdan oʻtishning oxirgi sharti). Bot har birida ADMIN boʻlishi kerak.
REQUIRED_CHANNELS = [c.strip() for c in os.getenv(
    "REQUIRED_CHANNELS", "@qizlarovozi_uz;@qizlarakademiyasiuz;@marjonajurakulova").split(";") if c.strip()]

MIN_AGE = int(os.getenv("MIN_AGE", "7"))
MAX_AGE = int(os.getenv("MAX_AGE", "60"))

DB_PATH = os.getenv("DB_PATH", "marathon.db")

# Supabase (PostgreSQL). Berilsa — maʼlumotlar Supabase'da saqlanadi, berilmasa — DB_PATH dagi SQLite faylda.
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
DB_SCHEMA = os.getenv("DB_SCHEMA", "").strip()  # faqat testlar uchun (alohida sxema)

# Webhook (Render). Render RENDER_EXTERNAL_URL ni oʻzi beradi; berilmasa bot polling rejimida ishlaydi.
WEBHOOK_BASE = (os.getenv("WEBHOOK_URL") or os.getenv("RENDER_EXTERNAL_URL") or "").strip().rstrip("/")
PORT = int(os.getenv("PORT", "8080"))
