import telebot
import os
import logging
import psycopg2
from psycopg2 import pool
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BOT_TOKEN = os.getenv("BOT_TOKEN")
DB_NAME = os.getenv("DB_NAME")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Configure Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    logger.error("BOT_TOKEN not found in .env file")
    exit(1)

bot = telebot.TeleBot(BOT_TOKEN)

# Initialize PostgreSQL Connection Pool
try:
    db_pool = psycopg2.pool.SimpleConnectionPool(
        1, 10,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME
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
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
    try:
        conn = db_pool.getconn()
        cur = conn.cursor()
        
        # Professional UPSERT (Insert or Update)
        # We use ON CONFLICT DO NOTHING to simply ignore if user exists,
        # OR we could update the 'last_name' etc. Here we assume we just want to save new users.
        insert_query = """
        INSERT INTO telegram_users (user_id, username, first_name, last_name)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (user_id) DO UPDATE 
        SET username = EXCLUDED.username, 
            first_name = EXCLUDED.first_name, 
            last_name = EXCLUDED.last_name;
        """
        
        cur.execute(insert_query, (user.id, user.username, user.first_name, user.last_name))
        conn.commit()
        cur.close()
        
        logger.info(f"User {user.id} ({user.first_name}) saved/updated in database.")
        
    except Exception as e:
        logger.error(f"Error saving user {user.id}: {e}")
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
