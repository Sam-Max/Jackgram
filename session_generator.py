from telethon.sync import TelegramClient
from telethon.sessions import StringSession
import asyncio

# Replace with your actual API ID and API Hash
API_ID = 0  # e.g., 12345
API_HASH = ""  # e.g., "0123456789abcdef0123456789abcdef"


async def generate_session_string():
    if not API_ID or not API_HASH:
        print("Please set your API_ID and API_HASH in session_generator.py")
        return

    async with TelegramClient(StringSession(), API_ID, API_HASH) as client:
        session = client.session.save()
        print(f"\n✅ Your Telethon String Session:\n\n{session}\n")
        print("Keep this string safe and do not share it with anyone!")


if __name__ == "__main__":
    asyncio.run(generate_session_string())
