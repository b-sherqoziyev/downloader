import asyncpg
import logging
from app.config import DATABASE_URL

logger = logging.getLogger(__name__)

db_pool = None

async def init_db():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(dsn=DATABASE_URL)
        
        async with db_pool.acquire() as conn:
            # Users table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS telegram_users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # Cached media table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS cached_media (
                    url_hash VARCHAR(255) PRIMARY KEY,
                    video_file_id VARCHAR(255),
                    audio_file_id VARCHAR(255),
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise e

async def close_db():
    global db_pool
    if db_pool:
        await db_pool.close()

# Users Logic
async def save_user(user_id, username, first_name, last_name, joined_at):
    async with db_pool.acquire() as conn:
        try:
            # Check if user exists
            exists = await conn.fetchval('SELECT 1 FROM telegram_users WHERE user_id = $1', user_id)
            
            if not exists:
                await conn.execute('''
                    INSERT INTO telegram_users (user_id, username, first_name, last_name, joined_at)
                    VALUES ($1, $2, $3, $4, $5)
                ''', user_id, username, first_name, last_name, joined_at)
                return True # True means new user
            else:
                await conn.execute('''
                    UPDATE telegram_users 
                    SET username = $1, first_name = $2, last_name = $3
                    WHERE user_id = $4
                ''', username, first_name, last_name, user_id)
                return False
        except Exception as e:
            logger.error(f"Error saving user {user_id}: {e}")
            return False

async def get_stats(today_start, month_start):
    async with db_pool.acquire() as conn:
        total = await conn.fetchval('SELECT count(*) FROM telegram_users')
        today = await conn.fetchval('SELECT count(*) FROM telegram_users WHERE joined_at >= $1', today_start)
        month = await conn.fetchval('SELECT count(*) FROM telegram_users WHERE joined_at >= $1', month_start)
        return total, today, month

# Cache Logic
async def get_cached_media(url_hash):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow('SELECT video_file_id, audio_file_id FROM cached_media WHERE url_hash = $1', url_hash)
        if row:
            return dict(row)
        return None

async def save_cached_video(url_hash, video_file_id):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO cached_media (url_hash, video_file_id)
            VALUES ($1, $2)
            ON CONFLICT (url_hash) DO UPDATE 
            SET video_file_id = EXCLUDED.video_file_id
        ''', url_hash, video_file_id)

async def save_cached_audio(url_hash, audio_file_id):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            UPDATE cached_media 
            SET audio_file_id = $2
            WHERE url_hash = $1
        ''', url_hash, audio_file_id)
