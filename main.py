import telebot
import instaloader
import os
import shutil
import uuid
import logging
from telebot import types
from moviepy import VideoFileClip
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found in .env file")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# Global loader removed in favor of per-request instances


# Base directory for downloads
DOWNLOADS_DIR = "downloads"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)


def cleanup(folder_path):
    """Safely remove a directory."""
    try:
        if os.path.exists(folder_path):
            shutil.rmtree(folder_path, ignore_errors=True)
            logger.info(f"Cleaned up: {folder_path}")
    except Exception as e:
        logger.error(f"Error cleaning up {folder_path}: {e}")


@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(message.chat.id, "Salom! Instagram video havolasini yuboring.")


@bot.message_handler(func=lambda message: True)
def get_instagram_video(message):
    url = message.text.strip()
    
    # Simple validation
    if "instagram.com" not in url:
        bot.reply_to(message, "Iltimos, to'g'ri Instagram havolasini yuboring.")
        return

    try:
        # Extract shortcode safely
        if "/reel/" in url:
            shortcode = url.split("/reel/")[1].split("/")[0]
        elif "/p/" in url:
            shortcode = url.split("/p/")[1].split("/")[0]
        else:
            bot.reply_to(message, "Havola formati noto'g'ri.")
            return
    except IndexError:
        bot.reply_to(message, "Havoladan shortcode ajratib olinmadi.")
        return

    # Use a unique ID for this request to avoid collisions
    request_id = str(uuid.uuid4())
    
    # Instaloader tends to sanitize targets. Using a simple UUID string as the target name 
    # ensures it creates a predictable folder name (the UUID itself) in the current directory.
    # We avoid passing nested paths like "downloads/uuid" because Instaloader might sanitize separators.
    download_target_folder = request_id
    
    # We will eventually move it here
    final_download_path = os.path.join(DOWNLOADS_DIR, request_id)
    
    loader_message = bot.send_message(message.chat.id, "Video yuklanmoqda...", disable_notification=True)

    try:
        # User-specific instance for thread safety
        local_loader = instaloader.Instaloader(
            download_comments=False,
            download_geotags=False,
            download_pictures=False,
            download_video_thumbnails=False,
            save_metadata=False,
            compress_json=False
        )
        
        # Download logic
        post = instaloader.Post.from_shortcode(local_loader.context, shortcode)
        
        # This will create a directory named `request_id` in the current working directory
        local_loader.download_post(post, target=download_target_folder)
        
        # Move the downloaded folder to our downloads directory to keep root clean and consistent with callback logic
        if os.path.exists(download_target_folder):
            if os.path.exists(final_download_path):
                shutil.rmtree(final_download_path) # Should not happen with UUID, but safety first
            shutil.move(download_target_folder, final_download_path)
            # logger.info(f"Moved {download_target_folder} to {final_download_path}")
        else:
            logger.warning(f"Expected download folder {download_target_folder} not found in root.")

        # Now search in the final path
        video_path = None
        
        if os.path.exists(final_download_path):
            for root, dirs, files in os.walk(final_download_path):
                for file in files:
                    if file.endswith(".mp4"):
                        video_path = os.path.join(root, file)
                        break
                if video_path:
                    break
        
        if video_path:
            with open(video_path, "rb") as video:
                markup = types.InlineKeyboardMarkup()
                # Callback data: "audio:{request_id}"
                btn_audio = types.InlineKeyboardButton("Audioni yuklab olish", callback_data=f"audio:{request_id}")
                markup.add(btn_audio)
                
                # Get caption and truncate if necessary (Telegram limit is 1024 chars)
                caption = post.caption if post.caption else ""
                if len(caption) > 1024:
                    caption = caption[:1021] + "..."
                
                bot.send_video(message.chat.id, video, reply_markup=markup, caption=caption)
            
            # Note: We do not delete yet to allow audio extraction
        else:
            logger.warning(f"Video not found in {final_download_path}.")
            bot.reply_to(message, "Uzr, videoni topib bo'lmadi. Havola to'g'riligini tekshiring.")
            cleanup(final_download_path)

    except Exception as e:
        logger.error(f"Error downloading video: {e}")
        # Generic error message for user
        bot.reply_to(message, "Uzr, videoni yuklab bo'lmadi. Keyinroq urinib ko'ring.")
        
        # Cleanup potential leftovers
        cleanup(download_target_folder)
        cleanup(final_download_path)
        
    finally:
        try:
            bot.delete_message(message.chat.id, loader_message.message_id)
        except Exception:
            pass


@bot.callback_query_handler(func=lambda call: call.data.startswith("audio:"))
def callback_query(call):
    try:
        request_id = call.data.split(":")[1]
        download_path = os.path.join(DOWNLOADS_DIR, request_id)
        
        if not os.path.exists(download_path):
            bot.answer_callback_query(call.id, "Fayl topilmadi yoki muddati o'tgan.", show_alert=True)
            return

        bot.answer_callback_query(call.id, "Audio tayyorlanmoqda...")
        loader_msg = bot.send_message(call.message.chat.id, "Audio qirqib olinmoqda...")

        video_path = None
        for root, dirs, files in os.walk(download_path):
            for file in files:
                if file.endswith(".mp4"):
                    video_path = os.path.join(root, file)
                    break
        
        if video_path:
            # Generate nice audio name inside the same folder
            audio_path = os.path.join(download_path, "Instagram_Audio.mp3")
            
            try:
                # Load video and extract audio
                video_clip = VideoFileClip(video_path)
                
                # Check if video has audio
                if video_clip.audio is None:
                     bot.send_message(call.message.chat.id, "Bu videoda audio mavjud emas.")
                else:
                    video_clip.audio.write_audiofile(audio_path, logger=None)
                    video_clip.close() # Important to close the file handle
                    
                    with open(audio_path, "rb") as audio_file:
                        bot.send_audio(
                            call.message.chat.id, 
                            audio_file, 
                            caption="Videodan olingan audio",
                            title="Instagram Audio",
                            performer="Smart Downloader Bot"
                        )
            except Exception as e:
                logger.error(f"Error processing audio: {e}")
                bot.send_message(call.message.chat.id, "Audio yuklashda xatolik.")
            finally:
                if 'video_clip' in locals():
                    try:
                        video_clip.close()
                    except:
                        pass
        else:
            bot.send_message(call.message.chat.id, "Video fayl topilmadi.")

        # Cleanup after audio is sent OR if error occurred
        cleanup(download_path)
        
        try:
            bot.delete_message(call.message.chat.id, loader_msg.message_id)
        except:
            pass

    except Exception as e:
        logger.error(f"Callback error: {e}")
        bot.send_message(call.message.chat.id, "Xatolik yuz berdi.")

if __name__ == "__main__":
    logger.info("Bot ishga tushdi...")
    bot.infinity_polling()
