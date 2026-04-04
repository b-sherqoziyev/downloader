import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_IDS_RAW = os.getenv("ADMIN_IDS", "")
USE_LOCAL_API = os.getenv("USE_LOCAL_API", "False").lower() == "true"
LOCAL_API_SERVER_URL = os.getenv("LOCAL_API_SERVER_URL", "http://localhost:8081")
TELEGRAM_API_ID = os.getenv("TELEGRAM_API_ID")
TELEGRAM_API_HASH = os.getenv("TELEGRAM_API_HASH")
ADMIN_IDS = []
for aid in ADMIN_IDS_RAW.split(","):
    if aid.strip().isdigit():
        ADMIN_IDS.append(int(aid.strip()))

DOWNLOADS_DIR = "downloads"
if not os.path.exists(DOWNLOADS_DIR):
    os.makedirs(DOWNLOADS_DIR)
