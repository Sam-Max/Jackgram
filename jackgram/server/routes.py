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
from jackgram.utils.custom_dl import ByteStreamer
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


@routes.get("/dl/{tmdb_id}", allow_head=True)
async def stream_handler(request: web.Request):
    print("routes::stream_handler")
    try:
        tmdb_id = request.match_info['tmdb_id']
        secure_hash = request.query.get('hash')
        return await media_streamer(request, tmdb_id, secure_hash)
    except InvalidHash as e:
        raise web.HTTPForbidden(text=e.message)
    except FileNotFound as e:
        raise web.HTTPNotFound(text=e.message)
    except (AttributeError, BadStatusLine, ConnectionResetError):
        pass
    except Exception as e:
        traceback.print_exc()
        raise web.HTTPInternalServerError(text=str(e))
    

async def media_streamer(request: web.Request, tmdb_id: int, secure_hash: str):
    print("routes::media_streamer")
    range_header = request.headers.get("Range", 0)

    if StreamBot in class_cache:
        tg_connect = class_cache[StreamBot]
    else:
        logging.debug(f"Creating new ByteStreamer object for client")
        tg_connect = ByteStreamer(StreamBot)
        class_cache[StreamBot] = tg_connect

    file_id = await tg_connect.get_file_properties(tmdb_id, secure_hash)
    
    if file_id.unique_id[:6] != secure_hash:
        logging.debug(f"Invalid hash for message with ID {id}")
        raise InvalidHash
    
    file_size = file_id.file_size

    if range_header:
        from_bytes, until_bytes = range_header.replace("bytes=", "").split("-")
        from_bytes = int(from_bytes)
        until_bytes = int(until_bytes) if until_bytes else file_size - 1
    else:
        from_bytes = request.http_range.start or 0
        until_bytes = (request.http_range.stop or file_size) - 1

    if (until_bytes > file_size) or (from_bytes < 0) or (until_bytes < from_bytes):
        return web.Response(
            status=416,
            body="416: Range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )

    chunk_size = 1024 * 1024
    until_bytes = min(until_bytes, file_size - 1)

    offset = from_bytes - (from_bytes % chunk_size)
    first_part_cut = from_bytes - offset
    last_part_cut = until_bytes % chunk_size + 1

    req_length = until_bytes - from_bytes + 1
    part_count = math.ceil(until_bytes / chunk_size) - math.floor(offset / chunk_size)
    
    body = tg_connect.yield_file(
        file_id, offset, first_part_cut, last_part_cut, part_count, chunk_size
    )

    mime_type = file_id.mime_type
    file_name = file_id.file_name
    disposition = "attachment"

    if mime_type:
        if not file_name:
            try:
                file_name = f"{secrets.token_hex(2)}.{mime_type.split('/')[1]}"
            except (IndexError, AttributeError):
                file_name = f"{secrets.token_hex(2)}.unknown"
    else:
        if file_name:
            mime_type = mimetypes.guess_type(file_id.file_name)
        else:
            mime_type = "application/octet-stream"
            file_name = f"{secrets.token_hex(2)}.unknown"

    return web.Response(
        status=206 if range_header else 200,
        body=body,
        headers={
            "Content-Type": f"{mime_type}",
            "Content-Range": f"bytes {from_bytes}-{until_bytes}/{file_size}",
            "Content-Length": str(req_length),
            "Content-Disposition": f'{disposition}; filename="{file_name}"',
            "Accept-Ranges": "bytes",
        },
    )

