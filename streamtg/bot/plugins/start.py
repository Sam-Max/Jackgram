from asyncio import sleep
from streamtg.bot import BASE_URL, get_db, StreamBot
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import (
    Message,
)
import requests

from streamtg.bot.index import index_channel
from streamtg.utils.bot_utils import generate_link

session = requests.Session()
db = get_db()


@StreamBot.on_message(filters.command("start") & filters.private)
async def start(bot: Client, message: Message):
    await message.reply_text("Welcome to StreamTGBot!!.")


@StreamBot.on_message(filters.command("index") & filters.private)
async def index(bot: Client, message: Message):
    args = message.text.split()[1:]

    if len(args) == 1:
        first_id = int(args[0])
        last_id = message.id
    elif len(args) == 2:
        first_id, last_id = map(int, args)
        if last_id <= first_id:
            await message.reply(
                text="The second value (last_id) must be greater than the first value (first_id)."
            )
            return
    else:
        await message.reply(text="Use /index first_id last_id")
        return

    try:
        start_message = (
            "🔄 Perform this action only once\n\n"
            "📋 Files indexing is currently in progress.\n\n"
            "🚫 Please refrain from sending any additional files or indexing other channels until this process completes.\n\n"
            "⏳ Please be patient and wait a few moments."
        )

        wait_msg = await message.reply(text=start_message)

        await index_channel(message.chat.id, first_id, last_id)

        await wait_msg.delete()

        done_message = (
            "✅ All your files have been successfully stored in the database. You're all set!\n\n"
            "📁 You don't need to index again unless you make changes to the database."
        )

        await bot.send_message(chat_id=message.chat.id, text=done_message)

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
    search_query = message.text.split()[1]
    results, _ = await db.search_tmdb(search_query)

    if results:
        results_list = []
        for result in results:
            if result["type"] == "movie":
                title = result["title"]
                for file in result["file_info"]:
                    title = file.get("original_title")
                    channel_id = file.get("chn_id")
                    message_id = file.get("msg_id")
                    hash = file.get("hash")
                    url = generate_link(channel_id, message_id, hash)
                    link = f"[{title}]({url})"
                    print(link)
            # else:
            #     url = generate_link(channel_id, message_id, hash)

            results_list.append(link)
    else:
        await message.reply_text("No results found.")
        return

    await message.reply_text(link, parse_mode="Markdown")


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
