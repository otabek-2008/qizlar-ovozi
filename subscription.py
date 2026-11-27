"""Majburiy obuna (reklama / homiylar).

Roʻyxat admin paneldagi «📣 Reklama» boʻlimida boshqariladi va config.REQUIRED_CHANNELS da
saqlanadi: har bir qator — bitta homiyning JSON yozuvi:
    {"kind": "channel|group|bot|link", "ref": "@username yoki -100ID", "url": "...",
     "title": "...", "check": true}

* kanal / guruh — bot u yerda admin (guruhda aʼzo) boʻlsa, obuna HAQIQATDAN tekshiriladi;
* bot, Instagram, sayt va boshqa havolalar — Telegram tekshira olmaydi, ular faqat tugma
  sifatida koʻrsatiladi (roʻyxatdan oʻtishda bir marta).
Eski formatdagi qatorlar ("@kanal [havola]") ham oʻqiladi.
"""
import json
import logging
import re
import time
from dataclasses import asdict, dataclass

from aiogram import BaseMiddleware, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import settings_store
import texts

log = logging.getLogger(__name__)

OK_STATUSES = {"creator", "administrator", "member", "restricted"}
CACHE_SECONDS = 300          # obuna tasdiqlansa, 5 daqiqa qayta tekshirilmaydi
MAX_SPONSORS = 15
_ok_until: dict[int, float] = {}

KINDS = {
    "channel": ("📢", "Kanal"),
    "group": ("👥", "Guruh"),
    "bot": ("🤖", "Bot"),
    "link": ("🔗", "Havola"),
}


@dataclass
class Sponsor:
    kind: str       # channel | group | bot | link
    ref: str        # @username yoki -100... ID (tekshiriladiganlar uchun), aks holda ""
    url: str        # obuna boʻlish havolasi
    title: str      # tugmadagi nom
    check: bool     # obuna Telegram orqali tekshiriladimi

    @property
    def icon(self) -> str:
        return KINDS.get(self.kind, KINDS["link"])[0]

    def dump(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False)


def load(line: str) -> Sponsor:
    line = line.strip()
    if line.startswith("{"):
        d = json.loads(line)
        return Sponsor(d.get("kind", "link"), d.get("ref", ""), d.get("url", ""),
                       d.get("title") or d.get("ref") or "Homiy", bool(d.get("check")))
    # eski format: "@kanal [havola]"
    parts = line.split()
    ref = parts[0]
    url = parts[1] if len(parts) > 1 else (f"https://t.me/{ref[1:]}" if ref.startswith("@") else "")
    return Sponsor("channel", ref, url, ref, True)


def sponsors() -> list[Sponsor]:
    out = []
    for line in config.REQUIRED_CHANNELS:
        try:
            out.append(load(line))
        except Exception:  # noqa: BLE001
            log.warning("Reklama yozuvi oʻqilmadi: %r", line)
    return out


def chat_id_of(ref: str):
    return int(ref) if ref.lstrip("-").isdigit() else ref


def _status(member) -> str:
    status = getattr(member, "status", "")
    return getattr(status, "value", status)


async def missing_channels(bot: Bot, user_id: int) -> list[Sponsor]:
    """Foydalanuvchi obuna boʻlmagan TEKSHIRILADIGAN homiylar (boʻsh — hammasi joyida)."""
    if not config.REQUIRED_CHANNELS or _ok_until.get(user_id, 0) > time.time():
        return []
    missing = []
    for s in sponsors():
        if not s.check:
            continue
        try:
            member = await bot.get_chat_member(chat_id_of(s.ref), user_id)
            status = _status(member)
            if status not in OK_STATUSES or (status == "restricted" and not getattr(member, "is_member", True)):
                missing.append(s)
        except TelegramAPIError as e:
            # bot huquqidan ayrilgan — hammani bloklab qoʻymaslik uchun oʻtkazib yuboramiz
            log.warning("Obunani tekshirib boʻlmadi %s: %s", s.ref, e)
    if not missing:
        _ok_until[user_id] = time.time() + CACHE_SECONDS
    return missing


async def prompt_items(bot: Bot, user_id: int) -> list[Sponsor]:
    """Roʻyxatdan oʻtishning oxirgi qadamida koʻrsatiladiganlar: obuna boʻlinmagan kanal/guruhlar
    va barcha tekshirilmaydigan havolalar (bot, Instagram va h.k.)."""
    if not config.REQUIRED_CHANNELS:
        return []
    missing = await missing_channels(bot, user_id)
    return missing + [s for s in sponsors() if not s.check]


def forget(user_id: int) -> None:
    _ok_until.pop(user_id, None)


def reset_cache() -> None:
    _ok_until.clear()


def prompt_kb(items: list[Sponsor]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"{s.icon} {s.title}", url=s.url)] for s in items if s.url]
    rows.append([InlineKeyboardButton(text=texts.BTN_SUB_CHECK, callback_data="sub:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def prompt_text(items: list[Sponsor]) -> str:
    import html
    names = "\n".join(f"{s.icon} <b>{html.escape(s.title)}</b>" for s in items)
    return texts.SUB_REQUIRED.format(channels=names)


# ---------------------------------------------------------------- admin: yangi homiy qoʻshish
_TG_LINK = re.compile(r"^(?:https?://)?(?:www\.)?(?:t\.me|telegram\.me)/(?:s/)?([A-Za-z]\w{3,31})/?(?:\?.*)?$")
_URL = re.compile(r"^https?://\S+\.\S+$")


def _norm_url(u: str) -> str:
    u = u.strip()
    if not re.match(r"^[a-z]+://", u, re.I) and re.match(r"^[\w-]+(\.[\w-]+)*\.[a-z]{2,}(/|$)", u, re.I):
        u = "https://" + u
    return u


async def parse_sponsor(bot: Bot, text: str) -> tuple[Sponsor | None, str | None, str | None]:
    """Admin yozgan matndan homiy yasaydi. (homiy, xato, ogohlantirish) qaytaradi.

    1-qator: @username | t.me/... havola | -100ID [taklif havolasi] | istalgan https:// havola
    2-qator (ixtiyoriy): tugmadagi nom
    """
    lines = [x.strip() for x in text.strip().splitlines() if x.strip()]
    if not lines:
        return None, "Havola yoki @username yozing.", None
    first = lines[0].split()
    custom = " ".join(" ".join(lines[1:]).split())[:60] if len(lines) > 1 else ""
    help_text = ("Tushunmadim. 1-qatorga faqat havola yoki @username yozing, masalan:\n"
                 "<code>@kanal_nomi</code>\n<code>https://t.me/guruh_nomi</code>\n"
                 "<code>@homiy_bot</code>\n<code>https://instagram.com/sahifa</code>\n"
                 "Tugma nomi — 2-qatorga.")
    target, extra_url = first[0], (_norm_url(first[1]) if len(first) > 1 else "")
    if extra_url and not _URL.match(extra_url):
        return None, help_text, None

    ref = ""
    m = _TG_LINK.match(target)
    if m and m.group(1).lower() not in ("joinchat", "addlist", "share"):
        ref = "@" + m.group(1)
    elif re.match(r"^@[A-Za-z]\w{3,31}$", target):
        ref = target
    elif re.match(r"^-100\d{5,}$", target):
        ref = target
    else:
        url = _norm_url(target)
        if not _URL.match(url):
            return None, help_text, None
        title = custom or ("Telegram" if "t.me/" in url else re.sub(r"^https?://(www\.)?", "", url).split("/")[0])
        return Sponsor("link", "", url, title, False), None, (
            "Bu havolaga obunani Telegram tekshira olmaydi — u roʻyxatdan oʻtishda tugma sifatida koʻrsatiladi."
            + ("\n💡 Yopiq kanal boʻlsa, uni ID va havola bilan qoʻshing: <code>-1001234567890 " + url + "</code>"
               if "t.me/+" in url or "joinchat" in url else ""))

    uname = ref[1:] if ref.startswith("@") else ""
    if uname.lower().endswith("bot"):
        return Sponsor("bot", "", extra_url or f"https://t.me/{uname}", custom or ref, False), None, (
            "Botni ishga tushirganini Telegram tekshira olmaydi — u tugma sifatida koʻrsatiladi.")

    try:
        chat = await bot.get_chat(chat_id_of(ref))
    except TelegramAPIError:
        if not uname:
            return None, f"«{ref}» topilmadi. Botni oʻsha kanal/guruhga <b>admin</b> qilib qoʻshing.", None
        return Sponsor("link", "", extra_url or f"https://t.me/{uname}", custom or ref, False), None, (
            f"Bot {ref} ni koʻra olmadi, shuning uchun obuna <b>tekshirilmaydi</b> (faqat tugma).\n"
            "Tekshirilishi kerak boʻlsa: botni u yerga admin qiling, bu yozuvni oʻchirib, qayta qoʻshing.")

    ctype = getattr(getattr(chat, "type", ""), "value", getattr(chat, "type", "")) or "channel"
    kind = "channel" if ctype == "channel" else ("group" if ctype in ("group", "supergroup") else "link")
    url = extra_url or (f"https://t.me/{chat.username}" if getattr(chat, "username", None)
                        else (getattr(chat, "invite_link", None) or ""))
    if not url:
        return None, (f"«{html_escape(chat.title)}» yopiq. Taklif havolasini ham yozing:\n"
                      f"<code>{chat.id} https://t.me/+XXXX</code>"), None
    title = custom or getattr(chat, "title", None) or ref
    saved_ref = f"@{chat.username}" if getattr(chat, "username", None) else str(chat.id)
    if kind == "link":
        return Sponsor("link", "", url, title, False), None, "Bu kanal yoki guruh emas — faqat tugma sifatida koʻrsatiladi."

    try:
        status = _status(await bot.get_chat_member(chat.id, bot.id))
    except TelegramAPIError:
        status = ""
    can_check = status in ("administrator", "creator") or (kind == "group" and status in ("member", "restricted"))
    note = None
    if not can_check:
        where = "kanalga" if kind == "channel" else "guruhga"
        note = (f"Bot «{html_escape(title)}» {where} admin emas, shuning uchun obuna <b>tekshirilmaydi</b> "
                f"(faqat tugma).\nTekshirilishi kerak boʻlsa: botni {where} admin qiling, bu yozuvni oʻchirib, "
                "qayta qoʻshing.")
    return Sponsor(kind, saved_ref if can_check else "", url, title, can_check), None, note


def html_escape(s) -> str:
    import html
    return html.escape(str(s or ""))


async def check_problems(bot: Bot) -> list[str]:
    """Bot huquqidan ayrilgan (tekshiriladigan) homiylar roʻyxati — adminlarni ogohlantirish uchun."""
    problems = []
    for s in sponsors():
        if not s.check:
            continue
        try:
            status = _status(await bot.get_chat_member(chat_id_of(s.ref), bot.id))
        except TelegramAPIError:
            status = ""
        ok = status in ("administrator", "creator") or (s.kind == "group" and status in ("member", "restricted"))
        if not ok:
            problems.append(f"Bot «{html_escape(s.title)}» ({s.ref}) da admin emas — obuna tekshirilmayapti.")
    return problems


class SubscriptionMiddleware(BaseMiddleware):
    """Roʻyxatdan oʻtgan, lekin kanal/guruhdan chiqib ketganlarga bot ishlamaydi.

    Roʻyxatdan oʻtmaganlar oʻtkaziladi — ular uchun obuna roʻyxatdan oʻtishning OXIRGI qadamida tekshiriladi.
    Adminlar va guruhlar (tekshiruv guruhi) tekshirilmaydi.
    """

    async def __call__(self, handler, event, data):
        import db
        user = data.get("event_from_user")
        if not config.REQUIRED_CHANNELS or not user or settings_store.is_admin(user.id):
            return await handler(event, data)
        message = event if isinstance(event, Message) else getattr(event, "message", None)
        if message is None or message.chat.type != "private":
            return await handler(event, data)
        if isinstance(event, CallbackQuery) and event.data == "sub:check":
            return await handler(event, data)
        u = await db.get_user(user.id)
        if not u or u["auto_admin"]:
            return await handler(event, data)

        bot: Bot = data["bot"]
        missing = await missing_channels(bot, user.id)
        if not missing:
            return await handler(event, data)
        if isinstance(event, CallbackQuery):
            await event.answer(texts.SUB_ALERT, show_alert=True)
        await message.answer(prompt_text(missing), reply_markup=prompt_kb(missing), disable_web_page_preview=True)
        return None
