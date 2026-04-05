import logging
from pyrogram import Client
from app.config import API_ID, API_HASH, SESSION_STRING, STORAGE_CHANNEL_ID

logger = logging.getLogger(__name__)

# Initialize UserBot Client
userbot = None

if API_ID and API_HASH:
    if SESSION_STRING:
        # Use existing session
        userbot = Client(
            "zeno_userbot",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=SESSION_STRING,
            in_memory=True
        )
    else:
        # Create new session (requires first-time login via terminal)
        userbot = Client(
            "zeno_userbot",
            api_id=API_ID,
            api_hash=API_HASH,
            workdir="."
        )

async def upload_large_file(file_path: str, caption: str, progress_callback=None):
    """Uploads file to storage channel using Userbot and returns message object"""
    if not userbot:
        raise ValueError("UserBot sozlanmagan!")
        
    try:
        # Standard progress callback for pyrogram
        async def pyrogram_progress(current, total):
            if progress_callback:
                percent = (current / total) * 100
                # Speed/ETA are harder to calculate here without more logic, 
                # so we just pass progress percent for now
                progress_callback(percent, 0, 0)

        # Upload to Storage Channel
        sent_msg = await userbot.send_video(
            chat_id=STORAGE_CHANNEL_ID,
            video=file_path,
            caption=caption,
            progress=pyrogram_progress
        )
        return sent_msg
    except Exception as e:
        logger.error(f"Userbot upload error: {e}", exc_info=True)
        return None
