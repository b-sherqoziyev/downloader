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
            # Set session timezone to UTC
            await conn.execute("SET TIME ZONE 'UTC';")
            
            # Users table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS telegram_users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    joined_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    is_banned BOOLEAN DEFAULT FALSE
                );
            ''')
            
            # Migration for old users: add new columns if they don't exist
            try:
                await conn.execute('ALTER TABLE telegram_users ADD COLUMN is_active BOOLEAN DEFAULT TRUE;')
            except asyncpg.exceptions.DuplicateColumnError:
                pass
            
            try:
                await conn.execute('ALTER TABLE telegram_users ADD COLUMN is_banned BOOLEAN DEFAULT FALSE;')
            except asyncpg.exceptions.DuplicateColumnError:
                pass

            
            # Channels table for forced subscription
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS mandatory_channels (
                    channel_id VARCHAR(255) PRIMARY KEY,
                    url VARCHAR(255),
                    title VARCHAR(255),
                    added_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # Cached media table
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS cached_media (
                    url_hash VARCHAR(255) PRIMARY KEY,
                    video_file_id VARCHAR(255),
                    url TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                );
            ''')
            
            # Migration: add url column if it doesn't exist
            try:
                await conn.execute('ALTER TABLE cached_media ADD COLUMN url TEXT;')
            except asyncpg.exceptions.DuplicateColumnError:
                pass
            
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
                    SET username = $1, first_name = $2, last_name = $3, is_active = TRUE
                    WHERE user_id = $4
                ''', username, first_name, last_name, user_id)
                return False
        except Exception as e:
            logger.error(f"Error saving user {user_id}: {e}")
            return False

async def update_user_status(user_id, is_active=None, is_banned=None):
    async with db_pool.acquire() as conn:
        try:
            if is_active is not None and is_banned is not None:
                await conn.execute('UPDATE telegram_users SET is_active = $1, is_banned = $2 WHERE user_id = $3', is_active, is_banned, user_id)
            elif is_active is not None:
                await conn.execute('UPDATE telegram_users SET is_active = $1 WHERE user_id = $2', is_active, user_id)
            elif is_banned is not None:
                await conn.execute('UPDATE telegram_users SET is_banned = $1 WHERE user_id = $2', is_banned, user_id)
        except Exception as e:
            logger.error(f"Error updating status for user {user_id}: {e}")

async def get_user(search_query):
    # Search by ID or Username
    async with db_pool.acquire() as conn:
        query = 'SELECT * FROM telegram_users WHERE user_id::text = $1 OR username ILIKE $2 LIMIT 1'
        search_like = search_query.replace('@', '')
        row = await conn.fetchrow(query, search_query, search_like)
        return dict(row) if row else None

async def get_stats(today_start, wau_start, mau_start):
    async with db_pool.acquire() as conn:
        total = await conn.fetchval('SELECT count(*) FROM telegram_users')
        today = await conn.fetchval('SELECT count(*) FROM telegram_users WHERE joined_at >= $1', today_start)
        wau = await conn.fetchval('SELECT count(*) FROM telegram_users WHERE joined_at >= $1', wau_start)
        mau = await conn.fetchval('SELECT count(*) FROM telegram_users WHERE joined_at >= $1', mau_start)
        active = await conn.fetchval('SELECT count(*) FROM telegram_users WHERE is_active = TRUE')
        banned = await conn.fetchval('SELECT count(*) FROM telegram_users WHERE is_banned = TRUE')
        return {
            "total": total,
            "today": today,
            "wau": wau,
            "mau": mau,
            "active": active,
            "banned": banned
        }

async def get_all_users(active_only=False):
    async with db_pool.acquire() as conn:
        if active_only:
            rows = await conn.fetch('SELECT user_id FROM telegram_users WHERE is_active = TRUE AND is_banned = FALSE')
        else:
            rows = await conn.fetch('SELECT user_id FROM telegram_users')
        return [row['user_id'] for row in rows]

async def get_users_paginated(limit=10, offset=0):
    async with db_pool.acquire() as conn:
        rows = await conn.fetch('''
            SELECT user_id, username, first_name, joined_at, is_active, is_banned 
            FROM telegram_users 
            ORDER BY joined_at DESC 
            LIMIT $1 OFFSET $2
        ''', limit, offset)
        return [dict(row) for row in rows]

async def get_users_total_count():
    async with db_pool.acquire() as conn:
        return await conn.fetchval('SELECT count(*) FROM telegram_users')


# Channels Logic
async def add_channel(channel_id, url, title):
    async with db_pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO mandatory_channels (channel_id, url, title)
                VALUES ($1, $2, $3)
                ON CONFLICT (channel_id) DO UPDATE 
                SET url = EXCLUDED.url, title = EXCLUDED.title
            ''', str(channel_id), url, title)
            return True
        except Exception as e:
            logger.error(f"Error adding channel: {e}")
            return False

async def remove_channel(channel_id):
    async with db_pool.acquire() as conn:
        try:
            res = await conn.execute('DELETE FROM mandatory_channels WHERE channel_id = $1', str(channel_id))
            return res != "DELETE 0"
        except Exception as e:
            logger.error(f"Error removing channel: {e}")
            return False

async def get_all_channels(limit=None, offset=0):
    async with db_pool.acquire() as conn:
        if limit:
            rows = await conn.fetch('SELECT channel_id, url, title FROM mandatory_channels ORDER BY added_at ASC LIMIT $1 OFFSET $2', limit, offset)
        else:
            rows = await conn.fetch('SELECT channel_id, url, title FROM mandatory_channels ORDER BY added_at ASC')
        return [dict(row) for row in rows]

async def get_channels_count():
    async with db_pool.acquire() as conn:
        return await conn.fetchval('SELECT count(*) FROM mandatory_channels')

# Cache Logic
async def get_cached_media(url_hash):
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow('SELECT video_file_id, url FROM cached_media WHERE url_hash = $1', url_hash)
        if row:
            return dict(row)
        return None

async def save_cached_video(url_hash, video_file_id, url=None):
    async with db_pool.acquire() as conn:
        if url:
             await conn.execute('''
                INSERT INTO cached_media (url_hash, video_file_id, url)
                VALUES ($1, $2, $3)
                ON CONFLICT (url_hash) DO UPDATE 
                SET video_file_id = EXCLUDED.video_file_id, url = EXCLUDED.url
            ''', url_hash, video_file_id, url)
        else:
            await conn.execute('''
                INSERT INTO cached_media (url_hash, video_file_id)
                VALUES ($1, $2)
                ON CONFLICT (url_hash) DO UPDATE 
                SET video_file_id = EXCLUDED.video_file_id
            ''', url_hash, video_file_id)

async def save_url_to_cache(url_hash, url):
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO cached_media (url_hash, url)
            VALUES ($1, $2)
            ON CONFLICT (url_hash) DO UPDATE 
            SET url = EXCLUDED.url
        ''', url_hash, url)

# save_cached_audio removed
