import telebot
import os
import logging
import psycopg2
import pytz
from datetime import datetime
from psycopg2 import pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = os.getenv("ADMIN_ID")
if ADMIN_ID:
    try:
        ADMIN_ID = int(ADMIN_ID)
    except ValueError:
        ADMIN_ID = None

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found in .env file")
    exit(1)

if not DATABASE_URL:
    logger.error("DATABASE_URL not found in .env file")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# Initialize PostgreSQL Connection Pool
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        dsn=DATABASE_URL
    )
    if db_pool:
        logger.info("PostgreSQL connection pool created successfully")
except Exception as e:
    logger.error(f"Error creating connection pool: {e}")
    exit(1)


def init_db():
    """Create users table if it doesn't exist."""
    conn = None
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        create_table_query = """
        CREATE TABLE IF NOT EXISTS telegram_users (
            user_id BIGINT PRIMARY KEY,
            username VARCHAR(255),
            first_name VARCHAR(255),
            last_name VARCHAR(255),
            joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
        """
        cur.execute(create_table_query)
        conn.commit()
        cur.close()
        logger.info("Database table checked/created.")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        if conn:
            db_pool.putconn(conn)


@bot.message_handler(commands=['start'])
def start_handler(message):
    user = message.from_user
    conn = None
    
    # Tashkent time
    tz = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tz)
    
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        
        # Check if user exists
        cur.execute("SELECT user_id FROM telegram_users WHERE user_id = %s", (user.id,))
        exists = cur.fetchone()
        
        is_new_user = False
        
        if not exists:
            insert_query = """
            INSERT INTO telegram_users (user_id, username, first_name, last_name, joined_at)
            VALUES (%s, %s, %s, %s, %s)
            """
            cur.execute(insert_query, (user.id, user.username, user.first_name, user.last_name, current_time))
            is_new_user = True
        else:
            update_query = """
            UPDATE telegram_users 
            SET username = %s, first_name = %s, last_name = %s
            WHERE user_id = %s
            """
            cur.execute(update_query, (user.username, user.first_name, user.last_name, user.id))
            
        conn.commit()
        
        logger.info(f"User {user.id} ({user.first_name}) saved/updated in database.")
        
        # Notify admin about new user
        if is_new_user and ADMIN_ID:
            try:
                username_str = f"@{user.username}" if user.username else "yo'q"
                admin_msg = (
                    f"➕ <b>Yangi foydalanuvchi!</b>\n\n"
                    f"<b>ID:</b> <code>{user.id}</code>\n"
                    f"<b>Ism:</b> {user.first_name}\n"
                    f"<b>Username:</b> {username_str}\n"
                    f"<b>Vaqt:</b> {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
                )
                bot.send_message(ADMIN_ID, admin_msg, parse_mode='HTML')
            except Exception as e:
                logger.error(f"Error sending msg to admin: {e}")
                
        # If admin, give stats
        if ADMIN_ID and user.id == ADMIN_ID:
            cur.execute("SELECT count(*) FROM telegram_users;")
            total_users = cur.fetchone()[0]
            
            today_start = current_time.replace(hour=0, minute=0, second=0, microsecond=0)
            cur.execute("SELECT count(*) FROM telegram_users WHERE joined_at >= %s;", (today_start,))
            today_users = cur.fetchone()[0]
            
            month_start = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            cur.execute("SELECT count(*) FROM telegram_users WHERE joined_at >= %s;", (month_start,))
            month_users = cur.fetchone()[0]
            
            stats_msg = (
                f"📊 <b>Bot Statistikasi</b>\n\n"
                f"👥 Umumiy foydalanuvchilar: {total_users} ta\n"
                f"📅 Bugun qo'shilganlar: {today_users} ta\n"
                f"🗓 Shu oy qo'shilganlar: {month_users} ta\n\n"
                f"🕒 Hozirgi vaqt: {current_time.strftime('%Y-%m-%d %H:%M:%S')}"
            )
            bot.send_message(user.id, stats_msg, parse_mode='HTML')
            
        cur.close()
        
    except Exception as e:
        logger.error(f"Error in start_handler: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            db_pool.putconn(conn)
            
    # No reply message as requested


if __name__ == "__main__":
    init_db()
    logger.info("Bot started...")
    bot.infinity_polling()