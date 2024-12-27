from pyrogram import Client
from pyrogram.errors import UserIsBot
import asyncio

API_KEY = ""  # Replace with your actual API key
API_HASH = ""  # Replace with your actual API hash


async def generate_session_string():
    async with Client(
        name="Jackgram-User", api_id=API_KEY, api_hash=API_HASH, in_memory=True
    ) as app:
        session = await app.export_session_string()
        try:
            await app.send_message("me", f"#Jackgram\n\n<code>{session}</code>")
        except UserIsBot:
            pass
        print(f"Done!!, String Session: {session}")


asyncio.run(generate_session_string())
