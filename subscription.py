"""Majburiy kanallarga obunani tekshirish.

Kanallar admin paneldagi «📢 Majburiy kanallar» sozlamasida saqlanadi (config.REQUIRED_CHANNELS),
har bir qator: "<@username yoki -100ID> [havola]". Bot har bir kanalda ADMIN boʻlishi shart.
"""
import logging
import time
from dataclasses import dataclass

from aiogram import BaseMiddleware, Bot
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

import config
import settings_store
import texts

log = logging.getLogger(__name__)

OK_STATUSES = {"creator", "administrator", "member", "restricted"}
CACHE_SECONDS = 300          # obuna tasdiqlansa, 5 daqiqa qayta tekshirilmaydi
_ok_until: dict[int, float] = {}


@dataclass
class Channel:
    ref: str        # @username yoki -100... ID
    url: str        # obuna boʻlish havolasi
    title: str      # kanal nomi


_channels: dict[str, Channel] = {}


def parse_line(line: str) -> tuple[str, str]:
    parts = line.split()
    ref = parts[0]
    url = parts[1] if len(parts) > 1 else (f"https://t.me/{ref[1:]}" if ref.startswith("@") else "")
    return ref, url


def chat_id_of(ref: str):
    return int(ref) if ref.lstrip("-").isdigit() else ref


async def describe(bot: Bot, line: str) -> Channel:
    ref, url = parse_line(line)
    ch = _channels.get(line)
    if ch is None:
        title = ref
        try:
            chat = await bot.get_chat(chat_id_of(ref))
            title = chat.title or ref
            url = url or (f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or ""))
        except TelegramAPIError as e:
            log.warning("Kanal maʼlumoti olinmadi %s: %s", ref, e)
        ch = Channel(ref, url, title)
        _channels[line] = ch
    return ch


async def missing_channels(bot: Bot, user_id: int) -> list[Channel]:
    """Foydalanuvchi obuna boʻlmagan kanallar roʻyxati (boʻsh — hammasiga obuna)."""
    if not config.REQUIRED_CHANNELS or _ok_until.get(user_id, 0) > time.time():
        return []
    missing = []
    for line in config.REQUIRED_CHANNELS:
        ref, _ = parse_line(line)
        try:
            member = await bot.get_chat_member(chat_id_of(ref), user_id)
            status = getattr(member, "status", "")
            status = getattr(status, "value", status)
            if status not in OK_STATUSES or (status == "restricted" and not getattr(member, "is_member", True)):
                missing.append(await describe(bot, line))
        except TelegramAPIError as e:
            # Kanal notoʻgʻri sozlangan (bot admin emas) — hammani bloklab qoʻymaslik uchun oʻtkazib yuboramiz
            log.warning("Obunani tekshirib boʻlmadi %s: %s", ref, e)
    if not missing:
        _ok_until[user_id] = time.time() + CACHE_SECONDS
    return missing


def forget(user_id: int) -> None:
    _ok_until.pop(user_id, None)


def reset_cache() -> None:
    _ok_until.clear()
    _channels.clear()


def prompt_kb(channels: list[Channel]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"📢 {c.title}", url=c.url)] for c in channels if c.url]
    rows.append([InlineKeyboardButton(text=texts.BTN_SUB_CHECK, callback_data="sub:check")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def prompt_text(channels: list[Channel]) -> str:
    names = "\n".join(f"📢 <b>{c.title}</b>" for c in channels)
    return texts.SUB_REQUIRED.format(channels=names)


async def validate_channel(bot: Bot, raw: str) -> tuple[str | None, str | None]:
    """Admin kiritgan kanalni tekshiradi. (saqlanadigan qator, xato) qaytaradi."""
    ref, url = parse_line(raw)
    if not (ref.startswith("@") or ref.lstrip("-").isdigit()):
        return None, f"«{ref}» — kanal @username yoki -100… ID koʻrinishida boʻlsin."
    try:
        chat = await bot.get_chat(chat_id_of(ref))
    except TelegramAPIError:
        return None, f"«{ref}» topilmadi. Manzilni tekshiring va botni kanalga <b>admin</b> qilib qoʻshing."
    try:
        me = await bot.get_chat_member(chat.id, bot.id)
        status = getattr(me.status, "value", me.status)
    except TelegramAPIError:
        status = ""
    if status not in ("administrator", "creator"):
        return None, f"Bot «{chat.title}» kanalida admin emas. Avval botni kanalga <b>admin</b> qilib qoʻshing."
    url = url or (f"https://t.me/{chat.username}" if chat.username else (chat.invite_link or ""))
    if not url:
        return None, (f"«{chat.title}» yopiq kanal. Taklif havolasini ham yozing:\n"
                      f"<code>{ref} https://t.me/+XXXX</code>")
    saved = f"@{chat.username}" if chat.username else str(chat.id)
    return (saved if chat.username and url == f"https://t.me/{chat.username}" else f"{saved} {url}"), None


class SubscriptionMiddleware(BaseMiddleware):
    """Roʻyxatdan oʻtgan, lekin kanallardan chiqib ketganlarga bot ishlamaydi.

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
