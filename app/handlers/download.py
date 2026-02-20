import os
import hashlib
from aiogram import Router, F, types
from aiogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile,
    InlineQuery, InlineQueryResultVideo, InlineQueryResultAudio
)
from aiogram.fsm.context import FSMContext
from app.database import get_cached_media, save_cached_video, save_cached_audio
from app.utils.downloader import async_download_video, async_extract_audio, cleanup

router = Router()

def get_url_hash(url: str) -> str:
    """Generate MD5 hash for URL to use as DB Key"""
    return hashlib.md5(url.encode('utf-8')).hexdigest()

@router.message(F.text)
async def handle_video_url(message: Message, state: FSMContext):
    # Ignore if user is currently in any FSM state (like adding channels)
    current_state = await state.get_state()
    if current_state is not None:
        return
        
    url = message.text.strip()
    is_instagram = "instagram.com" in url
    is_tiktok = "tiktok.com" in url
    is_twitter = "twitter.com" in url or "x.com" in url
    is_youtube = "youtube.com" in url or "youtu.be" in url
    
    if not (is_instagram or is_youtube or is_tiktok or is_twitter):
        await message.reply("Iltimos, to'g'ri (Instagram, YouTube, TikTok yoki X/Twitter) havolasini yuboring.")
        return

    loader_message = await message.answer("Video tekshirilmoqda...", disable_notification=True)
    
    # 1. Check Cache
    url_hash = get_url_hash(url)
    cached_data = await get_cached_media(url_hash)
    
    if cached_data and cached_data.get('video_file_id'):
        video_id = cached_data['video_file_id']
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Audioni yuklab olish", callback_data=f"audio:{url_hash}")],
            [InlineKeyboardButton(text="↗️ Do'stlarga ulashish", switch_inline_query=f"zo'r bot ekan")]
        ])
        await message.answer_video(
            video_id, 
            caption="Video keshdan yuklandi! ⚡", 
            reply_markup=markup
        )
        await loader_message.delete()
        return

    # 2. Download from scratch
    await loader_message.edit_text("Video yuklanmoqda... Kuting ⏳")
    
    result = await async_download_video(url, is_instagram)
    if not result["success"]:
        await message.reply(f"Uzr, videoni yuklab bo'lmadi.\nXato: {result.get('error')}")
        await loader_message.delete()
        return
        
    video_path = result["video_path"]
    caption = result["caption"]
    
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Audioni yuklab olish", callback_data=f"audio:{url_hash}")],
        [InlineKeyboardButton(text="↗️ Do'stlarga ulashish", switch_inline_query=f"zo'r bot ekan")]
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
        await message.reply("Kechirasiz, videoni yuklash jarayonida potentsial xatolik yuz berdi.")
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
    if cached_data and cached_data.get('audio_file_id'):
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↗️ Do'stlarga ulashish", switch_inline_query=f"zo'r bot ekan")]
        ])
        await callback.message.answer_audio(
            cached_data['audio_file_id'], 
            caption="Audio yuklandi! ⚡",
            reply_markup=markup
        )
        await callback.answer()
        return

    if not cached_data or not cached_data.get('video_file_id'):
         await callback.answer("Video ID si eskirgan. Qaytadan video havolasini yuboring.", show_alert=True)
         return
         
    video_file_id = cached_data['video_file_id']
    await callback.answer("Audio tayyorlanmoqda ⏳")
    audio_loader = await callback.message.answer("Audio ajratilmoqda...")

    # We need to redownload video briefly to extract audio (since we deleted local MP4)
    # Getting it directly from Telegram is faster using bot.download()
    
    try:
        # Download from telegram to temp
        video = await callback.bot.get_file(video_file_id)
        temp_video_path = f"downloads/temp_{url_hash}.mp4"
        os.makedirs("downloads", exist_ok=True)
        await callback.bot.download_file(video.file_path, destination=temp_video_path)
        
        # Extract Audio
        result = await async_extract_audio(temp_video_path, f"temp_{url_hash}")
        if not result["success"]:
            await callback.message.answer(result.get("error", "Audio olinishda xatolik."))
            await audio_loader.delete()
            return
            
        audio_file = FSInputFile(result["audio_path"])
        markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="↗️ Do'stlarga ulashish", switch_inline_query=f"zo'r bot ekan")]
        ])
        sent_message = await callback.message.answer_audio(
            audio_file, 
            caption="Instagram Audio 🎵",
            performer="Smart Downloader Bot",
            reply_markup=markup
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
    
    # Check if query contains the trigger string and a hash
    if query.startswith("share_"):
        parts = query.split("_")
        if len(parts) == 3:
            media_type = parts[1] # "vid" or "aud"
            url_hash = parts[2]
            
            cached_data = await get_cached_media(url_hash)
            if not cached_data:
                return
                
            results = []
            
            if media_type == "vid" and cached_data.get('video_file_id'):
                results.append(
                    InlineQueryResultVideo(
                        id=url_hash,
                        video_file_id=cached_data['video_file_id'],
                        title="🎥 Videoni Yuborish",
                        description="Ushbu videoni do'stingizga yuboring",
                        mime_type="video/mp4" # Telegram requires this sometimes, default to mp4
                    )
                )
            elif media_type == "aud" and cached_data.get('audio_file_id'):
                 results.append(
                    InlineQueryResultAudio(
                        id=url_hash,
                        audio_file_id=cached_data['audio_file_id'],
                        title="🎵 Audioni Yuborish",
                        description="Ushbu qo'shiqni do'stingizga yuboring"
                    )
                )
                
            if results:
                await inline_query.answer(results, cache_time=300, is_personal=True)
