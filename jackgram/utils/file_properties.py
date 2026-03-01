from __future__ import annotations
import logging
from typing import Any, Optional, Dict

from fastapi import Request
from jackgram.bot.bot import get_db
from jackgram.utils.utils import extract_media_by_hash

db = get_db()


async def get_file_info_dict(
    request: Request, secure_hash: str
) -> Optional[Dict[str, Any]]:
    tmdb_id = request.query_params.get("tmdb_id")
    file_id = request.query_params.get("file_id")

    logging.info(
        f"get_file_info_dict: tmdb_id={tmdb_id}, file_id={file_id}, secure_hash={secure_hash}"
    )

    if tmdb_id:
        data = await db.get_tmdb(int(tmdb_id))
        logging.info(f"get_file_info_dict: data={data}")
        if data:
            media = await extract_media_by_hash(data, secure_hash)
        else:
            return None
    elif file_id:
        media = await db.get_media_file(file_id)
        if not media or media.get("hash") != secure_hash:
            return None
    else:
        return None

    return media
