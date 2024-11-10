from pyrogram import Client
from dotenv import load_dotenv
from os import environ as env

from streamtg.utils.database import Database

plugins = {"root": "streamtg/bot/plugins"}
no_updates = None


load_dotenv()

API_ID = int(env.get("API_ID"))
API_HASH = str(env.get("API_HASH"))
BOT_TOKEN = str(env.get("BOT_TOKEN"))
OWNER_ID = int(env.get("OWNER_ID", ""))
DATABASE_URL = str(env.get("DATABASE_URL"))
SLEEP_THRESHOLD = int(env.get("SLEEP_THRESHOLD", "60"))
AUTH_USERS = list(set(int(x) for x in str(env.get("AUTH_USERS", "")).split()))

# WebServer
PORT = int(env.get("PORT", 8080))
BASE_URL = "http://127.0.0.1:{}/".format(str(PORT))
BIND_ADDRESS = str(env.get("BIND_ADDRESS", "0.0.0.0"))
PING_INTERVAL = int(env.get("PING_INTERVAL", "1200"))


StreamBot = Client(
    name="stream_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    plugins=plugins,
    bot_token=BOT_TOKEN,
    sleep_threshold=SLEEP_THRESHOLD,
    no_updates=no_updates,
)

def get_db():
    return Database(DATABASE_URL, "streamtgdb")