import logging
from os import getenv
import sys

from pyrogram import Client
from dotenv import load_dotenv

from jackgram.utils.database import Database

plugins = {"root": "jackgram/bot/plugins"}
no_updates = None

load_dotenv("config.env", override=True)

API_ID = getenv("API_ID")
if API_ID:
    API_ID = int(API_ID)
else:
    logging.error("API_ID variable is missing! Exiting now")
    sys.exit(1)

API_HASH = getenv("API_HASH")
if not API_HASH:
    logging.error("API_HASH variable is missing! Exiting now")
    sys.exit(1)
    
BOT_TOKEN = getenv("BOT_TOKEN")
if not BOT_TOKEN:
    logging.error("BOT_TOKEN variable is missing! Exiting now")
    sys.exit(1)

LOGS_CHANNEL = getenv("LOGS_CHANNEL")
if not LOGS_CHANNEL:
    logging.error("LOGS_CHANNEL variable is missing! Exiting now")
    sys.exit(1)

TMDB_API = getenv("TMDB_API")
if not TMDB_API:
    logging.error("TMDB_API variable is missing! Exiting now")
    sys.exit(1)

SESSION_STRING = getenv("SESSION_STRING", "")
DATABASE_URL = getenv("DATABASE_URL", "mongodb://admin:admin@mongo:27017")
BACKUP_DIR = getenv("BACKUP_DIR", "/app/database")
SLEEP_THRESHOLD = int(getenv("SLEEP_THRESHOLD", "60"))
# AUTH_USERS = list(set(int(x) for x in str(getenv("AUTH_USERS", "")).split()))
TMDB_LANGUAGE = getenv("TMDB_LANGUAGE", "en-US")

# WebServer
PORT = int(getenv("PORT", 5000))
BASE_URL = getenv("BASE_URL")
if BASE_URL:
    BASE_URL = f"{BASE_URL}:{PORT}"
else:
    BASE_URL = f"http://127.0.0.1:{PORT}"

BIND_ADDRESS = getenv("BIND_ADDRESS", "0.0.0.0")
SECRET_KEY = getenv("SECRET_KEY", "")
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
    name="stream_user",
    api_id=API_ID,
    api_hash=API_HASH,
    session_string=SESSION_STRING,
    sleep_threshold=SLEEP_THRESHOLD,
    no_updates=True,
    in_memory=True,
)


def get_db():
    return Database(DATABASE_URL, "jackgramdb")
