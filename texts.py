"""Bot matnlari — hammasi shu faylda.

Formatlash (Telegram HTML): <b>qalin</b>, <i>kursiv</i>, <code>kod</code>, <blockquote>ajratilgan blok</blockquote>.
Belgilar tizimi (hamma joyda bir xil maʼnoda):
    ✅ bajarildi   ⏳ kutilmoqda   ❌ rad / xato   ⚠️ ogohlantirish   🔒 yopiq   ▫️ hali yoʻq
    💌 taklif      🎙 dars         🎟 davomat      🎓 kurs / sertifikat   🏆 reyting   🛠 admin
"""


# ================================================================ yordamchi funksiyalar
def progress(done: int, total: int, size: int = 10) -> str:
    """▰▰▰▱▱▱ koʻrinishidagi jarayon chizigʻi."""
    total = max(total, 1)
    done = max(0, min(done, total))
    filled = round(done / total * size)
    return "▰" * filled + "▱" * (size - filled)


def step(n: int, text: str, total: int = 5) -> str:
    """Roʻyxatdan oʻtish qadamlari sarlavhasi."""
    return f"<b>{n}/{total}</b>  {progress(n, total, total)}\n\n{text}"


PLACES = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


def place(i: int) -> str:
    return PLACES[i - 1] if 1 <= i <= len(PLACES) else f"<b>{i}.</b>"


# ================================================================ tugmalar
BTN_REF = "💌 Taklif qilish"
BTN_ME = "📊 Natijalarim"
BTN_CODE = "🎟 Davomat kodi"
BTN_CERT = "🎓 Sertifikat yuborish"
BTN_TOP = "🏆 Reyting"
BTN_ADMIN = "🛠 Admin panel"
BTN_SUB_CHECK = "✅ Obuna boʻldim — tekshirish"
BTN_SEND_PHONE = "📱 Raqamimni yuborish"
BTN_SHARE = "💌 Doʻstlarga yuborish"
BTN_CANCEL = "✖️ Bekor qilish"
MENU_BUTTONS = {BTN_REF, BTN_ME, BTN_CODE, BTN_CERT, BTN_TOP}

# ================================================================ majburiy obuna
SUB_REQUIRED = (
    "📢 <b>Botdan foydalanish uchun homiylarimizga obuna boʻling</b>\n\n"
    "{channels}\n\n"
    "<blockquote>1️⃣ Har birini ochib, obuna boʻling (kanal yoki guruhga qoʻshiling, botni ishga tushiring)\n"
    "2️⃣ Soʻng pastdagi «" + BTN_SUB_CHECK + "» tugmasini bosing</blockquote>"
)
SUB_ALERT = "📢 Avval homiylarimizga obuna boʻling."
SUB_STILL = "❌ Hali obuna boʻlmagansiz: {channels}"
SUB_OK = "✅ <b>Rahmat!</b> Obuna tasdiqlandi."

# ================================================================ roʻyxatdan oʻtish
WELCOME = (
    "🌸 <b>«{marathon}»</b> marafoniga xush kelibsiz!\n\n"
    "<blockquote>📅 1 hafta  ·  🎙 {lessons} ta mavzu  ·  🎓 sertifikat</blockquote>\n\n"
    "Qatnashish uchun qisqa roʻyxatdan oʻting — atigi 1 daqiqa ⏱"
)
ASK_FIRST_NAME = "👤 <b>Ismingiz?</b>\n<i>Masalan: Malika</i>"
ASK_LAST_NAME = "👤 <b>Familiyangiz?</b>\n<i>Masalan: Karimova</i>"
ASK_PHONE = (
    "📱 <b>Telefon raqamingiz</b>\n"
    "Pastdagi tugmani bosing yoki yozing: <code>+998901234567</code>"
)
ASK_BIRTH = (
    "🎂 <b>Tugʻilgan sanangiz</b>\n"
    "Avval <b>yilni</b> tanlang 👇\n"
    "<i>yoki yozib yuboring: 15.03.2008</i>"
)
BIRTH_MONTH = "🎂 <b>{year}-yil</b>\nEndi <b>oyni</b> tanlang 👇"
BIRTH_DAY = "🎂 <b>{month}, {year}</b>\nEndi <b>kunni</b> tanlang 👇"
BIRTH_DONE = "🎂 Tugʻilgan sana: <b>{date}</b> ✅"
BIRTH_EXPIRED = "Bu tugma eskirgan. Roʻyxatdan oʻtish: /start"
PHONE_OK = "✅ Raqam qabul qilindi: <b>{phone}</b>"
MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "Iyun",
          "Iyul", "Avgust", "Sentabr", "Oktabr", "Noyabr", "Dekabr"]
ASK_STUDY = (
    "🏫 <b>Oʻqish yoki ish joyingiz (aniq manzili)</b>\n"
    "<i>Masalan: 21-maktab (Toshkent sh., Chilonzor tumani)</i>"
)

BAD_NAME = "⚠️ Faqat harflardan foydalaning (2–40 belgi). Qayta yozing:"
BAD_PHONE = "⚠️ Raqam notoʻgʻri. Tugmani bosing yoki <code>+998901234567</code> koʻrinishida yozing."
OWN_PHONE_ONLY = "⚠️ Iltimos, <b>oʻzingizning</b> raqamingizni yuboring."
PHONE_TAKEN = "⚠️ Bu raqam bilan boshqa akkaunt roʻyxatdan oʻtgan. Boshqa raqam kiriting."
BAD_BIRTH = "⚠️ Sana notoʻgʻri. Masalan: <code>15.03.2008</code>"
BAD_AGE = "⚠️ Tugʻilgan sanani tekshirib, qayta kiriting."
BAD_STUDY = "⚠️ Oʻqish yoki ish joyingizni aniq manzili bilan yozing (5–200 belgi)."
TEXT_ONLY = "✍️ Javobni matn koʻrinishida yozing."

REGISTERED = (
    "🎉 <b>Tabriklaymiz, {name}!</b>\n"
    "Siz roʻyxatdan muvaffaqiyatli oʻtdingiz.\n\n"
    "Marafonga kirish uchun bitta qadam qoldi 👇"
)
ALREADY_REGISTERED = "🌸 <b>Qaytganingizdan xursandmiz, {name}!</b>\nKerakli boʻlimni tanlang 👇"
NOT_REGISTERED = "👋 Avval roʻyxatdan oʻting: /start"
USE_MENU = "👇 Kerakli boʻlimni pastdagi menyudan tanlang."

ADMIN_WELCOME = (
    "🛠 <b>Assalomu alaykum!</b>\n"
    "Siz <b>adminsiz</b> — roʻyxatdan oʻtishingiz shart emas, barcha boʻlimlar siz uchun ochiq.\n\n"
    "<blockquote>🛠 Boshqaruv: «" + BTN_ADMIN + "» yoki /admin\n"
    "🎟 Davomat va 🎓 sertifikat ham ishlaydi</blockquote>\n\n"
    "<i>💡 Yakuniy sertifikatga Telegram'dagi ismingiz yoziladi. Toʻliq ism-familiyangiz "
    "yozilishini istasangiz: /register</i>"
)
ADMIN_NOT_PARTICIPANT = (
    "🔒 Bu boʻlim ishtirokchilar uchun.\n\n"
    "<blockquote>Boshqaruv: «" + BTN_ADMIN + "»\nIshtirokchi boʻlish: /register</blockquote>"
)

# ================================================================ takliflar
REF_INFO = (
    "💌 <b>Doʻstlaringizni taklif qiling</b>\n\n"
    "Marafonda qatnashish uchun loyihani <b>{need} ta doʻstingizga</b> ulashing. "
    "Doʻstingiz havola orqali roʻyxatdan oʻtgach, taklif hisoblanadi.\n\n"
    "<blockquote>🔗 Shaxsiy havolangiz:\n{link}</blockquote>\n\n"
    "{bar}  <b>{count}/{need}</b>"
)
SHARE_TEXT = "🌸 «{marathon}» marafoniga qoʻshil! 1 hafta, {lessons} ta mavzu va sertifikat. Roʻyxatdan oʻtish 👇"
REF_NEW = (
    "🎉 <b>{name}</b> havolangiz orqali qoʻshildi!\n\n"
    "{bar}  <b>{count}/{need}</b>\n"
    "Yana <b>{left}</b> ta doʻst — va siz marafon ishtirokchisisiz ✨"
)
REF_NEW_MORE = (
    "🎉 <b>{name}</b> havolangiz orqali qoʻshildi!\n\n"
    "💌 Jami takliflaringiz: <b>{count}</b>\n"
    "<i>🏆 Eng faol qizlar marafon yakunida taqdirlanadi.</i>"
)
ELIGIBLE = (
    "🥳 <b>Tabriklaymiz!</b>\n\n"
    "Siz {need} ta doʻstingizni taklif qildingiz va <b>«{marathon}»</b> marafonining "
    "rasmiy ishtirokchisiga aylandingiz 🌸\n\n"
    "<blockquote>📢 Darslar boshlanishi haqida shu yerda xabar beramiz.</blockquote>\n\n"
    "💡 Taklif qilishda davom eting — eng faol qizlar taqdirlanadi 🏆"
)
ELIGIBLE_MANUAL = (
    "🥳 <b>Tabriklaymiz!</b>\n\n"
    "Tashkilotchilar sizga <b>«{marathon}»</b> marafonida ishtirok etish huquqini berdi 🌸\n\n"
    "<blockquote>📢 Darslar boshlanishi haqida shu yerda xabar beramiz.</blockquote>"
)
NEED_REFERRALS = (
    "🔒 <b>Bu boʻlim ishtirokchilar uchun</b>\n\n"
    "Ochish uchun {need} ta doʻstingizni taklif qiling:\n"
    "{bar}  <b>{count}/{need}</b>\n\n"
    "👉 «" + BTN_REF + "» tugmasini bosing"
)

# ================================================================ reyting
TOP_TITLE = "🏆 <b>Eng faol qizlar</b>\n<i>Taklif qilingan doʻstlar soni boʻyicha</i>\n"
TOP_EMPTY = "🏆 Hozircha takliflar yoʻq.\nBirinchi boʻling — havolangizni ulashing! 💌"
TOP_ROW = "{place}  {name} — <b>{cnt}</b>"
TOP_ME = "\n<blockquote>📍 Sizning oʻrningiz: <b>{rank}</b>  ·  💌 {cnt} ta taklif</blockquote>"
TOP_ME_NONE = "\n<blockquote>📍 Siz hali hech kimni taklif qilmadingiz.</blockquote>"

# ================================================================ davomat
NO_OPEN_LESSON = (
    "⏳ <b>Davomat hozir yopiq</b>\n"
    "Dars vaqtida spiker kodni aytadi — oʻshanda shu yerga yuborasiz."
)
ASK_CODE = "🎟 <b>Davomat kodi</b>\nDarsda aytilgan kodni yuboring:"
CODE_WRONG = "❌ Kod notoʻgʻri. Tekshirib, qayta yuboring."
CODE_ALREADY = "☑️ <b>{num}-dars</b> boʻyicha davomatingiz allaqachon olingan."
CODE_CLOSED = "⌛️ Afsuski, davomat vaqti tugadi."
CODE_OK = "✅ <b>{num}-dars</b> — davomat qabul qilindi!\n\n{bar}  <b>{count}/{total}</b> dars"
ALL_LESSONS_DONE = (
    "🎉 <b>Barcha {total} ta darsda qatnashdingiz!</b>\n\n"
    "<blockquote>🎓 Sertifikat uchun oxirgi qadam: <b>{platform}</b> platformasidagi {courses} ta kursni "
    "tugatib, sertifikatlarini «" + BTN_CERT + "» boʻlimiga yuboring.</blockquote>"
)
LESSON_OPEN_NOTIFY = (
    "🔴 <b>JONLI DARS  ·  {num}-dars</b>\n"
    "🎙 <b>{title}</b>\n\n"
    "🎟 Davomat ochildi! Darsda aytilgan kodni yuboring.\n"
    "<blockquote>⏱ {minutes} daqiqa — soat <b>{until}</b> gacha</blockquote>\n\n"
    "<i>Kodni shunchaki yozib yuborsangiz kifoya.</i>"
)
CANCELLED = "✖️ Bekor qilindi."

# ================================================================ kurs sertifikatlari
HOMEWORK_CLOSED = (
    "⏳ <b>Kurs vazifasi hali ochilmagan</b>\n"
    "Darslar yakunlangach shu yerda xabar beramiz."
)
HOMEWORK_OPEN_NOTIFY = (
    "🎓 <b>Yakuniy vazifa</b>\n\n"
    "<b>{platform}</b> platformasidagi {count} ta kursni tugating va sertifikatlarini botga yuboring:\n\n"
    "{courses}\n{link}\n"
    "<blockquote>⚠️ Sertifikat <b>{start}</b> yoki undan keyin olingan boʻlishi shart. "
    "Oldingi sertifikatlar hisobga olinmaydi.</blockquote>\n\n"
    "👉 «" + BTN_CERT + "» tugmasini bosing"
)
CHOOSE_COURSE = (
    "🎓 <b>Qaysi kurs sertifikatini yuborasiz?</b>\n\n"
    "<blockquote>⚠️ Sertifikat sanasi: <b>{start}</b> yoki undan keyin</blockquote>"
)
ALL_COURSES_SENT = "✅ Barcha kurslar boʻyicha sertifikat yuborgansiz.\nHolatini «" + BTN_ME + "» boʻlimida kuzating."
SEND_CERT_FILE = (
    "📎 <b>{course}</b>\n\n"
    "Sertifikatni <b>rasm</b> yoki <b>PDF</b> koʻrinishida yuboring.\n"
    "<i>Ism-familiya va sana aniq koʻrinib tursin.</i>"
)
BAD_CERT_FILE = "⚠️ Sertifikatni rasm yoki PDF fayl koʻrinishida yuboring."
CERT_DUPLICATE = "⚠️ Bu fayl avval yuborilgan. Oʻzingizning sertifikatingizni yuboring."
CERT_ALREADY = "Bu kurs boʻyicha sertifikat allaqachon yuborilgan · {status}"
CERT_RECEIVED = (
    "📨 <b>Qabul qilindi!</b>\n"
    "Sertifikatingiz tekshiruvga yuborildi — natijasini shu yerda bildiramiz ⏳"
)
CERT_APPROVED = "✅ <b>{course}</b> — sertifikat tasdiqlandi!\n\n{bar}  <b>{done}/{total}</b> kurs"
CERT_REJECTED = (
    "❌ <b>{course}</b> — sertifikat qabul qilinmadi\n\n"
    "<blockquote>Sabab: {reason}</blockquote>\n\n"
    "Toʻgʻri sertifikatni qayta yuborishingiz mumkin 👉 «" + BTN_CERT + "»"
)
COURSES_DONE_NEED_LESSONS = (
    "🎉 <b>Barcha kurslaringiz tasdiqlandi!</b>\n\n"
    "<blockquote>🎓 Sertifikat uchun barcha darslarda qatnashgan boʻlish kerak: "
    "<b>{att}/{total}</b></blockquote>"
)
STATUS_NAMES = {"approved": "✅ tasdiqlandi", "pending": "⏳ tekshirilmoqda", "rejected": "❌ rad etildi"}
NOT_SENT = "▫️ yuborilmagan"
REJECT_REASONS = {
    "old": "Sertifikat sanasi marafon boshlanishidan ({start}) oldin",
    "course": "Bu sertifikat tanlangan kursga tegishli emas",
    "name": "Sertifikatdagi ism-familiya sizniki bilan mos emas",
    "bad": "Fayl oʻqilmaydi yoki u sertifikat emas",
}

# ================================================================ yakuniy sertifikat
FINAL_CERT = (
    "🎓 <b>Tabriklaymiz, {name}!</b>\n\n"
    "Siz <b>«{marathon}»</b> marafonini muvaffaqiyatli yakunladingiz 🌸\n"
    "Shaxsiy sertifikatingiz ilova qilindi ✨"
)
CLUB_INVITE = "\n\n💎 <b>Siz clubga qabul qilindingiz!</b>\n{link}"

# ================================================================ natijalarim
ME = (
    "📊 <b>{name}</b>\n\n"
    "💌 <b>Takliflar</b>{eligible}\n"
    "{ref_bar}  <b>{refs}</b>\n"
    "🏆 Reytingdagi oʻrningiz: <b>{rank}</b>\n\n"
    "🎙 <b>Darslar</b>  ·  {att}/{total}\n"
    "<blockquote>{lessons}</blockquote>\n\n"
    "🎓 <b>Kurslar</b>  ·  {done}/{courses_total}\n"
    "<blockquote>{courses}</blockquote>\n\n"
    "🏅 <b>Sertifikat:</b> {final}"
)
ME_ELIGIBLE = "  ·  ✅ ishtirokchi"

# ================================================================ admin
ADMIN_HELP = """🛠 <b>Admin buyruqlari</b>
<i>Hammasini tugmalar orqali ham qilsa boʻladi: /admin</i>

📊 <b>Natijalar</b>
<blockquote>/stats — umumiy statistika
/top [N] — eng koʻp taklif qilganlar
/export — Excel (CSV) fayl
/user &lt;ID | @username | telefon&gt; — ishtirokchi haqida</blockquote>

🎙 <b>Darslar</b>
<blockquote>/lessons — darslar va davomat
/lesson_title N Mavzu — dars mavzusi
/open_lesson N [daqiqa] [kod] — davomatni ochish
/close_lesson N — davomatni yopish</blockquote>

🎓 <b>Kurslar va sertifikatlar</b>
<blockquote>/homework_on · /homework_off — qabulni ochish / yopish
/pending — tekshirilmaganlar
/check_all — yakuniy sertifikatlarni tarqatish
/issue_cert ID — sertifikatni qoʻlda berish
/eligible ID — qoʻlda ishtirok huquqi berish</blockquote>

⚙️ <b>Boshqa</b>
<blockquote>/set_review_group — (guruhda) tekshiruv guruhi
/myid — oʻz ID raqamingiz
Xabarga reply + /broadcast — hammaga tarqatish</blockquote>"""

ADMIN_CERT_CAPTION = (
    "🎓 Kurs sertifikati #{id}\n\n"
    "👤 {name}\n"
    "🔗 {username}  ·  ID {tg_id}\n"
    "📘 {course}\n"
    "✅ Tasdiqlangan: {done}/{total}\n\n"
    "⚠️ Tekshiring: sana {start} yoki undan keyin, ism-familiya mos."
)
