"""Umumiy biznes-mantiq: referal, davomat, sertifikatlar, xabar tarqatish."""
import asyncio
import html
import logging
from datetime import datetime

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramRetryAfter
from aiogram.types import BotCommand, BotCommandScopeChat, BufferedInputFile

import config
import db
import keyboards as kb
import settings_store
import texts
from certificate import render_certificate

log = logging.getLogger(__name__)
_bg_tasks: set[asyncio.Task] = set()


def fmt_date(d) -> str:
    return d.strftime("%d.%m.%Y")


def local_now() -> datetime:
    return datetime.now(config.TZ)


def full_name(u) -> str:
    return f"{u['first_name']} {u['last_name']}".strip()


def short_name(u) -> str:
    return f"{u['first_name']} {u['last_name'][:1]}.".strip() if u["last_name"] else u["first_name"]


def run_background(coro) -> None:
    task = asyncio.create_task(coro)
    _bg_tasks.add(task)
    task.add_done_callback(_bg_tasks.discard)


async def set_admin_commands(bot: Bot) -> None:
    commands = [
        BotCommand(command="start", description="Boshlash / menyu"),
        BotCommand(command="admin", description="Admin panel"),
        BotCommand(command="help_admin", description="Admin buyruqlari"),
    ]
    for uid in settings_store.all_admins():
        try:
            await bot.set_my_commands(commands, scope=BotCommandScopeChat(chat_id=uid))
        except TelegramAPIError:
            pass  # admin hali botga /start bosmagan


async def referral_link(bot: Bot, tg_id: int) -> str:
    me = await bot.me()
    return f"https://t.me/{me.username}?start=ref{tg_id}"


async def is_eligible(u) -> bool:
    if settings_store.is_admin(u["tg_id"]):
        return True  # adminlar uchun taklif sharti yoʻq — boʻlimlar doim ochiq
    if u["eligible_at"]:
        return True
    if await db.referral_count(u["tg_id"]) >= config.REQUIRED_REFERRALS:
        await db.set_eligible(u["tg_id"])
        return True
    return False


async def safe_send(bot: Bot, chat_id: int, text: str, **kwargs) -> bool:
    for _ in range(3):
        try:
            await bot.send_message(chat_id, text, **kwargs)
            return True
        except TelegramRetryAfter as e:
            await asyncio.sleep(e.retry_after + 1)
        except TelegramAPIError as e:
            log.info("Xabar yuborilmadi %s: %s", chat_id, e)
            return False
    return False


async def broadcast(bot: Bot, ids: list[int], text: str | None = None,
                    copy_from: tuple[int, int] | None = None, report_to: int | None = None) -> None:
    ok = fail = 0
    for uid in ids:
        sent = False
        for _ in range(3):
            try:
                if copy_from:
                    await bot.copy_message(uid, copy_from[0], copy_from[1])
                else:
                    await bot.send_message(uid, text)
                sent = True
                break
            except TelegramRetryAfter as e:
                await asyncio.sleep(e.retry_after + 1)
            except TelegramAPIError:
                break
        ok, fail = (ok + 1, fail) if sent else (ok, fail + 1)
        await asyncio.sleep(0.05)  # Telegram limiti: ~20 xabar/soniya
    if report_to:
        await safe_send(bot, report_to, f"📢 <b>Xabar tarqatildi</b>\n<blockquote>✅ Yetkazildi: <b>{ok}</b>\n"
                                        f"❌ Yetkazilmadi: <b>{fail}</b></blockquote>\n"
                                        f"<i>Yetkazilmaganlar botni bloklagan boʻlishi mumkin.</i>")


# ---------------------------------------------------------------- referal
async def on_new_referral(bot: Bot, referrer_id: int, new_name: str) -> None:
    count = await db.referral_count(referrer_id)
    need = config.REQUIRED_REFERRALS
    name = html.escape(new_name)
    if count < need:
        text = texts.REF_NEW.format(name=name, count=count, need=need, left=need - count,
                                    bar=texts.progress(count, need))
    else:
        text = texts.REF_NEW_MORE.format(name=name, count=count)
    await safe_send(bot, referrer_id, text)
    if count >= need and await db.set_eligible(referrer_id):
        await safe_send(bot, referrer_id, texts.ELIGIBLE.format(need=need, marathon=config.MARATHON_NAME))


# ---------------------------------------------------------------- davomat
def _norm(code: str) -> str:
    return "".join(code.split()).upper()


async def try_code(tg_id: int, text: str):
    """('ok'|'already'|'wrong'|'closed', lesson)"""
    lessons = await db.open_lessons()
    if not lessons:
        return "closed", None
    code = _norm(text)
    for lesson in lessons:
        if lesson["code"] and _norm(lesson["code"]) == code:
            if await db.mark_attendance(tg_id, lesson["num"]):
                return "ok", lesson
            return "already", lesson
    return "wrong", None


async def after_attendance(bot: Bot, tg_id: int, lesson_num: int) -> str:
    count = await db.attendance_count(tg_id)
    text = texts.CODE_OK.format(num=lesson_num, count=count, total=config.LESSONS_COUNT,
                                bar=texts.progress(count, config.LESSONS_COUNT))
    if count >= config.LESSONS_COUNT and config.REQUIRE_COURSES_FOR_CERT:
        if await db.approved_course_count(tg_id) < len(config.COURSES):
            text += "\n\n" + texts.ALL_LESSONS_DONE.format(
                total=config.LESSONS_COUNT, platform=config.PLATFORM_NAME, courses=len(config.COURSES))
    return text


# ---------------------------------------------------------------- kurs sertifikatlari
async def send_cert_to_admins(bot: Bot, cert_id: int) -> None:
    c = await db.get_course_cert(cert_id)
    u = await db.get_user(c["tg_id"])
    caption = html.escape(texts.ADMIN_CERT_CAPTION.format(
        id=cert_id,
        name=full_name(u),
        username=f"@{u['username']}" if u["username"] else "username yoʻq",
        tg_id=u["tg_id"],
        course=config.COURSES[c["course_idx"]] if c["course_idx"] < len(config.COURSES) else c["course_idx"],
        done=await db.approved_course_count(u["tg_id"]),
        total=len(config.COURSES),
        start=fmt_date(config.MARATHON_START),
    ))
    targets = [config.ADMIN_CHAT_ID] if config.ADMIN_CHAT_ID else list(settings_store.all_admins())
    for target in targets:
        try:
            if c["file_type"] == "photo":
                await bot.send_photo(target, c["file_id"], caption=caption, reply_markup=kb.review_kb(cert_id))
            else:
                await bot.send_document(target, c["file_id"], caption=caption, reply_markup=kb.review_kb(cert_id))
        except TelegramAPIError as e:
            log.warning("Sertifikat #%s adminga (%s) yuborilmadi: %s", cert_id, target, e)


# ---------------------------------------------------------------- yakuniy sertifikat
async def conditions_met(tg_id: int) -> bool:
    if await db.attendance_count(tg_id) < config.LESSONS_COUNT:
        return False
    if config.REQUIRE_COURSES_FOR_CERT and await db.approved_course_count(tg_id) < len(config.COURSES):
        return False
    return True


async def check_final(bot: Bot, tg_id: int) -> bool:
    """Shartlar bajarilgan bo'lsa, yakuniy sertifikatni avtomatik beradi."""
    if await db.get_final(tg_id) or not await conditions_met(tg_id):
        return False
    if not await db.create_final(tg_id):
        return False  # parallel chaqiruv allaqachon bergan
    return await send_final(bot, tg_id)


async def send_final(bot: Bot, tg_id: int) -> bool:
    u = await db.get_user(tg_id)
    final = await db.get_final(tg_id)
    if not u or not final:
        return False
    serial = f"QO-{final['id']:05d}"
    issued = datetime.fromisoformat(final["issued_at"]).astimezone(config.TZ).date()
    png = await asyncio.to_thread(render_certificate, full_name(u), serial, issued)
    caption = texts.FINAL_CERT.format(name=html.escape(full_name(u)), marathon=config.MARATHON_NAME)
    if config.CLUB_LINK:
        caption += texts.CLUB_INVITE.format(link=config.CLUB_LINK)
    try:
        await bot.send_document(tg_id, BufferedInputFile(png, filename=f"Sertifikat_{serial}.png"), caption=caption)
        return True
    except TelegramAPIError as e:
        log.warning("Yakuniy sertifikat %s ga yuborilmadi: %s", tg_id, e)
        return False
