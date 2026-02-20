import asyncio
import logging
from aiogram import Bot, Dispatcher
from app.config import BOT_TOKEN
from app.database import init_db, close_db
from app.handlers import base, download

# Setup structured logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN is missing!")
        return
        
    # Start DB
    await init_db()
    
    # Initialize Bot and Dispatcher
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    
    # Register routers
    dp.include_router(base.router)
    dp.include_router(download.router)
    
    # Drop pending updates and start polling
    await bot.delete_webhook(drop_pending_updates=True)
    try:
        logger.info("Bot ishga tushdi (Aiogram 3.x)...")
        await dp.start_polling(bot)
    finally:
        await close_db()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
