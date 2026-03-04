import asyncio
import secrets
import math
import logging
import traceback

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import StreamingResponse
from jackgram.bot.bot import StreamBot, get_db
from jackgram.server.exceptions import FileNotFound, InvalidHash

import uuid
import time
from typing import Dict, Any

from jackgram.bot.bot import USE_TOKEN_SYSTEM
from fastapi import Depends
from jackgram.server.api.bot_api import verify_api_token
from jackgram.utils.file_properties import get_file_info_dict
from jackgram.utils.telegram_stream import (
    multi_session_manager,
    TelegramMediaRef,
    ParallelTransferrer,
)

active_streams: Dict[str, Dict[str, Any]] = {}

from telethon.errors import (
    FloodWaitError,
    ChannelPrivateError,
    ChatAdminRequiredError,
    UserNotParticipantError,
    FileReferenceExpiredError,
    MessageIdInvalidError,
    PeerIdInvalidError,
)
from jackgram.utils.http_utils import (
    parse_range_header,
    _content_disposition_header,
    get_content_type,
)

from jackgram import __version__

routes = APIRouter()

db = get_db()


@routes.get("/status")
async def root_route_handler():
    return {
        "server_status": "running",
        "telegram_bot": "jackgram",
        "version": __version__,
    }


@routes.head("/dl")
@routes.get("/dl")
async def stream_handler(
    request: Request,
    hash: str = Query(...),
    download: bool = Query(False),
    _=Depends(verify_api_token),
):
    try:
        return await media_streamer(request, hash, download)
    except InvalidHash as e:
        raise HTTPException(status_code=403, detail=e.message)
    except FileNotFound as e:
        raise HTTPException(status_code=404, detail=e.message)
    except (asyncio.CancelledError, BrokenPipeError, ConnectionResetError) as e:
        raise HTTPException(status_code=499, detail=str(e))
    except FloodWaitError as e:
        wait_seconds = getattr(e, "seconds", 60)
        raise HTTPException(
            status_code=429,
            detail=f"Rate limited by Telegram. Please wait {wait_seconds} seconds.",
            headers={"Retry-After": str(wait_seconds)},
        )
    except (ChannelPrivateError, ChatAdminRequiredError, UserNotParticipantError) as e:
        raise HTTPException(
            status_code=403, detail="Access denied to this chat/channel."
        )
    except FileReferenceExpiredError as e:
        raise HTTPException(
            status_code=410, detail="File reference expired or inaccessible."
        )
    except (MessageIdInvalidError, PeerIdInvalidError) as e:
        raise HTTPException(status_code=404, detail="Message or chat not found.")
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


async def media_streamer(request: Request, secure_hash: str, as_download: bool = False):
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

    mime_type = media_dict.get("mime_type")
    file_name = media_dict.get("file_name") or f"{secrets.token_hex(2)}.unknown"
    content_type = get_content_type(mime_type, file_name)

    # Handle HEAD requests
    if request.method == "HEAD":
        headers = {
            "Content-Type": content_type,
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "Content-Disposition": _content_disposition_header(file_name, as_download),
        }
        return Response(headers=headers)

    from_bytes, until_bytes = parse_range_header(range_header, file_size)
    req_length = until_bytes - from_bytes + 1

    # Initialize MultiSessionManager to get client client and reference
    client = await multi_session_manager.get_client()
    ref = TelegramMediaRef(chat_id=chat_id, message_id=message_id)

    # Pre-validate file access
    file_location, dc_id, actual_size_res = (
        await multi_session_manager._resolve_file_location(ref, file_size)
    )

    # Cancel event: set when client disconnects so the download engine aborts fast
    cancel_event = asyncio.Event()

    async def _disconnect_watcher():
        """Poll for client disconnect and signal the download to abort."""
        try:
            while not cancel_event.is_set():
                if await request.is_disconnected():
                    logging.debug("Client disconnected, setting cancel_event")
                    cancel_event.set()
                    return
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass

    async def _stream_tracker(
        stream_id: str, filename: str, file_size: int, generator, dc_id: int
    ):
        active_streams[stream_id] = {
            "id": stream_id,
            "filename": filename,
            "size": file_size,
            "bytes_sent": 0,
            "start_time": time.time(),
            "speed": 0.0,
            "dc_id": dc_id,
            "cancelled": False,
        }
        last_time = time.time()
        last_bytes = 0

        # Start disconnect watcher in the background
        watcher_task = asyncio.ensure_future(_disconnect_watcher())

        try:
            async for chunk in generator:
                # Check if the stream was manually cancelled from the admin panel
                if active_streams.get(stream_id, {}).get("cancelled"):
                    logging.info(f"Stream {stream_id} cancelled by admin.")
                    cancel_event.set()
                    break

                # Check if the client has disconnected (fast path via cancel_event)
                if cancel_event.is_set():
                    logging.info(f"Client disconnected, stopping stream {stream_id}")
                    break

                active_streams[stream_id]["bytes_sent"] += len(chunk)
                now = time.time()
                elapsed = now - last_time
                if elapsed > 1.0:
                    speed = (
                        active_streams[stream_id]["bytes_sent"] - last_bytes
                    ) / elapsed
                    active_streams[stream_id]["speed"] = speed
                    last_time = now
                    last_bytes = active_streams[stream_id]["bytes_sent"]
                yield chunk
        except (Exception, asyncio.CancelledError) as e:
            logging.info(f"Stream {stream_id} ended: {type(e).__name__}")
        finally:
            # Signal cancellation and stop the disconnect watcher
            cancel_event.set()
            watcher_task.cancel()

            # Schedule cleanup as a background task — we cannot reliably
            # `await` inside an async generator's `finally` block when
            # Python is finalizing it via GeneratorExit.  A background
            # task runs outside that constrained context.
            async def _do_cleanup():
                try:
                    await watcher_task
                except (asyncio.CancelledError, Exception):
                    pass
                await transferrer._cleanup()
                logging.debug(f"Stream {stream_id}: MTProto connections cleaned up")

            asyncio.ensure_future(_do_cleanup())
            active_streams.pop(stream_id, None)
            logging.debug(f"Stream {stream_id} removed from active_streams")

    # Stream the file using ParallelTransferrer
    transferrer = ParallelTransferrer(multi_session_manager, dc_id=dc_id)
    generator_body = transferrer.download(
        file=file_location,
        file_size=file_size,
        offset=from_bytes,
        limit=req_length,
        cancel_event=cancel_event,
    )

    stream_id = str(uuid.uuid4())
    body = _stream_tracker(stream_id, file_name, file_size, generator_body, dc_id)

    headers = {
        "Content-Type": content_type,
        "Content-Length": str(req_length),
        "Accept-Ranges": "bytes",
        "Content-Disposition": _content_disposition_header(file_name, as_download),
    }

    if range_header:
        headers["Content-Range"] = f"bytes {from_bytes}-{until_bytes}/{file_size}"

    logging.info(f"File Size: {file_size}")
    logging.info(f"Content-Range: bytes {from_bytes}-{until_bytes}/{file_size}")
    logging.info(f"Content-Length: {req_length}")

    return StreamingResponse(
        content=body, status_code=206 if range_header else 200, headers=headers
    )
