from jackgram.bot.bot import StreamBot
import asyncio
import logging
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


from jackgram.bot.utils import index_queue


@StreamBot.on(events.NewMessage(func=lambda e: e.is_channel and e.media))
async def private_receive_handler(event):
    message = event.message
    try:
        if not message.media:
            return

        # Put the raw message into the async queue for background processing
        await index_queue.put(message)

    except FloodWaitError as e:
        logging.warning(f"FloodWait in channel handler: sleeping for {e.seconds}s")
        await asyncio.sleep(e.seconds)
    except Exception as e:
        logging.error(f"Error in channel auto-index handler: {e}")
