import asyncio
import logging
from os import getenv
import sys

from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

from jackgram.utils.database import Database

no_updates = None
lock = asyncio.Lock()

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

LOGS_CHANNELS_STR = getenv("LOGS_CHANNEL")
if not LOGS_CHANNELS_STR:
    logging.error("LOGS_CHANNEL variable is missing! Exiting now")
    sys.exit(1)

LOGS_CHANNELS = []
for ch in LOGS_CHANNELS_STR.split(","):
    ch = ch.strip()
    if not ch:
        continue
    if ":" in ch:
        cid, name = ch.split(":", 1)
        LOGS_CHANNELS.append({"id": int(cid.strip()), "name": name.strip()})
    else:
        LOGS_CHANNELS.append({"id": int(ch), "name": f"Channel {ch}"})

if not LOGS_CHANNELS:
    logging.error("LOGS_CHANNEL variable is invalid! Exiting now")
    sys.exit(1)

# Keep the first one as default for backwards compatibility
LOGS_CHANNEL = LOGS_CHANNELS[0]["id"]

TMDB_API = getenv("TMDB_API")
if not TMDB_API:
    logging.error("TMDB_API variable is missing! Exiting now")
    sys.exit(1)

import json

SESSION_STRINGS = []
_session_strings_env = getenv("SESSION_STRING", getenv("SESSION_STRINGS", ""))
if _session_strings_env:
    # Try parsing as JSON array first, fallback to comma-separated
    try:
        SESSION_STRINGS = json.loads(_session_strings_env)
        if not isinstance(SESSION_STRINGS, list):
            SESSION_STRINGS = [str(SESSION_STRINGS)]
    except json.JSONDecodeError:
        SESSION_STRINGS = [
            s.strip() for s in _session_strings_env.split(",") if s.strip()
        ]

DATABASE_URL = getenv("DATABASE_URL", "mongodb://admin:admin@mongo:27017")
BACKUP_DIR = getenv("BACKUP_DIR", "/app/database")
SLEEP_THRESHOLD = int(getenv("SLEEP_THRESHOLD", "60"))
AUTH_USERS = getenv("AUTH_USERS", "{}")
try:
    AUTH_USERS = json.loads(AUTH_USERS)
except json.JSONDecodeError:
    AUTH_USERS = {"admin": "admin"}

# Bot command authorization – comma-separated Telegram user IDs
_admin_ids_env = getenv("ADMIN_IDS", "")
ADMIN_IDS: set[int] = set()
if _admin_ids_env:
    ADMIN_IDS = {
        int(uid.strip()) for uid in _admin_ids_env.split(",") if uid.strip().isdigit()
    }
    logging.info(f"Authorized admin IDs: {ADMIN_IDS}")
else:
    logging.warning(
        "ADMIN_IDS is not set – all private-chat users can execute bot commands. "
        "Set ADMIN_IDS in config.env to restrict access."
    )

TMDB_LANGUAGE = getenv("TMDB_LANGUAGE", "en-US")
WORKERS = int(getenv("WORKERS", "10"))

# WebServer
PORT = int(getenv("PORT", 5000))
BASE_URL = getenv("BASE_URL")
if BASE_URL:
    BASE_URL = f"{BASE_URL}:{PORT}"
else:
    BASE_URL = f"http://127.0.0.1:{PORT}"

BIND_ADDRESS = getenv("BIND_ADDRESS", "0.0.0.0")
SECRET_KEY = getenv("SECRET_KEY", "your-secret-token")

USE_TOKEN_SYSTEM = getenv("USE_TOKEN_SYSTEM", "True")
USE_TOKEN_SYSTEM = USE_TOKEN_SYSTEM.strip().lower() == "true"

PING_INTERVAL = int(getenv("PING_INTERVAL", "1200"))

# Scraping Filters (used during /index)
INDEX_MIN_SIZE_MB = int(getenv("INDEX_MIN_SIZE_MB", "50"))
INDEX_ADULT_KEYWORDS = getenv("INDEX_ADULT_KEYWORDS", "")  # comma-separated overrides
INDEX_ALLOWED_EXTENSIONS = getenv(
    "INDEX_ALLOWED_EXTENSIONS", ""
)  # comma-separated overrides

StreamBot = TelegramClient(
    "stream_bot",
    api_id=API_ID,
    api_hash=API_HASH,
)


def get_db():
    return Database(DATABASE_URL, "jackgramdb")
