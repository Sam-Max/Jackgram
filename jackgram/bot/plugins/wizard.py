import asyncio
import logging
import re
import PTN

from telethon import events, Button
from telethon.tl.types import Message

from jackgram.bot.bot import StreamBot, LOGS_CHANNELS
from jackgram.bot.utils import send_message
from jackgram.utils.utils import (
    extract_file_info,
    format_filename,
    get_file_title,
    process_movie,
    process_series,
)
from jackgram.utils.tmdb import get_tmdb

tmdb = get_tmdb()


@StreamBot.on(
    events.NewMessage(
        func=lambda e: e.is_private and (e.document or getattr(e, "video", None))
    )
)
async def wizard_start(event: Message):
    # Ignore commands disguised as captions
    if event.text and event.text.startswith("/"):
        return

    chat_id = event.chat_id
    sender_id = event.sender_id

    # Fast-fail for multipart/split files
    filename = getattr(event.file, "name", "") or getattr(event.message, "message", "")
    if filename:
        multipart_pattern = re.compile(
            r"(?:part|cd|disc|disk)[s._-]*\d+(?=\.\w+$)", re.IGNORECASE
        )
        if multipart_pattern.search(filename):
            await event.reply(
                "❌ **Upload Rejected**\n\nThis appears to be a split/multipart file (e.g., Part 1, CD 2). These are not supported because they cannot be streamed natively."
            )
            return

    # Auto-detect IMDb ID from caption
    caption_text = event.text or ""
    imdb_match = re.search(r"tt\d{7,8}", caption_text)
    detected_imdb_id = imdb_match.group(0) if imdb_match else None

    async with StreamBot.conversation(chat_id, timeout=120) as conv:
        try:
            # Step 1: Ask for media type
            prompt_text = "🧙‍♂️ **User Contribution Wizard**\n\nI detected a media file."
            if detected_imdb_id:
                prompt_text += f"\n\n🔍 **Auto-detected IMDb ID:** `{detected_imdb_id}`\nIs this a Movie or a TV Show?"
            else:
                prompt_text += " Is this a Movie or a TV Show?"

            prompt_msg = await conv.send_message(
                prompt_text,
                buttons=[
                    [
                        Button.inline("🎬 Movie", b"movie"),
                        Button.inline("📺 TV Show", b"series"),
                    ],
                    [Button.inline("❌ Cancel", b"cancel")],
                ],
            )

            res = await conv.wait_event(
                events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
            )
            action = res.data.decode()

            if action == "cancel":
                await res.edit("❌ Wizard cancelled.")
                return

            media_type = action
            type_str = "Movie" if media_type == "movie" else "TV Show"
            await res.edit(f"✅ Selected: **{type_str}**")

            # Step 2: Source TMDb ID (Auto or Manual)
            tmdb_id = None
            if detected_imdb_id:
                wait_msg = await conv.send_message(
                    f"🔍 Fetching TMDb data for `{detected_imdb_id}`..."
                )
                tmdb_id = await asyncio.to_thread(
                    tmdb.find_media_id, detected_imdb_id, media_type
                )
                await wait_msg.delete()
            else:
                await conv.send_message(
                    f"Please send the **TMDb ID** or the **exact title** of the {type_str}."
                )
                reply = await conv.get_response()
                query = reply.text.strip()

                if query.isdigit():
                    tmdb_id = int(query)
                else:
                    wait_msg = await conv.send_message("🔍 Searching TMDb...")
                    tmdb_id = await asyncio.to_thread(
                        tmdb.find_media_id, query, media_type
                    )
                    await wait_msg.delete()

            if not tmdb_id:
                await conv.send_message(
                    "❌ Could not find a match on TMDb. Wizard cancelled."
                )
                return

            # Fetch details
            details = await asyncio.to_thread(tmdb.get_details, tmdb_id, media_type)
            if not details or "id" not in details:
                await conv.send_message(
                    "❌ Failed to fetch TMDb details. Wizard cancelled."
                )
                return

            title = details.get("title") or details.get("name")
            year = (
                details.get("release_date")
                or details.get("first_air_date")
                or "Unknown"
            )
            if year and "-" in year:
                year = year.split("-")[0]

            # Step 3: Handle TV Show specific data (Season/Episode)
            season, episode = None, None
            if media_type == "series":
                # Try to parse from filename first
                filename = format_filename(get_file_title(event))
                ptn_data = PTN.parse(filename)
                season = ptn_data.get("season")
                episode = ptn_data.get("episode")

                if season is None or episode is None:
                    await conv.send_message(
                        "This is a TV Show, but I couldn't detect the Season and Episode from the filename.\n\nPlease reply with Season and Episode in the format: `S01E05`"
                    )
                    se_reply = await conv.get_response()
                    se_text = se_reply.text.strip().upper()

                    match = re.match(r"S(\d+)E(\d+)", se_text)
                    if match:
                        season = int(match.group(1))
                        episode = int(match.group(2))
                    else:
                        await conv.send_message("❌ Invalid format. Wizard cancelled.")
                        return

            # Step 3.5: Logs Channel
            selected_log_channel = LOGS_CHANNELS[0]["id"]
            if len(LOGS_CHANNELS) > 1:
                log_buttons = []
                for i, ch_info in enumerate(LOGS_CHANNELS):
                    log_buttons.append(
                        Button.inline(
                            f"{ch_info['name']}",
                            f"wiz_log_{i}".encode(),
                        )
                    )

                formatted_buttons = [
                    log_buttons[i : i + 2] for i in range(0, len(log_buttons), 2)
                ]
                formatted_buttons.append([Button.inline("❌ Cancel", b"cancel")])

                log_prompt = await conv.send_message(
                    "📂 **Which Logs Channel should I use to store this file?**",
                    buttons=formatted_buttons,
                )

                res_log = await conv.wait_event(
                    events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
                )
                action_log = res_log.data.decode()

                if action_log == "cancel":
                    await res_log.edit("❌ Wizard cancelled.")
                    return

                if action_log.startswith("wiz_log_"):
                    idx = int(action_log.split("_")[-1])
                    selected_log_channel = LOGS_CHANNELS[idx]["id"]
                    await res_log.edit(
                        f"✅ Selected Logs Channel: **{LOGS_CHANNELS[idx]['name']}**"
                    )

            # Step 4: Confirmation
            confirm_text = f"🍿 **Confirm Indexing**\n\nTitle: **{title}** ({year})\nType: **{type_str}**"
            if media_type == "series":
                confirm_text += f"\nSeason: **{season}** | Episode: **{episode}**"

            confirm_msg = await conv.send_message(
                confirm_text,
                buttons=[
                    [Button.inline("✅ Confirm & Index", b"confirm")],
                    [Button.inline("❌ Cancel", b"cancel")],
                ],
            )

            res_confirm = await conv.wait_event(
                events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
            )
            if res_confirm.data.decode() != "confirm":
                await res_confirm.edit("❌ Wizard cancelled.")
                return

            await res_confirm.edit("⏳ Indexing...")

            # Step 5: Process and Index
            # Forward the message to the logs channel to safely store it
            log_msg = await send_message(StreamBot, event, selected_log_channel)

            # Extract file info from the new log message
            final_filename = format_filename(get_file_title(log_msg))
            file_info = await extract_file_info(log_msg, final_filename)

            # Save to Database
            if media_type == "movie":
                await process_movie(tmdb_id, details, file_info)
            else:
                ep_details = await asyncio.to_thread(
                    tmdb.get_episode_details, tmdb_id, episode, season
                )
                data = {"season": season, "episode": episode}
                await process_series(tmdb_id, data, details, ep_details, file_info)

            await conv.send_message(
                "🎉 **Successfully Indexed!**\n\nThe media has been validated by you and perfectly added to the database."
            )

        except asyncio.TimeoutError:
            await conv.send_message(
                "⏳ Wizard timed out. Please send the file again to restart."
            )
        except Exception as e:
            logging.error(f"Wizard error: {e}")
            await conv.send_message("❌ An unexpected error occurred while processing.")
