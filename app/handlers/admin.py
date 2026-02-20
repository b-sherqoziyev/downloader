import asyncio
import re
import pytz
from datetime import datetime
from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, LinkPreviewOptions
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import logging

from app.config import ADMIN_ID
from app.database import get_all_users, add_channel, remove_channel, get_all_channels, get_stats

logger = logging.getLogger(__name__)

router = Router()

class AdminStates(StatesGroup):
    waiting_for_channel_data = State()
    waiting_for_remove_id = State()
    waiting_for_broadcast_msg = State()

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="➖ Kanalni o'chirish", callback_data="admin_del_channel")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="admin_list_channels")],
        [InlineKeyboardButton(text="📣 Xabar tarqatish (Broadcast)", callback_data="admin_broadcast")],
    ])

def get_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
    ])

@router.message(Command("admin"))
async def admin_panel(message: Message, state: FSMContext):
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        return
    
    await state.clear()
    
    text = "👑 <b>Admin Panel</b>\n\nQuyidagi tugmalardan birini tanlang:"
    await message.answer(text, reply_markup=get_admin_keyboard(), parse_mode='HTML')

@router.callback_query(F.data == "admin_cancel")
async def admin_cancel_callback(callback: CallbackQuery, state: FSMContext):
    if not ADMIN_ID or callback.from_user.id != ADMIN_ID:
        return
        
    await state.clear()
    await callback.message.delete()
    await callback.message.answer(
        "Amal bekor qilindi.\n\n👑 <b>Admin Panel</b>\nQuyidagi tugmalardan birini tanlang:", 
        reply_markup=get_admin_keyboard(),
        parse_mode='HTML'
    )
    await callback.answer("Amal bekor qilindi")

@router.callback_query(F.data == "admin_stats")
async def admin_stats_callback(callback: CallbackQuery):
    if not ADMIN_ID or callback.from_user.id != ADMIN_ID:
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
        await callback.message.delete()
        await callback.message.answer(stats_msg, reply_markup=get_admin_keyboard(), parse_mode='HTML')
    except Exception as e:
        await callback.message.answer("Statistika olishda xatolik yuz berdi.")
        
    await callback.answer()

# --- Add Channel ---
@router.callback_query(F.data == "admin_add_channel")
async def start_add_channel(callback: CallbackQuery, state: FSMContext):
    if not ADMIN_ID or callback.from_user.id != ADMIN_ID:
        return
    await callback.message.delete()
    await callback.message.answer(
        "Kanal ma'lumotlarini qator tashlab yuboring:\n1. Kanal ID (masalan: -1001234567890)\n2. Havola (https://t.me/...)\n3. Nom (Kanal Nomi)",
        reply_markup=get_cancel_keyboard()
    )
    await state.set_state(AdminStates.waiting_for_channel_data)
    await callback.answer()

@router.message(AdminStates.waiting_for_channel_data)
async def process_channel_data(message: Message, state: FSMContext):
    data = message.text.split('\n')
    if len(data) != 3:
        await message.answer("Xato format. Qaytadan 3 qatorda yuboring yoki bekor qiling:", reply_markup=get_cancel_keyboard())
        return
        
    channel_id = re.sub(r'^\d+\.\s*', '', data[0].strip())
    url = re.sub(r'^\d+\.\s*', '', data[1].strip())
    title = re.sub(r'^\d+\.\s*', '', data[2].strip())
    
    success = await add_channel(channel_id, url, title)
    
    if success:
        await message.answer(f"✅ Kanal qo'shildi!\n{title} ({channel_id})", reply_markup=get_admin_keyboard())
    else:
        await message.answer("❌ Kanal qo'shishda xatolik yuz berdi.", reply_markup=get_admin_keyboard())
    await state.clear()

# --- Remove Channel ---
@router.callback_query(F.data == "admin_del_channel")
async def start_del_channel(callback: CallbackQuery, state: FSMContext):
    if not ADMIN_ID or callback.from_user.id != ADMIN_ID:
        return
    await callback.message.delete()
    await callback.message.answer("O'chirmoqchi bo'lgan kanal ID sini yuboring:", reply_markup=get_cancel_keyboard())
    await state.set_state(AdminStates.waiting_for_remove_id)
    await callback.answer()

@router.message(AdminStates.waiting_for_remove_id)
async def process_del_channel(message: Message, state: FSMContext):
    channel_id = message.text.strip()
    success = await remove_channel(channel_id)
    
    if success:
         await message.answer("✅ Kanal olib tashlandi!", reply_markup=get_admin_keyboard())
    else:
         await message.answer("❌ Bunday kanal topilmadi.", reply_markup=get_admin_keyboard())
    await state.clear()

# --- List Channels ---
@router.callback_query(F.data == "admin_list_channels")
async def list_channels(callback: CallbackQuery):
    if not ADMIN_ID or callback.from_user.id != ADMIN_ID:
        return
    channels = await get_all_channels()
    await callback.message.delete()
    
    if not channels:
         await callback.message.answer("Manjburiy kanallar ro'yxati bo'sh.", reply_markup=get_admin_keyboard())
         return
         
    text = "📋 Kanallar ro'yxati:\n\n"
    for ch in channels:
        text += f"- <b>{ch['title']}</b>\n  ID: {ch['channel_id']}\n  URL: {ch['url']}\n\n"
        
    await callback.message.answer(text, disable_web_page_preview=True, reply_markup=get_admin_keyboard(), parse_mode="HTML")
    await callback.answer()

# --- Broadcast ---
@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not ADMIN_ID or callback.from_user.id != ADMIN_ID:
        return
    await callback.message.delete()
    await callback.message.answer("Tarqatmoqchi bo'lgan xabaringizni yuboring (Rasm, video yoki matn):", reply_markup=get_cancel_keyboard())
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await callback.answer()

@router.callback_query(F.data == "check_subscription")
async def handle_check_subscription(callback: CallbackQuery):
    user_id = callback.from_user.id
    channels = await get_all_channels()
    
    if not channels:
        await callback.message.delete()
        await callback.message.answer("Salom! Instagram yoki YouTube video havolasini yuboring.")
        await callback.answer()
        return
        
    unsubscribed = False
    for ch in channels:
        try:
            member_status = await callback.bot.get_chat_member(chat_id=ch['channel_id'], user_id=user_id)
            if member_status.status in ['left', 'kicked', 'banned']:
                unsubscribed = True
                break
        except Exception:
            unsubscribed = True
            break
            
    if unsubscribed:
        await callback.answer("Siz hali barcha kanallarga a'zo bo'lmadingiz!", show_alert=True)
    else:
        await callback.message.delete()
        await callback.message.answer("✅ Obuna tasdiqlandi! Endi qator tashlab video yoki qoshiq havolasini yuboravering.")
        await callback.answer("Obuna muvaffaqiyatli!")

@router.message(AdminStates.waiting_for_broadcast_msg)
async def process_broadcast(message: Message, state: FSMContext):
    users = await get_all_users()
    if not users:
        await message.answer("Bazada foydalanuvchilar yo'q.", reply_markup=get_admin_keyboard())
        await state.clear()
        return

    await message.answer(f"Xabar {len(users)} ta foydalanuvchiga yuborilmoqda. Iltimos kuting...")
    
    success_count = 0
    fail_count = 0
    
    for user_id in users:
        try:
            # send_copy accepts kwargs for the underlying send method (send_message, send_photo etc.)
            await message.send_copy(
                chat_id=user_id, 
                link_preview_options=LinkPreviewOptions(is_disabled=True)
            )
            success_count += 1
            await asyncio.sleep(0.05) # Rate limiting bot api 30 msg/sec
        except Exception:
            fail_count += 1
            
    await message.answer(f"✅ Tarqatma yakunlandi!\n\n🟢 Muvaffaqiyatli: {success_count}\n🔴 Yetib bormadi (Botni bloklagan): {fail_count}", reply_markup=get_admin_keyboard())
    await state.clear()
