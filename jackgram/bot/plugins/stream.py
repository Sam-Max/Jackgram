from jackgram.bot.bot import StreamBot
import asyncio
from telethon import events
from telethon.errors import FloodWaitError
import PTN
from jackgram.utils.utils import (
    extract_file_info,
    format_filename,
    get_file_title,
    get_media_details,
    process_files,
    process_movie,
    process_series,
)


@StreamBot.on(events.NewMessage(func=lambda e: e.is_channel and e.media))
async def private_receive_handler(event):
    message = event.message
    try:
        if not message.media:
            return

        title = get_file_title(message)
        filename = format_filename(title)
        file_info = await extract_file_info(message, filename)

        data = PTN.parse(filename)
        media_details_result = await get_media_details(data)

        media_id = media_details_result["media_id"]
        media_details = media_details_result["media_details"]
        episode_details = media_details_result["episode_details"]

        if media_id:
            if "season" in data and "episode" in data:
                await process_series(
                    media_id, data, media_details, episode_details, file_info
                )
            else:
                await process_movie(media_id, media_details, file_info)
        else:
            await process_files(file_info)

    except FloodWaitError as e:
        print(f"Sleeping for {e.seconds}s")
        await asyncio.sleep(e.seconds)
        sender = await event.get_sender()
        sender_name = getattr(sender, "first_name", "Unknown")
        sender_id = getattr(sender, "id", "Unknown")
        await event.client.send_message(
            entity=event.chat_id,
            message=f"Got FloodWait of {e.seconds}s from [{sender_name}](tg://user?id={sender_id})\n\n**USER ID:** `{sender_id}`",
            link_preview=False,
        )
