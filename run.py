import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.client.telegram import TelegramAPIServer
from aiogram.fsm.storage.memory import MemoryStorage
from app.config import BOT_TOKEN, USE_LOCAL_API, LOCAL_API_SERVER_URL
from app.database import init_db, close_db
from app.handlers import base, download
from app.handlers.admin import router as admin_router
from app.middlewares.subscription import CheckSubscriptionMiddleware

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
    if USE_LOCAL_API:
        logger.info(f"Local Bot API server ishlatilmoqda (is_local=True): {LOCAL_API_SERVER_URL}")
        local_server = TelegramAPIServer.from_base(LOCAL_API_SERVER_URL, is_local=True)
        bot = Bot(token=BOT_TOKEN, server=local_server)
    else:
        bot = Bot(token=BOT_TOKEN)
        
    dp = Dispatcher(storage=MemoryStorage())
    
    # Global Middleware for subscriptions
    dp.message.middleware(CheckSubscriptionMiddleware())
    
    # Register routers
    dp.include_router(admin_router)
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
