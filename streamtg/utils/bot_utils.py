import datetime
from pyrogram.enums import ChatType
from pyrogram.types import Message
from pyrogram.file_id import FileId
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message
from streamtg.bot import BASE_URL, StreamBot
from streamtg import bot_logger


def get_file_info(message):
    media = get_media_from_message(message)
    if message.chat.type == ChatType.PRIVATE:
        user_id = message.from_user.id
    else:
        user_id = message.chat.id
    return {
        "user_id": user_id,
        "file_id": getattr(media, "file_id", ""),
        "file_unique_id": getattr(media, "file_unique_id", ""),
        "file_name": get_name(message),
        "file_size": getattr(media, "file_size", 0),
        "mime_type": getattr(media, "mime_type", "None/unknown"),
    }


def get_media_from_message(message):
    media_types = (
        "audio",
        "document",
        "photo",
        "sticker",
        "animation",
        "video",
        "voice",
        "video_note",
    )
    for attr in media_types:
        media = getattr(message, attr, None)
        if media:
            return media


def get_name(media_msg):
    if isinstance(media_msg, Message):
        media = get_media_from_message(media_msg)
        file_name = getattr(media, "file_name", "")
    elif isinstance(media_msg, FileId):
        file_name = getattr(media_msg, "file_name", "")

    if not file_name:
        if isinstance(media_msg, Message) and media_msg.media:
            media_type = media_msg.media.value
        elif media_msg.file_type:
            media_type = media_msg.file_type.name.lower()
        else:
            media_type = "file"

        formats = {
            "photo": "jpg",
            "audio": "mp3",
            "voice": "ogg",
            "video": "mp4",
            "animation": "mp4",
            "video_note": "mp4",
            "sticker": "webp",
        }

        ext = formats.get(media_type)
        ext = "." + ext if ext else ""

        date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        file_name = f"{media_type}-{date}{ext}"

    return file_name


async def generate_link(_id):
    page_link = f"{BASE_URL}watch/{_id}"
    stream_link = f"{BASE_URL}dl/{_id}"
    file_link = f"https://t.me/{StreamBot.username}?start=file_{_id}"

    bot_logger.info(page_link)
    bot_logger.info(stream_link)
    bot_logger.info(file_link)