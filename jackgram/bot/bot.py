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

LOGS_CHANNEL = getenv("LOGS_CHANNEL")
if not LOGS_CHANNEL:
    logging.error("LOGS_CHANNEL variable is missing! Exiting now")
    sys.exit(1)
LOGS_CHANNEL = int(LOGS_CHANNEL)

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
# AUTH_USERS = list(set(int(x) for x in str(getenv("AUTH_USERS", "")).split()))
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

StreamBot = TelegramClient(
    "stream_bot",
    api_id=API_ID,
    api_hash=API_HASH,
)


def get_db():
    return Database(DATABASE_URL, "jackgramdb")
