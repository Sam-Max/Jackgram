from streamtg.bot import get_db, StreamBot
from streamtg.utils.database import Database
from streamtg.server.exceptions import FileNotFound
from pyrogram import filters, Client
from pyrogram.types import Message
import requests

session = requests.Session()
db = get_db()


@StreamBot.on_message(filters.command("start") & filters.private)
async def start(bot: Client, message: Message):
    pass


@StreamBot.on_message(filters.command("stream") & filters.private)
async def stream(bot: Client, message: Message):
    pass