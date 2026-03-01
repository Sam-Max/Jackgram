import asyncio
import secrets
import math
import logging
import traceback

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from jackgram.bot.bot import StreamBot, get_db
from jackgram.server.exceptions import FileNotFound, InvalidHash

from jackgram.utils.file_properties import get_file_info_dict
from jackgram.utils.telegram_stream import (
    multi_session_manager,
    TelegramMediaRef,
    ParallelTransferrer,
)

routes = APIRouter()

db = get_db()


@routes.get("/status")
async def root_route_handler():
    return {
        "server_status": "running",
        "telegram_bot": "jackgram",
        "version": "1.0.0",
    }


@routes.get("/dl")
async def stream_handler(request: Request, hash: str = Query(...)):
    try:
        return await media_streamer(request, hash)
    except InvalidHash as e:
        raise HTTPException(status_code=403, detail=e.message)
    except FileNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)
    except (asyncio.CancelledError, BrokenPipeError, ConnectionResetError) as e:
        raise HTTPException(status_code=499, detail=str(e))
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


async def media_streamer(request: Request, secure_hash: str):
    """
    Handles streaming media files based on a secure hash and HTTP Range requests.
    """
    range_header = request.headers.get("Range")
    logging.info(f"Range header: {range_header}")

    media_dict = await get_file_info_dict(request, secure_hash)
    if not media_dict:
        raise FileNotFound

    # Validate secure hash
    if media_dict.get("hash") != secure_hash:
        raise InvalidHash

    chat_id = media_dict.get("chat_id")
    message_id = media_dict.get("message_id")
    if not chat_id or not message_id:
        raise FileNotFound

    file_size = int(media_dict.get("file_size", 0))

    # Parse Range header
    if range_header:
        try:
            from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
            from_bytes = int(from_bytes)
            until_bytes = (
                min(int(until_bytes), file_size - 1) if until_bytes else file_size - 1
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="Bad Request")
    else:
        from_bytes = 0
        until_bytes = file_size - 1

    # Validate range
    if (until_bytes >= file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return Response(
            "416: Range not satisfiable",
            status_code=416,
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    req_length = until_bytes - from_bytes + 1

    # Initialize MultiSessionManager to get client client and reference
    client = await multi_session_manager.get_client()
    ref = TelegramMediaRef(chat_id=chat_id, message_id=message_id)

    # Pre-validate file access
    file_location, dc_id, actual_size_res = (
        await multi_session_manager._resolve_file_location(ref, file_size)
    )

    # Stream the file using ParallelTransferrer
    transferrer = ParallelTransferrer(multi_session_manager, dc_id=dc_id)
    body = transferrer.download(
        file=file_location,
        file_size=file_size,
        offset=from_bytes,
        limit=req_length,
    )

    mime_type = media_dict.get("mime_type", "application/octet-stream")
    file_name = media_dict.get("file_name") or f"{secrets.token_hex(2)}.unknown"

    headers = {
        "Content-Type": mime_type,
        "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
        "Content-Length": str(req_length),
        "Content-Disposition": f'attachment; filename="{file_name}"',
        "Accept-Ranges": "bytes",
    }

    logging.info(f"File Size: {file_size}")
    logging.info(f"Content-Range: bytes {from_bytes}-{until_bytes}/{file_size}")
    logging.info(f"Content-Length: {req_length}")

    return StreamingResponse(
        content=body, status_code=206 if range_header else 200, headers=headers
    )
