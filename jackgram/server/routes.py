import secrets
import time
import math
import logging
import mimetypes
import traceback
from aiohttp import web
from aiohttp.http_exceptions import BadStatusLine
from jackgram.bot import StreamBot, get_db
from jackgram.server.exceptions import FileNotFound, InvalidHash
from jackgram import __version__, StartTime
from jackgram.utils.custom_dl import TelegramStreamer
from jackgram.utils.utils import get_readable_time

routes = web.RouteTableDef()

class_cache = {}
db = get_db()


@routes.get("/status", allow_head=True)
async def root_route_handler(_):
    return web.json_response(
        {
            "server_status": "running",
            "uptime": get_readable_time(time.time() - StartTime),
            "telegram_bot": "@" + StreamBot.me.username,
            "version": __version__,
        }
    )


@routes.get("/dl", allow_head=True)
async def stream_handler(request: web.Request):
    print("routes::stream_handler")
    try:
        return await media_streamer(request)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FileNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        traceback.print_exc()
        raise web.HTTPInternalServerError(text=str(e))


async def media_streamer(request: web.Request):
    """
    Handles streaming media files based on a secure hash and HTTP Range requests.
    """
    secure_hash = request.query.get("hash")
    range_header = request.headers.get("Range")

    # Retrieve or initialize the TelegramStreamer instance
    tg_connect = class_cache.get(StreamBot)
    if not tg_connect:
        logging.debug("Creating new TelegramStreamer object for client")
        tg_connect = TelegramStreamer(StreamBot)
        class_cache[StreamBot] = tg_connect

    file_id = await tg_connect.get_file_properties(request, secure_hash)

    # Validate secure hash
    if file_id.unique_id[:6] != secure_hash:
        logging.debug(f"Invalid hash for message with ID {file_id}")
        raise InvalidHash

    file_size = file_id.file_size

    # Parse Range header or HTTP range
    if range_header:
        try:
            from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
            from_bytes = int(from_bytes)
            until_bytes = int(until_bytes) if until_bytes else file_size - 1
        except ValueError:
            return web.Response(status=400, body="400: Bad Request")
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = (request.http_range.stop or file_size) - 1

    # Validate range
    if (until_bytes >= file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
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

    return web.Response(status=206 if range_header else 200, body=body, headers=headers)
