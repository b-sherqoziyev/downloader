import os
import shutil
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
from app.config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# Create a larger thread pool for higher concurrency
executor = ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) * 4))

def cleanup(folder_path):
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)
            logger.info(f"Cleaned up: {folder_path}")
    except Exception as e:
        logger.error(f"Error cleaning up {folder_path}: {e}")

def sync_download_video(url, is_youtube, progress_callback=None):
    request_id = str(uuid.uuid4())
    final_download_path = os.path.join(DOWNLOADS_DIR, request_id)
    os.makedirs(final_download_path, exist_ok=True)
    
    # Progress hook for yt-dlp
    def ydl_progress_hook(d):
        if d['status'] == 'downloading' and progress_callback:
            p = d.get('downloaded_bytes', 0)
            total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
            if total > 0:
                percent = (p / total) * 100
                speed = d.get('speed', 0)
                eta = d.get('eta', 0)
                progress_callback(percent, speed, eta)
    
    try:
        from app.config import PO_TOKEN, VISITOR_DATA
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(final_download_path, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'progress_hooks': [ydl_progress_hook],
            'extractor_args': {
                'youtube': { 
                    'player_client': ['android', 'ios', 'web'],
                    'po_token': [PO_TOKEN] if PO_TOKEN else None,
                    'visitor_data': VISITOR_DATA if VISITOR_DATA else None
                },
                'pinterest': { 'referer': ['https://www.pinterest.com/'] }
            }
        }
        
        # Check for cookies.txt
        if os.path.exists('cookies.txt'):
            ydl_opts['cookiefile'] = 'cookies.txt'
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            title = info.get('title', 'Video')
            caption = title[:1021] + "..." if len(title) > 1024 else title
                
        video_path = None
        for root, dirs, files in os.walk(final_download_path):
            for file in files:
                if file.endswith((".mp4", ".webm", ".mkv", ".mov")):
                    video_path = os.path.join(root, file)
                    break
            if video_path: break
                
        if not video_path:
            raise ValueError("Video topilmadi")
            
        return {
            "success": True, 
            "video_path": video_path, 
            "caption": caption, 
            "request_id": request_id, 
            "folder": final_download_path
        }
        
    except Exception as e:
        logger.error(f"Sync download error: {e}")
        cleanup(final_download_path)
        return {"success": False, "error": "Yuklab bo'lmadi ❌"}

async def async_download_video(url, is_youtube, progress_callback=None):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, sync_download_video, url, is_youtube, progress_callback)

# Video extraction logic ends here
