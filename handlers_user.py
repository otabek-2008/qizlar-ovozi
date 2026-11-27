"""Ishtirokchilar uchun handlerlar: ro'yxatdan o'tish, referal, davomat, kurs sertifikatlari."""
import html
import re
from datetime import date, datetime

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

import config
import db
import keyboards as kb
import services
import settings_store
import subscription
import texts

router = Router(name="user")


class Reg(StatesGroup):
    first_name = State()
    last_name = State()
    phone = State()
    birth_date = State()
    study = State()


    subscribe = State()  # oxirgi qadam: majburiy kanallarga obuna


def _step(n: int, text: str) -> str:
    """Qadam sarlavhasi: kanallar boʻlsa 6 ta qadam, boʻlmasa 5 ta."""
    return texts.step(n, text, total=6 if config.REQUIRED_CHANNELS else 5)


class Flow(StatesGroup):
    code = State()
    course_file = State()


NAME_RE = re.compile(r"^[^\W\d_]+(?:[ '\-ʻʼ’‘`][^\W\d_]+)*$")
PHONE_RE = re.compile(r"^\+?\d{9,15}$")


def _clean(text: str) -> str:
    text = " ".join(text.split())
    return text[:1].upper() + text[1:]


async def _profile(user):
    """Foydalanuvchi profili. Admin roʻyxatdan oʻtmagan boʻlsa — Telegram ismi bilan avtomatik ochiladi."""
    u = await db.get_user(user.id)
    if not u and settings_store.is_admin(user.id):
        u = await db.ensure_admin_profile(user.id, user.username, user.first_name or "Admin", user.last_name or "")
    return u


async def _registered(m: Message):
    u = await _profile(m.from_user)
    if not u:
        await m.answer(texts.NOT_REGISTERED, reply_markup=ReplyKeyboardRemove())
    return u


async def _need_refs_text(tg_id: int) -> str:
    count = await db.referral_count(tg_id)
    return texts.NEED_REFERRALS.format(need=config.REQUIRED_REFERRALS, count=count,
                                       bar=texts.progress(count, config.REQUIRED_REFERRALS))


def _ref_info(link: str, count: int) -> str:
    need = config.REQUIRED_REFERRALS
    return texts.REF_INFO.format(link=link, need=need, count=count, bar=texts.progress(count, need))


@router.message(Command("myid"))
async def cmd_myid(m: Message):
    await m.answer(f"🆔 Sizning Telegram ID raqamingiz:\n<code>{m.from_user.id}</code>\n"
                   f"<i>Ustiga bossangiz, nusxalanadi.</i>")


# ================================================================ /start va ro'yxatdan o'tish
@router.message(CommandStart())
async def cmd_start(m: Message, command: CommandObject, state: FSMContext):
    await state.clear()
    u = await db.get_user(m.from_user.id)
    if settings_store.is_admin(m.from_user.id) and (not u or u["auto_admin"]):
        await m.answer(texts.ADMIN_WELCOME, reply_markup=kb.main_menu(m.from_user.id))
        return
    if u:
        await m.answer(texts.ALREADY_REGISTERED.format(name=html.escape(u["first_name"])), reply_markup=kb.main_menu(m.from_user.id))
        return

    ref = None
    arg = command.args or ""
    if arg.startswith("ref") and arg[3:].isdigit():
        ref = int(arg[3:])
        if ref == m.from_user.id or not await db.get_user(ref):
            ref = None
    await _begin_registration(m, state, ref)


@router.message(Command("register"))
async def cmd_register(m: Message, state: FSMContext):
    """Admin ixtiyoriy ravishda ishtirokchi sifatida ham roʻyxatdan oʻtishi mumkin."""
    await state.clear()
    u = await db.get_user(m.from_user.id)
    if u and not u["auto_admin"]:
        return await m.answer(texts.ALREADY_REGISTERED.format(name=html.escape(u["first_name"])),
                              reply_markup=kb.main_menu(m.from_user.id))
    await _begin_registration(m, state, None)


async def _begin_registration(m: Message, state: FSMContext, ref: int | None) -> None:
    await state.update_data(ref=ref)
    await m.answer(texts.WELCOME.format(marathon=config.MARATHON_NAME, lessons=config.LESSONS_COUNT),
                   reply_markup=ReplyKeyboardRemove())
    await m.answer(_step(1, texts.ASK_FIRST_NAME))
    await state.set_state(Reg.first_name)


@router.message(Reg.first_name, F.text)
async def reg_first_name(m: Message, state: FSMContext):
    name = _clean(m.text)
    if not (2 <= len(name) <= 40) or not NAME_RE.match(name):
        return await m.answer(texts.BAD_NAME)
    await state.update_data(first_name=name)
    await state.set_state(Reg.last_name)
    await m.answer(_step(2, texts.ASK_LAST_NAME))


@router.message(Reg.last_name, F.text)
async def reg_last_name(m: Message, state: FSMContext):
    name = _clean(m.text)
    if not (2 <= len(name) <= 40) or not NAME_RE.match(name):
        return await m.answer(texts.BAD_NAME)
    await state.update_data(last_name=name)
    await state.set_state(Reg.phone)
    await m.answer(_step(3, texts.ASK_PHONE), reply_markup=kb.phone_kb())


async def _save_phone(m: Message, state: FSMContext, raw: str):
    digits = re.sub(r"\D", "", raw)
    if len(digits) == 9:  # 901234567 -> 998901234567
        digits = "998" + digits
    phone = "+" + digits
    if await db.phone_taken(phone, m.from_user.id):
        return await m.answer(texts.PHONE_TAKEN, reply_markup=kb.phone_kb())
    await state.update_data(phone=phone)
    await state.set_state(Reg.birth_date)
    # telefon tugmasini yopamiz, keyin sana tanlash tugmalarini chiqaramiz
    await m.answer(texts.PHONE_OK.format(phone=phone), reply_markup=ReplyKeyboardRemove())
    await m.answer(_step(4, texts.ASK_BIRTH), reply_markup=kb.birth_years_kb(0))


@router.message(Reg.phone, F.contact)
async def reg_phone_contact(m: Message, state: FSMContext):
    if m.contact.user_id and m.contact.user_id != m.from_user.id:
        return await m.answer(texts.OWN_PHONE_ONLY, reply_markup=kb.phone_kb())
    await _save_phone(m, state, m.contact.phone_number)


@router.message(Reg.phone, F.text)
async def reg_phone_text(m: Message, state: FSMContext):
    raw = re.sub(r"[\s\-()]", "", m.text)
    if not PHONE_RE.match(raw):
        return await m.answer(texts.BAD_PHONE, reply_markup=kb.phone_kb())
    await _save_phone(m, state, raw)


@router.message(Reg.birth_date, F.text)
async def reg_birth(m: Message, state: FSMContext):
    raw = m.text.strip().replace("/", ".").replace("-", ".").replace(",", ".")
    try:
        born = datetime.strptime(raw, "%d.%m.%Y").date()
    except ValueError:
        return await m.answer(texts.BAD_BIRTH, reply_markup=kb.birth_years_kb(0))
    if not _age_ok(born):
        return await m.answer(texts.BAD_AGE, reply_markup=kb.birth_years_kb(0))
    await _save_birth(m, state, born)


def _age_ok(born: date) -> bool:
    today = date.today()
    age = today.year - born.year - ((today.month, today.day) < (born.month, born.day))
    return config.MIN_AGE <= age <= config.MAX_AGE


async def _save_birth(m: Message, state: FSMContext, born: date) -> None:
    await state.update_data(birth_date=born.isoformat())
    await state.set_state(Reg.study)
    await m.answer(_step(5, texts.ASK_STUDY))


@router.callback_query(Reg.birth_date, F.data.startswith("bd:"))
async def cb_birth(cb: CallbackQuery, state: FSMContext):
    p = cb.data.split(":")
    kind = p[1]
    try:
        if kind == "y":  # yillar sahifasi
            await cb.message.edit_text(_step(4, texts.ASK_BIRTH), reply_markup=kb.birth_years_kb(int(p[2])))
        elif kind == "Y":  # yil tanlandi -> oylar
            year = int(p[2])
            await cb.message.edit_text(_step(4, texts.BIRTH_MONTH.format(year=year)),
                                       reply_markup=kb.birth_months_kb(year))
        elif kind == "M":  # oy tanlandi -> kunlar
            year, month = int(p[2]), int(p[3])
            await cb.message.edit_text(
                _step(4, texts.BIRTH_DAY.format(month=texts.MONTHS[month - 1], year=year)),
                reply_markup=kb.birth_days_kb(year, month))
        elif kind == "D":  # kun tanlandi -> tayyor
            born = date(int(p[2]), int(p[3]), int(p[4]))
            if not _age_ok(born):
                return await cb.answer(texts.BAD_AGE.replace("⚠️ ", ""), show_alert=True)
            await cb.message.edit_text(texts.BIRTH_DONE.format(date=born.strftime("%d.%m.%Y")))
            await _save_birth(cb.message, state, born)
    except TelegramBadRequest:
        pass  # "message is not modified" — tugma ikki marta bosilgan
    await cb.answer()


@router.callback_query(F.data.startswith("bd:"))
async def cb_birth_expired(cb: CallbackQuery):
    await cb.answer(texts.BIRTH_EXPIRED, show_alert=True)


@router.message(Reg.study, F.text)
async def reg_study(m: Message, state: FSMContext, bot: Bot):
    study = " ".join(m.text.split())
    if not (5 <= len(study) <= 200):
        return await m.answer(texts.BAD_STUDY)
    await state.update_data(study=study)
    # oxirgi shart — homiylarga (reklama) obuna
    items = await subscription.prompt_items(bot, m.from_user.id)
    if not items:
        return await _finish_registration(m, state, bot, m.from_user)
    await state.set_state(Reg.subscribe)
    await m.answer(_step(6, subscription.prompt_text(items)), reply_markup=subscription.prompt_kb(items),
                   disable_web_page_preview=True)


async def _finish_registration(m: Message, state: FSMContext, bot: Bot, user) -> None:
    """Barcha qadamlar (va obuna) bajarilgach — ishtirokchini bazaga yozadi."""
    data = await state.get_data()
    await state.clear()
    if "phone" not in data or "study" not in data:
        await m.answer(texts.NOT_REGISTERED)
        return

    await db.delete_auto_admin(user.id)  # admin profili haqiqiy maʼlumot bilan almashadi
    created = await db.add_user(
        user.id, user.username, data["first_name"], data["last_name"],
        data["phone"], data["birth_date"], data["study"], data.get("ref"),
    )
    if not created:
        await m.answer(texts.ALREADY_REGISTERED.format(name=html.escape(data["first_name"])),
                       reply_markup=kb.main_menu(user.id))
        return

    link = await services.referral_link(bot, user.id)
    await m.answer(texts.REGISTERED.format(name=html.escape(data["first_name"])), reply_markup=kb.main_menu(user.id))
    await m.answer(_ref_info(link, 0), reply_markup=kb.share_kb(link), disable_web_page_preview=True)
    if data.get("ref"):
        await services.on_new_referral(bot, data["ref"], f"{data['first_name']} {data['last_name']}")


@router.callback_query(F.data == "sub:check")
async def cb_sub_check(cb: CallbackQuery, state: FSMContext, bot: Bot):
    subscription.forget(cb.from_user.id)
    missing = await subscription.missing_channels(bot, cb.from_user.id)
    if missing:
        return await cb.answer(texts.SUB_STILL.format(channels=", ".join(c.title for c in missing)),
                               show_alert=True)
    await cb.answer("✅")
    try:
        await cb.message.edit_text(texts.SUB_OK)
    except TelegramBadRequest:
        pass
    if await state.get_state() == Reg.subscribe.state:
        return await _finish_registration(cb.message, state, bot, cb.from_user)
    if await db.get_user(cb.from_user.id):
        await cb.message.answer(texts.USE_MENU, reply_markup=kb.main_menu(cb.from_user.id))
    else:
        await cb.message.answer(texts.NOT_REGISTERED)


@router.message(Reg.subscribe)
async def reg_subscribe_wait(m: Message, state: FSMContext, bot: Bot):
    subscription.forget(m.from_user.id)
    missing = await subscription.missing_channels(bot, m.from_user.id)
    if not missing:
        return await _finish_registration(m, state, bot, m.from_user)
    items = await subscription.prompt_items(bot, m.from_user.id)
    await m.answer(_step(6, subscription.prompt_text(items)), reply_markup=subscription.prompt_kb(items),
                   disable_web_page_preview=True)


@router.message(StateFilter(Reg.first_name, Reg.last_name, Reg.birth_date, Reg.study))
async def reg_not_text(m: Message):
    await m.answer(texts.TEXT_ONLY)


@router.message(Reg.phone)
async def reg_phone_other(m: Message):
    await m.answer(texts.BAD_PHONE, reply_markup=kb.phone_kb())


# ================================================================ menyu tugmalari (istalgan holatda ishlaydi)
@router.message(F.text == texts.BTN_REF)
async def menu_ref(m: Message, state: FSMContext, bot: Bot):
    await state.clear()
    if not (u := await _registered(m)):
        return
    link = await services.referral_link(bot, u["tg_id"])
    count = await db.referral_count(u["tg_id"])
    await m.answer(_ref_info(link, count), reply_markup=kb.share_kb(link), disable_web_page_preview=True)


@router.message(F.text == texts.BTN_TOP)
async def menu_top(m: Message, state: FSMContext):
    await state.clear()
    if not (u := await _registered(m)):
        return
    rows = await db.top_referrers(10)
    if not rows:
        return await m.answer(texts.TOP_EMPTY)
    lines = [texts.TOP_TITLE]
    for i, r in enumerate(rows, 1):
        lines.append(texts.TOP_ROW.format(place=texts.place(i), name=html.escape(services.short_name(r)),
                                          cnt=r["cnt"]))
    rank = await db.user_rank(u["tg_id"])
    if rank:
        lines.append(texts.TOP_ME.format(rank=rank, cnt=await db.referral_count(u["tg_id"])))
    else:
        lines.append(texts.TOP_ME_NONE)
    await m.answer("\n".join(lines))


@router.message(F.text == texts.BTN_ME)
async def menu_me(m: Message, state: FSMContext):
    await state.clear()
    if not (u := await _registered(m)):
        return
    uid = u["tg_id"]
    refs = await db.referral_count(uid)
    eligible = await services.is_eligible(u)
    attended = await db.user_attendance(uid)
    statuses = await db.course_status(uid)
    final = await db.get_final(uid)
    rank = await db.user_rank(uid)

    lessons = await db.get_lessons()
    lesson_lines = "\n".join(
        f"{'✅' if l['num'] in attended else '▫️'} {l['num']}-dars"
        + (f"  ·  {html.escape(l['title'])}" if l["title"] and l["title"] != f"{l['num']}-dars" else "")
        for l in lessons
    ) or "—"
    def _course_line(i: int, name: str) -> str:
        icon, label = texts.STATUS_NAMES.get(statuses.get(i), texts.NOT_SENT).split(" ", 1)
        return f"{icon} {html.escape(name)}  ·  <i>{label}</i>"

    course_lines = "\n".join(_course_line(i, n) for i, n in enumerate(config.COURSES)) or "—"
    await m.answer(texts.ME.format(
        name=html.escape(services.full_name(u)),
        refs=f"{refs}/{config.REQUIRED_REFERRALS}" if refs < config.REQUIRED_REFERRALS else f"{refs} ta",
        ref_bar=texts.progress(refs, config.REQUIRED_REFERRALS),
        eligible=texts.ME_ELIGIBLE if eligible else "",
        rank=rank or "—",
        att=len([n for n in attended if n <= config.LESSONS_COUNT]), total=config.LESSONS_COUNT,
        lessons=lesson_lines,
        done=sum(1 for i in range(len(config.COURSES)) if statuses.get(i) == "approved"),
        courses_total=len(config.COURSES),
        courses=course_lines,
        final=f"✅ berilgan  ·  <code>QO-{final['id']:05d}</code>" if final else "⏳ hali berilmagan",
    ))


@router.message(F.text == texts.BTN_CODE)
async def menu_code(m: Message, state: FSMContext):
    await state.clear()
    if not (u := await _registered(m)):
        return
    if config.REQUIRE_REFERRALS_TO_ATTEND and not await services.is_eligible(u):
        return await m.answer(await _need_refs_text(u["tg_id"]))
    if not await db.open_lessons():
        return await m.answer(texts.NO_OPEN_LESSON)
    await state.set_state(Flow.code)
    await m.answer(texts.ASK_CODE, reply_markup=kb.cancel_kb())


@router.message(F.text == texts.BTN_CERT)
async def menu_cert(m: Message, state: FSMContext):
    await state.clear()
    if not (u := await _registered(m)):
        return
    if config.REQUIRE_REFERRALS_TO_ATTEND and not await services.is_eligible(u):
        return await m.answer(await _need_refs_text(u["tg_id"]))
    if await db.get_setting("homework_open") != "1":
        return await m.answer(texts.HOMEWORK_CLOSED)
    statuses = await db.course_status(u["tg_id"])
    available = [(i, c) for i, c in enumerate(config.COURSES) if statuses.get(i) not in ("approved", "pending")]
    if not available:
        return await m.answer(texts.ALL_COURSES_SENT)
    await m.answer(texts.CHOOSE_COURSE.format(start=services.fmt_date(config.MARATHON_START)),
                   reply_markup=kb.courses_kb(available))


@router.callback_query(F.data == "cancel")
async def cb_cancel(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await cb.message.edit_text(texts.CANCELLED)
    except Exception:
        pass
    await cb.answer()


# ================================================================ davomat kodi
async def _handle_code_result(m: Message, bot: Bot, status: str, lesson) -> None:
    if status == "ok":
        await m.answer(await services.after_attendance(bot, m.from_user.id, lesson["num"]),
                       reply_markup=kb.main_menu(m.from_user.id))
        await services.check_final(bot, m.from_user.id)
    elif status == "already":
        await m.answer(texts.CODE_ALREADY.format(num=lesson["num"]), reply_markup=kb.main_menu(m.from_user.id))
    elif status == "closed":
        await m.answer(texts.CODE_CLOSED, reply_markup=kb.main_menu(m.from_user.id))


@router.message(Flow.code, F.text)
async def got_code(m: Message, state: FSMContext, bot: Bot):
    status, lesson = await services.try_code(m.from_user.id, m.text)
    if status == "wrong":
        return await m.answer(texts.CODE_WRONG, reply_markup=kb.cancel_kb())
    await state.clear()
    await _handle_code_result(m, bot, status, lesson)


# ================================================================ kurs sertifikatini yuborish
@router.callback_query(F.data.startswith("course:"))
async def cb_course(cb: CallbackQuery, state: FSMContext):
    idx = int(cb.data.split(":")[1])
    if not (0 <= idx < len(config.COURSES)) or not await _profile(cb.from_user):
        return await cb.answer()
    status = (await db.course_status(cb.from_user.id)).get(idx)
    if status in ("approved", "pending"):
        return await cb.answer(texts.CERT_ALREADY.format(status=texts.STATUS_NAMES[status]), show_alert=True)
    await state.set_state(Flow.course_file)
    await state.update_data(course_idx=idx)
    await cb.message.edit_text(texts.SEND_CERT_FILE.format(course=html.escape(config.COURSES[idx])),
                               reply_markup=kb.cancel_kb())
    await cb.answer()


@router.message(Flow.course_file, F.photo | F.document)
async def got_cert_file(m: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    idx = data.get("course_idx")
    if idx is None:
        await state.clear()
        return await m.answer(texts.USE_MENU, reply_markup=kb.main_menu(m.from_user.id))

    if m.photo:
        file, ftype = m.photo[-1], "photo"
    else:
        mime = m.document.mime_type or ""
        if not (mime.startswith("image/") or mime == "application/pdf"):
            return await m.answer(texts.BAD_CERT_FILE)
        file, ftype = m.document, "document"

    status = (await db.course_status(m.from_user.id)).get(idx)
    if status in ("approved", "pending"):
        await state.clear()
        return await m.answer(texts.CERT_ALREADY.format(status=texts.STATUS_NAMES[status]),
                              reply_markup=kb.main_menu(m.from_user.id))
    if await db.file_used(file.file_unique_id):
        return await m.answer(texts.CERT_DUPLICATE)

    cert_id = await db.add_course_cert(m.from_user.id, idx, file.file_id, file.file_unique_id, ftype)
    await state.clear()
    await m.answer(texts.CERT_RECEIVED, reply_markup=kb.main_menu(m.from_user.id))
    await services.send_cert_to_admins(bot, cert_id)


@router.message(Flow.course_file)
async def cert_file_bad(m: Message):
    await m.answer(texts.BAD_CERT_FILE)


# ================================================================ boshqa matnlar
@router.message(StateFilter(None), F.text)
async def fallback_text(m: Message, bot: Bot):
    if m.text.startswith("/"):
        return
    u = await _profile(m.from_user)
    if not u:
        return await m.answer(texts.NOT_REGISTERED)
    # Kod "✅ Davomat kodi" tugmasisiz to'g'ridan-to'g'ri yozilgan bo'lishi mumkin
    if await db.open_lessons():
        if config.REQUIRE_REFERRALS_TO_ATTEND and not await services.is_eligible(u):
            return await m.answer(await _need_refs_text(u["tg_id"]))
        status, lesson = await services.try_code(u["tg_id"], m.text)
        if status != "wrong":
            return await _handle_code_result(m, bot, status, lesson)
        return await m.answer(texts.CODE_WRONG, reply_markup=kb.main_menu(m.from_user.id))
    await m.answer(texts.USE_MENU, reply_markup=kb.main_menu(m.from_user.id))
