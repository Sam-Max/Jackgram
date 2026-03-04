import asyncio
from asyncio import sleep
import logging
import json
import os
from datetime import datetime, timedelta
import jwt

from bson.objectid import ObjectId

from telethon import events, Button
from telethon.errors import FloodWaitError

from jackgram.bot.bot import BACKUP_DIR, SECRET_KEY, get_db, StreamBot, LOGS_CHANNELS
from jackgram.bot.auth import admin_only
from jackgram.bot.utils import index_channel
from jackgram.utils.telegram_stream import multi_session_manager
from jackgram.utils.utils import (
    extract_media_file_raw,
    extract_movie_info_raw,
    extract_show_info_raw,
)

from jackgram import __version__

db = get_db()


@StreamBot.on(events.NewMessage(pattern=r"^/start(?: |$)", func=lambda e: e.is_private))
async def start(event):
    await event.reply(
        f"🚀 **Jackgram v{__version__}**\n\n"
        "👋 **Welcome to JackgramBot!**\n\n"
        "**📌 Indexing**\n"
        "/index — Index files from a channel (wizard or direct)\n\n"
        "**🔍 Search & Browse**\n"
        "/search `<query>` — Find indexed files\n"
        "/count — Database statistics\n\n"
        "**🗃️ Database Management**\n"
        "/del `<tmdb_id>` — Delete a TMDb entry\n"
        "/del_channel `<chat_id>` — Delete all entries for a chat\n"
        "/save_db — Back up the database\n"
        "/load_db — Restore from backup (reply to JSON)\n"
        "/del_db `<name>` — Delete a database\n\n"
        "**🔧 Admin**\n"
        "/token — Generate an API access token\n"
        "/log — Download the bot log file\n\n"
        "🧙‍♂️ **Contribute:** Send a media file directly to start the contribution wizard!\n"
        "🚀 Files posted in indexed channels are auto-processed!"
    )


@StreamBot.on(events.NewMessage(pattern=r"^/index(?: |$)", func=lambda e: e.is_private))
@admin_only
async def index(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]

    selected_log_channel = LOGS_CHANNELS[0]["id"]

    # Power user: direct command with args
    if len(args) >= 4:
        try:
            chat_id, first_id, count_msg = map(int, args[:3])
            client_type = args[3].lower()
            last_id = first_id + count_msg - 1

            if len(args) == 5:
                selected_log_channel = int(args[4])

            if client_type == "bot":
                client = StreamBot
            elif client_type == "user":
                client = await multi_session_manager.get_client()
            else:
                await event.reply("Invalid client type. Use 'bot' or 'user'.")
                return

            if count_msg <= 0:
                await event.reply("The count must be greater than 0.")
                return

            # Continue to indexing logic below (shared)
        except ValueError:
            await event.reply("Invalid IDs. Please provide numbers.")
            return

    # User friendly: Interactive Wizard
    elif len(args) == 0:
        sender_id = event.sender_id
        async with StreamBot.conversation(event.chat_id, timeout=300) as conv:
            try:
                # Step 1: Chat ID
                await conv.send_message(
                    "🔍 **Indexing Wizard**\n\nPlease send the **Chat ID** or **Username** of the channel you want to index."
                )
                chat_reply = await conv.get_response()
                chat_id = chat_reply.text.strip()
                if chat_id.startswith("@"):
                    pass  # Telethon handles usernames
                elif chat_id.replace("-", "").isdigit():
                    chat_id = int(chat_id)
                else:
                    await conv.send_message("❌ Invalid Chat ID or Username.")
                    return

                # Step 2: Range (First ID & Count)
                await conv.send_message(
                    "🔢 Send the **Start Message ID** and the **Count of Messages** to index separated by a space (e.g., `1 100`)."
                )
                range_reply = await conv.get_response()
                try:
                    first_id, count_msg = map(int, range_reply.text.split())
                    if count_msg <= 0:
                        await conv.send_message("❌ The count must be greater than 0.")
                        return
                    last_id = first_id + count_msg - 1
                except ValueError:
                    await conv.send_message(
                        "❌ Invalid format. Please send two numbers separated by a space."
                    )
                    return

                # Step 2.5: Logs Channel
                if len(LOGS_CHANNELS) > 1:
                    log_buttons = []
                    for i, ch_info in enumerate(LOGS_CHANNELS):
                        log_buttons.append(
                            Button.inline(
                                f"{ch_info['name']}",
                                f"idx_log_{i}".encode(),
                            )
                        )

                    # split buttons in rows of 2
                    formatted_buttons = [
                        log_buttons[i : i + 2] for i in range(0, len(log_buttons), 2)
                    ]
                    formatted_buttons.append(
                        [Button.inline("❌ Cancel", b"idx_cancel")]
                    )

                    log_prompt = await conv.send_message(
                        "📂 **Which Logs Channel should I use?**",
                        buttons=formatted_buttons,
                    )

                    res_log = await conv.wait_event(
                        events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
                    )
                    action_log = res_log.data.decode()

                    if action_log == "idx_cancel":
                        await res_log.edit("❌ Indexing cancelled.")
                        return

                    if action_log.startswith("idx_log_"):
                        idx = int(action_log.split("_")[-1])
                        selected_log_channel = LOGS_CHANNELS[idx]["id"]
                        await res_log.edit(
                            f"✅ Selected Logs Channel: **{LOGS_CHANNELS[idx]['name']}**"
                        )

                # Step 3: Client Type Buttons
                prompt = await conv.send_message(
                    "🤖 **Which client should I use for indexing?**\n\n"
                    "• **Bot**: Faster to start, but subject to strict bot limits.\n"
                    "• **User**: Uses your multi-session user accounts, better for large channels.",
                    buttons=[
                        [
                            Button.inline("🤖 Bot", b"idx_bot"),
                            Button.inline("👤 User", b"idx_user"),
                        ],
                        [Button.inline("❌ Cancel", b"idx_cancel")],
                    ],
                )

                res = await conv.wait_event(
                    events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
                )
                action = res.data.decode()

                if action == "idx_cancel":
                    await res.edit("❌ Indexing cancelled.")
                    return

                client_type = "bot" if action == "idx_bot" else "user"

                if client_type == "bot":
                    client = StreamBot
                else:
                    client = await multi_session_manager.get_client()

                await res.edit(
                    f"✅ Selected: **{client_type.capitalize()}**\n⏳ Starting index..."
                )

            except asyncio.TimeoutError:
                await conv.send_message("⏳ Indexing wizard timed out.")
                return
            except Exception as e:
                logging.error(f"Index wizard error: {e}")
                await conv.send_message(f"❌ Error: {e}")
                return
    else:
        await event.reply(
            "🚀 **Quick Indexing**\n\n"
            "Usage: `/index chat_id first_id count client_type [logs_channel]`\n"
            "Example: `/index -10012345 1 500 bot`\n\n"
            "💡 Or just send `/index` without parameters to use the **wizard**!"
        )
        return

    # Re-check client availability if selected via wizard/power user
    if not client:
        await event.reply("❌ Selected client is not available or configured.")
        return

    # Shared Indexing Logic
    total_range = last_id - first_id + 1
    try:
        start_message = (
            "🔄 **Indexing in progress...**\n\n"
            f"📡 Channel: `{chat_id}`\n"
            f"📨 Range: `{first_id}` → `{last_id}` ({total_range} messages)\n"
            f"📂 Output: `{selected_log_channel}`\n\n"
            "⏳ 0% — Starting...\n\n"
            "🚫 Do not start another index until this completes."
        )
        wait_msg = await event.reply(start_message)

        # Progress callback updates the message periodically
        async def on_progress(stats, current_id):
            processed = current_id - first_id
            pct = min(int(processed / total_range * 100), 100)
            bar_filled = pct // 5
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            try:
                await wait_msg.edit(
                    f"🔄 **Indexing in progress...**\n\n"
                    f"📡 Channel: `{chat_id}`\n"
                    f"`{bar}` **{pct}%**\n\n"
                    f"  ✅ Indexed: **{stats.get('indexed', 0)}**\n"
                    f"  ⏭️ Skipped: {stats.get('skipped_no_media', 0) + stats.get('skipped_size', 0) + stats.get('skipped_keyword', 0) + stats.get('skipped_ext', 0)}\n"
                    f"  ❌ Errors: {stats.get('errors', 0)}\n\n"
                    f"📨 Message `{current_id}` / `{last_id}`"
                )
            except Exception:
                pass  # Ignore edit failures (e.g. FloodWait)

        stats = await index_channel(
            client,
            chat_id,
            first_id,
            last_id,
            progress_callback=on_progress,
            logs_channel=selected_log_channel,
        )

        await wait_msg.delete()

        total_skipped = (
            stats.get("skipped_size", 0)
            + stats.get("skipped_keyword", 0)
            + stats.get("skipped_ext", 0)
        )
        summary = (
            "✅ **Indexing complete!**\n\n"
            "📊 **Stats:**\n"
            f"  • Indexed: **{stats.get('indexed', 0)}**\n"
            f"  • Skipped (too small): {stats.get('skipped_size', 0)}\n"
            f"  • Skipped (adult keyword): {stats.get('skipped_keyword', 0)}\n"
            f"  • Skipped (invalid ext): {stats.get('skipped_ext', 0)}\n"
            f"  • Skipped (no media): {stats.get('skipped_no_media', 0)}\n"
            f"  • Errors: {stats.get('errors', 0)}\n\n"
            f"Total skipped by filters: **{total_skipped}**"
        )
        await event.reply(summary)

    except FloodWaitError as e:
        logging.warning(f"FloodWait during index: sleeping for {e.seconds}s")
        await sleep(e.seconds)
        await event.reply(f"⏳ Got FloodWait of {e.seconds}s")


@StreamBot.on(
    events.NewMessage(pattern=r"^/search(?: |$)", func=lambda e: e.is_private)
)
@admin_only
async def search(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) >= 1:
        search_query = " ".join(args)
    else:
        await event.reply("Use /search <query>")
        return

    results, total = await db.search_tmdb(search_query)
    if not results:
        await event.reply("No results found.")
        return

    all_files = []
    for result in results[:5]:
        result_type = result.get("type")
        if result_type == "movie":
            info = extract_movie_info_raw(result)
            all_files.extend(info.get("files", []))
        elif result_type == "tv":
            info = extract_show_info_raw(result)
            all_files.extend(info.get("files", []))
        else:
            all_files.append(extract_media_file_raw(result))

    if not all_files:
        await event.reply("No files associated found.")
        return

    results_list = "\n".join(
        f"{idx + 1}. [{file.get('title', 'Unknown')}]({file.get('url', '#')})"
        for idx, file in enumerate(all_files[:20])
    )

    await event.reply(
        f'🔍 Found {total} result(s) for "{search_query}":\n\n{results_list}',
        link_preview=False,
    )


@StreamBot.on(events.NewMessage(pattern=r"^/del(?: |$)", func=lambda e: e.is_private))
@admin_only
async def delete(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 1:
        try:
            tmdb_id = int(args[0])
        except ValueError:
            await event.reply("❌ Invalid TMDb ID. Please provide a number.")
            return
    else:
        await event.reply("Use /del <tmdb_id>")
        return

    result = await db.del_tmdb(tmdb_id=tmdb_id)

    if result.deleted_count > 0:
        await event.reply("✅ Entry deleted successfully.")
    else:
        await event.reply("No document found with the given TMDb ID.")


@StreamBot.on(
    events.NewMessage(pattern=r"^/del_channel(?: |$)", func=lambda e: e.is_private)
)
@admin_only
async def delete_channel(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 1:
        try:
            chat_id = int(args[0])
        except ValueError:
            await event.reply(
                "❌ Invalid Chat ID. Please provide a number (e.g. `-10012345`)."
            )
            return
    else:
        await event.reply("Use /del_channel <chat_id>")
        return

    # Add confirmation
    await event.reply(
        f"⚠️ **Are you sure you want to delete all entries associated with chat `{chat_id}`?**",
        buttons=[
            [
                Button.inline(
                    "✅ Yes, delete",
                    f"delch_confirm:{chat_id}".encode(),
                ),
            ],
            [Button.inline("❌ Cancel", b"delch_cancel")],
        ],
    )


@StreamBot.on(events.CallbackQuery(pattern=b"delch_"))
async def delete_channel_callback(event):
    # Auth check
    from jackgram.bot.bot import ADMIN_IDS

    if ADMIN_IDS and event.sender_id not in ADMIN_IDS:
        await event.answer("⛔ Not authorized.", alert=True)
        return

    data = event.data.decode()
    if data == "delch_cancel":
        await event.edit("❌ Deletion cancelled.")
        return

    if data.startswith("delch_confirm:"):
        chat_id = int(data.split(":", 1)[1])
        await event.edit(f"⏳ Deleting entries for `{chat_id}`...")

        stats = await db.del_by_chat_id(chat_id)

        summary = (
            f"✅ **Deletion Complete!**\n\n"
            f"📊 **Stats:**\n"
            f"  • Raw Files Deleted: **{stats['raw_deleted']}**\n"
            f"  • Movies Modified: **{stats['movies_modified']}**\n"
            f"  • TV Shows Modified: **{stats['tv_modified']}**\n\n"
            "Entries with no remaining files were also removed."
        )
        await event.edit(summary)


@StreamBot.on(events.NewMessage(pattern=r"^/count(?: |$)", func=lambda e: e.is_private))
@admin_only
async def count(event):
    movies = await db.count_movies()
    tv = await db.count_tv()
    files = await db.count_media_files()
    total = movies + tv + files

    from jackgram.utils.utils import get_readable_size

    total_storage = await db.get_total_storage()
    storage_str = get_readable_size(total_storage)

    await event.reply(
        "📊 **Database Statistics**\n\n"
        f"🎬 Movies: **{movies}**\n"
        f"📺 TV Shows: **{tv}**\n"
        f"📁 Raw Files: **{files}**\n"
        f"━━━━━━━━━━━━━━━━━\n"
        f"📦 Total entries: **{total}**\n"
        f"💾 Total storage: **{storage_str}**"
    )


@StreamBot.on(
    events.NewMessage(pattern=r"^/save_db(?: |$)", func=lambda e: e.is_private)
)
@admin_only
async def save_database(event):
    status_msg = await event.reply("⏳ **Starting database backup...**")
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except PermissionError:
        await status_msg.edit(
            f"❌ Cannot create backup directory `{BACKUP_DIR}` — permission denied.\n"
            "💡 Set `BACKUP_DIR` in config.env to a writable path."
        )
        return

    backup_data = {}
    collections = await db.list_collections()
    total_collections = len(collections)

    for i, collection_name in enumerate(collections):
        await status_msg.edit(
            f"⏳ **Backing up database...**\n"
            f"Processing collection: `{collection_name}` ({i+1}/{total_collections})"
        )
        collection = db.db[collection_name]
        cursor = collection.find({})
        data = await cursor.to_list(length=None)

        serialized = []
        for doc in data:
            doc_copy = doc.copy()
            doc_copy["_id"] = str(doc_copy["_id"])
            serialized.append(doc_copy)

        backup_data[collection_name] = serialized

    await status_msg.edit("💾 **Writing backup file...**")
    backup_file = os.path.join(BACKUP_DIR, "database_backup.json")
    try:
        with open(backup_file, "w") as file:
            json.dump(backup_data, file, indent=4)
    except OSError as e:
        await status_msg.edit(f"❌ Failed to write backup file: {e}")
        return

    import time
    from jackgram.utils.utils import get_readable_size

    await status_msg.edit("📤 **Starting upload to Telegram...**")

    last_edit = time.time()

    async def upload_progress(current, total):
        nonlocal last_edit
        now = time.time()
        if now - last_edit >= 2.0 or current == total:
            pct = min(int(current / total * 100), 100) if total else 0
            bar_filled = pct // 5
            bar = "█" * bar_filled + "░" * (20 - bar_filled)

            curr_str = get_readable_size(current)
            total_str = get_readable_size(total)

            try:
                await status_msg.edit(
                    f"📤 **Uploading backup file to Telegram...**\n\n"
                    f"`{bar}` **{pct}%**\n"
                    f"📦 {curr_str} / {total_str}"
                )
                last_edit = now
            except Exception:
                pass

    try:
        await event.client.send_file(
            event.chat_id,
            file=backup_file,
            caption="✅ **Backup completed!**\n\nAll collections and fields (including new poster data) have been exported.",
            progress_callback=upload_progress,
        )
    finally:
        await status_msg.delete()


@StreamBot.on(
    events.NewMessage(pattern=r"^/load_db(?: |$)", func=lambda e: e.is_private)
)
@admin_only
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
                    # Invalid ObjectId — insert as new document instead
                    document.pop("_id")
                    await collection.insert_one(document)
                    continue
                await collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": document},
                    upsert=True,
                )

    await event.reply("Database restored successfully from the uploaded file!")


@StreamBot.on(
    events.NewMessage(pattern=r"^/del_db(?: |$)", func=lambda e: e.is_private)
)
@admin_only
async def delete_database(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 1:
        database_name = args[0]
    else:
        await event.reply("Use /del_db <database_name>")
        return

    await event.reply(
        f"⚠️ **Are you sure you want to DELETE the entire `{database_name}` database?**\n\n"
        "This action is **irreversible**.",
        buttons=[
            [
                Button.inline(
                    "✅ Yes, delete it",
                    f"deldb_confirm:{database_name}".encode(),
                ),
            ],
            [Button.inline("❌ Cancel", b"deldb_cancel")],
        ],
    )


@StreamBot.on(events.CallbackQuery(pattern=b"deldb_"))
async def delete_database_callback(event):
    # Auth check — reuse ADMIN_IDS
    from jackgram.bot.bot import ADMIN_IDS

    if ADMIN_IDS and event.sender_id not in ADMIN_IDS:
        await event.answer("⛔ Not authorized.", alert=True)
        return

    data = event.data.decode()
    if data == "deldb_cancel":
        await event.edit("❌ Database deletion cancelled.")
        return

    if data.startswith("deldb_confirm:"):
        database_name = data.split(":", 1)[1]
        await db.client.drop_database(database_name)
        await event.edit(f"✅ Database `{database_name}` has been deleted.")


@StreamBot.on(events.NewMessage(pattern=r"^/token(?: |$)", func=lambda e: e.is_private))
@admin_only
async def generate_token(event):
    sender = await event.get_sender()
    payload = {
        "user_id": sender.id,
        "exp": datetime.now() + timedelta(days=7),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    await event.reply(token)


@StreamBot.on(events.NewMessage(pattern=r"^/log(?: |$)", func=lambda e: e.is_private))
@admin_only
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
