import logging
from typing import Any, Callable, Dict, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from app.database import get_all_channels
from app.config import ADMIN_ID

logger = logging.getLogger(__name__)

class CheckSubscriptionMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[Message, Dict[str, Any]], Awaitable[Any]],
        event: Message,
        data: Dict[str, Any]
    ) -> Any:
        
        if not isinstance(event, Message) or not event.text:
            return await handler(event, data)
            
        text = event.text.lower()
        if text.startswith(('/admin', '/addchannel', '/delchannel', '/channels', '/broadcast')):
            return await handler(event, data)
            
        user_id = event.from_user.id
        
        # Bypass check completely for the admin
        if ADMIN_ID and user_id == ADMIN_ID:
            return await handler(event, data)
            
        channels = await get_all_channels()
        
        if not channels:
            # No mandatory channels, proceed
            return await handler(event, data)
            
        unsubscribed_channels = []
        
        for ch in channels:
            try:
                member_status = await event.bot.get_chat_member(chat_id=ch['channel_id'], user_id=user_id)
                # Check if member left or got kicked
                if member_status.status in ['left', 'kicked', 'banned']:
                    unsubscribed_channels.append(ch)
            except Exception as e:
                # If bot is not admin in channel, or chat not found, we assume they must subscribe
                # However, to avoid spamming errors, we add it to the list
                unsubscribed_channels.append(ch)
                if "chat not found" not in str(e).lower():
                    logger.warning(f"Could not check membership for {ch['channel_id']}: {e}")
                
        if unsubscribed_channels:
            buttons = []
            for ch in unsubscribed_channels:
                buttons.append([InlineKeyboardButton(text=ch['title'], url=ch['url'])])
            
            # Add a check button at the bottom
            buttons.append([InlineKeyboardButton(text="🔄 Tekshirish", callback_data="check_subscription")])
                
            markup = InlineKeyboardMarkup(inline_keyboard=buttons)
            text_msg = "Botdan to‘liq foydalanish uchun quyidagi kanallarga obuna bo‘ling!"
            
            if event.text:
                await event.answer(text_msg, reply_markup=markup)
            
            # Stop propagation
            return
            
        # User is subbed to all, proceed
        return await handler(event, data)
