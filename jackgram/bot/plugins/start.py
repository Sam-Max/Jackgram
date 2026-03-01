from asyncio import sleep
import json
import os
from datetime import datetime, timedelta
import jwt

from bson.objectid import ObjectId

from telethon import events
from telethon.errors import FloodWaitError

from jackgram.bot.bot import BACKUP_DIR, SECRET_KEY, get_db, StreamBot, StreamUser
from jackgram.bot.utils import index_channel
from jackgram.utils.utils import (
    extract_movie_info,
    extract_show_info_raw,
)


db = get_db()


@StreamBot.on(events.NewMessage(pattern=r"^/start(?: |$)", func=lambda e: e.is_private))
async def start(event):
    await event.reply(
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


@StreamBot.on(events.NewMessage(pattern=r"^/index(?: |$)", func=lambda e: e.is_private))
async def index(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 4:
        chat_id, first_id, last_id = map(int, args[:-1])
        client_type = args[-1]

        if client_type == "bot":
            client = StreamBot
        elif client_type == "user":
            client = StreamUser
        else:
            await event.reply("Invalid client type.")
            return

        if last_id <= first_id:
            await event.reply(
                "The second value (last_id) must be greater than the first value (first_id)."
            )
            return
    else:
        await event.reply(
            "Usage: /index chat_id first_id last_id client_type\n\n"
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
        wait_msg = await event.reply(start_message)

        await index_channel(client, chat_id, first_id, last_id)

        await wait_msg.delete()
        await event.reply(
            "✅ All your files have been successfully stored in the database!!\n\n"
        )

    except FloodWaitError as e:
        print(f"Sleeping for {e.seconds}s")
        await sleep(e.seconds)
        await event.reply(f"Got Floodwait of {e.seconds}s")


@StreamBot.on(
    events.NewMessage(pattern=r"^/search(?: |$)", func=lambda e: e.is_private)
)
async def search(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) >= 1:
        search_query = " ".join(args)
    else:
        await event.reply("Use /search query")
        return

    results, _ = await db.search_tmdb(search_query)
    if not results:
        await event.reply("No results found.")
        return

    result = results[0]
    info = (
        extract_movie_info(result, result.get("tmdb_id"))
        if result["type"] == "movie"
        else extract_show_info_raw(result)
    )

    if not info.get("files"):
        await event.reply("No files associated found.")
        return

    results_list = "\n".join(
        f"{idx + 1}. [{file['title']}]({file['url']})"
        for idx, file in enumerate(info["files"])
    )

    await event.reply(f"Results:\n\n{results_list}", link_preview=False)


@StreamBot.on(events.NewMessage(pattern=r"^/del(?: |$)", func=lambda e: e.is_private))
async def delete(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 1:
        id = int(args[0])
    else:
        await event.reply("Use /del imdb_id")
        return

    result = await db.del_tdmb(tmdb_id=id)

    if result.deleted_count > 0:
        await event.reply("Entry deleted successfully.")
    else:
        await event.reply("No document found with the given criteria")


@StreamBot.on(events.NewMessage(pattern=r"^/count(?: |$)", func=lambda e: e.is_private))
async def count(event):
    result = await db.count_tmdb()
    if result > 0:
        await event.reply(f"There are {result} number of entries on the database")
    else:
        await event.reply("No document found with the given criteria")


@StreamBot.on(
    events.NewMessage(pattern=r"^/save_db(?: |$)", func=lambda e: e.is_private)
)
async def save_database(event):
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

    await event.client.send_file(
        event.chat_id,
        file=backup_file,
        caption="Backup completed! Here is your database backup file.",
    )


@StreamBot.on(
    events.NewMessage(pattern=r"^/load_db(?: |$)", func=lambda e: e.is_private)
)
async def load_database(event):
    if not event.is_reply:
        await event.reply("Please reply to a JSON file with this command.")
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.document:
        await event.reply("Please reply to a JSON file with this command.")
        return

    file_path = await event.client.download_media(reply_msg)
    if not file_path or not file_path.endswith(".json"):
        await event.reply("The file must be a JSON file.")
        return

    with open(file_path, "r") as file:
        try:
            backup_data = json.load(file)
        except json.JSONDecodeError:
            await event.reply(
                "Failed to load the file. Please ensure it is a valid JSON file."
            )
            return

    if not isinstance(backup_data, dict):
        await event.reply(
            "Invalid JSON structure. The file must contain a dictionary with collection names as keys."
        )
        return

    for collection_name, documents in backup_data.items():
        if not isinstance(documents, list):
            await event.reply(
                f"Invalid data for collection '{collection_name}'. Expected a list of documents."
            )
            continue

        collection = db.db[collection_name]
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

    await event.reply("Database restored successfully from the uploaded file!")


@StreamBot.on(
    events.NewMessage(pattern=r"^/del_db(?: |$)", func=lambda e: e.is_private)
)
async def delete_database(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 1:
        database_name = args[0]
    else:
        await event.reply("Use /del_db database_name")
        return

    await db.client.drop_database(database_name)
    await event.reply(f"Database '{database_name}' has been deleted.")


@StreamBot.on(events.NewMessage(pattern=r"^/token(?: |$)", func=lambda e: e.is_private))
async def generate_token(event):
    sender = await event.get_sender()
    payload = {
        "user_id": sender.id,
        "exp": datetime.now() + timedelta(days=7),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    await event.reply(token)


@StreamBot.on(events.NewMessage(pattern=r"^/log(?: |$)", func=lambda e: e.is_private))
async def send_log_file(event):
    log_file_path = os.path.join(os.getcwd(), "bot.log")
    if os.path.exists(log_file_path):
        await event.client.send_file(
            event.chat_id,
            file=log_file_path,
            caption="Here is the bot.log file.",
        )
    else:
        await event.reply("The bot.log file does not exist.")
