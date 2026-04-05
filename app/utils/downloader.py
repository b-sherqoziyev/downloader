import os
import shutil
import uuid
import asyncio
import logging
import aiohttp
from datetime import datetime, timezone, timedelta
from concurrent.futures import ThreadPoolExecutor
import yt_dlp
from app.config import DOWNLOADS_DIR

logger = logging.getLogger(__name__)

# Create a larger thread pool for higher concurrency
executor = ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 1) * 4))

COBALT_URL = "https://api.cobalt.tools/api/json"

def cleanup(folder_path):
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)
            logger.info(f"Cleaned up: {folder_path}")
    except Exception as e:
        logger.error(f"Error cleaning up {folder_path}: {e}")

async def download_via_cobalt(url, final_download_path, progress_callback=None):
    """Try to download using Cobalt API which handles most bypasses."""
    try:
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        payload = {
            "url": url,
            "videoQuality": "1080",
            "filenameStyle": "pretty"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(COBALT_URL, json=payload, headers=headers, timeout=60) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.warning(f"Cobalt API returned {resp.status}: {text}")
                    return None
                
                data = await resp.json()
                if data.get("status") not in ["stream", "redirect", "picker"]:
                    logger.warning(f"Cobalt API status not stream/redirect: {data}")
                    return None
                
                # Some videos return multiple links (picker), we take the first high quality one
                if data.get("status") == "picker":
                    download_url = data["picker"][0]["url"]
                else:
                    download_url = data["url"]

                # Now download the actual file from Cobalt's processed link
                async with session.get(download_url, timeout=300) as video_resp:
                    if video_resp.status != 200:
                        return None
                    
                    filename = data.get("filename") or f"video_{uuid.uuid4().hex[:8]}.mp4"
                    # Ensure filename doesn't have illegal chars
                    filename = "".join(c for c in filename if c.isalnum() or c in "._- ").strip()
                    file_path = os.path.join(final_download_path, filename)
                    
                    total_size = int(video_resp.headers.get("content-length", 0))
                    downloaded = 0
                    
                    with open(file_path, "wb") as f:
                        async for chunk in video_resp.content.iter_chunked(1024 * 64):
                            if chunk:
                                f.write(chunk)
                                downloaded += len(chunk)
                                if progress_callback and total_size > 0:
                                    percent = (downloaded / total_size) * 100
                                    # ETA and Speed estimation omitted for simplicity in Cobalt mode
                                    progress_callback(percent, 0, 0)
                                    
                    return {
                        "video_path": file_path,
                        "caption": data.get("filename") or "Video @yt_savers_bot"
                    }
    except Exception as e:
        logger.error(f"Cobalt download error: {e}")
        return None

def sync_download_video_yt_dlp(url, final_download_path, progress_callback=None):
    """Original yt-dlp logic as fallback."""
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
        ydl_opts = {
            'format': 'bestvideo+bestaudio/best',
            'outtmpl': os.path.join(final_download_path, '%(title)s.%(ext)s'),
            'quiet': True,
            'no_warnings': True,
            'nocheckcertificate': True,
            'progress_hooks': [ydl_progress_hook],
            'extractor_args': {
                'youtube': { 'player_client': ['android', 'ios', 'web'] },
                'pinterest': { 'referer': ['https://www.pinterest.com/'] }
            }
        }
        
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
                
        if not video_path: return None
            
        return {"success": True, "video_path": video_path, "caption": caption}
    except Exception as e:
        logger.error(f"yt-dlp fallback error: {e}")
        return None

async def async_download_video(url, is_youtube, progress_callback=None):
    request_id = str(uuid.uuid4())
    final_download_path = os.path.join(DOWNLOADS_DIR, request_id)
    os.makedirs(final_download_path, exist_ok=True)
    
    try:
        # 1. Try Cobalt first (The Professional Way)
        logger.info(f"Attempting Cobalt download for {url}")
        cobalt_result = await download_via_cobalt(url, final_download_path, progress_callback)
        
        if cobalt_result:
            logger.info(f"Cobalt download successful for {url}")
            return {
                "success": True, 
                "video_path": cobalt_result["video_path"], 
                "caption": cobalt_result["caption"], 
                "request_id": request_id, 
                "folder": final_download_path
            }
        
        # 2. Fallback to yt-dlp
        logger.info(f"Cobalt failed, falling back to yt-dlp for {url}")
        loop = asyncio.get_running_loop()
        yt_result = await loop.run_in_executor(executor, sync_download_video_yt_dlp, url, final_download_path, progress_callback)
        
        if yt_result:
            return {
                "success": True, 
                "video_path": yt_result["video_path"], 
                "caption": yt_result["caption"], 
                "request_id": request_id, 
                "folder": final_download_path
            }
            
        return {"success": False, "error": "Yuklab bo'lmadi ❌"}
        
    except Exception as e:
        logger.error(f"General download error: {e}")
        cleanup(final_download_path)
        return {"success": False, "error": "Xatolik yuz berdi ☹️"}

# Video extraction logic ends here
