import calendar
from datetime import date
from urllib.parse import urlencode

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

import config
import settings_store
import texts


def main_menu(user_id: int | None = None) -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(text=texts.BTN_REF), KeyboardButton(text=texts.BTN_ME)],
        [KeyboardButton(text=texts.BTN_CODE), KeyboardButton(text=texts.BTN_CERT)],
        [KeyboardButton(text=texts.BTN_TOP)],
    ]
    if user_id is not None and settings_store.is_admin(user_id):
        rows[-1].append(KeyboardButton(text=texts.BTN_ADMIN))
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    """Roʻyxatdan oʻtmagan admin uchun menyu."""
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=texts.BTN_ADMIN)]], resize_keyboard=True)


def phone_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text=texts.BTN_SEND_PHONE, request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


# ---------------------------------------------------------------- tugʻilgan sana tanlash
YEARS_PER_PAGE = 20


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, callback_data=data)


def birth_years() -> list[int]:
    this = date.today().year
    return list(range(this - config.MIN_AGE, this - config.MAX_AGE - 1, -1))


def birth_year_page(year: int) -> int:
    years = birth_years()
    return years.index(year) // YEARS_PER_PAGE if year in years else 0


def birth_years_kb(page: int = 0) -> InlineKeyboardMarkup:
    years = birth_years()
    pages = max(1, -(-len(years) // YEARS_PER_PAGE))
    page = max(0, min(page, pages - 1))
    chunk = years[page * YEARS_PER_PAGE:(page + 1) * YEARS_PER_PAGE]
    rows = [[_btn(str(y), f"bd:Y:{y}") for y in chunk[i:i + 4]] for i in range(0, len(chunk), 4)]
    nav = []
    if page > 0:
        nav.append(_btn("◀️ Yangiroq", f"bd:y:{page - 1}"))
    if page < pages - 1:
        nav.append(_btn("Oldingi yillar ▶️", f"bd:y:{page + 1}"))
    if nav:
        rows.append(nav)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def birth_months_kb(year: int) -> InlineKeyboardMarkup:
    rows = [[_btn(texts.MONTHS[m - 1], f"bd:M:{year}:{m}") for m in range(i, i + 3)] for i in range(1, 13, 3)]
    rows.append([_btn(f"◀️ Yil: {year}", f"bd:y:{birth_year_page(year)}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def birth_days_kb(year: int, month: int) -> InlineKeyboardMarkup:
    days = calendar.monthrange(year, month)[1]
    buttons = [_btn(str(d), f"bd:D:{year}:{month}:{d}") for d in range(1, days + 1)]
    rows = [buttons[i:i + 7] for i in range(0, len(buttons), 7)]
    rows.append([_btn(f"◀️ Oy: {texts.MONTHS[month - 1]}", f"bd:Y:{year}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def share_kb(link: str) -> InlineKeyboardMarkup:
    text = texts.SHARE_TEXT.format(marathon=config.MARATHON_NAME, lessons=config.LESSONS_COUNT)
    url = "https://t.me/share/url?" + urlencode({"url": link, "text": text})
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.BTN_SHARE, url=url)]])


def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="cancel")]])


def courses_kb(available: list[tuple[int, str]]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=f"📘 {name}", callback_data=f"course:{idx}")] for idx, name in available]
    rows.append([InlineKeyboardButton(text=texts.BTN_CANCEL, callback_data="cancel")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def review_kb(cert_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"cc:ok:{cert_id}"),
        InlineKeyboardButton(text="❌ Rad etish", callback_data=f"cc:rej:{cert_id}"),
    ]])


def reject_reasons_kb(cert_id: int) -> InlineKeyboardMarkup:
    start = config.MARATHON_START.strftime("%d.%m.%Y")
    rows = [
        [InlineKeyboardButton(text="❌ " + reason.format(start=start)[:58], callback_data=f"cc:r:{cert_id}:{key}")]
        for key, reason in texts.REJECT_REASONS.items()
    ]
    rows.append([InlineKeyboardButton(text="◀️ Orqaga", callback_data=f"cc:back:{cert_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
