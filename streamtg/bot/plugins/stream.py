from streamtg.bot import StreamBot
import asyncio
from pyrogram import filters, Client
from pyrogram.errors import FloodWait
from pyrogram.types import Message
from pyrogram.enums.parse_mode import ParseMode
import PTN
from streamtg.utils.index_utils import (
    extract_file_info,
    format_filename,
    get_file_title,
    get_media_details,
    process_movie,
    process_series,
)


@StreamBot.on_message(
    filters.channel
    & (
        filters.document
        | filters.video
        | filters.video_note
        | filters.audio
        | filters.voice
        | filters.animation
        | filters.photo
    ),
)
async def private_receive_handler(bot: Client, message: Message):
    try:
        file = message.video or message.document
        title = get_file_title(file, message)
        filename = format_filename(title)
        file_info = await extract_file_info(file, message, filename)

        data = PTN.parse(filename)
        media_id, media_details, episode_details = await get_media_details(data)

        if media_id and media_details:
            if "season" in data and "episode" in data:
                await process_series(
                    media_id, data, media_details, episode_details, file_info
                )
            else:
                await process_movie(media_id, media_details, file_info)
        
    except FloodWait as e:
        print(f"Sleeping for {str(e.value)}s")
        await asyncio.sleep(e.value)
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Got FloodWait of {str(e.value)}s from [{message.from_user.first_name}](tg://user?id={message.from_user.id})\n\n**ᴜsᴇʀ ɪᴅ :** `{str(message.from_user.id)}`",
            disable_web_page_preview=True,
            parse_mode=ParseMode.MARKDOWN,
        )
