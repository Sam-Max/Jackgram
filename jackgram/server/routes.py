import asyncio
import secrets
import math
import logging
import traceback

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from jackgram.bot.bot import StreamBot, get_db
from jackgram.server.exceptions import FileNotFound, InvalidHash
from jackgram.utils.custom_dl import TelegramStreamer

routes = APIRouter()

class_cache = {}
db = get_db()


@routes.get("/status")
async def root_route_handler():
    return {
        "server_status": "running",
        "telegram_bot": "@" + StreamBot.me.username,
        "version": "0.0.1",
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

    # Retrieve or initialize the TelegramStreamer instance
    tg_connect = class_cache.get(StreamBot)
    if not tg_connect:
        logging.debug("Creating new TelegramStreamer object for client")
        tg_connect = TelegramStreamer(StreamBot)
        class_cache[StreamBot] = tg_connect

    file_id = await tg_connect.get_file_properties(request, secure_hash)

    # Validate secure hash
    if file_id.unique_id[:6] != secure_hash:
        logging.info(f"Invalid hash for message with ID {file_id.unique_id}")
        raise InvalidHash

    file_size = file_id.file_size

    # Parse Range header or HTTP range
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

    # Calculate offsets and chunk details
    chunk_size = 1024 * 1024  # 1 MB
    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1
    req_length = until_bytes - from_bytes + 1
    part_count = math.ceil((until_bytes + 1) / chunk_size) - math.floor(
        offset / chunk_size
    )

    # Stream the file
    body = tg_connect.yield_file(
        file_id, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )

    # Determine MIME type and file name
    mime_type = file_id.mime_type or "application/octet-stream"
    file_name = file_id.file_name or f"{secrets.token_hex(2)}.unknown"

    ## If not file name, it generates a random name with an inferred extension based on the MIME type.
    if not file_id.file_name and file_id.mime_type:
        try:
            extension = file_id.mime_type.split("/")[1]
            file_name = f"{secrets.token_hex(2)}.{extension}"
        except (IndexError, AttributeError):
            pass

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
