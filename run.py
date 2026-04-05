import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from app.config import BOT_TOKEN, COOKIES_CONTENT
from app.database import init_db, close_db
from app.handlers import base, download
from app.handlers.admin import router as admin_router
from app.middlewares.subscription import CheckSubscriptionMiddleware
from app.utils.userbot import userbot

# Setup structured logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN topilmadi! .env faylini tekshiring.")
        return
        
    # Cookies.txt yaratish (Railway uchun)
    if COOKIES_CONTENT:
        try:
            with open("cookies.txt", "w", encoding="utf-8") as f:
                f.write(COOKIES_CONTENT)
            logger.info("Cookies.txt muvaffaqiyatli yaratildi.")
        except Exception as e:
            logger.error(f"Cookies.txt yaratishda xato: {e}")
            
    # Baza ishga tushirish
    await init_db()
    
    # Bot va Dispatcher sozlamalari
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    
    # Global Middleware (Obuna va Ban nazorati)
    dp.message.middleware(CheckSubscriptionMiddleware())
    
    # Routerlarni ulash
    dp.include_router(admin_router)
    dp.include_router(base.router)
    dp.include_router(download.router)
    
    # Eski xabarlarni o'tkazib yuborish va pollingni boshlash
    await bot.delete_webhook(drop_pending_updates=True)
    
    # Userbotni ishga tushirish (agar sozlangan bo'lsa)
    if userbot:
        logger.info("Userbot ishga tushmoqda...")
        await userbot.start()
    try:
        logger.info("Bot muvaffaqiyatli ishga tushdi! (Aiogram 3.x)")
        await dp.start_polling(bot)
    finally:
        if userbot:
            await userbot.stop()
        await close_db()
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
