import os
import asyncio
import hashlib
from aiogram import Router, F, types
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
    InlineQuery, InlineQueryResultCachedVideo, InlineQueryResultCachedAudio
)
from aiogram.fsm.context import FSMContext
from app.database import get_cached_media, save_cached_video
from app.utils.downloader import async_download_video, cleanup
from app.utils.userbot import userbot, upload_large_file

router = Router()

def get_url_hash(url: str) -> str:
    """Generate MD5 hash for URL to use as DB Key"""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

async def animate_progress(message: Message, base_text: str, current_data: dict):
    """Updates progress bar in Telegram message"""
    last_text = ""
    while not current_data.get('done'):
        percent = current_data.get('percent', 0)
        speed = current_data.get('speed', 0)
        eta = current_data.get('eta', 0)
        
        # Create progress bar (20 blocks for 5% granularity)
        filled = int(percent / 5)
        bar = "█" * filled + "░" * (20 - filled)
        
        # Format speed
        speed_kb = speed / 1024
        speed_text = f"{speed_kb:.1f} KB/s" if speed_kb < 1024 else f"{speed_kb/1024:.1f} MB/s"
        
        new_text = (
            f"{base_text}\n\n"
            f"[{bar}] {percent:.1f}%\n"
            f"⚡ Tezlik: {speed_text}\n"
            f"⏳ Qolgan vaqt: {eta}s"
        )
        
        if new_text != last_text:
            try:
                await message.edit_text(new_text)
                last_text = new_text
            except Exception:
                pass
        
        await asyncio.sleep(2) # Throttling to avoid Telegram limits

@router.message(F.text)
async def handle_video_url(message: Message, state: FSMContext):
    # Ignore if user is currently in any FSM state (like adding channels)
    current_state = await state.get_state()
    if current_state is not None:
        return
        
    url = message.text.strip()
    is_instagram = "instagram.com" in url
    is_youtube = "youtube.com" in url or "youtu.be" in url
    is_twitter = "twitter.com" in url or "x.com" in url
    is_tiktok = "tiktok.com" in url
    is_facebook = "facebook.com" in url or "fb.watch" in url
    is_pinterest = "pinterest.com" in url
    
    # Generic URL check: if it's not one of the majors, just check if it looks like a URL
    if not (is_instagram or is_youtube or is_twitter or is_tiktok or is_facebook or is_pinterest or url.startswith("http")):
        await message.reply("Iltimos, video havolasini yuboring (TikTok, Instagram, YouTube, Facebook va h.k.)")
        return

    loader_message = await message.answer("Video tekshirilmoqda...", disable_notification=True)
    
    # 1. Check Cache
    url_hash = get_url_hash(url)
    cached_data = await get_cached_media(url_hash)
    
    me = await message.bot.get_me()
    
    if cached_data and cached_data.get('video_file_id'):
        video_id = cached_data['video_file_id']
        await message.answer_video(
            video_id, 
            caption=f"Video keshdan yuklandi! ⚡\n\nVia @{me.username}"
        )
        await loader_message.delete()
        return

    # 2. Download from scratch
    progress_data = {'percent': 0, 'speed': 0, 'eta': 0, 'done': False}
    
    def progress_callback(p, s, e):
        progress_data['percent'] = p
        progress_data['speed'] = s
        progress_data['eta'] = e

    progress_task = asyncio.create_task(animate_progress(loader_message, "Video yuklanmoqda...", progress_data))
    
    try:
        result = await async_download_video(url, is_youtube, progress_callback)
    finally:
        progress_data['done'] = True
        await progress_task
        
    if not result["success"]:
        await message.reply(f"Uzr, videoni yuklab bo'lmadi: {result.get('error', 'Noma`lum xatolik')}")
        await loader_message.delete()
        return
        
    video_path = result["video_path"]
    caption = result["caption"]
    if not caption:
        caption = f"Video - @{me.username}"
    else:
        caption = f"{caption}\n\nVia @{me.username}"
        
    markup = None # No buttons for now
    
    try:
        # 1. Try standard upload for files < 50MB
        video_file = FSInputFile(video_path)
        sent_message = await message.answer_video(
            video_file, 
            caption=caption
        )
        
        # Extract and Cache File ID
        file_id = sent_message.video.file_id
        await save_cached_video(url_hash, file_id, url)
        
    except Exception as e:
        # 2. Handle Large File (> 50MB) via Userbot bridge
        if "file is too large" in str(e).lower() or (os.path.exists(video_path) and os.path.getsize(video_path) > 48 * 1024 * 1024):
            if userbot:
                try:
                    await loader_message.edit_text("Fayl hajmi 50MB dan katta. Userbot orqali yuklanmoqda... 📤")
                    
                    # Restart progress for Userbot upload phase
                    progress_data['done'] = False
                    progress_task = asyncio.create_task(animate_progress(loader_message, "Userbot yuklamoqda (2GB gacha)...", progress_data))
                    
                    storage_msg = await upload_large_file(video_path, caption, progress_callback)
                    progress_data['done'] = True
                    await progress_task
                    
                    if storage_msg:
                        # Send directly by file_id (cleanest way, no 'forward' tag)
                        sent_message = await message.answer_video(
                            storage_msg.video.file_id,
                            caption=caption
                        )
                        # Cache the successful file_id
                        await save_cached_video(url_hash, sent_message.video.file_id, url)
                        return
                    else:
                        await message.reply("Userbot orqali yuklashda xatolik yuz berdi.")
                        return
                except Exception as ub_err:
                    import logging
                    logging.getLogger(__name__).error(f"Userbot fallback error: {ub_err}", exc_info=True)

        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Upload error: {e}", exc_info=True)
        await message.reply("Kechirasiz, videoni yuklashda xatolik yuz berdi. Fayl o'ta katta (2GB+) bo'lishi mumkin.")
    finally:
        # Always cleanup local storage
        if 'result' in locals() and isinstance(result, dict):
            cleanup(result.get("folder", ""))
        
        try:
            await loader_message.delete()
        except Exception:
            pass

# process_audio_callback removed

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
        
    if results:
        await inline_query.answer(results, cache_time=300, is_personal=False)
