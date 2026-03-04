from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from app.database import get_user, update_user_status, get_users_paginated, get_users_total_count
from .keyboards import get_back_keyboard, get_user_manage_keyboard, AdminStates, get_users_menu_keyboard, get_pagination_keyboard
from .core import is_admin

router = Router()

@router.callback_query(F.data == "admin_users")
async def admin_users_menu(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
        
    await state.clear()
    text = "👥 <b>Foydalanuvchilarni Boshqarish</b>\n\nQuyidagi amallardan birini tanlang:"
    await callback.message.edit_text(text, reply_markup=get_users_menu_keyboard(), parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data == "admin_users_search")
async def admin_users_search_start(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
        
    text = (
        "🔍 <b>Foydalanuvchini qidirish</b>\n\n"
        "Foydalanuvchi ID raqamini yoki Usernameni (@ bilan yoki belgisiz) yuboring:"
    )
    await callback.message.edit_text(text, reply_markup=get_back_keyboard("admin_users"), parse_mode='HTML')
    await state.set_state(AdminStates.waiting_for_user_search)
    await callback.answer()

@router.callback_query(F.data.startswith("admin_list_users:"))
async def admin_list_users(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
        
    page = int(callback.data.split(":")[1])
    limit = 10
    offset = page * limit
    
    users = await get_users_paginated(limit=limit, offset=offset)
    total_users = await get_users_total_count()
    
    if total_users == 0:
        await callback.message.edit_text("📋 Bazada foydalanuvchilar yo'q.", reply_markup=get_back_keyboard("admin_users"))
        return
        
    total_pages = (total_users + limit - 1) // limit
    
    text = f"📋 <b>Foydalanuvchilar ro'yxati</b> (Jami: {total_users} ta)\n\n"
    text += f"Sahifa: {page + 1}/{total_pages}\n\n"
    
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    keyboard = get_pagination_keyboard(page, total_pages, "admin_list_users").inline_keyboard
    
    user_rows = []
    for user in users:
        u_name = user['username'] if user['username'] else "yo'q"
        name = user['first_name'] if user['first_name'] else "isimsiz"
        # Truncate name if too long
        if len(name) > 15:
            name = name[:12] + "..."
            
        btn_text = f"👤 {name} (@{u_name})"
        user_rows.append([InlineKeyboardButton(text=btn_text, callback_data=f"admin_view_user:{user['user_id']}:{page}")])
        
    # Combine user buttons with pagination
    final_keyboard = user_rows + keyboard
    markup = InlineKeyboardMarkup(inline_keyboard=final_keyboard)
    
    await callback.message.edit_text(text, reply_markup=markup, parse_mode='HTML')
    await callback.answer()

@router.callback_query(F.data.startswith("admin_view_user:"))
async def admin_view_user_from_list(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
        
    parts = callback.data.split(":")
    user_id = parts[1]
    page = parts[2]
    
    user = await get_user(user_id)
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
        
    status_text = "🟢 Aktiv" if user['is_active'] else "🔴 Passiv (Botni bloklagan)"
    ban_text = "🚷 Ha" if user['is_banned'] else "✅ Yo'q"
    username_str = f"@{user['username']}" if user['username'] else "yo'q"
    
    info_msg = (
        f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
        f"<b>ID:</b> <code>{user['user_id']}</code>\n"
        f"<b>Ismi:</b> {user['first_name']}\n"
        f"<b>Username:</b> {username_str}\n"
        f"<b>Qo'shilgan:</b> {user['joined_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
        f"<b>Holat:</b> {status_text}\n"
        f"<b>Ban qilinganmi?:</b> {ban_text}"
    )
    
    # Custom back button to return to the list at the correct page
    markup = get_user_manage_keyboard(user['user_id'], user['is_banned'], page=int(page))
    custom_keyboard = markup.inline_keyboard[:-1] # Remove original back
    custom_keyboard.append([InlineKeyboardButton(text="🔙 Ro'yxatga qaytish", callback_data=f"admin_list_users:{page}")])
    
    await callback.message.edit_text(info_msg, reply_markup=InlineKeyboardMarkup(inline_keyboard=custom_keyboard), parse_mode='HTML')
    await callback.answer()

@router.message(AdminStates.waiting_for_user_search)
async def process_user_search(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
        
    search_query = message.text.strip()
    user = await get_user(search_query)
    
    if not user:
        await message.answer(
            "❌ Bunday foydalanuvchi topilmadi. Boshqa ID yoki Username kiritib ko'ring:",
            reply_markup=get_back_keyboard("admin_cancel")
        )
        return
        
    status_text = "🟢 Aktiv" if user['is_active'] else "🔴 Passiv (Botni bloklagan)"
    ban_text = "🚷 Ha" if user['is_banned'] else "✅ Yo'q"
    username_str = f"@{user['username']}" if user['username'] else "yo'q"
    
    info_msg = (
        f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
        f"<b>ID:</b> <code>{user['user_id']}</code>\n"
        f"<b>Ismi:</b> {user['first_name']}\n"
        f"<b>Username:</b> {username_str}\n"
        f"<b>Qo'shilgan:</b> {user['joined_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
        f"<b>Holat:</b> {status_text}\n"
        f"<b>Ban qilinganmi?:</b> {ban_text}"
    )
    
    await message.answer(
        info_msg, 
        reply_markup=get_user_manage_keyboard(user['user_id'], user['is_banned']),
        parse_mode='HTML'
    )
    # We clear state here so they don't keep searching automatically
    await state.clear()

@router.callback_query(F.data.startswith("admin_toggle_ban:"))
async def toggle_user_ban(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
        
    parts = callback.data.split(":")
    user_id = int(parts[1])
    
    # Check if we have page context
    page = parts[2] if len(parts) > 2 else None
    
    user = await get_user(str(user_id))
    
    if not user:
        await callback.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return
        
    new_status = not user['is_banned']
    await update_user_status(user_id, is_banned=new_status)
    
    action_text = "Ban qilindi 🔴" if new_status else "Bandan olindi 🟢"
    await callback.answer(f"Foydalanuvchi {action_text}", show_alert=True)
    
    # Reload the message with the updated status
    user['is_banned'] = new_status
    status_text = "🟢 Aktiv" if user['is_active'] else "🔴 Passiv (Botni bloklagan)"
    ban_text = "🚷 Ha" if user['is_banned'] else "✅ Yo'q"
    username_str = f"@{user['username']}" if user['username'] else "yo'q"
    
    info_msg = (
        f"👤 <b>Foydalanuvchi ma'lumotlari:</b>\n\n"
        f"<b>ID:</b> <code>{user['user_id']}</code>\n"
        f"<b>Ismi:</b> {user['first_name']}\n"
        f"<b>Username:</b> {username_str}\n"
        f"<b>Qo'shilgan:</b> {user['joined_at'].strftime('%Y-%m-%d %H:%M')}\n\n"
        f"<b>Holat:</b> {status_text}\n"
        f"<b>Ban qilinganmi?:</b> {ban_text}"
    )
    
    # Reload keyboard with context
    if page is not None:
        markup = get_user_manage_keyboard(user['user_id'], user['is_banned'], page=int(page))
        custom_keyboard = markup.inline_keyboard[:-1]
        custom_keyboard.append([InlineKeyboardButton(text="🔙 Ro'yxatga qaytish", callback_data=f"admin_list_users:{page}")])
        reply_markup = InlineKeyboardMarkup(inline_keyboard=custom_keyboard)
    else:
        reply_markup = get_user_manage_keyboard(user['user_id'], user['is_banned'])

    await callback.message.edit_text(
        info_msg, 
        reply_markup=reply_markup,
        parse_mode='HTML'
    )

@router.callback_query(F.data.startswith("admin_msg_user:"))
async def process_msg_user(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
        
    parts = callback.data.split(":")
    user_id = int(parts[1])
    page = parts[2] if len(parts) > 2 else None
    
    text = (
        f"✍️ <code>{user_id}</code> raqamli foydalanuvchiga yubormoqchi bo'lgan xabaringizni kiriting:\n\n"
        f"<i>(Matn, rasm, video jo'natishingiz mumkin)</i>"
    )
    
    back_callback = f"admin_list_users:{page}" if page else "admin_users"
    await callback.message.edit_text(text, reply_markup=get_back_keyboard(back_callback), parse_mode='HTML')
    await state.update_data(target_user_id=user_id, back_callback=back_callback)
    await state.set_state(AdminStates.waiting_for_user_message)
    await callback.answer()

@router.message(AdminStates.waiting_for_user_message)
async def send_direct_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
        
    data = await state.get_data()
    target_user_id = data.get("target_user_id")
    back_callback = data.get("back_callback", "admin_users")
    
    try:
        await message.send_copy(chat_id=target_user_id)
        await message.answer(f"✅ Xabar <code>{target_user_id}</code> ga muvaffaqiyatli yuborildi!", reply_markup=get_back_keyboard(back_callback), parse_mode='HTML')
    except Exception as e:
        await message.answer(f"❌ Xatolik yuz berdi. Foydalanuvchi botni bloklagan bo'lishi mumkin.\n\n{e}", reply_markup=get_back_keyboard(back_callback))
        
    await state.clear()
