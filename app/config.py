import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = []
for aid in ADMIN_IDS_RAW.split(","):
    if aid.strip().isdigit():
        ADMIN_IDS.append(int(aid.strip()))

# UserBot Configuration
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_STRING = os.getenv("SESSION_STRING")
STORAGE_CHANNEL_ID = os.getenv("STORAGE_CHANNEL_ID")
COOKIES_CONTENT = os.getenv("COOKIES_CONTENT")
PO_TOKEN = os.getenv("PO_TOKEN") # New
VISITOR_DATA = os.getenv("VISITOR_DATA") # New
if STORAGE_CHANNEL_ID and STORAGE_CHANNEL_ID.startswith("-100"):
    STORAGE_CHANNEL_ID = int(STORAGE_CHANNEL_ID)

DOWNLOADS_DIR = os.path.join(os.getcwd(), "downloads")
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)
