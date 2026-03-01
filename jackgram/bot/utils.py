import asyncio
import logging
import PTN
import traceback
from typing import Dict, Optional
from telethon import TelegramClient
from telethon.tl.types import Message
from telethon.errors import FloodWaitError
from jackgram.bot.bot import (
    LOGS_CHANNEL,
    INDEX_MIN_SIZE_MB,
    INDEX_ADULT_KEYWORDS,
    INDEX_ALLOWED_EXTENSIONS,
)
from jackgram.utils.scraping_filters import ScrapingFilters, _parse_csv
from jackgram.utils.utils import (
    extract_file_info,
    format_filename,
    get_file_title,
    get_media_details,
    process_files,
    process_movie,
    process_series,
)

# ── Build the filters singleton from config ─────────────────────────────────

_adult_kw = _parse_csv(INDEX_ADULT_KEYWORDS) if INDEX_ADULT_KEYWORDS else None
_allowed_ext = (
    _parse_csv(INDEX_ALLOWED_EXTENSIONS) if INDEX_ALLOWED_EXTENSIONS else None
)

scraping_filters = ScrapingFilters(
    min_size_mb=INDEX_MIN_SIZE_MB,
    adult_keywords=_adult_kw,
    allowed_extensions=_allowed_ext,
)

# ── Async Queue System ──────────────────────────────────────────────────────
index_queue = asyncio.Queue()


async def process_index_queue():
    """Background worker to process individual files added to the queue."""
    logging.info("Async Indexing Queue worker started.")
    while True:
        try:
            message = await index_queue.get()

            title: str = get_file_title(message)
            filename: str = format_filename(title)

            file_name = getattr(message.file, "name", "") or ""
            file_size = getattr(message.file, "size", 0) or 0

            skip, reason = scraping_filters.should_skip(
                filename=file_name, file_size=file_size
            )

            if skip:
                logging.info(f"Queue File Skipped: {reason} (file: {file_name})")
            else:
                logging.info(f"Queue processing: {file_name}")
                file_info = await extract_file_info(message, filename)

                data: dict = PTN.parse(filename)
                media_details_result = await get_media_details(data)

                media_id: Optional[str] = media_details_result.get("media_id")
                media_details: Optional[dict] = media_details_result.get(
                    "media_details"
                )
                episode_details: Optional[dict] = media_details_result.get(
                    "episode_details"
                )

                if media_id:
                    if "season" in data and "episode" in data:
                        await process_series(
                            media_id,
                            data,
                            media_details,
                            episode_details,
                            file_info,
                        )
                    else:
                        await process_movie(media_id, media_details, file_info)
                else:
                    await process_files(file_info)

                logging.info(f"Queue successfully indexed: {file_name}")

        except Exception as e:
            logging.error(
                f"Error in process_index_queue: {e}\n{traceback.format_exc()}"
            )
        finally:
            index_queue.task_done()


async def fetch_message(
    client: TelegramClient, chat_id: int, message_id: int
) -> Optional[Message]:
    try:
        messages = await client.get_messages(chat_id, ids=[message_id])
        if not messages:
            return None

        message = messages[0]
        if not message:
            return None

        logging.debug(f"Fetched message: {message.id}")
        return message
    except FloodWaitError as e:
        logging.warning(f"Rate limit hit. Waiting for {e.seconds} seconds.")
        await asyncio.sleep(e.seconds)
        return await fetch_message(client, chat_id, message_id)
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
        return None


async def send_message(
    client: TelegramClient, message: Message, dest_channel: int
) -> Message:
    return await client.send_message(
        dest_channel, message=message.message or "", file=message.media
    )


async def index_channel(
    client: TelegramClient,
    chat_id: int,
    first_message_id: int,
    last_message_id: int,
    batch_size: int = 50,
    progress_callback=None,
) -> Dict[str, int]:
    """Index a range of messages from a channel, applying scraping filters.

    Returns a stats dict with counters for indexed, skipped, and errored
    messages.
    """
    stats: Dict[str, int] = {
        "indexed": 0,
        "skipped_size": 0,
        "skipped_keyword": 0,
        "skipped_ext": 0,
        "skipped_no_media": 0,
        "errors": 0,
    }

    progress_counter = 0
    current_message_id: int = first_message_id
    while current_message_id <= last_message_id:
        batch_message_ids: list[int] = list(
            range(
                current_message_id,
                min(current_message_id + batch_size, last_message_id + 1),
            )
        )
        for message_id in batch_message_ids:
            try:
                orig_message: Optional[Message] = await fetch_message(
                    client, chat_id, message_id
                )

                # Only process documents and videos
                if not orig_message or not (
                    orig_message.document or getattr(orig_message, "video", None)
                ):
                    stats["skipped_no_media"] += 1
                    await asyncio.sleep(1)
                    progress_counter += 1
                    if progress_callback and progress_counter % 25 == 0:
                        await progress_callback(stats, message_id)
                    continue

                title: str = get_file_title(orig_message)
                filename: str = format_filename(title)

                # ── Apply scraping filters ──────────────────────────
                file_name = getattr(orig_message.file, "name", "") or ""
                file_size = getattr(orig_message.file, "size", 0) or 0

                skip, reason = scraping_filters.should_skip(
                    filename=file_name, file_size=file_size
                )
                if skip:
                    logging.info(
                        f"Skipped message {message_id}: {reason} "
                        f"(file: {file_name})"
                    )
                    # Categorise the skip reason for stats
                    if "too small" in (reason or ""):
                        stats["skipped_size"] += 1
                    elif "Adult keyword" in (reason or ""):
                        stats["skipped_keyword"] += 1
                    elif "extension" in (reason or "").lower():
                        stats["skipped_ext"] += 1
                    elif "Multipart" in (reason or ""):
                        stats[
                            "skipped_ext"
                        ] += 1  # Group multipart skip as extension/format skip
                    await asyncio.sleep(1)
                    progress_counter += 1
                    if progress_callback and progress_counter % 25 == 0:
                        await progress_callback(stats, message_id)
                    continue
                # ────────────────────────────────────────────────────

                # Forward message to LOGS_CHANNEL only if it passed all filters!
                message = await send_message(client, orig_message, LOGS_CHANNEL)

                file_info = await extract_file_info(message, filename)

                data: dict = PTN.parse(filename)
                media_details_result = await get_media_details(data)

                media_id: Optional[str] = media_details_result.get("media_id")
                media_details: Optional[dict] = media_details_result.get(
                    "media_details"
                )
                episode_details: Optional[dict] = media_details_result.get(
                    "episode_details"
                )

                if media_id:
                    if "season" in data and "episode" in data:
                        await process_series(
                            media_id,
                            data,
                            media_details,
                            episode_details,
                            file_info,
                        )
                    else:
                        await process_movie(media_id, media_details, file_info)
                else:
                    await process_files(file_info)

                stats["indexed"] += 1
                await asyncio.sleep(1)

                progress_counter += 1
                if progress_callback and progress_counter % 25 == 0:
                    await progress_callback(stats, message_id)

            except Exception as e:
                logging.error(f"Error indexing message {message_id}: {e}")
                stats["errors"] += 1
        current_message_id += batch_size

    return stats
