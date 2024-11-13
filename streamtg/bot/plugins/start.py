from asyncio import sleep
from streamtg.bot import get_db, StreamBot
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import (
    Message,
)
import requests
from streamtg.bot.index import index_channel
from streamtg.utils.bot_utils import generate_link
from streamtg.utils.utils import extract_movie_info, extract_show_info_raw

session = requests.Session()
db = get_db()


@StreamBot.on_message(filters.command("start") & filters.private)
async def start(bot: Client, message: Message):
    await message.reply_text("Welcome to StreamTGBot!!.")


@StreamBot.on_message(filters.command("index") & filters.private)
async def index(bot: Client, message: Message):
    args = message.text.split()[1:]
    if len(args) == 3:
        chat_id, first_id, last_id = map(int, args)
        if last_id <= first_id:
            await message.reply(
                text="The second value (last_id) must be greater than the first value (first_id)."
            )
            return
    else:
        await message.reply(text="Use /index chat_id first_id last_id")
        return

    try:
        start_message = (
            "🔄 Perform this action only once\n\n"
            "⏳ Files indexing is currently in progress.\n\n"
            "🚫 Do not send any additional files or indexing other channels until this process completes.\n\n"
        )

        wait_msg = await message.reply(text=start_message)

        await index_channel(chat_id, first_id, last_id)

        await wait_msg.delete()

        await bot.send_message(
            chat_id=message.chat.id,
            text="✅ All your files have been successfully stored in the database. You're all set!\n\n",
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
        for i in info:
            count += 1
            link = (i["title"], i["link"])
            results_list += f"{count}.{link}\n"

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
