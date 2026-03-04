from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message
import pytz
from datetime import datetime
from app.config import ADMIN_IDS
from app.database import save_user, get_user

router = Router()

@router.message(Command("start"))
async def start_handler(message: Message):
    user = message.from_user
    tz = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tz)
    
    # Check if user is banned
    db_user = await get_user(str(user.id))
    if db_user and db_user.get('is_banned'):
        return
    
    # Save user to DB
    is_new = await save_user(user.id, user.username, user.first_name, user.last_name, current_time)
    
    if is_new and ADMIN_IDS:
        for admin_id in ADMIN_IDS:
            try:
                username_str = f"@{user.username}" if user.username else "yo'q"
                admin_msg = (
                    f"➕ <b>Yangi foydalanuvchi!</b>\n\n"
                    f"<b>ID:</b> <code>{user.id}</code>\n"
                    f"<b>Ism:</b> {user.first_name}\n"
                    f"<b>Username:</b> {username_str}\n"
                    f"<b>Vaqt:</b> {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await message.bot.send_message(admin_id, admin_msg, parse_mode='HTML')
            except Exception:
                pass
            
    await message.answer("""
Salom! Bu mashhur ijtimoiy tarmoqlardan video/foto/audio yuklab olish uchun bot.\n\n
Uni qanday ishlatish kerak:
1. Ijtimoiy tarmoqlardan biriga kiring.
2. Qiziqarli video/foto tanlang.
3. "Link nusxalash" tugmasini bosing.
4. Link botga yuboring va yuklab olingan faylni oling!

🔗 Botdan yuklab olish mumkin:
• YouTube
• Instagram
• Twitter""")
