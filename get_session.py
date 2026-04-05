from pyrogram import Client
import asyncio

async def main():
    api_id = input("API_IDni kiriting: ")
    api_hash = input("API_HASHni kiriting: ")
    
    async with Client("temp_session", api_id=api_id, api_hash=api_hash, in_memory=True) as app:
        print("\nSIZNING SESSION_STRINGINGIZ:\n")
        print(await app.export_session_string())
        print("\nUshbu satrni nusxalab oling va Railway'da SESSION_STRING o'zgaruvchisiga qo'shing.")

asyncio.run(main())
