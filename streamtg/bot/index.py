import asyncio
import logging
import PTN
from pyrogram.errors import FloodWait
from streamtg.bot import LOGS_CHANNEL
from streamtg.utils.index_utils import (
    extract_file_info,
    format_filename,
    get_file_title,
    get_media_details,
    process_movie,
    process_series,
)


async def fetch_message(client, chat_id, message_id):
    try:
        message = await client.get_messages(chat_id, message_id)
        print(message)
        if file := message.video or message.document:
            return await send_message(client, message, file, LOGS_CHANNEL)
    except FloodWait as e:
        logging.warning(f"Rate limit hit. Waiting for {e.value} seconds.")
        await asyncio.sleep(e.value)
        return await fetch_message(client, chat_id, message_id)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


async def send_message(client, message, file, dest_channel):
    return await client.send_cached_media(
        dest_channel, caption=message.caption, file_id=file.file_id
    )


async def index_channel(
    client, chat_id, first_message_id, last_message_id, batch_size=50
):
    current_message_id = first_message_id
    while current_message_id <= last_message_id:
        batch_message_ids = list(
            range(
                current_message_id,
                min(current_message_id + batch_size, last_message_id + 1),
            )
        )
        for message_id in batch_message_ids:
            try:
                message = await fetch_message(client, chat_id, message_id)
                if message:
                    file = message.video or message.document
                    title = get_file_title(file, message)
                    filename = format_filename(title)
                    file_info = await extract_file_info(file, message, filename)

                    data = PTN.parse(filename)
                    media_id, media_details, episode_details = await get_media_details(
                        data
                    )

                    if media_id and media_details:
                        if "season" in data and "episode" in data:
                            await process_series(
                                media_id,
                                data,
                                media_details,
                                episode_details,
                                file_info,
                            )
                        else:
                            await process_movie(media_id, media_details, file_info)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error: {e}")
        current_message_id += batch_size
