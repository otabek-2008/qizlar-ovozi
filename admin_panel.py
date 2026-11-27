"""Tugmali Admin panel: marafonning barcha tashkiliy sozlamalari bot ichidan boshqariladi."""
import asyncio
import html
import io

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

import admin_auth
import certificate
import subscription
import config
import db
import handlers_admin as ha
import services
import settings_store as st
import texts

router = Router(name="admin_panel")
router.message.filter(ha.IsAdmin())
router.callback_query.filter(ha.IsAdmin())


class AdminInput(StatesGroup):
    waiting = State()


BACK = ("◀️ Orqaga", "ap:main")
CANCEL = ("✖️ Bekor qilish", "ap:cancel")

ICONS = {
    "MARATHON_NAME": "🌸", "MARATHON_START": "📅", "REQUIRED_REFERRALS": "💌", "LESSONS_COUNT": "🎙",
    "DEFAULT_CODE_MINUTES": "⏱", "REQUIRE_REFERRALS_TO_ATTEND": "🔐", "COURSES": "📘", "PLATFORM_NAME": "🏷",
    "PLATFORM_LINK": "🔗", "REQUIRE_COURSES_FOR_CERT": "🎓", "CLUB_LINK": "💎", "ORGANIZER": "🏢",
    "ADMIN_CHAT_ID": "👥", "CERT_NAME_Y": "↕️", "CERT_NAME_COLOR": "🎨", "REQUIRED_CHANNELS": "📢",
}


def _kb(rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t, callback_data=d) for t, d in row] for row in rows
    ])


async def _show(target, text: str, rows) -> None:
    """Panel oynasini ko'rsatadi: tugma bosilgan bo'lsa — o'sha xabarni tahrirlaydi."""
    markup = _kb(rows)
    if isinstance(target, CallbackQuery):
        try:
            await target.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
            return
        except TelegramBadRequest as e:
            if "not modified" in str(e):
                return
        target = target.message
    await target.answer(text, reply_markup=markup, disable_web_page_preview=True)


async def _ask(target, state: FSMContext, prompt: str, extra_rows=None, **data) -> None:
    await state.set_state(AdminInput.waiting)
    await state.set_data(data)
    await _show(target, prompt, (extra_rows or []) + [[CANCEL]])


# ================================================================ bosh menyu
async def show_main(target) -> None:
    users = len(await db.all_user_ids(participants_only=True))
    eligible = len(await db.all_user_ids(only_eligible=True, participants_only=True))
    hw = await db.get_setting("homework_open") == "1"
    pending = await db.count_pending()
    open_now = await db.open_lessons()
    live = (f"\n🔴 <b>Hozir davomat ochiq:</b> " + ", ".join(f"{l['num']}-dars" for l in open_now)) if open_now else ""
    text = (
        f"🛠 <b>Admin panel</b>\n"
        f"<i>🌸 {html.escape(config.MARATHON_NAME)}  ·  📅 {st.display('MARATHON_START')}</i>\n\n"
        f"<blockquote>👥 Roʻyxatdan oʻtgan: <b>{users}</b>\n"
        f"✅ Ishtirokchilar: <b>{eligible}</b>\n"
        f"🎓 Kurs vazifasi: {'🟢 ochiq' if hw else '⚫️ yopiq'}"
        + (f"\n⏳ Tekshiruv kutmoqda: <b>{pending}</b>" if pending else "")
        + f"</blockquote>{live}\n\nBoʻlimni tanlang 👇"
    )
    await _show(target, text, [
        [("📊 Statistika", "ap:stats"), ("🏆 Reyting", "ap:top")],
        [("🎙 Darslar va davomat", "ap:lessons")],
        [(f"🎓 Kurs vazifasi{f' · {pending}' if pending else ''}", "ap:hw"), ("🖼 Sertifikat", "ap:cert")],
        [("👥 Ishtirokchilar", "ap:u"), ("📥 Excel", "ap:export")],
        [("⚙️ Sozlamalar", "ap:set"), ("📢 Xabar", "ap:bc")],
        [("👮 Adminlar", "ap:admins"), ("🔄 Yangilash", "ap:main")],
        [("🚪 Chiqish", "ap:logout")],
    ])


@router.callback_query(F.data == "ap:main")
async def cb_main(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main(cb)
    await cb.answer()


@router.callback_query(F.data == "ap:cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_main(cb)
    await cb.answer("Bekor qilindi")


# ================================================================ statistika, reyting, excel
@router.callback_query(F.data == "ap:stats")
async def cb_stats(cb: CallbackQuery):
    await _show(cb, await ha.stats_text(), [[("🔄 Yangilash", "ap:stats"), BACK]])
    await cb.answer()


@router.callback_query(F.data == "ap:top")
async def cb_top(cb: CallbackQuery):
    text = await ha.top_text(20)
    await _show(cb, text[:4000], [[("🔄 Yangilash", "ap:top"), BACK]])
    await cb.answer()


@router.callback_query(F.data == "ap:export")
async def cb_export(cb: CallbackQuery):
    await cb.answer("Tayyorlanmoqda...")
    await ha.send_export(cb.message)


# ================================================================ darslar
async def show_lessons(target) -> None:
    lessons = await db.get_lessons()
    buttons = [(f"{l['num']}-dars", f"ap:l:{l['num']}") for l in lessons]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([("🎙 Darslar soni", "ap:e:LESSONS_COUNT"), ("⏱ Kod vaqti", "ap:e:DEFAULT_CODE_MINUTES")])
    rows.append([("🔄 Yangilash", "ap:lessons"), BACK])
    await _show(target, await ha.lessons_text() + "\n\nDarsni tanlang 👇", rows)


async def show_lesson(target, num: int) -> None:
    l = await db.get_lesson(num)
    s = await db.stats(db.now_iso())
    text = (
        f"🎙 <b>{num}-dars  ·  {html.escape(l['title'] or '')}</b>\n\n"
        f"<blockquote>{ha.lesson_status(l)}\n"
        f"👥 Qatnashgan: <b>{s['lessons'].get(num, 0)}</b></blockquote>\n\n"
        f"🟢 Vaqtni tanlang — kod avtomatik yaratiladi, ishtirokchilarga xabar ketadi."
    )
    await _show(target, text, [
        [(f"🟢 {x} daq", f"ap:lo:{num}:{x}") for x in (5, 10, 15, 30)],
        [("🎟 Oʻz kodim bilan", f"ap:lc:{num}")],
        [("⚫️ Yopish", f"ap:lx:{num}"), ("✏️ Mavzu", f"ap:lt:{num}")],
        [("◀️ Darslar", "ap:lessons")],
    ])


@router.callback_query(F.data == "ap:lessons")
async def cb_lessons(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_lessons(cb)
    await cb.answer()


@router.callback_query(F.data.startswith("ap:l:"))
async def cb_lesson(cb: CallbackQuery):
    await show_lesson(cb, int(cb.data.split(":")[2]))
    await cb.answer()


@router.callback_query(F.data.startswith("ap:lo:"))
async def cb_lesson_open(cb: CallbackQuery, bot: Bot):
    _, _, num, minutes = cb.data.split(":")
    await cb.answer("Ochilmoqda...")
    await ha.open_lesson_now(bot, cb.message.chat.id, int(num), int(minutes), None)
    await show_lesson(cb, int(num))


@router.callback_query(F.data.startswith("ap:lx:"))
async def cb_lesson_close(cb: CallbackQuery):
    num = int(cb.data.split(":")[2])
    await db.close_lesson(num)
    await cb.answer("Davomat yopildi")
    await show_lesson(cb, num)


@router.callback_query(F.data.startswith("ap:lc:"))
async def cb_lesson_code(cb: CallbackQuery, state: FSMContext):
    num = int(cb.data.split(":")[2])
    await _ask(cb, state,
               f"🎟 <b>{num}-dars  ·  oʻz kodingiz</b>\n\n"
               f"Kodni yozing. Xohlasangiz, yoniga daqiqani ham: <code>ROSE 15</code>\n"
               f"<i>Daqiqa yozilmasa — {config.DEFAULT_CODE_MINUTES} daqiqa</i>",
               action="lesson_code", num=num)
    await cb.answer()


@router.callback_query(F.data.startswith("ap:lt:"))
async def cb_lesson_title(cb: CallbackQuery, state: FSMContext):
    num = int(cb.data.split(":")[2])
    await _ask(cb, state, f"✏️ <b>{num}-dars mavzusi</b>\n\nYangi mavzuni yozing:\n<i>Masalan: Oʻziga ishonch</i>",
               action="lesson_title", num=num)
    await cb.answer()


# ================================================================ kurs vazifasi
async def show_homework(target) -> None:
    hw = await db.get_setting("homework_open") == "1"
    pending = await db.count_pending()
    courses = "\n".join(f"📘 {html.escape(c)}" for c in config.COURSES) or "—"
    link = f"\n🔗 {html.escape(config.PLATFORM_LINK)}" if config.PLATFORM_LINK else ""
    text = (
        f"🎓 <b>Kurs vazifasi</b>\n"
        f"{'🟢 Sertifikatlar qabul qilinmoqda' if hw else '⚫️ Qabul yopiq'}\n\n"
        f"🏷 <b>{html.escape(config.PLATFORM_NAME)}</b>{link}\n"
        f"<blockquote>{courses}</blockquote>\n\n"
        f"📅 Sertifikat sanasi: <b>{st.display('MARATHON_START')}</b> dan\n"
        f"🎓 Yakuniy sertifikat uchun kurslar sharti: {st.display('REQUIRE_COURSES_FOR_CERT')}\n"
        f"⏳ Tekshiruv kutmoqda: <b>{pending}</b>"
    )
    await _show(target, text, [
        [("⚫️ Qabulni yopish", "ap:hw:off") if hw else ("🟢 Qabulni ochish · xabar ketadi", "ap:hw:on")],
        [("📘 Kurslar", "ap:e:COURSES"), ("🔗 Havola", "ap:e:PLATFORM_LINK")],
        [("🏷 Platforma nomi", "ap:e:PLATFORM_NAME"), ("🎓 Kurslar sharti", "ap:e:REQUIRE_COURSES_FOR_CERT")],
        [(f"📤 Tekshiruvga chiqarish · {pending}", "ap:pending")],
        [("🏅 Yakuniy sertifikatlarni tarqatish", "ap:checkall")],
        [BACK],
    ])


@router.callback_query(F.data == "ap:hw")
async def cb_hw(cb: CallbackQuery):
    await show_homework(cb)
    await cb.answer()


@router.callback_query(F.data.in_({"ap:hw:on", "ap:hw:off"}))
async def cb_hw_toggle(cb: CallbackQuery, bot: Bot):
    await ha.set_homework(bot, cb.message.chat.id, cb.data.endswith("on"))
    await show_homework(cb)
    await cb.answer()


@router.callback_query(F.data == "ap:pending")
async def cb_pending(cb: CallbackQuery, bot: Bot):
    await cb.answer()
    await ha.resend_pending(cb.message, bot)


@router.callback_query(F.data == "ap:checkall")
async def cb_checkall(cb: CallbackQuery, bot: Bot):
    await cb.answer("Tekshirilmoqda...")
    await ha.check_all(cb.message, bot)


# ================================================================ sozlamalar
async def show_settings(target) -> None:
    lines = ["⚙️ <b>Marafon sozlamalari</b>\n"]
    for key in st.SETTINGS_MENU:
        f = st.FIELDS[key]
        value = st.display(key)
        if f.kind == "list":
            value = ", ".join(getattr(config, key)) or "—"
        lines.append(f"{ICONS.get(key, '•')} {f.title}\n      <b>{html.escape(value)}</b>")
    lines.append("\nOʻzgartirish uchun tanlang 👇")
    buttons = [(f"{ICONS.get(k, '')} {st.FIELDS[k].title}", f"ap:e:{k}") for k in st.SETTINGS_MENU]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([BACK])
    await _show(target, "\n".join(lines), rows)


@router.callback_query(F.data == "ap:set")
async def cb_settings(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_settings(cb)
    await cb.answer()


@router.callback_query(F.data.startswith("ap:e:"))
async def cb_edit(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":", 2)[2]
    f = st.FIELDS.get(key)
    if not f:
        return await cb.answer()
    if f.kind == "bool":
        await st.set_value(key, not getattr(config, key))
        await cb.answer(f"{f.title}: {st.display(key)}", show_alert=True)
        return await show_settings(cb)
    prompt = (f"{ICONS.get(key, '✏️')} <b>{f.title}</b>\n\n"
              f"<blockquote>Hozir: <b>{html.escape(st.display(key))}</b></blockquote>\n\n"
              + (f"<i>{html.escape(f.hint)}</i>\n\n" if f.hint else "")
              + "✍️ Yangi qiymatni yozib yuboring:")
    extra = [[("🗑 Tozalash", f"ap:clr:{key}")]] if f.clearable else None
    await _ask(cb, state, prompt, extra, action="set", key=key)
    await cb.answer()


@router.callback_query(F.data.startswith("ap:clr:"))
async def cb_clear(cb: CallbackQuery, state: FSMContext):
    key = cb.data.split(":", 2)[2]
    f = st.FIELDS[key]
    await st.set_value(key, 0 if f.kind == "chat" else ([] if f.kind == "channels" else ""))
    await state.clear()
    await cb.answer("Tozalandi")
    await show_settings(cb)


# ================================================================ sertifikat
async def show_cert(target) -> None:
    template = "✅ oʻzingiz yuklagan rasm" if certificate.has_template() else "▫️ yoʻq — bot oʻz dizaynini chizadi"
    text = (
        "🖼 <b>Yakuniy sertifikat</b>\n\n"
        f"<blockquote>🖼 Shablon: {template}\n"
        f"↕️ Ism joyi: <b>{st.display('CERT_NAME_Y')}</b> (yuqoridan)\n"
        f"🎨 Ism rangi: <b>{st.display('CERT_NAME_COLOR')}</b>\n"
        f"🏢 Tashkilotchi: <b>{html.escape(st.display('ORGANIZER'))}</b>\n"
        f"💎 Club: {html.escape(st.display('CLUB_LINK'))}</blockquote>\n\n"
        "💡 <i>Dizayneringizdan <b>ismsiz</b> sertifikat rasmini olib yuklang, soʻng «Namuna» bilan "
        "ism toʻgʻri joyga tushganini tekshiring.</i>"
    )
    rows = [
        [("👁 Namunani koʻrish", "ap:cp")],
        [("📤 Shablon yuklash", "ap:ct")] + ([("🗑 Oʻchirish", "ap:cd")] if certificate.has_template() else []),
        [("↕️ Ism joyi", "ap:e:CERT_NAME_Y"), ("🎨 Ism rangi", "ap:e:CERT_NAME_COLOR")],
        [("🏢 Tashkilotchi", "ap:e:ORGANIZER"), ("💎 Club havolasi", "ap:e:CLUB_LINK")],
        [BACK],
    ]
    await _show(target, text, rows)


@router.callback_query(F.data == "ap:cert")
async def cb_cert(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_cert(cb)
    await cb.answer()


async def _send_preview(m: Message) -> None:
    png = await asyncio.to_thread(certificate.render_certificate, "Oʻgʻiloy Gʻaniyeva", "QO-00000",
                                  services.local_now().date())
    await m.answer_document(BufferedInputFile(png, filename="namuna.png"),
                            caption="👁 <b>Sertifikat namunasi</b>\n<i>Ism — misol uchun</i>")


@router.callback_query(F.data == "ap:cp")
async def cb_cert_preview(cb: CallbackQuery):
    await cb.answer("Tayyorlanmoqda...")
    await _send_preview(cb.message)


@router.callback_query(F.data == "ap:ct")
async def cb_cert_template(cb: CallbackQuery, state: FSMContext):
    await _ask(cb, state,
               "📤 <b>Shablon yuklash</b>\n\n"
               "<b>Ism yozilmagan</b> sertifikat rasmini yuboring (PNG/JPG).\n"
               "<i>💡 Sifat buzilmasligi uchun 📎 → Fayl koʻrinishida yuboring.</i>",
               action="template")
    await cb.answer()


@router.callback_query(F.data == "ap:cd")
async def cb_cert_delete(cb: CallbackQuery):
    await certificate.delete_template()
    await cb.answer("Shablon oʻchirildi — bot oʻz dizaynidan foydalanadi", show_alert=True)
    await show_cert(cb)


# ================================================================ xabar yuborish
@router.callback_query(F.data == "ap:bc")
async def cb_broadcast(cb: CallbackQuery, state: FSMContext):
    await _ask(cb, state,
               "📢 <b>Xabar yuborish</b>\n\n"
               "Tarqatmoqchi boʻlgan xabaringizni yuboring — matn, rasm, video yoki ovozli xabar.\n"
               "<i>Keyingi qadamda kimlarga yuborishni tanlaysiz.</i>",
               action="broadcast")
    await cb.answer()


@router.callback_query(F.data.in_({"ap:bca:all", "ap:bca:elig"}))
async def cb_broadcast_go(cb: CallbackQuery, state: FSMContext, bot: Bot):
    data = await state.get_data()
    src = data.get("src")
    await state.clear()
    if not src:
        return await cb.answer("Xabar topilmadi, qaytadan boshlang.", show_alert=True)
    ids = await db.all_user_ids(only_eligible=cb.data.endswith("elig"))
    services.run_background(services.broadcast(bot, ids, copy_from=tuple(src), report_to=cb.message.chat.id))
    await _show(cb, f"📢 <b>Yuborilmoqda...</b>\n👥 Qabul qiluvchilar: <b>{len(ids)}</b>\n"
                    f"<i>Tugagach hisobot keladi.</i>", [[BACK]])
    await cb.answer()


# ================================================================ ishtirokchilar (qidirish, oʻchirish)
async def show_user(target, tg_id: int) -> None:
    u = await db.get_user(tg_id)
    if not u:
        return await _show(target, "🔎 Ishtirokchi topilmadi (oʻchirilgan boʻlishi mumkin).",
                           [[("📋 Roʻyxat", "ap:u"), ("🔎 Qidirish", "ap:us")], [BACK]])
    refs = await db.referral_count(tg_id)
    referrer = await db.get_user(u["referrer_id"]) if u["referrer_id"] else None
    ref_row = []
    if referrer:
        ref_row.append((f"🔗 Kim taklif qilgan: {services.short_name(referrer)}", f"ap:uv:{referrer['tg_id']}"))
    if refs:
        ref_row.append((f"💌 Taklif qilganlari · {refs}", f"ap:ui:{tg_id}"))
    rows = [ref_row] if ref_row else []
    rows += [
        [("✏️ Tahrirlash", f"ap:ue:{tg_id}"), ("🗑 Oʻchirish", f"ap:ud:{tg_id}")],
        [("📋 Roʻyxat", "ap:u"), ("🔎 Qidirish", "ap:us")],
        [BACK],
    ]
    await _show(target, await ha.user_card(u), rows)


INVITEE_BUTTONS = 30


@router.callback_query(F.data.startswith("ap:ui:"))
async def cb_user_invitees(cb: CallbackQuery):
    uid = int(cb.data.split(":")[2])
    u = await db.get_user(uid)
    if not u:
        return await cb.answer("Topilmadi", show_alert=True)
    invitees = await db.get_invitees(uid)
    text = await ha.invitees_text(u)
    buttons = [(f"👤 {services.short_name(r)}", f"ap:uv:{r['tg_id']}") for r in invitees[:INVITEE_BUTTONS]]
    rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    rows.append([("◀️ Kartochka", f"ap:uv:{uid}")])
    if len(text) <= 4000:
        await _show(cb, text, rows)
    else:  # juda koʻp boʻlsa — toʻliq roʻyxat alohida xabarlarda
        await ha.send_long(cb.message, text)
        await _show(cb, f"💌 Toʻliq roʻyxat yuqorida ({len(invitees)} ta). Kartochkani ochish uchun tanlang 👇", rows)
    await cb.answer()


# ---------------------------------------------------------------- ishtirokchini tahrirlash
EDIT_FIELDS = {
    "first_name": ("👤", "Ism", "Masalan: Malika"),
    "last_name": ("👤", "Familiya", "Masalan: Karimova"),
    "phone": ("📱", "Telefon", "Masalan: +998901234567"),
    "birth_date": ("🎂", "Tugʻilgan sana", "Kun.Oy.Yil, masalan: 15.03.2008"),
    "study_place": ("🏫", "Oʻqish / ish joyi", "Aniq manzili bilan, masalan: 21-maktab (Toshkent sh., Chilonzor tumani)"),
}


def _fmt_birth(value: str) -> str:
    return ".".join(reversed(value.split("-"))) if value and value != "—" else "—"


async def show_user_edit(target, tg_id: int, note: str = "") -> None:
    u = await db.get_user(tg_id)
    if not u:
        return await show_user(target, tg_id)
    eligible = await services.is_eligible(u)
    text = (
        (f"{note}\n\n" if note else "")
        + f"✏️ <b>Tahrirlash  ·  {html.escape(services.full_name(u))}</b>\n\n"
        f"<blockquote>👤 {html.escape(u['first_name'])} {html.escape(u['last_name'])}\n"
        f"📱 {html.escape(u['phone'])}\n"
        f"🎂 {_fmt_birth(u['birth_date'])}\n"
        f"🏫 {html.escape(u['study_place'] or '—')}\n"
        f"🎟 Ishtirok huquqi: {'✅ bor' if eligible else '🔒 yoʻq'}\n"
        f"🎙 Davomat: {await db.attendance_count(tg_id)}/{config.LESSONS_COUNT}</blockquote>\n\n"
        "Nimani oʻzgartiramiz? 👇"
    )
    await _show(target, text, [
        [("👤 Ism", f"ap:uef:{tg_id}:first_name"), ("👤 Familiya", f"ap:uef:{tg_id}:last_name")],
        [("📱 Telefon", f"ap:uef:{tg_id}:phone"), ("🎂 Tugʻilgan sana", f"ap:uef:{tg_id}:birth_date")],
        [("🏫 Oʻqish / ish joyi", f"ap:uef:{tg_id}:study_place")],
        [("🔒 Huquqni olish" if eligible else "🎟 Ishtirok huquqini berish", f"ap:uel:{tg_id}"),
         ("🎙 Davomat", f"ap:uea:{tg_id}")],
        [("◀️ Kartochka", f"ap:uv:{tg_id}")],
    ])


@router.callback_query(F.data.startswith("ap:ue:"))
async def cb_user_edit(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_user_edit(cb, int(cb.data.split(":")[2]))
    await cb.answer()


@router.callback_query(F.data.startswith("ap:uef:"))
async def cb_user_edit_field(cb: CallbackQuery, state: FSMContext):
    _, _, uid, field = cb.data.split(":", 3)
    uid = int(uid)
    u = await db.get_user(uid)
    if not u or field not in EDIT_FIELDS:
        return await cb.answer("Topilmadi", show_alert=True)
    icon, title, hint = EDIT_FIELDS[field]
    current = _fmt_birth(u[field]) if field == "birth_date" else (u[field] or "—")
    await _show(cb,
                f"{icon} <b>{title}</b>  ·  {html.escape(services.full_name(u))}\n\n"
                f"<blockquote>Hozir: <b>{html.escape(current)}</b></blockquote>\n\n"
                f"<i>{html.escape(hint)}</i>\n\n✍️ Yangi qiymatni yozib yuboring:",
                [[("✖️ Bekor qilish", f"ap:ue:{uid}")]])
    await state.set_state(AdminInput.waiting)
    await state.set_data({"action": "edit_user", "uid": uid, "field": field})
    await cb.answer()


@router.callback_query(F.data.startswith("ap:uel:"))
async def cb_user_toggle_eligible(cb: CallbackQuery):
    uid = int(cb.data.split(":")[2])
    u = await db.get_user(uid)
    if not u:
        return await cb.answer("Topilmadi", show_alert=True)
    if await services.is_eligible(u):
        refs = await db.referral_count(uid)
        if refs >= config.REQUIRED_REFERRALS or st.is_admin(uid):
            return await cb.answer(f"Olib boʻlmaydi: {'u admin' if st.is_admin(uid) else f'{refs} ta taklifi bor'} "
                                   f"— huquq avtomatik beriladi.", show_alert=True)
        await db.unset_eligible(uid)
        await cb.answer("🔒 Ishtirok huquqi olindi")
    else:
        await db.set_eligible(uid)
        await services.safe_send(cb.bot, uid, texts.ELIGIBLE_MANUAL.format(marathon=config.MARATHON_NAME))
        await cb.answer("🎟 Ishtirok huquqi berildi — ishtirokchiga xabar yuborildi")
    await show_user_edit(cb, uid)


async def show_user_attendance(target, tg_id: int) -> None:
    u = await db.get_user(tg_id)
    attended = await db.user_attendance(tg_id)
    lessons = await db.get_lessons()
    buttons = [(f"{'✅' if l['num'] in attended else '▫️'} {l['num']}-dars", f"ap:uat:{tg_id}:{l['num']}")
               for l in lessons]
    rows = [buttons[i:i + 3] for i in range(0, len(buttons), 3)]
    rows.append([("◀️ Tahrirlash", f"ap:ue:{tg_id}")])
    await _show(target,
                f"🎙 <b>Davomat  ·  {html.escape(services.full_name(u))}</b>\n\n"
                f"{texts.progress(len(attended), config.LESSONS_COUNT)}  "
                f"<b>{len([n for n in attended if n <= config.LESSONS_COUNT])}/{config.LESSONS_COUNT}</b>\n\n"
                "<i>Darsni bossangiz, davomat belgilanadi yoki olib tashlanadi "
                "(masalan, interneti uzilib kod yubora olmagan ishtirokchi uchun).</i>",
                rows)


@router.callback_query(F.data.startswith("ap:uea:"))
async def cb_user_attendance(cb: CallbackQuery):
    uid = int(cb.data.split(":")[2])
    if not await db.get_user(uid):
        return await cb.answer("Topilmadi", show_alert=True)
    await show_user_attendance(cb, uid)
    await cb.answer()


@router.callback_query(F.data.startswith("ap:uat:"))
async def cb_user_attendance_toggle(cb: CallbackQuery, bot: Bot):
    _, _, uid, num = cb.data.split(":")
    uid, num = int(uid), int(num)
    if not await db.get_user(uid):
        return await cb.answer("Topilmadi", show_alert=True)
    if num in await db.user_attendance(uid):
        await db.unmark_attendance(uid, num)
        await cb.answer(f"▫️ {num}-dars davomati olib tashlandi")
    else:
        await db.mark_attendance(uid, num)
        await cb.answer(f"✅ {num}-dars davomati belgilandi")
        if await services.check_final(bot, uid):  # barcha shartlar bajarilsa — sertifikat avtomatik
            await cb.message.answer("🏅 Ishtirokchi barcha shartlarni bajardi — yakuniy sertifikat yuborildi.")
    await show_user_attendance(cb, uid)


LIST_PAGE = 10
FILTER_NAMES = {"all": "Hammasi", "elig": "✅ Ishtirokchilar", "new": "🔒 Huquqsiz"}


async def show_user_list(target, filter_key: str = "all", page: int = 0) -> None:
    total = await db.count_users(filter_key)
    pages = max(1, -(-total // LIST_PAGE))
    page = max(0, min(page, pages - 1))
    rows_db = await db.list_users(filter_key, page * LIST_PAGE, LIST_PAGE)
    counts = {k: await db.count_users(k) for k in FILTER_NAMES}

    lines = [f"👥 <b>Ishtirokchilar roʻyxati</b>  ·  {FILTER_NAMES[filter_key]}: <b>{total}</b>",
             "<i>Eng yangilari tepada. Kartochkani ochish uchun ismni bosing.</i>\n"]
    if not rows_db:
        lines.append("Hozircha hech kim yoʻq.")
    for i, r in enumerate(rows_db, page * LIST_PAGE + 1):
        status = "✅" if r["eligible_at"] else "🔒"
        lines.append(f"<b>{i}.</b> {status} <b>{html.escape(services.full_name(r))}</b>\n"
                     f"      📱 {html.escape(r['phone'])}  ·  💌 {r['refs']}  ·  "
                     f"🎙 {r['att']}/{config.LESSONS_COUNT}  ·  🕒 {ha.local(r['registered_at'])}")

    buttons = [(f"{i}. {services.short_name(r)}", f"ap:uv:{r['tg_id']}")
               for i, r in enumerate(rows_db, page * LIST_PAGE + 1)]
    kb_rows = [buttons[i:i + 2] for i in range(0, len(buttons), 2)]
    if pages > 1:
        kb_rows.append([
            ("◀️", f"ap:ul:{filter_key}:{page - 1}") if page > 0 else ("·", "ap:noop"),
            (f"{page + 1} / {pages}", "ap:noop"),
            ("▶️", f"ap:ul:{filter_key}:{page + 1}") if page < pages - 1 else ("·", "ap:noop"),
        ])
    kb_rows.append([(("• " if k == filter_key else "") + f"{name} · {counts[k]}", f"ap:ul:{k}:0")
                    for k, name in FILTER_NAMES.items()])
    kb_rows.append([("🔎 Qidirish", "ap:us"), BACK])
    await _show(target, "\n".join(lines), kb_rows)


@router.callback_query(F.data == "ap:u")
async def cb_users(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await show_user_list(cb)
    await cb.answer()


@router.callback_query(F.data.startswith("ap:ul:"))
async def cb_user_list(cb: CallbackQuery, state: FSMContext):
    _, _, filter_key, page = cb.data.split(":")
    await state.clear()
    await show_user_list(cb, filter_key, int(page))
    await cb.answer()


@router.callback_query(F.data == "ap:noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()


@router.callback_query(F.data == "ap:us")
async def cb_users_search(cb: CallbackQuery, state: FSMContext):
    await _ask(cb, state,
               "🔎 <b>Ishtirokchini qidirish</b>\n\n"
               "Quyidagilardan birini yozing:\n"
               "<blockquote>Telegram ID — <code>123456789</code>\n"
               "Username — <code>@malika</code>\n"
               "Telefon — <code>+998901234567</code></blockquote>",
               [[("📋 Roʻyxatga qaytish", "ap:u")]],
               action="find_user")
    await cb.answer()


@router.callback_query(F.data.startswith("ap:uv:"))
async def cb_user_view(cb: CallbackQuery):
    await show_user(cb, int(cb.data.split(":")[2]))
    await cb.answer()


@router.callback_query(F.data.startswith("ap:ud:"))
async def cb_user_delete_ask(cb: CallbackQuery):
    uid = int(cb.data.split(":")[2])
    u = await db.get_user(uid)
    if not u:
        await cb.answer("Allaqachon oʻchirilgan", show_alert=True)
        return await show_user(cb, uid)
    att = await db.attendance_count(uid)
    refs = await db.referral_count(uid)
    await _show(cb,
                f"⚠️ <b>Ishtirokchini oʻchirasizmi?</b>\n\n"
                f"👤 <b>{html.escape(services.full_name(u))}</b>  ·  🆔 <code>{uid}</code>\n\n"
                f"<blockquote>Quyidagilar butunlay oʻchadi:\n"
                f"• roʻyxatdan oʻtish maʼlumotlari\n"
                f"• davomat ({att} ta dars)\n"
                f"• kurs va yakuniy sertifikatlari</blockquote>\n\n"
                f"<i>💌 U taklif qilgan {refs} ta doʻst oʻchmaydi. Uni taklif qilgan odamning "
                f"takliflar soni 1 taga kamayadi.\n"
                f"Bu amalni qaytarib boʻlmaydi. Ishtirokchi xohlasa, /start orqali qaytadan roʻyxatdan oʻtadi.</i>",
                [[("🗑 Ha, oʻchirish", f"ap:udy:{uid}"), ("✖️ Yoʻq", f"ap:uv:{uid}")]])
    await cb.answer()


@router.callback_query(F.data.startswith("ap:udy:"))
async def cb_user_delete(cb: CallbackQuery):
    uid = int(cb.data.split(":")[2])
    u = await db.get_user(uid)
    name = html.escape(services.full_name(u)) if u else str(uid)
    if not await db.delete_user(uid):
        await cb.answer("Allaqachon oʻchirilgan", show_alert=True)
    else:
        await cb.answer("Oʻchirildi")
    await _show(cb, f"🗑 <b>{name}</b> oʻchirildi.", [[("📋 Roʻyxat", "ap:u"), ("🔎 Qidirish", "ap:us")], [BACK]])


# ================================================================ adminlar
async def show_admins(target, bot: Bot) -> None:
    lines = ["👮 <b>Adminlar</b>\n"]
    for uid in sorted(st.all_admins()):
        u = await db.get_user(uid)
        if not u:
            name = "<i>faqat admin, ishtirokchi emas</i>"
        else:
            name = f"<b>{html.escape(services.full_name(u))}</b>" + ("  <i>(faqat admin)</i>" if u["auto_admin"] else "")
        tag = "  ·  ⭐️ asosiy" if uid in config.ADMIN_IDS else ""
        lines.append(f"👤 {name}{tag}\n      🆔 <code>{uid}</code>")
    group = st.display("ADMIN_CHAT_ID")
    lines.append(f"\n👥 Tekshiruv guruhi: <b>{html.escape(group)}</b>")
    lines.append("\n💡 <i>Yangi admin ID raqamini botga /myid yozib biladi. "
                 "Panelga kirish uchun parolni unga shaxsan ayting.</i>")
    await _show(target, "\n".join(lines), [
        [("➕ Qoʻshish", "ap:aa"), ("➖ Oʻchirish", "ap:ar")],
        [("🔑 Parolni oʻzgartirish", "ap:pw")],
        [("👥 Tekshiruv guruhi", "ap:e:ADMIN_CHAT_ID")],
        [BACK],
    ])


@router.callback_query(F.data == "ap:admins")
async def cb_admins(cb: CallbackQuery, state: FSMContext, bot: Bot):
    await state.clear()
    await show_admins(cb, bot)
    await cb.answer()


@router.callback_query(F.data.in_({"ap:aa", "ap:ar"}))
async def cb_admin_edit(cb: CallbackQuery, state: FSMContext):
    adding = cb.data == "ap:aa"
    await _ask(cb, state,
               ("➕ <b>Yangi admin</b>\n\nTelegram ID raqamini yozing:\n"
                "<i>💡 U botga /myid yozib bilib oladi.</i>"
                if adding else "➖ <b>Adminni oʻchirish</b>\n\nID raqamini yozing:"),
               action="admin_add" if adding else "admin_remove")
    await cb.answer()


async def _validate_user_field(uid: int, field: str, text: str) -> tuple[str | None, str | None]:
    """(qiymat, xato) — roʻyxatdan oʻtishdagi qoidalar bilan bir xil."""
    import re
    from datetime import datetime as _dt

    import handlers_user as hu

    if field in ("first_name", "last_name"):
        name = hu._clean(text)
        if not (2 <= len(name) <= 40) or not hu.NAME_RE.match(name):
            return None, "Faqat harflardan foydalaning (2–40 belgi)."
        return name, None
    if field == "phone":
        raw = re.sub(r"[\s\-()]", "", text)
        if not hu.PHONE_RE.match(raw):
            return None, "Raqam notoʻgʻri. Masalan: +998901234567"
        digits = re.sub(r"\D", "", raw)
        if len(digits) == 9:
            digits = "998" + digits
        phone = "+" + digits
        if await db.phone_taken(phone, uid):
            return None, "Bu raqam bilan boshqa ishtirokchi roʻyxatdan oʻtgan."
        return phone, None
    if field == "birth_date":
        raw = text.strip().replace("/", ".").replace("-", ".").replace(",", ".")
        try:
            born = _dt.strptime(raw, "%d.%m.%Y").date()
        except ValueError:
            return None, "Sana notoʻgʻri. Masalan: 15.03.2008"
        if not hu._age_ok(born):
            return None, f"Yosh {config.MIN_AGE}–{config.MAX_AGE} oraligʻida boʻlishi kerak."
        return born.isoformat(), None
    if field == "study_place":
        study = " ".join(text.split())
        if not (5 <= len(study) <= 200):
            return None, "Aniq manzili bilan yozing (5–200 belgi)."
        return study, None
    return None, "Bu maydonni oʻzgartirib boʻlmaydi."


# ================================================================ kiritilgan qiymatlarni qabul qilish
@router.message(AdminInput.waiting, ~F.text.in_(texts.MENU_BUTTONS))
async def on_input(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    action = data.get("action")
    if m.text and m.text.startswith("/"):
        await state.clear()
        return await m.answer("Bekor qilindi.")

    if action == "template":
        if m.photo:
            file = m.photo[-1]
        elif m.document and (m.document.mime_type or "").startswith("image/"):
            file = m.document
        else:
            return await m.answer("⚠️ Rasm (PNG/JPG) yuboring.")
        buf = io.BytesIO()
        await bot.download(file, destination=buf)
        try:
            w, h = await certificate.save_template(buf.getvalue())
        except Exception:  # noqa: BLE001
            return await m.answer("⚠️ Rasmni ochib boʻlmadi. Boshqa fayl yuboring.")
        await state.clear()
        await m.answer(f"✅ Shablon saqlandi ({w}×{h}). Namunani tekshiring 👇")
        await _send_preview(m)
        return await show_cert(m)

    if action == "broadcast":
        await state.update_data(src=[m.chat.id, m.message_id])
        total = len(await db.all_user_ids())
        elig = len(await db.all_user_ids(only_eligible=True))
        return await _show(m, "📢 <b>Kimlarga yuboramiz?</b>", [
            [(f"👥 Hammaga ({total})", "ap:bca:all")],
            [(f"🎟 Faqat ishtirokchilarga ({elig})", "ap:bca:elig")],
            [CANCEL],
        ])

    if not m.text:
        return await m.answer("⚠️ Iltimos, matn koʻrinishida yozing.")
    text = m.text.strip()

    if action == "set":
        key = data["key"]
        f = st.FIELDS[key]
        try:
            value = st.parse(f, text)
        except ValueError as e:
            return await m.answer(f"⚠️ {html.escape(str(e))}\nQayta yozing yoki bekor qiling.")
        if f.kind == "channels" and value:
            checked, errors = [], []
            for line in value:
                saved, error = await subscription.validate_channel(bot, line)
                (errors.append(error) if error else checked.append(saved))
            if errors:
                return await m.answer("⚠️ " + "\n\n⚠️ ".join(errors) + "\n\nToʻgʻrilab, qayta yuboring yoki bekor qiling.")
            value = checked
        await st.set_value(key, value)
        await state.clear()
        await m.answer(f"✅ <b>{f.title}</b> saqlandi\n<blockquote>{html.escape(st.display(key))}</blockquote>")
        if key.startswith("CERT_") or key in ("ORGANIZER", "CLUB_LINK"):
            return await show_cert(m)
        if key in ("COURSES", "PLATFORM_LINK", "PLATFORM_NAME"):
            return await show_homework(m)
        if key in ("LESSONS_COUNT", "DEFAULT_CODE_MINUTES"):
            return await show_lessons(m)
        if key == "ADMIN_CHAT_ID":
            return await show_admins(m, bot)
        return await show_settings(m)

    if action == "edit_user":
        uid, field = data["uid"], data["field"]
        if not await db.get_user(uid):
            await state.clear()
            return await show_user(m, uid)
        value, error = await _validate_user_field(uid, field, text)
        if error:
            return await m.answer(f"⚠️ {error}\nQayta yozing yoki bekor qiling.")
        await db.update_user_field(uid, field, value)
        await state.clear()
        return await show_user_edit(m, uid, note=f"✅ <b>{EDIT_FIELDS[field][1]}</b> saqlandi")

    if action == "find_user":
        u = await db.find_user(text)
        if not u:
            return await m.answer("🔎 Topilmadi. ID, @username yoki telefonni tekshirib, qayta yozing:")
        await state.clear()
        return await show_user(m, u["tg_id"])

    if action == "lesson_title":
        await db.set_lesson_title(data["num"], " ".join(text.split())[:100])
        await state.clear()
        return await show_lesson(m, data["num"])

    if action == "lesson_code":
        parts = text.split()
        minutes = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else None
        await state.clear()
        await ha.open_lesson_now(bot, m.chat.id, data["num"], minutes, parts[0][:30])
        return await show_lesson(m, data["num"])

    if action in ("admin_add", "admin_remove"):
        if not text.lstrip("-").isdigit():
            return await m.answer("⚠️ ID faqat raqamlardan iborat boʻladi. Qayta yozing.")
        uid = int(text)
        extra = list(config.EXTRA_ADMINS)
        if action == "admin_add":
            if uid not in extra and uid not in config.ADMIN_IDS:
                extra.append(uid)
            await st.set_value("EXTRA_ADMINS", extra)
            await services.set_admin_commands(bot)
            await services.safe_send(bot, uid, "👮 Sizga admin huquqi berildi. Panel: /admin\n"
                                               "Kirish parolini sizni qoʻshgan admindan soʻrang.")
        else:
            if uid in config.ADMIN_IDS:
                return await m.answer("⚠️ Asosiy adminni faqat .env faylidan oʻchirish mumkin.")
            await st.set_value("EXTRA_ADMINS", [x for x in extra if x != uid])
            await admin_auth.logout(uid)
        await state.clear()
        return await show_admins(m, bot)

    await state.clear()
    await show_main(m)
