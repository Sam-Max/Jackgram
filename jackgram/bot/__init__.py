from os import getenv

from pyrogram import Client
from dotenv import load_dotenv

from jackgram.utils.database import Database

plugins = {"root": "jackgram/bot/plugins"}
no_updates = None

load_dotenv('config.env', override=True)

API_ID = int(getenv("API_ID"))
API_HASH = str(getenv("API_HASH"))
BOT_TOKEN = str(getenv("BOT_TOKEN"))
SESSION_STRING = getenv("SESSION_STRING", "")
DATABASE_URL = str(getenv("DATABASE_URL"))
BACKUP_DIR = str(getenv("BACKUP_DIR"))
LOGS_CHANNEL = int(getenv("LOGS_CHANNEL", None))   
SLEEP_THRESHOLD = int(getenv("SLEEP_THRESHOLD", "60"))
AUTH_USERS = list(set(int(x) for x in str(getenv("AUTH_USERS", "")).split()))

# WebServer
PORT = int(getenv("PORT", 8080))
BASE_URL = "http://127.0.0.1:{}".format(str(PORT))
BIND_ADDRESS = str(getenv("BIND_ADDRESS", "0.0.0.0"))
SECRET_KEY = str(getenv("SECRET_KEY", ""))
PING_INTERVAL = int(getenv("PING_INTERVAL", "1200"))


StreamBot = Client(
    name="stream_bot",
    api_id=API_ID,
    api_hash=API_HASH,
    plugins=plugins,
    bot_token=BOT_TOKEN,
    sleep_threshold=SLEEP_THRESHOLD,
    no_updates=no_updates,
)

StreamUser = Client(
    name='stream_user',
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    sleep_threshold=SLEEP_THRESHOLD,
    no_updates=True,
    in_memory=True,
)


def get_db():
    return Database(DATABASE_URL, "jackgramdb")

