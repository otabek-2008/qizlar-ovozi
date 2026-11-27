# «Qizlar ovozi» marafon boti

1 haftalik, 5 ta darsdan iborat marafon uchun Telegram bot.

## Ishga tushirish (3 qadam)

1. **`sozlash.bat`** faylini ikki marta bosing:
   - @BotFather bergan tokenni qoʻyasiz (bot tokenni tekshiradi);
   - botga telefoningizdan «salom» yozasiz, dastur sizni topadi va ID'ingizni oʻzi `.env` ga yozadi.
2. **`ishga_tushirish.bat`** faylini ikki marta bosing — bot ishlay boshlaydi (oyna ochiq turishi kerak).
3. Telegram'da botga **`/admin`** yozing va marafon sozlamalarini kiriting.

## Serverga joylash: Supabase (baza) + Render (bot)

Maʼlumotlar **Supabase**da (PostgreSQL), bot **Render**da ishlaydi — kompyuter oʻchsa ham bot ishlaydi.

1. **Supabase** — `supabase_ulash.bat` ni ikki marta bosing. Supabase → loyiha → **Connect** →
   **Session pooler** URI ni qoʻying (va baza parolini). Dastur ulanishni tekshiradi, `.env` ga yozadi va
   kompyuterdagi maʼlumotlarni (sozlamalar, parol, ishtirokchilar) Supabase'ga koʻchiradi.
2. **GitHub** — github.com da **private** repozitoriy oching va kodni yuklang (`.env` va baza yuklanmaydi).
3. **Render** — render.com → **New → Blueprint** → GitHub repozitoriyni tanlang. Render 3 ta qiymat soʻraydi:
   `BOT_TOKEN`, `ADMIN_IDS`, `DATABASE_URL` — ularni `.env` faylidan nusxalang.
4. **Kanallar** — botni @qizlarovozi_uz, @qizlarakademiyasiuz, @marjonajurakulova kanallariga **admin** qiling
   (aks holda obunani tekshira olmaydi; bot ishga tushganda muammo boʻlsa adminlarga yozadi).

Render bepul tarifida 15 daqiqa hech kim yozmasa bot «uxlaydi», keyingi xabarda ~1 daqiqada uygʻonadi
(xabar yoʻqolmaydi). Roʻyxatdan oʻtish qadamlari, admin sessiyalari, sertifikat shabloni bazada saqlanadi —
uygʻonganda hech narsa yoʻqolmaydi. Bot Render'da ishlayotganda kompyuterdagi `ishga_tushirish.bat` ishlamaydi
(xabarlar aralashmasligi uchun).

## Kompyuterga zaxira (Supabase + kompyuter — ikkalasida ham)

- `zaxira_olish.bat` — hozir zaxira olish. Natija `zaxira` papkasida: toʻliq baza (`marathon_…db`)
  va Excel'da ochiladigan roʻyxat (`ishtirokchilar_…csv`). Oxirgi 60 ta nusxa saqlanadi.
- `zaxira_jadval.bat` — bir marta bosing: kompyuter yoqiq boʻlganda **har 6 soatda** avtomatik zaxira.
- Zaxiradan Supabase'ga qaytarish: `python kochirish.py zaxira\marathon_YYYY-MM-DD_HH-MM.db`

## Majburiy obuna

Roʻyxatdan oʻtishning oxirgi (6-) qadami — kanallarga obuna. Obuna boʻlmaguncha ishtirokchi roʻyxatga
yozilmaydi; keyin kanaldan chiqib ketsa — qayta obuna boʻlmaguncha bot ishlamaydi. Kanallar:
Panel → ⚙️ Sozlamalar → 📢 Majburiy kanallar (saqlashda bot admin ekani tekshiriladi).

## Admin panel (`/admin` yoki «⚙️ Admin panel» tugmasi)

Panel **parol** bilan himoyalangan. Birinchi `/admin` da parol oʻrnatiladi, keyin har kirishda soʻraladi
(kirgandan keyin 12 soat ochiq turadi). Kirish uchun ikkala shart kerak: admin roʻyxatidagi ID **va** parol.
Yozilgan parol chatdan darhol oʻchiriladi; 5 ta xato urinishdan keyin 15 daqiqa blok.
Parolni oʻzgartirish: Panel → «👮 Adminlar va parol» → «🔑 Parolni oʻzgartirish».
Parol unutilsa: kompyuterda `parol_tiklash.bat` → keyingi `/admin` da yangisi oʻrnatiladi.

| Boʻlim | Nima qilinadi |
|---|---|
| 📊 Statistika | Roʻyxatdan oʻtganlar, ishtirokchilar, har bir dars davomati, faollar, sertifikat olganlar |
| 🏆 Reyting | Eng koʻp taklif qilganlar — ism, telefon, ID bilan |
| 📚 Darslar va davomat | Darsni tanlab: «🟢 10 daq» — davomat ochiladi, kod avtomatik chiqadi; oʻz kodingiz bilan ochish; yopish; mavzusini yozish; darslar soni |
| 🎓 Kurs vazifasi | Sertifikat qabulini ochish/yopish, kurslar roʻyxati, platforma havolasi, tekshirilmaganlar, yakuniy sertifikatlarni tarqatish |
| 🖼 Sertifikat | Oʻz shabloningizni yuklash, namuna koʻrish, ism joyi va rangi, tashkilotchi, club havolasi |
| ⚙️ Marafon sozlamalari | Nomi, boshlanish sanasi, kerakli takliflar soni, kod vaqti, shartlar va h.k. |
| 📢 Xabar yuborish | Istalgan xabarni hammaga yoki faqat ishtirokchilarga |
| 📥 Excel | Barcha ishtirokchilar jadvali |
| 👮 Adminlar | Admin qoʻshish/oʻchirish (yangi admin ID'ini botga `/myid` yozib biladi), tekshiruv guruhi |

Kurs sertifikatlarini guruhda tekshirish uchun: botni guruhga qoʻshing va guruhda `/set_review_group` yozing.

## Bot nima qiladi

1. **Roʻyxatdan oʻtish**: ism → familiya → telefon → tugʻilgan sana → oʻqish/ish joyi.
2. **Referal**: shaxsiy havola; har bir doʻst toʻliq roʻyxatdan oʻtganda «🎉 Siz Malikani taklif qildingiz (3/5)»;
   5 tada «🥳 Ishtirok etish imkoniyatiga ega boʻldingiz!».
3. **Davomat**: dars paytida panelda «🟢 10 daq» → spiker kodni aytadi → qizlar 10 daqiqa ichida botga yozadi.
4. **Kurs vazifasi**: Qizlar akademiyasidagi 3 ta kurs sertifikati → admin tasdiqlaydi yoki sabab bilan rad etadi
   (masalan, «sanasi marafon boshlanishidan oldin»).
5. **Yakuniy sertifikat**: 5/5 dars + 3/3 kurs bajarilganda bot ism-familiyali sertifikatni avtomatik yuboradi.

## Marafon kunlari tartibi

1. Oldindan: `/admin` → Sozlamalar (sana, kurslar) → Darslar (har bir dars mavzusi) → Sertifikat (shablon).
2. Har bir darsda: Darslar → N-dars → «🟢 10 daq» → chiqqan kodni spiker aytadi.
3. 5-darsdan keyin: Kurs vazifasi → «🟢 Qabulni ochish».
4. Sertifikatlarni tasdiqlab borasiz — yakuniy sertifikat avtomatik ketadi.
5. Yakunda: Statistika, Reyting, Excel.

Bot doimiy ishlashi uchun uni serverda (VPS) ishga tushirish kerak — kompyuter oʻchsa bot ham toʻxtaydi.

## Fayllar

- `sozlash.bat` / `sozlash.py` — token va admin ID'ni sozlash
- `ishga_tushirish.bat` / `bot.py` — botni ishga tushirish
- `admin_panel.py` — tugmali admin panel; `settings_store.py` — panel sozlamalari
- `texts.py` — **bot matnlari** (shu yerda tahrirlang)
- `handlers_user.py`, `handlers_admin.py`, `services.py`, `certificate.py`, `db.py`
- `marathon.db` — baza (barcha maʼlumotlar shu yerda; zaxira nusxasini olib turing)
