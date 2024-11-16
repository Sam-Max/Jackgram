from asyncio import sleep
import json
import os
from jackgram.bot import SECRET_KEY, get_db, StreamBot, StreamUser
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message
import requests
from jackgram.bot.index import index_channel
from jackgram.utils.bot_utils import generate_link
from jackgram.utils.utils import extract_movie_info, extract_show_info_raw
import datetime
import jwt

session = requests.Session()
db = get_db()


@StreamBot.on_message(filters.command("start") & filters.private)
async def start(bot: Client, message: Message):
    await message.reply_text("Welcome to StreamTGBot!!.")


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
        await message.reply(text="Use /index chat_id first_id last_id client_type")
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
            link = generate_link(tmdb_id=info["tmdb_id"], hash=i["hash"])
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
    backup_dir = "./database"
    os.makedirs(backup_dir, exist_ok=True)

    collections = await db.list_collections()
    for collection_name in collections:
        collection = db.db[collection_name]
        cursor = collection.find({})
        data = await cursor.to_list(length=None)

        for doc in data:
            doc["_id"] = str(doc["_id"])

        with open(os.path.join(backup_dir, f"{collection_name}.json"), "w") as file:
            json.dump(data, file, indent=4)

    await message.reply_text(
        f"Backup completed! Data saved in '{backup_dir}' directory."
    )


@StreamBot.on_message(filters.command("del_db") & filters.private)
async def delete_database(bot: Client, message: Message):
    args = message.text.split()[1:]
    if len(args) == 1:
        database_name = args[0]
    else:
        await message.reply(text="Use /del_db name")
        return

    await db.client.drop_database(database_name)

    await message.reply_text(f"Database '{database_name}' has been deleted.")


@StreamBot.on_message(filters.command("token") & filters.private)
async def generate_token(client, message):
    payload = {
        "user_id": message.user.id,
        "exp": datetime.now(datetime.timezone.utc)
        + datetime.timedelta(hours=24),  # Token expiration
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    await message.reply_text(token)
