from __future__ import annotations
from datetime import datetime
from typing import Any, Optional
from pyrogram.enums import ChatType
from pyrogram.types import Message
from pyrogram.file_id import FileId
from jackgram.bot import get_db
from jackgram.utils.utils import extract_media_by_hash


db = get_db()


def get_media_from_message(message: "Message") -> Any:
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


def get_media_file_size(m):
    media = get_media_from_message(m)
    return getattr(media, "file_size", "None")


def get_name(media_msg: Message | FileId) -> str:
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


def get_file_info(message):
    media = get_media_from_message(message)
    if message.chat.type == ChatType.PRIVATE:
        user_idx = message.from_user.id
    else:
        user_idx = message.chat.id
    return {
        "user_id": user_idx,
        "file_id": getattr(media, "file_id", ""),
        "file_unique_id": getattr(media, "file_unique_id", ""),
        "file_name": get_name(message),
        "file_size": getattr(media, "file_size", 0),
        "mime_type": getattr(media, "mime_type", "None/unknown"),
    }


async def get_file_ids(request, secure_hash) -> Optional[FileId]:
    print("file_properties::get_file_ids")

    tmdb_id = request.args.get('tmdb_id')
    file_id = request.args.get('file_id')

    if tmdb_id:
        results = await db.get_tmdb(tmdb_id)
        media = await extract_media_by_hash(results, secure_hash)
    elif file_id:
        media = await db.get_media_file(file_id)

    file_id = FileId.decode(media["file_id"])
    setattr(file_id, "file_name", media["file_name"])
    setattr(file_id, "file_size", media["file_size"])
    setattr(file_id, "mime_type", media["mime_type"])
    setattr(file_id, "unique_id",  media["file_unique_id"])
    return file_id

def is_media(message):
    return next(
        (
            getattr(message, attr)
            for attr in [
                "document",
                "photo",
                "video",
                "audio",
                "voice",
                "video_note",
                "sticker",
                "animation",
            ]
            if getattr(message, attr)
        ),
        None,
    )
