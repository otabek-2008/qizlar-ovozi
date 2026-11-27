"""Admin matnli buyruqlari, kurs sertifikatlarini tekshirish va panel uchun umumiy funksiyalar."""
import csv
import html
import io
import secrets
from datetime import datetime, timedelta, timezone

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command, CommandObject
from aiogram.types import BufferedInputFile, CallbackQuery, Message

import admin_auth
import config
import db
import keyboards as kb
import services
import settings_store
import texts


class IsAdmin(BaseFilter):
    """Admin roʻyxatida bor VA parolni kiritgan (sessiyasi ochiq)."""
    async def __call__(self, event) -> bool:
        return (bool(event.from_user) and settings_store.is_admin(event.from_user.id)
                and admin_auth.logged_in(event.from_user.id))


router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


async def send_long(m: Message, text: str) -> None:
    while text:
        if len(text) <= 4000:
            await m.answer(text)
            return
        cut = text.rfind("\n", 0, 4000)
        cut = cut if cut > 0 else 4000
        await m.answer(text[:cut])
        text = text[cut:].lstrip("\n")


def _lesson_num(arg: str | None) -> int | None:
    if arg and arg.isdigit() and 1 <= int(arg) <= config.LESSONS_COUNT:
        return int(arg)
    return None


def local(iso: str | None) -> str:
    if not iso:
        return "—"
    return datetime.fromisoformat(iso).astimezone(config.TZ).strftime("%d.%m %H:%M")


# ================================================================ umumiy funksiyalar (panel ham ishlatadi)
async def stats_text() -> str:
    today = services.local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    s = await db.stats(db.to_iso(today))
    lessons = await db.get_lessons()
    eligible = max(s["eligible"], 1)
    lesson_lines = "\n".join(
        f"{l['num']}-dars  {texts.progress(s['lessons'].get(l['num'], 0), eligible, 8)}  "
        f"<b>{s['lessons'].get(l['num'], 0)}</b>"
        for l in lessons
    ) or "—"
    certs = s["certs"]
    top = await db.top_referrers(3)
    top_lines = "\n".join(
        f"{texts.place(i)}  {html.escape(services.full_name(r))} — <b>{r['cnt']}</b>"
        for i, r in enumerate(top, 1)
    ) or "Hozircha takliflar yoʻq"
    return (
        f"📊 <b>Statistika  ·  {html.escape(config.MARATHON_NAME)}</b>\n"
        f"<i>🕒 {services.local_now():%d.%m.%Y %H:%M} holatiga</i>\n\n"
        f"👥 <b>Ishtirokchilar</b>\n"
        f"<blockquote>Roʻyxatdan oʻtgan: <b>{s['users']}</b>  ·  bugun +{s['today']}\n"
        f"Ishtirok huquqi ({config.REQUIRED_REFERRALS}+ taklif): <b>{s['eligible']}</b>\n"
        f"Taklif orqali kelgan: <b>{s['invited']}</b>  ·  taklif qilgan: {s['inviters']}</blockquote>\n\n"
        f"🎙 <b>Davomat</b>\n"
        f"<blockquote>{lesson_lines}\n"
        f"Faol (kamida 1 dars): <b>{s['any_lesson']}</b>\n"
        f"Barcha {config.LESSONS_COUNT} ta darsda: <b>{s['all_lessons']}</b></blockquote>\n\n"
        f"🎓 <b>Kurslar va sertifikatlar</b>\n"
        f"<blockquote>Kurs sertifikatlari: ✅ {certs.get('approved', 0)}  ⏳ {certs.get('pending', 0)}"
        f"  ❌ {certs.get('rejected', 0)}\n"
        f"{len(config.COURSES)} ta kursni tugatgan: <b>{s['courses_done']}</b>\n"
        f"🏅 Yakuniy sertifikat olgan: <b>{s['finals']}</b></blockquote>\n\n"
        f"🏆 <b>Eng faol qizlar</b>\n"
        f"<blockquote>{top_lines}</blockquote>"
    )


async def top_text(limit: int) -> str:
    rows = await db.top_referrers(min(limit, 500))
    if not rows:
        return texts.TOP_EMPTY
    lines = [f"🏆 <b>Top {len(rows)}  ·  eng koʻp taklif qilganlar</b>\n"]
    for i, r in enumerate(rows, 1):
        uname = f"  @{r['username']}" if r["username"] else ""
        lines.append(f"{texts.place(i)}  <b>{html.escape(services.full_name(r))}</b> — 💌 <b>{r['cnt']}</b>\n"
                     f"      📱 {r['phone']}{html.escape(uname)}  ·  🆔 <code>{r['tg_id']}</code>")
    return "\n".join(lines)


def lesson_status(l) -> str:
    now = db.now_iso()
    if not l["opens_at"]:
        return "▫️ hali ochilmagan"
    if l["opens_at"] <= now < l["closes_at"]:
        return f"🟢 <b>OCHIQ</b> · {local(l['closes_at'])} gacha · kod <code>{html.escape(l['code'])}</code>"
    return f"⚫️ yopilgan · {local(l['closes_at'])} · kod <code>{html.escape(l['code'] or '')}</code>"


async def lessons_text() -> str:
    s = await db.stats(db.now_iso())
    lines = ["🎙 <b>Darslar va davomat</b>\n"]
    for l in await db.get_lessons():
        lines.append(f"<b>{l['num']}. {html.escape(l['title'] or '')}</b>\n"
                     f"<blockquote>{lesson_status(l)}\n"
                     f"👥 Qatnashgan: <b>{s['lessons'].get(l['num'], 0)}</b></blockquote>")
    return "\n".join(lines)


async def open_lesson_now(bot: Bot, chat_id: int, num: int, minutes: int | None, code: str | None) -> None:
    minutes = max(1, min(minutes or config.DEFAULT_CODE_MINUTES, 24 * 60))
    code = code or str(secrets.randbelow(9000) + 1000)
    now = datetime.now(timezone.utc)
    closes = now + timedelta(minutes=minutes)
    await db.open_lesson(num, code, db.to_iso(now), db.to_iso(closes))
    lesson = await db.get_lesson(num)
    until = closes.astimezone(config.TZ).strftime("%H:%M")
    await bot.send_message(
        chat_id,
        f"🟢 <b>{num}-dars — davomat ochildi</b>\n\n"
        f"<blockquote>🎟 Kod:  <code>{html.escape(code)}</code>\n"
        f"⏱ {minutes} daqiqa · soat <b>{until}</b> gacha</blockquote>\n\n"
        f"🎙 Kodni darsda ayting.\n"
        f"<i>📢 Ishtirokchilarga xabar yuborilmoqda...</i>",
    )
    ids = await db.all_user_ids(only_eligible=config.REQUIRE_REFERRALS_TO_ATTEND)
    text = texts.LESSON_OPEN_NOTIFY.format(num=num, title=html.escape(lesson["title"] or ""),
                                           minutes=minutes, until=until)
    services.run_background(services.broadcast(bot, ids, text=text, report_to=chat_id))


async def set_homework(bot: Bot, chat_id: int, on: bool) -> None:
    await db.set_setting("homework_open", "1" if on else "0")
    if not on:
        await bot.send_message(chat_id, "⚫️ Kurs sertifikatlarini qabul qilish <b>yopildi</b>.")
        return
    await bot.send_message(chat_id, "🟢 Kurs sertifikatlarini qabul qilish <b>ochildi</b>.\n"
                                    "<i>📢 Ishtirokchilarga xabar yuborilmoqda...</i>")
    courses = "\n".join(f"📘 {html.escape(c)}" for c in config.COURSES)
    text = texts.HOMEWORK_OPEN_NOTIFY.format(
        platform=html.escape(config.PLATFORM_NAME), count=len(config.COURSES), courses=courses,
        link=f"🔗 {config.PLATFORM_LINK}\n" if config.PLATFORM_LINK else "",
        start=services.fmt_date(config.MARATHON_START),
    )
    ids = await db.all_user_ids(only_eligible=config.REQUIRE_REFERRALS_TO_ATTEND)
    services.run_background(services.broadcast(bot, ids, text=text, report_to=chat_id))


async def send_export(m: Message) -> None:
    rows = await db.export_rows()
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["Telegram ID", "Username", "Ism", "Familiya", "Telefon", "Tugʻilgan sana", "Oʻqish/ish joyi",
                "Roʻyxatdan oʻtgan", "Kim taklif qilgan", "Taklif qilgan telefoni", "Taklif qilgan ID",
                "Takliflar soni", "Kimlarni taklif qilgan", "Ishtirok huquqi",
                "Qatnashgan darslar soni", "Qatnashgan darslar", "Tasdiqlangan kurslar", "Yakuniy sertifikat"])
    for r in rows:
        w.writerow([
            r["tg_id"], r["username"] or "", r["first_name"], r["last_name"], r["phone"], r["birth_date"],
            r["study_place"] or "", local(r["registered_at"]),
            r["ref_name"] or ("oʻchirilgan" if r["referrer_id"] else "oʻzi kelgan"), r["ref_phone"] or "",
            r["referrer_id"] or "", r["refs"], r["invitees"] or "",
            "ha" if r["eligible_at"] else "yoʻq", r["att"], r["att_list"] or "", r["courses"],
            f"QO-{r['final_id']:05d}" if r["final_id"] else "",
        ])
    data = buf.getvalue().encode("utf-8-sig")
    name = f"ishtirokchilar_{services.local_now():%Y%m%d_%H%M}.csv"
    await m.answer_document(BufferedInputFile(data, filename=name),
                            caption=f"📥 <b>Ishtirokchilar roʻyxati</b>\n👥 Jami: <b>{len(rows)}</b>\n"
                                    f"<i>Excel'da ochiladi</i>")


async def resend_pending(m: Message, bot: Bot) -> None:
    rows = await db.pending_certs(10)
    if not rows:
        await m.answer("✅ Tekshirilmagan sertifikat yoʻq.")
        return
    for r in rows:
        await services.send_cert_to_admins(bot, r["id"])
    await m.answer(f"📤 <b>{len(rows)}</b> ta sertifikat tekshiruvga qayta yuborildi.")


async def check_all(m: Message, bot: Bot) -> None:
    issued = 0
    for uid in await db.users_with_full_attendance():
        if await services.check_final(bot, uid):
            issued += 1
    await m.answer(f"🏅 Yangi berilgan yakuniy sertifikatlar: <b>{issued}</b>")


# ================================================================ matnli buyruqlar
@router.message(Command("help_admin"))
async def cmd_help(m: Message):
    await m.answer(texts.ADMIN_HELP)


@router.message(Command("stats"))
async def cmd_stats(m: Message):
    await m.answer(await stats_text())


@router.message(Command("top"))
async def cmd_top(m: Message, command: CommandObject):
    limit = int(command.args) if command.args and command.args.isdigit() else 10
    await send_long(m, await top_text(limit))


@router.message(Command("export"))
async def cmd_export(m: Message):
    await send_export(m)


@router.message(Command("user"))
async def cmd_user(m: Message, command: CommandObject):
    if not command.args:
        return await m.answer("🔎 <b>Qidirish</b>\n<code>/user ID</code>  ·  <code>/user @username</code>  ·  "
                              "<code>/user +998901234567</code>")
    u = await db.find_user(command.args)
    if not u:
        return await m.answer("🔎 Topilmadi.")
    await m.answer(await user_card(u))
    if await db.referral_count(u["tg_id"]) > CARD_INVITEES:
        await send_long(m, await invitees_text(u))


CARD_INVITEES = 15  # kartochkada koʻrsatiladigan takliflar soni (qolgani alohida roʻyxatda)


async def invitees_text(u) -> str:
    """Ishtirokchi taklif qilgan BARCHA odamlar roʻyxati."""
    invitees = await db.get_invitees(u["tg_id"])
    if not invitees:
        return f"💌 <b>{html.escape(services.full_name(u))}</b> hali hech kimni taklif qilmagan."
    lines = [f"💌 <b>{html.escape(services.full_name(u))}</b> taklif qilganlar  ·  <b>{len(invitees)}</b> ta\n"]
    for i, r in enumerate(invitees, 1):
        lines.append(f"{i}. <b>{html.escape(services.full_name(r))}</b>\n"
                     f"      📱 {html.escape(r['phone'])}  ·  🆔 <code>{r['tg_id']}</code>  ·  🕒 {local(r['registered_at'])}")
    return "\n".join(lines)


async def user_card(u) -> str:
    """Ishtirokchi haqida toʻliq maʼlumot (/user va paneldagi «👥 Ishtirokchilar» uchun)."""
    uid = u["tg_id"]
    attended = sorted(await db.user_attendance(uid))
    statuses = await db.course_status(uid)
    final = await db.get_final(uid)
    courses = "\n".join(f"{texts.STATUS_NAMES.get(statuses.get(i), texts.NOT_SENT).split(' ', 1)[0]} "
                        f"{html.escape(c)}" for i, c in enumerate(config.COURSES)) or "—"
    referrer = await db.get_user(u["referrer_id"]) if u["referrer_id"] else None
    if referrer:
        came = (f"<b>{html.escape(services.full_name(referrer))}</b> taklifi bilan\n"
                f"      📱 {html.escape(referrer['phone'])}  ·  🆔 <code>{referrer['tg_id']}</code>")
    elif u["referrer_id"]:
        came = f"<i>oʻchirilgan ishtirokchi taklifi bilan</i> (🆔 <code>{u['referrer_id']}</code>)"
    else:
        came = "<i>oʻzi kelgan (taklifsiz)</i>"
    invitees = await db.get_invitees(uid)
    shown = invitees[:CARD_INVITEES]
    inv_lines = "\n".join(
        f"{i}. {html.escape(services.full_name(r))}  ·  {local(r['registered_at'])}" for i, r in enumerate(shown, 1)
    )
    if len(invitees) > len(shown):
        inv_lines += f"\n<i>… yana {len(invitees) - len(shown)} ta — «💌 Taklif qilganlari» tugmasida</i>"
    return (
        f"👤 <b>{html.escape(services.full_name(u))}</b>"
        + ("  <i>(admin profili)</i>" if u["auto_admin"] else "") + "\n"
        f"🆔 <code>{uid}</code>  ·  "
        f"{'@' + html.escape(u['username']) if u['username'] else '<i>username yoʻq</i>'}\n\n"
        f"<blockquote>📱 {u['phone']}\n"
        f"🎂 {'.'.join(reversed(u['birth_date'].split('-')))}\n"
        f"🏫 {html.escape(u['study_place'] or '—')}\n"
        f"🕒 Roʻyxatdan oʻtgan: {local(u['registered_at'])}</blockquote>\n\n"
        f"🔗 <b>Kim orqali kelgan:</b> {came}\n\n"
        f"💌 <b>Taklif qilganlari: {len(invitees)}</b>  ·  🏆 oʻrni: {await db.user_rank(uid) or '—'}  ·  "
        f"{'✅ ishtirokchi' if u['eligible_at'] else '🔒 ishtirokchi emas'}\n"
        + (f"<blockquote>{inv_lines}</blockquote>\n" if invitees else "")
        + "\n"
        f"🎙 Darslar: <b>{len(attended)}/{config.LESSONS_COUNT}</b>  "
        f"{texts.progress(len(attended), config.LESSONS_COUNT, config.LESSONS_COUNT)}\n"
        f"🎓 Kurslar:\n<blockquote>{courses}</blockquote>\n"
        f"🏅 Sertifikat: {'<code>QO-%05d</code>' % final['id'] if final else '—'}"
    )


@router.message(Command("lessons"))
async def cmd_lessons(m: Message):
    await m.answer(await lessons_text())


@router.message(Command("lesson_title"))
async def cmd_lesson_title(m: Message, command: CommandObject):
    parts = (command.args or "").split(maxsplit=1)
    num = _lesson_num(parts[0] if parts else None)
    if not num or len(parts) < 2:
        return await m.answer("💡 Foydalanish:/lesson_title 1 Oʻziga ishonch")
    await db.set_lesson_title(num, parts[1].strip()[:100])
    await m.answer(f"✅ {num}-dars mavzusi: {html.escape(parts[1].strip())}")


@router.message(Command("open_lesson"))
async def cmd_open_lesson(m: Message, command: CommandObject, bot: Bot):
    parts = (command.args or "").split()
    num = _lesson_num(parts[0] if parts else None)
    if not num:
        return await m.answer(f"💡 Foydalanish:/open_lesson N [daqiqa] [kod]\nMasalan: /open_lesson 1 10 2741\n"
                              f"N — 1 dan {config.LESSONS_COUNT} gacha")
    minutes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
    code = parts[2] if len(parts) > 2 else None
    await open_lesson_now(bot, m.chat.id, num, minutes, code)


@router.message(Command("close_lesson"))
async def cmd_close_lesson(m: Message, command: CommandObject):
    num = _lesson_num(command.args.strip() if command.args else None)
    if not num:
        return await m.answer("💡 Foydalanish:/close_lesson N")
    await db.close_lesson(num)
    await m.answer(f"⚫️ <b>{num}-dars</b> — davomat yopildi.")


@router.message(Command("homework_on"))
async def cmd_homework_on(m: Message, bot: Bot):
    await set_homework(bot, m.chat.id, True)


@router.message(Command("homework_off"))
async def cmd_homework_off(m: Message, bot: Bot):
    await set_homework(bot, m.chat.id, False)


@router.message(Command("pending"))
async def cmd_pending(m: Message, bot: Bot):
    await resend_pending(m, bot)


@router.message(Command("check_all"))
async def cmd_check_all(m: Message, bot: Bot):
    await check_all(m, bot)


@router.message(Command("set_review_group"))
async def cmd_set_review_group(m: Message):
    if m.chat.type == "private":
        return await m.answer("Bu buyruqni botni qoʻshgan guruhingizda yozing.")
    await settings_store.set_value("ADMIN_CHAT_ID", m.chat.id)
    await m.answer("✅ Endi kurs sertifikatlari shu guruhga tekshiruvga keladi.")


@router.message(Command("issue_cert"))
async def cmd_issue_cert(m: Message, command: CommandObject, bot: Bot):
    u = await db.find_user(command.args) if command.args else None
    if not u:
        return await m.answer("💡 Foydalanish:/issue_cert ID")
    await db.create_final(u["tg_id"])
    ok = await services.send_final(bot, u["tg_id"])
    await m.answer("✅ Sertifikat yuborildi." if ok else "⚠️ Yuborib boʻlmadi (foydalanuvchi botni bloklagan boʻlishi mumkin).")


@router.message(Command("eligible"))
async def cmd_eligible(m: Message, command: CommandObject, bot: Bot):
    u = await db.find_user(command.args) if command.args else None
    if not u:
        return await m.answer("💡 Foydalanish:/eligible ID")
    if await db.set_eligible(u["tg_id"]):
        await services.safe_send(bot, u["tg_id"], texts.ELIGIBLE_MANUAL.format(marathon=config.MARATHON_NAME))
    await m.answer(f"✅ {html.escape(services.full_name(u))} — ishtirok huquqi berildi.")


@router.message(Command("broadcast"))
async def cmd_broadcast(m: Message, command: CommandObject, bot: Bot):
    if not m.reply_to_message:
        return await m.answer("Tarqatmoqchi boʻlgan xabarga javob (reply) qilib /broadcast yozing.\n"
                              "/broadcast eligible — faqat ishtirok huquqini olganlarga.")
    only_eligible = (command.args or "").strip().lower() == "eligible"
    ids = await db.all_user_ids(only_eligible=only_eligible)
    await m.answer(f"📢 {len(ids)} ta foydalanuvchiga yuborilmoqda...")
    services.run_background(services.broadcast(
        bot, ids, copy_from=(m.chat.id, m.reply_to_message.message_id), report_to=m.chat.id))


# ================================================================ kurs sertifikatini tekshirish
@router.callback_query(F.data.startswith("cc:"))
async def cb_review(cb: CallbackQuery, bot: Bot):
    parts = cb.data.split(":")
    action, cert_id = parts[1], int(parts[2])
    c = await db.get_course_cert(cert_id)
    if not c:
        return await cb.answer("Topilmadi", show_alert=True)
    if c["status"] != "pending":
        await cb.answer("Bu sertifikat allaqachon koʻrib chiqilgan.", show_alert=True)
        try:
            await cb.message.edit_reply_markup(reply_markup=None)
        except TelegramAPIError:
            pass
        return

    if action == "rej":
        await cb.message.edit_reply_markup(reply_markup=kb.reject_reasons_kb(cert_id))
        return await cb.answer()
    if action == "back":
        await cb.message.edit_reply_markup(reply_markup=kb.review_kb(cert_id))
        return await cb.answer()

    course = config.COURSES[c["course_idx"]] if c["course_idx"] < len(config.COURSES) else str(c["course_idx"])
    admin = cb.from_user.full_name

    if action == "ok":
        if not await db.review_course_cert(cert_id, "approved", None, cb.from_user.id):
            return await cb.answer("Allaqachon koʻrib chiqilgan.", show_alert=True)
        mark = f"✅ TASDIQLANDI · {admin}"
        done = await db.approved_course_count(c["tg_id"])
        await services.safe_send(bot, c["tg_id"], texts.CERT_APPROVED.format(
            course=html.escape(course), done=done, total=len(config.COURSES),
            bar=texts.progress(done, len(config.COURSES))))
        if done >= len(config.COURSES) and not await services.conditions_met(c["tg_id"]):
            await services.safe_send(bot, c["tg_id"], texts.COURSES_DONE_NEED_LESSONS.format(
                total=config.LESSONS_COUNT, att=await db.attendance_count(c["tg_id"])))
        await services.check_final(bot, c["tg_id"])
    elif action == "r":
        key = parts[3] if len(parts) > 3 else "bad"
        reason = texts.REJECT_REASONS.get(key, texts.REJECT_REASONS["bad"]).format(
            start=services.fmt_date(config.MARATHON_START))
        if not await db.review_course_cert(cert_id, "rejected", reason, cb.from_user.id):
            return await cb.answer("Allaqachon koʻrib chiqilgan.", show_alert=True)
        mark = f"❌ RAD ETILDI · {admin}\nSabab: {reason}"
        await services.safe_send(bot, c["tg_id"], texts.CERT_REJECTED.format(
            course=html.escape(course), reason=html.escape(reason)))
    else:
        return await cb.answer()

    try:
        await cb.message.edit_caption(caption=html.escape((cb.message.caption or "") + "\n\n" + mark)[:1024],
                                      reply_markup=None)
    except TelegramAPIError:
        pass
    await cb.answer("Saqlandi")
