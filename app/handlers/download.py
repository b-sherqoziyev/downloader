import os
import asyncio
import hashlib
from aiogram import Router, F, types
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
    InlineQuery, InlineQueryResultCachedVideo, InlineQueryResultCachedAudio
)
from aiogram.fsm.context import FSMContext
from app.database import get_cached_media, save_cached_video, save_cached_audio
from app.utils.downloader import async_download_video, async_extract_audio, cleanup

router = Router()

def get_url_hash(url: str) -> str:
    """Generate MD5 hash for URL to use as DB Key"""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

async def animate_loading(message: Message, stop_event: asyncio.Event, base_text: str):
    """Animates a message with moving dots while download is in progress"""
    chars = ["🌑", "🌒", "🌓", "🌔", "🌕", "🌖", "🌗", "🌘"]
    idx = 0
    try:
        while not stop_event.is_set():
            await message.edit_text(f"{base_text} {chars[idx % len(chars)]}")
            idx += 1
            await asyncio.sleep(1)
    except Exception:
        pass

@router.message(F.text)
async def handle_video_url(message: Message, state: FSMContext):
    # Ignore if user is currently in any FSM state (like adding channels)
    current_state = await state.get_state()
    if current_state is not None:
        return
        
    url = message.text.strip()
    is_instagram = "instagram.com" in url
    is_twitter = "twitter.com" in url or "x.com" in url
    is_youtube = "youtube.com" in url or "youtu.be" in url
    
    if not (is_instagram or is_youtube or is_twitter):
        await message.reply("Iltimos, to'g'ri (Instagram, YouTube yoki X/Twitter) havolasini yuboring.")
        return

    loader_message = await message.answer("Video tekshirilmoqda...", disable_notification=True)
    
    # 1. Check Cache
    url_hash = get_url_hash(url)
    cached_data = await get_cached_media(url_hash)
    
    me = await message.bot.get_me()
    
    if cached_data and cached_data.get('video_file_id'):
        video_id = cached_data['video_file_id']
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Audioni yuklab olish", callback_data=f"audio:{url_hash}")],
        ])
        await message.answer_video(
            video_id, 
            caption=f"Video keshdan yuklandi! ⚡\n\nVia @{me.username}", 
            reply_markup=markup
        )
        await loader_message.delete()
        return

    # 2. Download from scratch
    stop_event = asyncio.Event()
    base_text = "Video yuklanmoqda..."
    animation_task = asyncio.create_task(animate_loading(loader_message, stop_event, base_text))
    
    try:
        result = await async_download_video(url, is_instagram)
    finally:
        stop_event.set()
        await animation_task
        
    if not result["success"]:
        await message.reply(f"Uzr, videoni yuklab bo'lmadi.")
        await loader_message.delete()
        return
        
    video_path = result["video_path"]
    caption = result["caption"]
    if not caption:
        caption = f"Video - @{me.username}"
    else:
        caption = f"{caption}\n\nVia @{me.username}"
        
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Audioni yuklab olish", callback_data=f"audio:{url_hash}")],
    ])
    
    try:
        # Send video and get message objects back to save File ID
        video_file = FSInputFile(video_path)
        sent_message = await message.answer_video(
            video_file, 
            caption=caption, 
            reply_markup=markup
        )
        
        # Extract File ID
        file_id = sent_message.video.file_id
        await save_cached_video(url_hash, file_id)
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Telegramga yuklashda xatolik: {e}")
        await message.reply("Kechirasiz, videoning hajmi katta.")
    finally:
        # Always cleanup the heavy MP4 file
        cleanup(result.get("folder", ""))
        try:
            await loader_message.delete()
        except Exception:
            pass

@router.callback_query(F.data.startswith("audio:"))
async def process_audio_callback(callback: types.CallbackQuery):
    url_hash = callback.data.split(":")[1]
    
    # 1. Check Audio Cache
    cached_data = await get_cached_media(url_hash)
    me = await callback.bot.get_me()
    
    if cached_data and cached_data.get('audio_file_id'):
        await callback.message.answer_audio(
            cached_data['audio_file_id'], 
            caption=f"🎵 {me.full_name} orqali yuklab olindi",
            performer=me.full_name
        )
        await callback.answer()
        return

    if not cached_data or not cached_data.get('video_file_id'):
         await callback.answer("Video ID si eskirgan. Qaytadan video havolasini yuboring.", show_alert=True)
         return
         
    video_file_id = cached_data['video_file_id']
    await callback.answer("Audio tayyorlanmoqda ⏳")
    audio_loader = await callback.message.answer("Audio ajratilmoqda...")

    # Animation and Process
    stop_event = asyncio.Event()
    animation_task = asyncio.create_task(animate_loading(audio_loader, stop_event, "Audio ajratilmoqda..."))
    
    try:
        # Download from telegram to temp
        video = await callback.bot.get_file(video_file_id)
        temp_video_path = f"downloads/temp_{url_hash}.mp4"
        os.makedirs("downloads", exist_ok=True)
        await callback.bot.download_file(video.file_path, destination=temp_video_path)
        
        # Extract Audio
        result = await async_extract_audio(temp_video_path, f"temp_{url_hash}", me.full_name)
        
        # Stop animation before proceeding with results
        stop_event.set()
        await animation_task
        
        if not result["success"]:
            await callback.message.answer(result.get("error", "Audio olinishda xatolik."))
            return
            
        audio_file = FSInputFile(result["audio_path"])
        sent_message = await callback.message.answer_audio(
            audio_file, 
            caption=f"🎵 {me.full_name} orqali yuklab olindi",
            performer=me.full_name
        )
        
        audio_id = sent_message.audio.file_id
        await save_cached_audio(url_hash, audio_id)
        
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Audio xatoligi: {e}")
        try:
            await callback.message.answer("Kechirasiz, audioni yuklash jarayonida xatolik yuz berdi. Iltimos, keyinroq qayta urinib ko'ring.")
        except Exception:
            pass
    finally:
        # Stop animation if it's still running (in case of exception)
        if not stop_event.is_set():
            stop_event.set()
            await animation_task
            
        # Cleanup
        try:
            if 'temp_video_path' in locals() and os.path.exists(temp_video_path):
                os.remove(temp_video_path)
            if 'result' in locals() and isinstance(result, dict):
                cleanup(result.get("folder", ""))
        except Exception:
            pass
            
        try:
            await audio_loader.delete()
        except Exception:
            pass

@router.inline_query()
async def process_inline_query(inline_query: InlineQuery):
    query = inline_query.query.strip()
    
    # Check for vid_HASH or aud_HASH
    if "_" not in query:
        return
        
    parts = query.split("_")
    if len(parts) != 2:
        return
        
    media_type, url_hash = parts
    
    cached_data = await get_cached_media(url_hash)
    if not cached_data:
        return
        
    me = await inline_query.bot.get_me()
    results = []
    
    if media_type == "vid" and cached_data.get('video_file_id'):
        results.append(
            InlineQueryResultCachedVideo(
                id=url_hash,
                video_file_id=cached_data['video_file_id'],
                title="🎥 Videoni ulashish",
                description="Do'stingizga yuborish uchun ustiga bosing",
                caption=f"Video via @{me.username}"
            )
        )
    elif media_type == "aud" and cached_data.get('audio_file_id'):
         results.append(
            InlineQueryResultCachedAudio(
                id=url_hash,
                audio_file_id=cached_data['audio_file_id'],
                title="🎵 Audioni ulashish",
                caption=f"Audio via @{me.username}"
            )
        )
        
    if results:
        await inline_query.answer(results, cache_time=300, is_personal=False)
