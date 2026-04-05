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
    
    # Use naive UTC for DB consistency
    from datetime import timezone
    current_time_utc = datetime.now(timezone.utc)
    current_time_naive = current_time_utc.replace(tzinfo=None)
    
    # Use Tashkent for display
    tz = pytz.timezone('Asia/Tashkent')
    display_time = current_time_utc.astimezone(tz)
    
    # Check if user is banned
    db_user = await get_user(str(user.id))
    if db_user and db_user.get('is_banned'):
        return
    
    # Save user to DB (using naive UTC)
    is_new = await save_user(user.id, user.username, user.first_name, user.last_name, current_time_naive)
    
    if is_new and ADMIN_IDS:
        for admin_id in ADMIN_IDS:
            try:
                username_str = f"@{user.username}" if user.username else "yo'q"
                admin_msg = (
                    f"➕ <b>Yangi foydalanuvchi!</b>\n\n"
                    f"<b>ID:</b> <code>{user.id}</code>\n"
                    f"<b>Ism:</b> {user.first_name}\n"
                    f"<b>Username:</b> {username_str}\n"
                    f"<b>Vaqt:</b> {display_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                await message.bot.send_message(admin_id, admin_msg, parse_mode='HTML')
            except Exception:
                pass
            
    await message.answer(f"Salom, {user.first_name}!\n\nVideo yuklash uchun havola yuboring. 📥")
