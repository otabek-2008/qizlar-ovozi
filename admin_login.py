"""Admin panelga parol bilan kirish, parol oʻrnatish va oʻzgartirish."""
import hashlib

from aiogram import Bot, F, Router
from aiogram.exceptions import TelegramAPIError
from aiogram.filters import BaseFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

import admin_auth as auth
import settings_store
import texts


class IsAdminId(BaseFilter):
    """Faqat ID boʻyicha admin (parol hali kiritilmagan boʻlishi mumkin)."""
    async def __call__(self, event) -> bool:
        return bool(event.from_user) and settings_store.is_admin(event.from_user.id)


class NotLoggedIn(BaseFilter):
    async def __call__(self, event) -> bool:
        return not auth.logged_in(event.from_user.id)


class Pw(StatesGroup):
    enter = State()      # kirish uchun parol
    current = State()    # o'zgartirishdan oldin joriy parol
    new1 = State()       # yangi parol
    new2 = State()       # yangi parolni takrorlash


router = Router(name="admin_login")
router.message.filter(IsAdminId())
router.callback_query.filter(IsAdminId())

ADMIN_COMMANDS = ["stats", "top", "export", "user", "lessons", "lesson_title", "open_lesson", "close_lesson",
                  "homework_on", "homework_off", "pending", "check_all", "set_review_group", "issue_cert",
                  "eligible", "broadcast", "help_admin"]
LOCKED = "🔒 Avval /admin orqali parolni kiriting."
NOT_PASSWORD = texts.MENU_BUTTONS | {texts.BTN_ADMIN}


async def _delete(m: Message) -> None:
    try:
        await m.delete()  # parol chatda qolmasin
    except TelegramAPIError:
        pass


async def _open_panel(m: Message) -> None:
    import admin_panel  # aylanma importning oldini olish uchun
    await admin_panel.show_main(m)


@router.message(Command("admin"))
@router.message(F.text == texts.BTN_ADMIN)
async def cmd_admin(m: Message, state: FSMContext):
    await state.clear()
    if m.chat.type != "private":
        return await m.answer("🔐 Admin panelni bot bilan <b>shaxsiy chatda</b> oching.")
    if auth.logged_in(m.from_user.id):
        return await _open_panel(m)
    if mins := auth.locked_minutes(m.from_user.id):
        return await m.answer(f"⛔️ Koʻp marta notoʻgʻri parol kiritildi. {mins} daqiqadan keyin urinib koʻring.")
    if not await auth.has_password():
        await state.set_state(Pw.new1)
        await state.update_data(mode="create")
        return await m.answer(
            "🔐 <b>Admin panel paroli hali oʻrnatilmagan.</b>\n\n"
            f"Yangi parol oʻylab toping (kamida {auth.MIN_LENGTH} belgi) va yuboring.\n"
            "Bu parolni faqat adminlarga ayting."
        )
    await state.set_state(Pw.enter)
    await m.answer("🔐 <b>Admin panel</b>\nParolni kiriting:\n<i>Xabaringiz darhol oʻchiriladi.</i>")


@router.message(Pw.enter, F.text, ~F.text.in_(NOT_PASSWORD))
async def pw_enter(m: Message, state: FSMContext):
    await _delete(m)
    uid = m.from_user.id
    if mins := auth.locked_minutes(uid):
        await state.clear()
        return await m.answer(f"⛔️ Bloklangan. {mins} daqiqadan keyin urinib koʻring.")
    if await auth.check_password(m.text):
        await state.clear()
        await auth.login(uid)
        await m.answer(f"🔓 <b>Xush kelibsiz!</b>\n<i>Panel {auth.SESSION_HOURS} soat davomida ochiq turadi.</i>")
        return await _open_panel(m)
    left = auth.register_fail(uid)
    if left == 0:
        await state.clear()
        return await m.answer(f"⛔️ Parol {auth.MAX_FAILS} marta notoʻgʻri kiritildi. "
                              f"{auth.LOCK_MINUTES} daqiqaga bloklandi.")
    await m.answer(f"❌ Parol notoʻgʻri. Yana {left} ta urinish qoldi.")


@router.message(Pw.current, F.text, ~F.text.in_(NOT_PASSWORD))
async def pw_current(m: Message, state: FSMContext):
    await _delete(m)
    if not await auth.check_password(m.text):
        left = auth.register_fail(m.from_user.id)
        if left == 0:
            await state.clear()
            await auth.logout(m.from_user.id)
            return await m.answer(f"⛔️ {auth.LOCK_MINUTES} daqiqaga bloklandi.")
        return await m.answer(f"❌ Joriy parol notoʻgʻri. Yana {left} ta urinish qoldi.")
    await state.set_state(Pw.new1)
    await state.update_data(mode="change")
    await m.answer(f"✅ Toʻgʻri. Endi yangi parolni yuboring (kamida {auth.MIN_LENGTH} belgi):")


@router.message(Pw.new1, F.text, ~F.text.in_(NOT_PASSWORD))
async def pw_new1(m: Message, state: FSMContext):
    await _delete(m)
    pw = m.text.strip()
    if len(pw) < auth.MIN_LENGTH or pw.startswith("/"):
        return await m.answer(f"⚠️ Parol kamida {auth.MIN_LENGTH} belgidan iborat boʻlsin. Boshqasini yuboring:")
    # bazaga parolning oʻzi emas, faqat xeshi yoziladi (takrorlashni solishtirish uchun)
    await state.update_data(pw_check=hashlib.sha256(pw.encode()).hexdigest())
    await state.set_state(Pw.new2)
    await m.answer("🔁 Tasdiqlash uchun parolni <b>yana bir marta</b> yuboring:")


@router.message(Pw.new2, F.text, ~F.text.in_(NOT_PASSWORD))
async def pw_new2(m: Message, state: FSMContext, bot: Bot):
    await _delete(m)
    data = await state.get_data()
    pw = m.text.strip()
    if hashlib.sha256(pw.encode()).hexdigest() != data.get("pw_check"):
        await state.set_state(Pw.new1)
        return await m.answer("⚠️ Parollar mos kelmadi. Yangi parolni qaytadan yuboring:")
    await auth.set_password(pw)
    await state.clear()
    if data.get("mode") == "change":
        await auth.logout_all()  # boshqa adminlar yangi parol bilan qayta kiradi
    await auth.login(m.from_user.id)
    await m.answer("🔐 <b>Parol saqlandi!</b>\n<i>Uni faqat adminlarga ayting va hech qayerga yozib qoʻymang.</i>")
    await _open_panel(m)


# ---------------------------------------------------------------- parolsiz kirishga urinishlar
@router.message(Command(*ADMIN_COMMANDS), NotLoggedIn())
async def locked_command(m: Message):
    await m.answer(LOCKED)


@router.callback_query(F.data.startswith("ap:") | F.data.startswith("cc:"), NotLoggedIn())
async def locked_callback(cb: CallbackQuery):
    await cb.answer("🔒 Sessiya tugagan. Botda /admin yozib, parolni kiriting.", show_alert=True)


# ---------------------------------------------------------------- panel ichidan: parolni o'zgartirish, chiqish
@router.callback_query(F.data == "ap:pw")
async def cb_change_pw(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await state.set_state(Pw.current)
    await cb.message.answer("🔑 Parolni oʻzgartirish. Avval <b>joriy</b> parolni yuboring:")
    await cb.answer()


@router.callback_query(F.data == "ap:logout")
async def cb_logout(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await auth.logout(cb.from_user.id)
    try:
        await cb.message.edit_text("🚪 Paneldan chiqdingiz. Qayta kirish: /admin")
    except TelegramAPIError:
        pass
    await cb.answer()
