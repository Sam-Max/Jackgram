import asyncio
import logging
import PTN
from typing import Optional
from pyrogram import Client
from pyrogram.types import Message, Document, Video
from pyrogram.errors import FloodWait
from jackgram.bot.bot import LOGS_CHANNEL
from jackgram.utils.utils import (
    extract_file_info,
    format_filename,
    get_file_title,
    get_media_details,
    process_files,
    process_movie,
    process_series,
)


async def fetch_message(
    client: Client, chat_id: int, message_id: int
) -> Optional[Message]:
    try:
        message: Message = await client.get_messages(chat_id, message_id)
        logging.debug(f"Fetched message: {message}")
        if file := message.video or message.document:
            return await send_message(client, message, file, LOGS_CHANNEL)
    except FloodWait as e:
        logging.warning(f"Rate limit hit. Waiting for {e.value} seconds.")
        await asyncio.sleep(e.value)
        return await fetch_message(client, chat_id, message_id)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


async def send_message(
    client: Client, message: Message, file: Video | Document, dest_channel: int
) -> Message:
    return await client.send_cached_media(
        dest_channel, caption=message.caption, file_id=file.file_id
    )


async def index_channel(
    client: Client,
    chat_id: int,
    first_message_id: int,
    last_message_id: int,
    batch_size: int = 50,
) -> None:
    current_message_id: int = first_message_id
    while current_message_id <= last_message_id:
        batch_message_ids: list[int] = list(
            range(
                current_message_id,
                min(current_message_id + batch_size, last_message_id + 1),
            )
        )
        for message_id in batch_message_ids:
            try:
                message: Optional[Message] = await fetch_message(
                    client, chat_id, message_id
                )
                if message:
                    file: Optional[Video | Document] = message.video or message.document
                    if file:
                        title: str = get_file_title(file, message)
                        filename: str = format_filename(title)
                        file_info = await extract_file_info(file, message, filename)

                        data: dict = PTN.parse(filename)
                        media_details_result = await get_media_details(data)

                        media_id: Optional[str] = media_details_result.get("media_id")
                        media_details: Optional[dict] = media_details_result.get(
                            "media_details"
                        )
                        episode_details: Optional[dict] = media_details_result.get(
                            "episode_details"
                        )

                        if media_id:
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
                        else:
                            await process_files(file_info)
                await asyncio.sleep(1)
            except Exception as e:
                print(f"Error: {e}")
        current_message_id += batch_size
