from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.state import State, StatesGroup

class AdminStates(StatesGroup):
    # Channel States
    waiting_for_channel_data = State()
    waiting_for_remove_id = State()
    
    # Broadcast States
    waiting_for_broadcast_msg = State()
    waiting_for_button_count = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_broadcast_confirm = State()
    
    # User Management States
    waiting_for_user_search = State()
    waiting_for_user_message = State()

def get_admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin_stats")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar b-vi", callback_data="admin_users")],
        [InlineKeyboardButton(text="📣 Tarqatish (Broadcast)", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔗 Majburiy Kanallar", callback_data="admin_channels")],
    ])

def get_cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
    ])

def get_users_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔍 Foydalanuvchini qidirish", callback_data="admin_users_search")],
        [InlineKeyboardButton(text="📋 Foydalanuvchilar ro'yxati", callback_data="admin_list_users:0")],
        [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_cancel")]
    ])

def get_back_keyboard(callback_data: str):
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data=callback_data)]
    ])

def get_channels_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kanal qo'shish", callback_data="admin_add_channel")],
        [InlineKeyboardButton(text="📋 Kanallar ro'yxati", callback_data="admin_list_channels:0")],
        [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="admin_cancel")]
    ])

def get_pagination_keyboard(current_page: int, total_pages: int, prefix: str):
    buttons = []
    nav_row = []
    
    if current_page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"{prefix}:{current_page - 1}"))
        
    nav_row.append(InlineKeyboardButton(text=f"{current_page + 1}/{total_pages}", callback_data="ignore"))
    
    if current_page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"{prefix}:{current_page + 1}"))
        
    buttons.append(nav_row)
    
    back_callback = "admin_cancel"
    if "list_channels" in prefix:
        back_callback = "admin_channels"
    elif "list_users" in prefix:
        back_callback = "admin_users"
        
    buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data=back_callback)])
    
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_user_manage_keyboard(user_id: int, is_banned: bool, page: int = None):
    ban_text = "🟢 Bandan Olish" if is_banned else "🔴 Ban Qilish"
    suffix = f":{page}" if page is not None else ""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=ban_text, callback_data=f"admin_toggle_ban:{user_id}{suffix}")],
        [InlineKeyboardButton(text="✉️ Xabar Yozish", callback_data=f"admin_msg_user:{user_id}{suffix}")],
        [InlineKeyboardButton(text="🔙 Orqaga", callback_data="admin_users")]
    ])

def get_button_count_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="0 ta (Tugmasiz)", callback_data="btn_count:0")],
        [InlineKeyboardButton(text="1 ta", callback_data="btn_count:1"), InlineKeyboardButton(text="2 ta", callback_data="btn_count:2")],
        [InlineKeyboardButton(text="3 ta", callback_data="btn_count:3")],
        [InlineKeyboardButton(text="🔙 Bekor qilish", callback_data="admin_cancel")]
    ])

def get_broadcast_confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Yuborishni boshlash", callback_data="admin_broadcast_send")],
        [InlineKeyboardButton(text="👁 Qayta Preview", callback_data="admin_broadcast_preview")],
        [InlineKeyboardButton(text="❌ Bekor qilish", callback_data="admin_cancel")]
    ])
