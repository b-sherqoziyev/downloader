from datetime import datetime, timezone, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.config import ADMIN_IDS
from app.database import get_stats
from .keyboards import get_admin_keyboard, get_channels_menu_keyboard

router = Router()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    
    await state.clear()
    text = "👑 <b>Admin Panel</b>\n\nQuyidagi tugmalardan birini tanlang:"
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode='HTML')

@router.callback_query(F.data == "admin_cancel")
async def admin_cancel_callback(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
        
    await state.clear()
    text = "👑 <b>Admin Panel</b>\n\nQuyidagi tugmalardan birini tanlang:"
    try:
        await callback.message.edit_text(text, reply_markup=get_admin_keyboard(), parse_mode='HTML')
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
        
    # Use UTC for DB queries to match TIMESTAMPTZ and avoid hosting environment mismatches
    now_utc = datetime.now(timezone.utc)
    today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
    
    # intervals
    wau_start = today_start - timedelta(days=7)
    mau_start = today_start - timedelta(days=30)
    
    # Tashkent timezone for display only
    tz_tashkent = pytz.timezone('Asia/Tashkent')
    current_time_tashkent = now_utc.astimezone(tz_tashkent)
    
    try:
        stats = await get_stats(today_start, wau_start, mau_start)
        
        # Calculate blocked users
        blocked = stats['total'] - stats['active']
        
        stats_msg = (
            f"📊 <b>Bot Statistikasi</b>\n\n"
            f"👥 Umumiy foydalanuvchilar: <b>{stats['total']}</b> ta\n"
            f"✅ Faol foydalanuvchilar: <b>{stats['active']}</b> ta\n"
            f"🚫 Botni bloklaganlar: <b>{blocked}</b> ta\n"
            f"🚷 Bandagi foydalanuvchilar: <b>{stats['banned']}</b> ta\n\n"
            f"📈 <b>O'sish dinamikasi:</b>\n"
            f"▫️ Bugun (DAU): +{stats['today']}\n"
            f"▫️ 7 kun ichida (WAU): +{stats['wau']}\n"
            f"▫️ 1 oy ichida (MAU): +{stats['mau']}\n\n"
            f"🕒 Hozirgi vaqt: {current_time_tashkent.strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        from .keyboards import get_back_keyboard
        await callback.message.edit_text(stats_msg, reply_markup=get_back_keyboard("admin_cancel"), parse_mode='HTML')
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Error getting stats: {e}")
        await callback.answer("Statistika olishda xatolik yuz berdi.", show_alert=True)
        
    await callback.answer()

@router.callback_query(F.data == "admin_channels")
async def admin_channels_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
        
    text = "🔗 <b>Majburiy Kanallar Boshqaruvi</b>\n\nBo'limni tanlang:"
    await callback.message.edit_text(text, reply_markup=get_channels_menu_keyboard(), parse_mode='HTML')
    await callback.answer()
