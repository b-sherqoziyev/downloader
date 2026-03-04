import os
import shutil
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
import instaloader
from moviepy import VideoFileClip
from app.config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# Create a thread pool so sync downloading doesn't block the async event loop
executor = ThreadPoolExecutor(max_workers=5)

def cleanup(folder_path):
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)
            logger.info(f"Cleaned up: {folder_path}")
    except Exception as e:
        logger.error(f"Error cleaning up {folder_path}: {e}")

def sync_download_video(url, is_instagram):
    request_id = str(uuid.uuid4())
    download_target_folder = request_id
    final_download_path = os.path.join(DOWNLOADS_DIR, request_id)
    os.makedirs(final_download_path, exist_ok=True)
    
    caption = ""
    video_path = None
    
    # Progress hook for yt-dlp
    def ydl_progress_hook(d):
        if d['status'] == 'downloading':
            p = d.get('_percent_str', '0%')
            s = d.get('_speed_str', 'N/A')
            t = d.get('_eta_str', 'N/A')
            # logger.info(f"Downloading: {p} at {s} ETA {t}")
            # We can't easily call async from here without more glue, 
            # but we can log it or use a shared state.
    
    try:
        if is_instagram:
            if "/reel/" in url:
                shortcode = url.split("/reel/")[1].split("/")[0]
            elif "/p/" in url:
                shortcode = url.split("/p/")[1].split("/")[0]
            else:
                raise ValueError("Havola formati noto'g'ri.")
                
            local_loader = instaloader.Instaloader(
                download_comments=False,
                download_geotags=False,
                download_pictures=False,
                download_video_thumbnails=False,
                save_metadata=False,
                compress_json=False
            )
            post = instaloader.Post.from_shortcode(local_loader.context, shortcode)
            local_loader.download_post(post, target=download_target_folder)
            
            if os.path.exists(download_target_folder):
                for item in os.listdir(download_target_folder):
                    shutil.move(os.path.join(download_target_folder, item), final_download_path)
                shutil.rmtree(download_target_folder, ignore_errors=True)
                
            raw_caption = post.caption if post.caption else ""
            caption = raw_caption[:1021] + "..." if len(raw_caption) > 1024 or len(raw_caption) < 1 else raw_caption
            # Note: bot_username will be handled in the handler now
            
        else: # is_youtube
            ydl_opts = {
                'format': 'best',
                'outtmpl': os.path.join(final_download_path, '%(title)s.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'nocheckcertificate': True,
                'extractor_args': {
                    'youtube': {
                        'player_client': ['android', 'ios'],
                        'skip': ['hls', 'dash']
                    }
                },
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                title = info.get('title', 'Video')
                caption = title[:1021] + "..." if len(title) > 1024 else title
                
        # Find video
        for root, dirs, files in os.walk(final_download_path):
            for file in files:
                if file.endswith((".mp4", ".webm", ".mkv")):
                    video_path = os.path.join(root, file)
                    break
            if video_path:
                break
                
        if not video_path:
            raise ValueError("Video topilmadi")
            
        return {"success": True, "video_path": video_path, "caption": caption, "request_id": request_id, "folder": final_download_path}
        
    except Exception as e:
        logger.error(f"Sync download error: {e}")
        cleanup(download_target_folder)
        cleanup(final_download_path)
        return {"success": False, "error": str(e)}

async def async_download_video(url, is_instagram):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, sync_download_video, url, is_instagram)

def sync_extract_audio(video_path, request_id, bot_name="Bot"):
    final_download_path = os.path.join(DOWNLOADS_DIR, request_id)
    os.makedirs(final_download_path, exist_ok=True)
    safe_name = bot_name.replace(" ", "_").replace("/", "_")
    audio_path = os.path.join(final_download_path, f"{safe_name}.mp3")
    
    try:
        video_clip = VideoFileClip(video_path)
        if video_clip.audio is None:
            video_clip.close()
            return {"success": False, "error": "Bu videoda audio mavjud emas."}
            
        video_clip.audio.write_audiofile(audio_path, logger=None)
        video_clip.close()
        
        return {"success": True, "audio_path": audio_path, "folder": final_download_path}
    except Exception as e:
        logger.error(f"Sync extract audio error: {e}")
        return {"success": False, "error": str(e)}

async def async_extract_audio(video_path, request_id, bot_name="Bot"):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, sync_extract_audio, video_path, request_id, bot_name)
