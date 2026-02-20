from aiogram import Router, types
from aiogram.filters import Command
from aiogram.types import Message
import pytz
from datetime import datetime
from app.config import ADMIN_ID
from app.database import save_user, get_stats

router = Router()

@router.message(Command("start"))
async def start_handler(message: Message):
    user = message.from_user
    tz = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tz)
    
    # Save user to DB
    is_new = await save_user(user.id, user.username, user.first_name, user.last_name, current_time)
    
    if is_new and ADMIN_ID:
        try:
            username_str = f"@{user.username}" if user.username else "yo'q"
            admin_msg = (
                f"➕ <b>Yangi foydalanuvchi!</b>\n\n"
                f"<b>ID:</b> <code>{user.id}</code>\n"
                f"<b>Ism:</b> {user.first_name}\n"
                f"<b>Username:</b> {username_str}\n"
                f"<b>Vaqt:</b> {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            # Use bot.send_message internally
            await message.bot.send_message(ADMIN_ID, admin_msg, parse_mode='HTML')
        except Exception:
            pass
            
    await message.answer("Salom! Instagram yoki YouTube video havolasini yuboring.")

@router.message(Command("stat"))
async def stat_handler(message: Message):
    user = message.from_user
    
    if not ADMIN_ID or user.id != ADMIN_ID:
        return
        
    tz = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tz)
    today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    try:
        total, today, month = await get_stats(today_start, month_start)
        stats_msg = (
            f"📊 <b>Bot Statistikasi</b>\n\n"
            f"👥 Umumiy foydalanuvchilar: {total} ta\n"
            f"📅 Bugun qo'shilganlar: {today} ta\n"
            f"🗓 Shu oy qo'shilganlar: {month} ta\n\n"
            f"🕒 Hozirgi vaqt: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        await message.answer(stats_msg, parse_mode='HTML')
    except Exception as e:
        await message.answer("Statistika olishda xatolik yuz berdi.")
