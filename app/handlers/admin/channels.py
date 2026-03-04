import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.fsm.context import FSMContext

from app.database import add_channel, remove_channel, get_all_channels, get_channels_count
from .keyboards import get_back_keyboard, get_pagination_keyboard, AdminStates
from .core import is_admin

router = Router()

PER_PAGE = 5

@router.callback_query(F.data == "admin_add_channel")
async def start_add_channel(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
        
    text = (
        "➕ <b>Yangi kanal qo'shish</b>\n\n"
        "Iltimos, qo'shmoqchi bo'lgan kanalingizdan bitta xabarni <b>Forward</b> qilib (uzatib) yuboring "
        "yoki qator tashlab qo'lda yozib qoldiring:\n\n"
        "1. Kanal ID (masalan: -100...)\n"
        "2. Havola (https://t.me/...)\n"
        "3. Nom (Kanal Nomi)"
    )
    await callback.message.edit_text(text, reply_markup=get_back_keyboard("admin_channels"), parse_mode='HTML')
    await state.set_state(AdminStates.waiting_for_channel_data)
    await callback.answer()

@router.message(AdminStates.waiting_for_channel_data)
async def process_channel_data(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
        
    # Handle forwarded messages
    if message.forward_origin:
        if message.forward_origin.type == "chat" and message.forward_origin.chat.type == "channel":
            channel = message.forward_origin.chat
            channel_id = str(channel.id)
            title = channel.title
            
            # Since bot can't know the invite link from just a forward natively (unless it's an admin),
            # Try to get chat through bot
            try:
                chat = await message.bot.get_chat(channel.id)
                url = chat.invite_link
                if not url and chat.username:
                    url = f"https://t.me/{chat.username}"
            except Exception:
                url = "NOMA'LUM"
                
            if url == "NOMA'LUM":
                await message.answer(
                    f"⚠️ Forward qilingan '{title}' ({channel_id}) kanali qabul qilindi, "
                    f"lekin men unga admin emasligim sababli Usernameni (URL) izlay olmadim. "
                    f"Iltimos, botni kanalga admin qilib qo'shing yoki qo'lda kiritish formatidan foydalaning.",
                    reply_markup=get_back_keyboard("admin_add_channel")
                )
                return
                
            success = await add_channel(channel_id, url, title)
            if success:
                await message.answer(f"✅ Kanal muvaffaqiyatli qo'shildi!\n{title} ({channel_id})", reply_markup=get_back_keyboard("admin_channels"))
            else:
                 await message.answer("❌ Kanal qo'shishda xatolik yuz berdi.", reply_markup=get_back_keyboard("admin_add_channel"))
            await state.clear()
            return
            
    # Handle manual entry
    if not message.text:
         await message.answer("❌ Noto'g'ri format. Yoki kanal xabarini forward qiling yoki 3 qatorda matn yuboring.", reply_markup=get_back_keyboard("admin_add_channel"))
         return
         
    data = message.text.split('\n')
    if len(data) != 3:
        await message.answer("❌ Xato format. Qaytadan 3 qatorda yuboring yoki bekor qiling:", reply_markup=get_back_keyboard("admin_add_channel"))
        return
        
    channel_id = re.sub(r'^\d+\.\s*', '', data[0].strip())
    url = re.sub(r'^\d+\.\s*', '', data[1].strip())
    title = re.sub(r'^\d+\.\s*', '', data[2].strip())
    
    success = await add_channel(channel_id, url, title)
    
    if success:
        await message.answer(f"✅ Kanal muvaffaqiyatli qo'shildi!\n{title} ({channel_id})", reply_markup=get_back_keyboard("admin_channels"))
    else:
        await message.answer("❌ Kanal qo'shishda xatolik yuz berdi.", reply_markup=get_back_keyboard("admin_channels"))
    await state.clear()

@router.callback_query(F.data.startswith("admin_list_channels:"))
async def list_channels(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
        
    page = int(callback.data.split(":")[1])
    offset = page * PER_PAGE
    
    channels = await get_all_channels(limit=PER_PAGE, offset=offset)
    total_channels = await get_channels_count()
    
    if total_channels == 0:
         await callback.message.edit_text("📋 Hozircha majburiy kanallar yo'q.", reply_markup=get_back_keyboard("admin_channels"))
         return
         
    total_pages = (total_channels + PER_PAGE - 1) // PER_PAGE
    
    text = f"📋 <b>Kanallar ro'yxati (Jami: {total_channels} ta)</b>\n\nSahifa: {page + 1}/{total_pages}\n\n"
    
    keyboard = get_pagination_keyboard(page, total_pages, "admin_list_channels").inline_keyboard
    
    # Prepend delete buttons
    del_row = []
    for ch in channels:
        text += f"🔹 <b>{ch['title']}</b>\n  ID: <code>{ch['channel_id']}</code>\n  URL: {ch['url']}\n\n"
        del_row.append([InlineKeyboardButton(text=f"🗑 O'chirish: {ch['title'][:15]}", callback_data=f"admin_del_channel:{ch['channel_id']}:{page}")])
        
    keyboard = del_row + keyboard
    markup = InlineKeyboardMarkup(inline_keyboard=keyboard)
        
    await callback.message.edit_text(text, disable_web_page_preview=True, reply_markup=markup, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("admin_del_channel:"))
async def delete_channel(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
        
    parts = callback.data.split(":")
    channel_id = parts[1]
    page = parts[2]
    
    success = await remove_channel(channel_id)
    if success:
        await callback.answer("✅ Kanal olib tashlandi!", show_alert=True)
        # Refresh the list
        callback.data = f"admin_list_channels:{page}"
        await list_channels(callback)
    else:
        await callback.answer("❌ Bunday kanal bazada topilmadi.", show_alert=True)
