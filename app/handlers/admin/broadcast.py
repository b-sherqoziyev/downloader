import asyncio
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext

from app.database import get_all_users, update_user_status
from .keyboards import get_back_keyboard, AdminStates, get_button_count_keyboard, get_broadcast_confirm_keyboard
from .core import is_admin

logger = logging.getLogger(__name__)
router = Router()

# Global dict to store broadcast task status
broadcast_status = {
    "is_running": False,
    "total": 0,
    "sent": 0,
    "failed": 0,
    "task": None
}

@router.callback_query(F.data == "admin_broadcast")
async def start_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
        
    if broadcast_status["is_running"]:
        text = (
            f"⚠️ <b>Diqqat!</b> Hozirda boshqa tarqatma amalga oshirilmoqda.\n\n"
            f"Jarayon: {broadcast_status['sent'] + broadcast_status['failed']} / {broadcast_status['total']}\n"
            f"✅ Yetib bordi: {broadcast_status['sent']}\n"
            f"❌ Xato/Blok: {broadcast_status['failed']}"
        )
        await callback.message.edit_text(text, reply_markup=get_back_keyboard("admin_cancel"), parse_mode='HTML')
        return

    text = (
        "📣 <b>Xabar tarqatish (Broadcast)</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni kiriting "
        "(Matn, Rasm, Video, Audio yoki Forward qilingan xabar bo'lishi mumkin):"
    )
    await callback.message.edit_text(text, reply_markup=get_back_keyboard("admin_cancel"), parse_mode='HTML')
    await state.set_state(AdminStates.waiting_for_broadcast_msg)
    await callback.answer()

@router.message(AdminStates.waiting_for_broadcast_msg)
async def process_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
        
    await state.update_data(broadcast_msg_id=message.message_id, broadcast_chat_id=message.chat.id)
    
    text = (
        "🔗 <b>Xabar ostiga URL tugma qo'shishni xohlaysizmi?</b>\n\n"
        "Tugmalar sonini tanlang (maksimal 3 ta):"
    )
    await message.answer(text, reply_markup=get_button_count_keyboard(), parse_mode='HTML')
    await state.set_state(AdminStates.waiting_for_button_count)

@router.callback_query(AdminStates.waiting_for_button_count, F.data.startswith("btn_count:"))
async def process_button_count(callback: CallbackQuery, state: FSMContext):
    count = int(callback.data.split(":")[1])
    
    if count == 0:
        await state.update_data(buttons=[])
        await show_broadcast_preview(callback.message, state)
        return
        
    await state.update_data(btn_count=count, current_btn=1, buttons=[])
    await callback.message.edit_text(
        f"1-chi tugma uchun <b>Matn</b> kiriting:",
        reply_markup=get_back_keyboard("admin_broadcast"),
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_for_button_text)
    await callback.answer()

@router.message(AdminStates.waiting_for_button_text)
async def process_button_text(message: Message, state: FSMContext):
    btn_text = message.text.strip()
    
    if len(btn_text) > 30:
        await message.answer("⚠️ Tugma matni juda uzun (max 30 belgi). Qayta kiriting:")
        return
        
    await state.update_data(temp_btn_text=btn_text)
    await message.answer(
        f"<b>'{btn_text}'</b> tugmasi uchun <b>URL</b> (Havola) kiriting:\n"
        f"<i>(Namuna: https://google.com)</i>",
        reply_markup=get_back_keyboard("admin_broadcast"),
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_for_button_url)

@router.message(AdminStates.waiting_for_button_url)
async def process_button_url(message: Message, state: FSMContext):
    url = message.text.strip()
    if not url.startswith(("http://", "https://")):
        await message.answer("⚠️ Havola 'http://' yoki 'https://' bilan boshlanishi shart. Qayta kiriting:")
        return
        
    data = await state.get_data()
    buttons = data.get("buttons", [])
    buttons.append({"text": data['temp_btn_text'], "url": url})
    
    current_btn = data['current_btn']
    btn_count = data['btn_count']
    
    if current_btn < btn_count:
        await state.update_data(buttons=buttons, current_btn=current_btn + 1)
        await message.answer(
            f"{current_btn + 1}-chi tugma uchun <b>Matn</b> kiriting:",
            reply_markup=get_back_keyboard("admin_broadcast"),
            parse_mode='HTML'
        )
        await state.set_state(AdminStates.waiting_for_button_text)
    else:
        await state.update_data(buttons=buttons)
        await show_broadcast_preview(message, state)

async def show_broadcast_preview(message: Message, state: FSMContext):
    data = await state.get_data()
    msg_id = data['broadcast_msg_id']
    chat_id = data['broadcast_chat_id']
    buttons = data.get("buttons", [])
    
    markup = None
    if buttons:
        kb = [[InlineKeyboardButton(text=b['text'], url=b['url'])] for b in buttons]
        markup = InlineKeyboardMarkup(inline_keyboard=kb)
        
    await message.answer("👁 <b>Xabar ko'rinishi (Preview):</b>")
    
    await message.bot.copy_message(
        chat_id=message.chat.id,
        from_chat_id=chat_id,
        message_id=msg_id,
        reply_markup=markup
    )
    
    await message.answer(
        "☝️ Xabar barchaga mana shunday ko'rinishda boradi. Tasdiqlaysizmi?",
        reply_markup=get_broadcast_confirm_keyboard(),
        parse_mode='HTML'
    )
    await state.set_state(AdminStates.waiting_for_broadcast_confirm)

@router.callback_query(AdminStates.waiting_for_broadcast_confirm, F.data == "admin_broadcast_preview")
async def redo_preview(callback: CallbackQuery, state: FSMContext):
    await show_broadcast_preview(callback.message, state)
    await callback.answer()

@router.callback_query(AdminStates.waiting_for_broadcast_confirm, F.data == "admin_broadcast_send")
async def finalize_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
        
    data = await state.get_data()
    users = await get_all_users(active_only=True)
    
    if not users:
        await callback.message.edit_text("Bazada faol foydalanuvchilar yo'q.", reply_markup=get_back_keyboard("admin_cancel"))
        await state.clear()
        return

    buttons = data.get("buttons", [])
    kb_markup = None
    if buttons:
        kb = [[InlineKeyboardButton(text=b['text'], url=b['url'])] for b in buttons]
        kb_markup = InlineKeyboardMarkup(inline_keyboard=kb)

    await callback.message.edit_text(
        f"🚀 Tarqatma boshlandi!\n\nJami {len(users)} ta foydalanuvchiga yuborilmoqda.",
        reply_markup=get_back_keyboard("admin_cancel")
    )
    
    task = asyncio.create_task(run_broadcast(
        bot=callback.message.bot, 
        users=users, 
        admin_id=callback.from_user.id, 
        source_chat_id=data['broadcast_chat_id'], 
        source_msg_id=data['broadcast_msg_id'], 
        reply_markup=kb_markup
    ))
    
    broadcast_status["is_running"] = True
    broadcast_status["total"] = len(users)
    broadcast_status["sent"] = 0
    broadcast_status["failed"] = 0
    broadcast_status["task"] = task
    
    await state.clear()
    await callback.answer()

async def run_broadcast(bot, users: list, admin_id: int, source_chat_id: int, source_msg_id: int, reply_markup=None):
    for user_id in users:
        try:
            await bot.copy_message(
                chat_id=user_id,
                from_chat_id=source_chat_id,
                message_id=source_msg_id,
                reply_markup=reply_markup
            )
            broadcast_status["sent"] += 1
        except Exception as e:
            logger.warning(f"Failed to send broadcast to {user_id}: {e}")
            broadcast_status["failed"] += 1
            await update_user_status(user_id, is_active=False)
            
        await asyncio.sleep(0.05)
        
    broadcast_status["is_running"] = False
    
    report = (
        f"✅ <b>Tarqatma muvaffaqiyatli yakunlandi!</b>\n\n"
        f"📊 <b>Hisobot:</b>\n"
        f"▫️ Jami baza: {broadcast_status['total']}\n"
        f"▫️ 🟢 Muvaffaqiyatli: {broadcast_status['sent']}\n"
        f"▫️ 🔴 Yetib bormadi (Bloklagan): {broadcast_status['failed']}\n\n"
        f"<i>Yuborilmaganlar avtomatik passiv holatiga o'tkazildi.</i>"
    )
    
    try:
        await bot.send_message(admin_id, report, parse_mode='HTML')
    except Exception:
        pass
