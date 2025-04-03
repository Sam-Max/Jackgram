from asyncio import sleep
import json
import os
from datetime import datetime, timedelta
import jwt

from bson.objectid import ObjectId

from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message

from jackgram.bot.bot import BACKUP_DIR, SECRET_KEY, get_db, StreamBot, StreamUser
from jackgram.bot.utils import index_channel
from jackgram.utils.utils import (
    extract_movie_info,
    extract_show_info_raw,
    generate_stream_url,
)


db = get_db()


@StreamBot.on_message(filters.command("start"))
async def start(bot, message):
    await message.reply_text(
        "👋 Welcome to JackgramBot!\n\n"
        "📌 Use /index to index files from a channel.\n"
        "🔍 Use /search to find indexed files.\n"
        "🗑️ Use /del to delete an entry by its IMDb ID.\n"
        "📊 Use /count to see the total number of entries in the database.\n"
        "💾 Use /save_db to back up the database.\n"
        "📂 Use /load_db to restore the database from a backup.\n"
        "❌ Use /del_db to delete a specific database.\n"
        "🔑 Use /token to generate an access token.\n\n"
        "🚀 Send a file to the logs channel to index it automatically!"
    )


@StreamBot.on_message(filters.command("index") & filters.private)
async def index(bot: Client, message: Message):
    args = message.text.split()[1:]
    if len(args) == 4:
        chat_id, first_id, last_id = map(int, args[:-1])
        client_type = args[-1]

        if client_type == "bot":
            client = StreamBot
        elif client_type == "user":
            client = StreamUser
        else:
            await message.reply(text="Invalid client type.")
            return

        if last_id <= first_id:
            await message.reply(
                text="The second value (last_id) must be greater than the first value (first_id)."
            )
            return
    else:
        await message.reply(
            text="Usage: /index chat_id first_id last_id client_type\n\n"
            "Example: /index 123456789 1 100 bot\n\n"
            "Note: client_type must be either 'bot' or 'user'."
        )
        return

    try:
        start_message = (
            "🔄 Perform this action only once\n\n"
            "⏳ Files indexing is currently in progress.\n\n"
            "🚫 Do not send any additional files or start indexing other channels until this process completes.\n\n"
        )

        wait_msg = await message.reply(text=start_message)

        await index_channel(client, chat_id, first_id, last_id)

        await wait_msg.delete()

        await bot.send_message(
            chat_id=message.chat.id,
            text="✅ All your files have been successfully stored in the database!!.\n\n",
        )

    except FloodWait as e:
        print(f"Sleeping for {str(e.value)}s")
        await sleep(e.value)
        await message.reply(
            text=f"Got Floodwait of {str(e.value)}s",
            disable_web_page_preview=True,
            parse_mode="Markdown",
        )


@StreamBot.on_message(filters.command("search") & filters.private)
async def search(bot: Client, message: Message):
    args = message.text.split()[1:]
    if len(args) == 1:
        search_query = args[0]
    else:
        await message.reply(text="Use /search query")
        return

    results, _ = await db.search_tmdb(search_query)
    if results:
        if results[0]["type"] == "movie":
            info = extract_movie_info(results[0])
        else:
            info = extract_show_info_raw(results[0])

        results_list = "Results:\n\n"
        count = 0
        for i in info["files"]:
            count += 1
            name = i["title"]
            link = generate_stream_url(tmdb_id=info["tmdb_id"], hash=i["hash"])
            results_list += f"{count}. [{name}]({link})\n"

        await message.reply_text(results_list)
    else:
        await message.reply_text("No results found.")


@StreamBot.on_message(filters.command("del") & filters.private)
async def delete(bot: Client, message: Message):
    args = message.text.split()[1:]
    if len(args) == 1:
        id = int(args[0])
    else:
        await message.reply(text="Use /del imdb_id")
        return

    result = await db.del_tdmb(tmdb_id=id)

    if result.deleted_count > 0:
        await message.reply_text("Entry deleted successfully.")
    else:
        await message.reply_text("No document found with the given criteria")


@StreamBot.on_message(filters.command("count") & filters.private)
async def count(bot: Client, message: Message):
    result = await db.count_tmdb()
    if result > 0:
        await message.reply_text(
            f"There are {result} number of entries on the database"
        )
    else:
        await message.reply_text("No document found with the given criteria")


@StreamBot.on_message(filters.command("save_db") & filters.private)
async def save_database(bot: Client, message: Message):
    os.makedirs(BACKUP_DIR, exist_ok=True)

    backup_data = {}
    collections = await db.list_collections()
    for collection_name in collections:
        collection = db.db[collection_name]
        cursor = collection.find({})
        data = await cursor.to_list(length=None)

        for doc in data:
            doc["_id"] = str(doc["_id"])

        backup_data[collection_name] = data

    backup_file = os.path.join(BACKUP_DIR, "database_backup.json")
    with open(backup_file, "w") as file:
        json.dump(backup_data, file, indent=4)

    await bot.send_document(
        chat_id=message.chat.id,
        document=backup_file,
        caption="Backup completed! Here is your database backup file.",
    )


@StreamBot.on_message(filters.command("load_db") & filters.private)
async def load_database(bot: Client, message: Message):
    if not message.reply_to_message or not message.reply_to_message.document:
        await message.reply_text("Please reply to a JSON file with this command.")
        return

    file_path = await bot.download_media(message.reply_to_message.document)
    if not file_path.endswith(".json"):
        await message.reply_text("The file must be a JSON file.")
        return

    with open(file_path, "r") as file:
        try:
            backup_data = json.load(file)
        except json.JSONDecodeError:
            await message.reply_text(
                "Failed to load the file. Please ensure it is a valid JSON file."
            )
            return

    if not isinstance(backup_data, dict):
        await message.reply_text(
            "Invalid JSON structure. The file must contain a dictionary with collection names as keys."
        )
        return

    for collection_name, documents in backup_data.items():
        if not isinstance(documents, list):
            await message.reply_text(
                f"Invalid data for collection '{collection_name}'. Expected a list of documents."
            )
            continue

        collection = db.db[collection_name]

        # Insert documents into the collection
        for document in documents:
            if "_id" in document:
                try:
                    document["_id"] = ObjectId(document["_id"])
                except Exception:
                    document.pop("_id")
                await collection.update_one(
                    {"_id": document.get("_id")},
                    {"$set": document},
                    upsert=True,
                )

    await message.reply_text("Database restored successfully from the uploaded file!")


@StreamBot.on_message(filters.command("del_db") & filters.private)
async def delete_database(bot: Client, message: Message):
    args = message.text.split()[1:]
    if len(args) == 1:
        database_name = args[0]
    else:
        await message.reply(text="Use /del_db database_name")
        return

    await db.client.drop_database(database_name)

    await message.reply_text(f"Database '{database_name}' has been deleted.")


@StreamBot.on_message(filters.command("token") & filters.private)
async def generate_token(client, message):
    payload = {
        "user_id": message.from_user.id,
        "exp": datetime.now() + timedelta(days=7),  # Token expiration
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    await message.reply_text(token)


@StreamBot.on_message(filters.command("log") & filters.private)
async def send_log_file(bot: Client, message: Message):
    log_file_path = os.path.join(os.getcwd(), "bot.log")
    if os.path.exists(log_file_path):
        await bot.send_document(
            chat_id=message.chat.id,
            document=log_file_path,
            caption="Here is the bot.log file.",
        )
    else:
        await message.reply_text("The bot.log file does not exist.")
