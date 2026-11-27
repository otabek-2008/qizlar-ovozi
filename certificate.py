"""Yakuniy sertifikat rasmini yaratish (ism-familiya bilan)."""
import io
import os
from datetime import date

from PIL import Image, ImageDraw, ImageFont

import config

_HERE = os.path.dirname(os.path.abspath(__file__))

BOLD_FONTS = [
    config.FONT_PATH,
    os.path.join(_HERE, "fonts", "bold.ttf"),
    "C:/Windows/Fonts/georgiab.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Georgia Bold.ttf",
]
REGULAR_FONTS = [
    config.FONT_PATH_REGULAR or config.FONT_PATH,
    os.path.join(_HERE, "fonts", "regular.ttf"),
    "C:/Windows/Fonts/georgia.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Supplemental/Georgia.ttf",
]

ROSE = "#B0185A"
GOLD = "#C9973F"
INK = "#2B1B24"
MUTED = "#6B4E5A"
PAPER = "#FFF8F4"


def _font(candidates: list[str], size: int):
    for path in candidates:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default(size=size)


def _safe(text: str) -> str:
    # Ba'zi shriftlarda oʻ/gʻ belgisi (U+02BB) bo'lmaydi — ko'rinishi bir xil bo'lgan belgiga almashtiramiz
    return text.replace("ʻ", "‘").replace("ʼ", "’")


def _fit(draw, text, candidates, max_width, start_size, min_size=36):
    size = start_size
    while size > min_size:
        font = _font(candidates, size)
        if draw.textlength(text, font=font) <= max_width:
            return font
        size -= 4
    return _font(candidates, min_size)


def _wrap(draw, text, font, max_width) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def _from_template(path: str, name: str, serial: str, issued: date) -> Image.Image:
    img = Image.open(path).convert("RGB")
    w, h = img.size
    d = ImageDraw.Draw(img)
    font = _fit(d, name, BOLD_FONTS, w * 0.8, int(h * 0.08))
    d.text((w * config.CERT_NAME_X, h * config.CERT_NAME_Y), name, font=font,
           fill=config.CERT_NAME_COLOR, anchor="mm")
    if config.CERT_DRAW_SERIAL:
        small = _font(REGULAR_FONTS, max(18, int(h * 0.022)))
        d.text((w * 0.5, h * 0.95), f"№ {serial}  ·  {issued:%d.%m.%Y}", font=small, fill=MUTED, anchor="mm")
    return img


def _default(name: str, serial: str, issued: date) -> Image.Image:
    w, h = 2480, 1754  # A4 albom, 300 dpi
    img = Image.new("RGB", (w, h), PAPER)
    d = ImageDraw.Draw(img)

    d.rectangle([50, 50, w - 50, h - 50], outline=ROSE, width=22)
    d.rectangle([105, 105, w - 105, h - 105], outline=GOLD, width=5)
    for cx, cy in [(105, 105), (w - 105, 105), (105, h - 105), (w - 105, h - 105)]:
        d.ellipse([cx - 28, cy - 28, cx + 28, cy + 28], fill=GOLD)

    cx = w / 2
    d.text((cx, 330), "SERTIFIKAT", font=_font(BOLD_FONTS, 180), fill=ROSE, anchor="mm")
    d.text((cx, 480), _safe(f"«{config.MARATHON_NAME}» marafoni"), font=_font(REGULAR_FONTS, 72),
           fill=MUTED, anchor="mm")
    d.text((cx, 650), "Ushbu sertifikat", font=_font(REGULAR_FONTS, 58), fill=MUTED, anchor="mm")

    name_font = _fit(d, name, BOLD_FONTS, w * 0.78, 150)
    d.text((cx, 820), name, font=name_font, fill=INK, anchor="mm")
    d.line([(cx - 850, 925), (cx + 850, 925)], fill=GOLD, width=5)

    if config.REQUIRE_COURSES_FOR_CERT:
        desc = (f"marafonning barcha {config.LESSONS_COUNT} ta darsida faol qatnashgani va "
                f"{config.PLATFORM_NAME} platformasidagi {len(config.COURSES)} ta kursni "
                f"muvaffaqiyatli tamomlagani uchun taqdim etiladi")
    else:
        desc = f"marafonning barcha {config.LESSONS_COUNT} ta darsida faol qatnashgani uchun taqdim etiladi"
    body = _font(REGULAR_FONTS, 58)
    y = 1040
    for line in _wrap(d, _safe(desc), body, w * 0.72):
        d.text((cx, y), line, font=body, fill=INK, anchor="mm")
        y += 82

    small = _font(REGULAR_FONTS, 46)
    label = _font(BOLD_FONTS, 46)
    d.text((430, 1470), f"{issued:%d.%m.%Y}", font=label, fill=INK, anchor="mm")
    d.line([(250, 1515), (610, 1515)], fill=MUTED, width=2)
    d.text((430, 1560), "Sana", font=small, fill=MUTED, anchor="mm")

    d.text((cx, 1470), _safe(config.ORGANIZER), font=label, fill=ROSE, anchor="mm")
    d.line([(cx - 330, 1515), (cx + 330, 1515)], fill=MUTED, width=2)
    d.text((cx, 1560), "Tashkilotchi", font=small, fill=MUTED, anchor="mm")

    d.text((w - 430, 1470), f"№ {serial}", font=label, fill=INK, anchor="mm")
    d.line([(w - 610, 1515), (w - 250, 1515)], fill=MUTED, width=2)
    d.text((w - 430, 1560), "Seriya raqami", font=small, fill=MUTED, anchor="mm")
    return img


# ---------------------------------------------------------------- shablon (bazada saqlanadi)
TEMPLATE_KEY = "cert_template"
_template: bytes | None = None  # xotiradagi nusxa; asl nusxa bazadagi "files" jadvalida


def legacy_template_path() -> str:
    """Eski usul: diskdagi fayl (bir marta bazaga koʻchiriladi)."""
    template = config.CERT_TEMPLATE or "templates/certificate.png"
    return template if os.path.isabs(template) else os.path.join(_HERE, template)


def set_cached(data: bytes | None) -> None:
    global _template
    _template = data


def has_template() -> bool:
    return _template is not None


def normalize_template(data: bytes) -> tuple[bytes, int, int]:
    """Admin yuklagan rasmni PNG ga oʻgiradi. (png, eni, boʻyi) qaytaradi."""
    img = Image.open(io.BytesIO(data)).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return buf.getvalue(), img.size[0], img.size[1]


async def load_template() -> None:
    """Ishga tushganda shablonni bazadan oladi (diskda eski fayl boʻlsa — bazaga koʻchiradi)."""
    import db
    data = await db.file_get(TEMPLATE_KEY)
    if data is None and os.path.exists(legacy_template_path()):
        with open(legacy_template_path(), "rb") as f:
            data = f.read()
        await db.file_set(TEMPLATE_KEY, data)
    set_cached(data)


async def save_template(data: bytes) -> tuple[int, int]:
    import asyncio
    import db
    png, w, h = await asyncio.to_thread(normalize_template, data)
    await db.file_set(TEMPLATE_KEY, png)
    set_cached(png)
    return w, h


async def delete_template() -> None:
    import db
    await db.file_delete(TEMPLATE_KEY)
    set_cached(None)
    if os.path.exists(legacy_template_path()):
        os.remove(legacy_template_path())


def render_certificate(full_name: str, serial: str, issued: date) -> bytes:
    name = _safe(full_name.strip())
    if _template is not None:
        img = _from_template(io.BytesIO(_template), name, serial, issued)
    else:
        img = _default(name, serial, issued)
    buf = io.BytesIO()
    img.save(buf, "PNG", optimize=True)
    return buf.getvalue()
