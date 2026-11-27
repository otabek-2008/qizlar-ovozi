"""Botni ishga tushirish.

- WEBHOOK_URL yoki RENDER_EXTERNAL_URL berilgan boʻlsa — webhook rejimi (Render).
- Aks holda — polling rejimi (oʻz kompyuteringizda).
"""
import asyncio
import hashlib
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import BotCommand

import admin_auth
import admin_login
import admin_panel
import certificate
import config
import db
import handlers_admin
import handlers_user
import services
import settings_store
import subscription
from fsm_storage import DbStorage
from subscription import SubscriptionMiddleware

log = logging.getLogger("bot")


async def prepare() -> tuple[Bot, Dispatcher]:
    if not config.BOT_TOKEN:
        raise SystemExit("BOT_TOKEN koʻrsatilmagan (.env yoki Render → Environment)")
    if not config.ADMIN_IDS:
        log.warning("ADMIN_IDS koʻrsatilmagan — admin buyruqlari hech kimga ishlamaydi")

    await db.init()
    await settings_store.apply_all()  # admin paneldagi sozlamalar
    await db.ensure_lessons()
    await admin_auth.load_sessions()
    await certificate.load_template()
    log.info("Baza: %s", "Supabase (PostgreSQL)" if db.IS_PG else f"SQLite ({config.DB_PATH})")

    bot = Bot(config.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=DbStorage())
    dp.message.outer_middleware(SubscriptionMiddleware())         # majburiy obuna
    dp.callback_query.outer_middleware(SubscriptionMiddleware())
    dp.include_router(admin_login.router)     # parol tekshiruvi eng birinchi
    dp.include_router(handlers_admin.router)  # admin buyruqlari (faqat parol kiritilgach)
    dp.include_router(admin_panel.router)
    dp.include_router(handlers_user.router)

    await bot.set_my_commands([BotCommand(command="start", description="Boshlash / menyu")])
    await services.set_admin_commands(bot)
    me = await bot.me()
    log.info("Bot: @%s", me.username)
    await warn_bad_channels(bot)
    return bot, dp


async def warn_bad_channels(bot: Bot) -> None:
    """Bot admin boʻlmagan kanallar haqida adminlarni ogohlantiradi (aks holda obuna tekshirilmaydi)."""
    problems = await subscription.check_problems(bot)
    if not problems:
        return
    text = ("⚠️ <b>Majburiy obuna toʻliq ishlamayapti</b>\n\n" + "\n\n".join(problems)
            + "\n\n<i>Botni qayta admin qiling yoki «📣 Reklama» boʻlimida yozuvni yangilang.</i>")
    log.warning("Kanal muammolari: %s", problems)
    for uid in settings_store.all_admins():
        await services.safe_send(bot, uid, text)


async def run_polling() -> None:
    import os
    probe = Bot(config.BOT_TOKEN)
    info = await probe.get_webhook_info()
    await probe.session.close()
    if info.url and os.getenv("FORCE_POLLING") != "1":
        print("\n⚠️  Bot hozir serverda (Render'da) ishlayapti — kompyuterda ishga tushirilmadi.\n"
              "    Ikkalasi birga ishlasa, xabarlar aralashib ketadi.\n"
              "    Baribir kompyuterda ishlatmoqchi boʻlsangiz: avval Render'da servisni toʻxtating (Suspend),\n"
              "    keyin .env fayliga FORCE_POLLING=1 qatorini qoʻshing.\n")
        return
    bot, dp = await prepare()
    try:
        await bot.delete_webhook(drop_pending_updates=False)
        log.info("Polling rejimi ishga tushdi")
        await dp.start_polling(bot)
    finally:
        await db.close()
        await bot.session.close()


async def run_webhook() -> None:
    from aiohttp import web
    from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

    bot, dp = await prepare()
    secret = hashlib.sha256(config.BOT_TOKEN.encode()).hexdigest()[:48]
    path = f"/tg/{secret[:16]}"

    app = web.Application()

    async def health(_request):
        return web.Response(text="ok")

    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=secret).register(app, path=path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", config.PORT).start()
    await bot.set_webhook(f"{config.WEBHOOK_BASE}{path}", secret_token=secret,
                          allowed_updates=dp.resolve_used_update_types(), drop_pending_updates=False)
    log.info("Webhook rejimi: %s (port %s)", config.WEBHOOK_BASE, config.PORT)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()
        await db.close()
        await bot.session.close()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    asyncio.run(run_webhook() if config.WEBHOOK_BASE else run_polling())


if __name__ == "__main__":
    main()
