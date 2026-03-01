"""
Telegram MTProto streaming support with parallel chunk downloads.

This module provides:
- TelegramSessionManager: Manages the Telethon client session
- TelegramMediaRef: Parsed reference to Telegram media (t.me links or file_id)
- ParallelTransferrer: FastTelethon-based parallel chunk downloader for high-speed streaming

Based on FastTelethon technique from mautrix-telegram for parallel downloads.
"""

import asyncio
import base64
import logging
import math
import re
import struct
from dataclasses import dataclass
from io import BytesIO
from typing import AsyncGenerator, Optional, Union
from urllib.parse import urlparse

from telethon import TelegramClient, utils
from telethon.crypto import AuthKey
from telethon.network import MTProtoSender
from telethon.sessions import StringSession
from telethon.tl.alltlobjects import LAYER
from telethon.tl.functions import InvokeWithLayerRequest
from telethon.tl.functions.auth import (
    ExportAuthorizationRequest,
    ImportAuthorizationRequest,
)
from telethon.tl.functions.upload import GetFileRequest
from telethon.tl.types import (
    Document,
    InputDocumentFileLocation,
    InputFileLocation,
    InputPeerPhotoFileLocation,
    InputPhotoFileLocation,
    Message,
    MessageMediaDocument,
    MessageMediaPhoto,
    Photo,
)

from jackgram.bot.bot import API_ID, API_HASH, BOT_TOKEN, WORKERS

logger = logging.getLogger(__name__)

# Type aliases for file locations
TypeLocation = Union[
    Document,
    InputDocumentFileLocation,
    InputPeerPhotoFileLocation,
    InputFileLocation,
    InputPhotoFileLocation,
]

# File type IDs for Bot API file_id
FILE_TYPE_THUMBNAIL = 0
FILE_TYPE_PROFILE_PHOTO = 1
FILE_TYPE_PHOTO = 2
FILE_TYPE_VOICE = 3
FILE_TYPE_VIDEO = 4
FILE_TYPE_DOCUMENT = 5
FILE_TYPE_ENCRYPTED = 6
FILE_TYPE_TEMP = 7
FILE_TYPE_STICKER = 8
FILE_TYPE_AUDIO = 9
FILE_TYPE_ANIMATION = 10
FILE_TYPE_ENCRYPTED_THUMBNAIL = 11
FILE_TYPE_WALLPAPER = 12
FILE_TYPE_VIDEO_NOTE = 13
FILE_TYPE_SECURE_RAW = 14
FILE_TYPE_SECURE = 15
FILE_TYPE_BACKGROUND = 16
FILE_TYPE_DOCUMENT_AS_FILE = 17

# Flags in type_id
TYPE_ID_WEB_LOCATION_FLAG = 1 << 24
TYPE_ID_FILE_REFERENCE_FLAG = 1 << 25


@dataclass
class DecodedFileId:
    """Decoded Bot API file_id structure."""

    type_id: int
    dc_id: int
    id: int
    access_hash: int
    file_reference: bytes = b""
    has_web_location: bool = False
    has_reference: bool = False


def _decode_telegram_base64(s: str) -> bytes:
    """Decode Telegram's URL-safe base64."""
    s = s.replace("-", "+").replace("_", "/")
    padding = 4 - len(s) % 4
    if padding != 4:
        s += "=" * padding
    return base64.b64decode(s)


def _rle_decode(data: bytes) -> bytes:
    """RLE decode Telegram's file_id encoding."""
    result = bytearray()
    i = 0
    while i < len(data):
        if data[i] == 0 and i + 1 < len(data):
            result.extend(bytes(data[i + 1]))
            i += 2
        else:
            result.append(data[i])
            i += 1
    return bytes(result)


def decode_file_id(file_id: str) -> DecodedFileId:
    """
    Decode a Bot API file_id into its components.

    Supports both old and new file_id formats (including version 4 with high sub_versions).

    Args:
        file_id: Bot API file_id string

    Returns:
        DecodedFileId with parsed components

    Raises:
        ValueError: If file_id cannot be decoded
    """
    try:
        decoded = _decode_telegram_base64(file_id)
        data = _rle_decode(decoded)
    except Exception as e:
        raise ValueError(f"Failed to decode file_id base64: {e}") from e

    if len(data) < 20:
        raise ValueError(f"file_id too short: {len(data)} bytes")

    buf = BytesIO(data)

    # Read type_id (4 bytes, little-endian)
    type_id_raw = struct.unpack("<i", buf.read(4))[0]

    # Extract flags and actual type
    has_web_location = bool(type_id_raw & TYPE_ID_WEB_LOCATION_FLAG)
    has_reference = bool(type_id_raw & TYPE_ID_FILE_REFERENCE_FLAG)
    type_id = type_id_raw & 0xFFFFFF

    # Read dc_id (4 bytes)
    dc_id = struct.unpack("<i", buf.read(4))[0]

    file_reference = b""
    if has_reference:
        # Read TL string (length-prefixed)
        ref_len_byte = buf.read(1)[0]
        if ref_len_byte == 254:
            # Long string: next 3 bytes are length
            ref_len = struct.unpack("<I", buf.read(3) + b"\x00")[0]
        else:
            ref_len = ref_len_byte

        file_reference = buf.read(ref_len)

        # Skip padding to 4-byte alignment
        total_len = 1 + (3 if ref_len_byte == 254 else 0) + ref_len
        padding = total_len % 4
        if padding:
            buf.read(4 - padding)

    # Read id and access_hash (8 bytes each)
    remaining = buf.read()
    if len(remaining) < 16:
        raise ValueError(f"file_id remaining data too short: {len(remaining)} bytes")

    id_val = struct.unpack("<q", remaining[0:8])[0]
    access_hash = struct.unpack("<q", remaining[8:16])[0]

    return DecodedFileId(
        type_id=type_id,
        dc_id=dc_id,
        id=id_val,
        access_hash=access_hash,
        file_reference=file_reference,
        has_web_location=has_web_location,
        has_reference=has_reference,
    )


@dataclass
class TelegramMediaRef:
    """
    Parsed reference to Telegram media.

    Can be constructed from:
    - t.me links: https://t.me/channel/123, https://t.me/c/123456789/456
    - file_id: Direct Telegram file IDs
    """

    chat_id: Optional[Union[int, str]] = None  # Channel/group/user ID or username
    message_id: Optional[int] = None  # Message ID for t.me links
    file_id: Optional[str] = None  # Direct file reference


@dataclass
class MediaInfo:
    """Information about a Telegram media file."""

    file_id: str
    file_size: int
    mime_type: str
    file_name: Optional[str] = None
    duration: Optional[int] = None  # For video/audio
    width: Optional[int] = None  # For video/photo
    height: Optional[int] = None  # For video/photo
    dc_id: Optional[int] = None


def parse_telegram_url(url: str) -> TelegramMediaRef:
    """
    Parse a Telegram URL or file_id into a TelegramMediaRef.

    Supported formats:
    - https://t.me/channel/123 (public channel)
    - https://t.me/c/123456789/456 (private channel)
    - https://t.me/username/123 (user/channel by username)
    - file_id (base64-encoded)

    Args:
        url: The URL or file_id to parse

    Returns:
        TelegramMediaRef with parsed information
    """
    if not url:
        raise ValueError("URL cannot be empty")

    # Check if it's a t.me link
    parsed = urlparse(url)
    if parsed.netloc in ("t.me", "telegram.me", "telegram.dog"):
        path_parts = parsed.path.strip("/").split("/")

        if len(path_parts) >= 2:
            # Format: /c/chat_id/message_id (private channel)
            if path_parts[0] == "c" and len(path_parts) >= 3:
                try:
                    # Private channel IDs need -100 prefix
                    chat_id = int(f"-100{path_parts[1]}")
                    message_id = int(path_parts[2])
                    return TelegramMediaRef(chat_id=chat_id, message_id=message_id)
                except ValueError as e:
                    raise ValueError(
                        f"Invalid private channel URL format: {url}"
                    ) from e

            # Format: /username/message_id (public channel or user)
            else:
                try:
                    username = path_parts[0]
                    message_id = int(path_parts[1])
                    return TelegramMediaRef(chat_id=username, message_id=message_id)
                except ValueError as e:
                    raise ValueError(f"Invalid public channel URL format: {url}") from e

        raise ValueError(f"Invalid Telegram URL format: {url}")

    # Check if it looks like a file_id (base64-like string)
    if re.match(r"^[A-Za-z0-9_-]+$", url) and len(url) > 20:
        return TelegramMediaRef(file_id=url)

    raise ValueError(f"Unrecognized Telegram URL or file_id format: {url}")


@dataclass
class DownloadSender:
    """Handles downloading chunks from a single connection."""

    client: TelegramClient
    sender: MTProtoSender
    request: GetFileRequest
    remaining: int
    stride: int

    async def next(self) -> Optional[bytes]:
        """Download the next chunk."""
        if not self.remaining:
            return None
        result = await self.client._call(self.sender, self.request)
        self.remaining -= 1
        self.request.offset += self.stride
        return result.bytes

    async def disconnect(self) -> None:
        """Disconnect this sender gracefully."""
        try:
            await self.sender.disconnect()
        except Exception:
            # Ignore errors during disconnect - connection may already be closed
            pass


class ParallelTransferrer:
    """
    Parallel chunk downloader using multiple DC connections and multiple accounts.

    Based on FastTelethon technique from mautrix-telegram, expanded to
    utilize multiple Telegram Client sessions if available.
    """

    def __init__(
        self, manager: "MultiSessionManager", dc_id: Optional[int] = None
    ) -> None:
        self.manager = manager

        # Keep loop reference from the first available client or asyncio event loop
        self.loop = asyncio.get_event_loop()

        self.dc_id = dc_id
        self.senders: Optional[list[DownloadSender]] = None
        # Cache auth keys per DC to avoid repeated ExportAuthorizationRequest calls
        self._dc_auth_keys: dict[int, "AuthKey"] = {}

    async def _cleanup(self) -> None:
        """Clean up all sender connections gracefully."""
        if self.senders:
            # Use return_exceptions=True to prevent one failed disconnect from blocking others
            await asyncio.gather(
                *[sender.disconnect() for sender in self.senders],
                return_exceptions=True,
            )
            self.senders = None

    @staticmethod
    def _get_connection_count(
        file_size: int, max_count: int = 20, full_size: int = 100 * 1024 * 1024
    ) -> int:
        """
        Calculate optimal number of connections based on file size.

        Small files use fewer connections, large files use more.
        """
        if file_size > full_size:
            return max_count
        return max(1, math.ceil((file_size / full_size) * max_count))

    async def _create_sender(self) -> tuple[TelegramClient, MTProtoSender]:
        """Create a new MTProtoSender connection to the DC from the session manager pool."""
        client = await self.manager.get_client()

        # If dc_id not specified, default to client's primary DC
        dc_id = self.dc_id or client.session.dc_id
        dc = await client._get_dc(dc_id)

        # Use cached auth key first, then fall back to session key if same DC
        auth_key = self._dc_auth_keys.get(dc_id)
        if auth_key is None and dc_id == client.session.dc_id:
            auth_key = client.session.auth_key

        sender = MTProtoSender(auth_key, loggers=client._log)
        await sender.connect(
            client._connection(
                dc.ip_address,
                dc.port,
                dc.id,
                loggers=client._log,
                proxy=client._proxy,
            )
        )
        if not auth_key:
            logger.debug(
                f"[Parallel] Exporting auth to DC {dc_id} for session {id(client.session.auth_key)}"
            )
            auth = await client(ExportAuthorizationRequest(dc_id))
            # Save and restore _init_request.query to avoid permanently mutating client state
            original_query = client._init_request.query
            try:
                client._init_request.query = ImportAuthorizationRequest(
                    id=auth.id, bytes=auth.bytes
                )
                req = InvokeWithLayerRequest(LAYER, client._init_request)
                await sender.send(req)
            finally:
                client._init_request.query = original_query
            # Cache the auth key so subsequent senders reuse it
            self._dc_auth_keys[dc_id] = sender.auth_key

        return client, sender

    async def _create_download_sender(
        self,
        file: TypeLocation,
        index: int,
        part_size: int,
        stride: int,
        part_count: int,
        base_offset: int = 0,
    ) -> DownloadSender:
        """Create a DownloadSender for a specific chunk offset."""
        client, sender = await self._create_sender()
        return DownloadSender(
            client=client,
            sender=sender,
            request=GetFileRequest(
                file, offset=base_offset + index * part_size, limit=part_size
            ),
            stride=stride,
            remaining=part_count,
        )

    async def _init_download(
        self,
        connections: int,
        file: TypeLocation,
        part_count: int,
        part_size: int,
        base_offset: int = 0,
    ) -> None:
        """Initialize all download senders."""
        minimum, remainder = divmod(part_count, connections)

        def get_part_count() -> int:
            nonlocal remainder
            if remainder > 0:
                remainder -= 1
                return minimum + 1
            return minimum

        # Create first sender synchronously to handle auth export
        self.senders = [
            await self._create_download_sender(
                file,
                0,
                part_size,
                connections * part_size,
                get_part_count(),
                base_offset,
            ),
            *await asyncio.gather(
                *[
                    self._create_download_sender(
                        file,
                        i,
                        part_size,
                        connections * part_size,
                        get_part_count(),
                        base_offset,
                    )
                    for i in range(1, connections)
                ]
            ),
        ]

    async def download(
        self,
        file: TypeLocation,
        file_size: int,
        offset: int = 0,
        limit: Optional[int] = None,
        part_size_kb: Optional[float] = None,
        connection_count: Optional[int] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Download file in parallel chunks.

        Args:
            file: The file location to download
            file_size: Total file size in bytes
            offset: Byte offset to start from (for range requests)
            limit: Number of bytes to download (None for entire file)
            part_size_kb: Chunk size in KB (auto-calculated if None)
            connection_count: Number of parallel connections (auto-calculated if None)

        Yields:
            Chunks of file data
        """
        # Calculate actual range
        if limit is None:
            limit = file_size - offset

        # Clamp connection count to configured max
        max_connections = min(WORKERS, 20)
        connection_count = connection_count or self._get_connection_count(
            limit, max_count=max_connections
        )
        connection_count = min(connection_count, max_connections)

        part_size = int(
            (part_size_kb or utils.get_appropriated_part_size(file_size)) * 1024
        )
        # Round offset down to part boundary
        aligned_offset = (offset // part_size) * part_size
        skip_bytes = offset - aligned_offset

        part_count = math.ceil((limit + skip_bytes) / part_size)

        logger.debug(
            f"Starting parallel download: {connection_count} connections, "
            f"{part_size} bytes/part, {part_count} parts, offset={offset}, aligned_offset={aligned_offset}"
        )

        await self._init_download(
            connection_count, file, part_count, part_size, base_offset=aligned_offset
        )

        try:
            part = 0
            bytes_yielded = 0
            while part < part_count and bytes_yielded < limit:
                tasks = [
                    self.loop.create_task(sender.next()) for sender in self.senders
                ]
                for task in tasks:
                    data = await task
                    if not data:
                        break

                    # Handle offset alignment - skip initial bytes if needed
                    if skip_bytes > 0:
                        if len(data) <= skip_bytes:
                            skip_bytes -= len(data)
                            part += 1
                            continue
                        data = data[skip_bytes:]
                        skip_bytes = 0

                    # Handle limit - truncate if we'd exceed
                    remaining = limit - bytes_yielded
                    if len(data) > remaining:
                        data = data[:remaining]

                    yield data
                    bytes_yielded += len(data)
                    part += 1

                    if bytes_yielded >= limit:
                        break

            logger.debug("Parallel download finished, cleaning up connections")
        finally:
            await self._cleanup()


class _SingleSenderPool:
    """
    Pool of persistent ``MTProtoSender`` connections per DC and Session.

    Instead of creating a new connection for every HLS segment request
    (which involves handshake + auth export overhead), this pool maintains
    a queue of idle senders per (session_key, DC). When a caller needs a sender, it
    borrows one from the pool (or creates a new one if the pool is empty).
    After use, the sender is returned to the pool for reuse.

    Senders that have been idle longer than ``_MAX_IDLE_SECONDS`` are
    discarded on checkout.
    """

    _MAX_IDLE_SECONDS = 120.0  # discard senders idle longer than this

    def __init__(self) -> None:
        # (session_auth_key_id, dc_id) -> list of (sender, auth_key, last_used_monotonic)
        self._pool: dict[
            tuple[int, int], list[tuple[MTProtoSender, AuthKey, float]]
        ] = {}
        self._lock = asyncio.Lock()
        # Cached auth keys per (session_auth_key_id, DC)
        self._auth_keys: dict[tuple[int, int], AuthKey] = {}

    def _get_session_key(self, client: TelegramClient) -> int:
        """Returns a unique identifier for the current client session."""
        return id(client.session.auth_key)

    async def acquire(
        self,
        client: TelegramClient,
        dc_id: int,
    ) -> tuple[MTProtoSender, AuthKey]:
        """
        Borrow a connected ``MTProtoSender`` for *dc_id*.

        Returns an existing idle sender if one is available, otherwise
        creates a new one (handling auth export if needed).
        """
        import time as _time

        session_key = self._get_session_key(client)
        pool_key = (session_key, dc_id)

        async with self._lock:
            bucket = self._pool.get(pool_key, [])
            now = _time.monotonic()
            # Try to find a live sender
            while bucket:
                sender, auth_key, last_used = bucket.pop()
                idle = now - last_used
                if idle > self._MAX_IDLE_SECONDS:
                    # Stale -- disconnect quietly
                    logger.debug(
                        "[sender_pool] Discarding stale sender for Session %s DC %d (idle %.0fs)",
                        session_key,
                        dc_id,
                        idle,
                    )
                    try:
                        await sender.disconnect()
                    except Exception:
                        pass
                    continue
                # Check if still connected
                if sender.is_connected():
                    logger.debug(
                        "[sender_pool] Reusing sender for Session %s DC %d (idle %.1fs)",
                        session_key,
                        dc_id,
                        idle,
                    )
                    return sender, auth_key
                else:
                    logger.debug(
                        "[sender_pool] Sender for Session %s DC %d disconnected, discarding",
                        session_key,
                        dc_id,
                    )
                    try:
                        await sender.disconnect()
                    except Exception:
                        pass

        # No reusable sender -- create a new one
        logger.debug("[sender_pool] Creating new sender for DC %d", dc_id)

        # NOTE: Called outside of lock to avoid blocking other clients
        # _create_sender manages its own local auth_keys caching safely.

        # We need to recreate the create_sender logic inline because it needs await
        auth_key = self._auth_keys.get(pool_key)
        if auth_key is None and dc_id == client.session.dc_id:
            auth_key = client.session.auth_key

        dc = await client._get_dc(dc_id)
        sender = MTProtoSender(auth_key, loggers=client._log)
        await sender.connect(
            client._connection(
                dc.ip_address,
                dc.port,
                dc.id,
                loggers=client._log,
                proxy=client._proxy,
            )
        )
        if not auth_key:
            logger.debug("[sender_pool] Exporting auth to DC %d", dc_id)
            auth = await client(ExportAuthorizationRequest(dc_id))
            # Save and restore _init_request.query to avoid permanently mutating client state
            original_query = client._init_request.query
            try:
                client._init_request.query = ImportAuthorizationRequest(
                    id=auth.id, bytes=auth.bytes
                )
                req = InvokeWithLayerRequest(LAYER, client._init_request)
                await sender.send(req)
            finally:
                client._init_request.query = original_query
            auth_key = sender.auth_key
            self._auth_keys[pool_key] = auth_key
        return sender, auth_key

    async def release(
        self,
        client: TelegramClient,
        dc_id: int,
        sender: MTProtoSender,
        auth_key: AuthKey,
    ) -> None:
        """Return a sender to the pool for reuse."""
        import time as _time

        session_key = self._get_session_key(client)
        pool_key = (session_key, dc_id)

        # Cache auth key
        if auth_key is not None:
            self._auth_keys[pool_key] = auth_key

        if not sender.is_connected():
            logger.debug(
                "[sender_pool] Sender for Session %s DC %d disconnected, not returning to pool",
                session_key,
                dc_id,
            )
            try:
                await sender.disconnect()
            except Exception:
                pass
            return

        async with self._lock:
            bucket = self._pool.setdefault(pool_key, [])
            bucket.append((sender, auth_key, _time.monotonic()))
            logger.debug(
                "[sender_pool] Returned sender to pool for Session %s DC %d (pool size=%d)",
                session_key,
                dc_id,
                len(bucket),
            )

    async def discard(self, sender: MTProtoSender) -> None:
        """Disconnect and discard a sender without returning it to the pool."""
        try:
            await sender.disconnect()
        except Exception:
            pass

    async def close_all(self) -> None:
        """Disconnect all pooled senders."""
        async with self._lock:
            for pool_key, bucket in self._pool.items():
                for sender, _, _ in bucket:
                    try:
                        await sender.disconnect()
                    except Exception:
                        pass
                bucket.clear()
            self._pool.clear()
            self._auth_keys.clear()


class MultiSessionManager:
    """
    Manages multiple Telethon client sessions for load balancing.

    Features:
    - Lazy and eager initialization
    - Session persistence via StringSession
    - Round-robin load balancing across multiple accounts
    - Automatic reconnection on disconnect
    - Thread-safe with asyncio lock
    - Persistent sender pool for HLS segment downloads
    """

    _MEDIA_INFO_CACHE_TTL = 3600  # 1 hour

    def __init__(self):
        self._clients: list[TelegramClient] = []
        self._lock = asyncio.Lock()
        self._initialized = False
        self._round_robin_index = 0
        # In-memory cache: key → (MediaInfo, expiry_timestamp)
        self._media_info_cache: dict[str, tuple["MediaInfo", float]] = {}
        # Persistent sender pool for single-connection downloads (HLS).
        self._sender_pool = _SingleSenderPool()

    async def initialize_all(self):
        """Initialize all configured sessions."""
        async with self._lock:
            if self._initialized:
                return

            if not API_ID or not API_HASH:
                raise ValueError(
                    "Telegram API credentials not configured (API_ID, API_HASH)"
                )

            from jackgram.bot.bot import SESSION_STRINGS

            if not SESSION_STRINGS:
                logger.warning(
                    "No SESSION_STRINGS configured. User client features will be disabled."
                )
                self._initialized = True
                return

            logger.info(f"Initializing {len(SESSION_STRINGS)} Telegram clients...")

            for i, session_str in enumerate(SESSION_STRINGS):
                try:
                    client = TelegramClient(
                        StringSession(session_str),
                        API_ID,
                        API_HASH,
                        request_retries=3,
                        connection_retries=3,
                        retry_delay=1,
                        timeout=10.0,
                    )
                    await client.connect()

                    if not await client.is_user_authorized():
                        logger.error(
                            f"Telegram session {i} is not authorized. Skipping."
                        )
                        continue

                    self._clients.append(client)
                except Exception as e:
                    logger.error(f"Failed to initialize session {i}: {e}")

            if not self._clients:
                raise RuntimeError(
                    "Failed to authorize any of the provided Telegram sessions."
                )

            self._initialized = True
            logger.info(
                f"Successfully initialized {len(self._clients)} Telegram clients."
            )

    async def get_client(self) -> TelegramClient:
        """
        Get a Telethon client using round-robin load balancing.

        Returns:
            Connected TelegramClient instance

        Raises:
            RuntimeError: If no clients are available
        """
        if not self._initialized:
            await self.initialize_all()

        async with self._lock:
            if not self._clients:
                raise RuntimeError("No Telegram clients are available/authorized.")

            # Find next connected client
            checked = 0
            while checked < len(self._clients):
                client = self._clients[self._round_robin_index]
                self._round_robin_index = (self._round_robin_index + 1) % len(
                    self._clients
                )

                if client.is_connected():
                    return client
                else:
                    try:
                        await client.connect()
                        if client.is_connected():
                            return client
                    except Exception as e:
                        logger.warning(f"Client connection failed: {e}")

                checked += 1

            raise RuntimeError(
                "All Telegram clients disconnected and could not reconnect."
            )

    async def close_all(self):
        """Disconnect all clients."""
        async with self._lock:
            for client in self._clients:
                if client.is_connected():
                    await client.disconnect()
            self._clients.clear()
            self._initialized = False
            await self._sender_pool.close_all()

    async def get_message(self, ref: TelegramMediaRef) -> Message:
        """
        Get a message by its reference.

        Args:
            ref: TelegramMediaRef with chat_id and message_id

        Returns:
            The Message object

        Raises:
            ValueError: If reference is incomplete
            Various Telegram errors: ChannelPrivateError, MessageIdInvalidError, etc.
        """
        if ref.chat_id is None or ref.message_id is None:
            raise ValueError("chat_id and message_id are required to fetch a message")

        client = await self.get_client()
        messages = await client.get_messages(ref.chat_id, ids=ref.message_id)

        if not messages:
            raise ValueError(f"Message {ref.message_id} not found in {ref.chat_id}")

        return messages

    def resolve_file_id(self, file_id: str) -> tuple[Union[Document, Photo], int]:
        """
        Resolve a Bot API file_id to a Telethon Document or Photo object.

        Supports both old and new file_id formats by using a custom decoder
        that handles all version/sub_version combinations.

        Args:
            file_id: Bot API style file_id string

        Returns:
            Tuple of (Document or Photo object, dc_id)

        Raises:
            ValueError: If file_id is invalid or cannot be decoded
        """
        # First try Telethon's built-in resolver (works for older formats)
        media = utils.resolve_bot_file_id(file_id)
        if media is not None:
            if isinstance(media, Document):
                return media, media.dc_id
            elif isinstance(media, Photo):
                return media, media.dc_id

        # Fall back to our custom decoder for newer formats
        logger.debug("Telethon couldn't decode file_id, trying custom decoder")
        decoded = decode_file_id(file_id)

        # Determine if it's a photo or document based on type_id
        if decoded.type_id in (
            FILE_TYPE_PHOTO,
            FILE_TYPE_PROFILE_PHOTO,
            FILE_TYPE_THUMBNAIL,
        ):
            # Create a Photo object
            return (
                Photo(
                    id=decoded.id,
                    access_hash=decoded.access_hash,
                    file_reference=decoded.file_reference,
                    date=None,
                    sizes=[],  # Empty, we don't have size info from file_id
                    dc_id=decoded.dc_id,
                ),
                decoded.dc_id,
            )
        else:
            # Create a Document object (video, audio, document, etc.)
            return (
                Document(
                    id=decoded.id,
                    access_hash=decoded.access_hash,
                    file_reference=decoded.file_reference,
                    date=None,
                    mime_type="",  # Unknown from file_id
                    size=0,  # Unknown from file_id
                    thumbs=None,
                    dc_id=decoded.dc_id,
                    attributes=[],
                ),
                decoded.dc_id,
            )

    def _media_info_cache_key(self, ref: TelegramMediaRef) -> str:
        """Derive an in-memory cache key for a TelegramMediaRef."""
        if ref.file_id and not ref.message_id:
            return f"fid:{ref.file_id}"
        if ref.chat_id is not None and ref.message_id is not None:
            return f"chat:{ref.chat_id}:msg:{ref.message_id}"
        return ""

    async def get_media_info(
        self, ref: TelegramMediaRef, use_cache: bool = True
    ) -> MediaInfo:
        """
        Get media information (size, type, attributes) for a Telegram reference.

        Args:
            ref: TelegramMediaRef to look up
            use_cache: Whether to use the in-memory cache

        Returns:
            MediaInfo object with file details

        Raises:
            ValueError: If reference is invalid or unsupported
            RuntimeError: If media info cannot be extracted
        """
        # Create a cache key from the reference
        cache_key = ""
        if ref.file_id:
            cache_key = f"file_id:{ref.file_id}"
        elif ref.chat_id and ref.message_id:
            cache_key = f"msg:{ref.chat_id}:{ref.message_id}"
        else:
            raise ValueError("Invalid TelegramMediaRef")

        if use_cache:
            import time

            now = time.time()
            if cache_key in self._media_info_cache:
                info, expiry = self._media_info_cache[cache_key]
                if now < expiry:
                    return info
                else:
                    del self._media_info_cache[cache_key]

        # Resolution depends on whether we have a file_id or a chat_id+message_id
        media = None
        dc_id = None
        file_name = None
        duration = None
        width = None
        height = None

        if ref.file_id:
            # Resolve file_id directly
            media, dc_id = self.resolve_file_id(ref.file_id)

            # Try to extract extra attributes if available
            # Note: For file_id, we often don't have full attributes unless
            # we fetch the original message, but we do our best.
            if isinstance(media, Document):
                for attr in getattr(media, "attributes", []):
                    if isinstance(attr, DocumentAttributeFilename):
                        file_name = attr.file_name
                    elif isinstance(attr, DocumentAttributeVideo):
                        duration = attr.duration
                        width = attr.w
                        height = attr.h
            elif isinstance(media, Photo):
                # For basic file_id photos, we don't have dimensions easily
                pass

        elif ref.chat_id and ref.message_id:
            # Fetch message to get media
            messages = await self.get_message(ref)
            message = messages[0] if isinstance(messages, list) else messages

            if not message.media:
                raise ValueError(
                    f"Message {ref.message_id} in {ref.chat_id} does not contain media"
                )

            # Extract media object and attributes
            if isinstance(message.media, MessageMediaDocument):
                doc = message.media.document
                if not isinstance(doc, Document):
                    raise ValueError("Invalid document in message")

                # Extract attributes
                file_name = None
                duration = None
                width = None
                height = None

                for attr in doc.attributes:
                    attr_dict = attr.to_dict()
                    if "file_name" in attr_dict:
                        file_name = attr_dict["file_name"]
                    if "duration" in attr_dict:
                        duration = attr_dict["duration"]
                    if "w" in attr_dict:
                        width = attr_dict["w"]
                    if "h" in attr_dict:
                        height = attr_dict["h"]

                return MediaInfo(
                    file_id=str(doc.id),
                    file_size=doc.size,
                    mime_type=doc.mime_type or "application/octet-stream",
                    file_name=file_name,
                    duration=duration,
                    width=width,
                    height=height,
                    dc_id=doc.dc_id,
                )

            elif isinstance(message.media, MessageMediaPhoto):
                photo = message.media.photo
                if not photo:
                    raise ValueError("Invalid photo in message")

                # Get largest photo size
                largest = max(
                    photo.sizes,
                    key=lambda s: getattr(s, "size", 0) if hasattr(s, "size") else 0,
                )

                return MediaInfo(
                    file_id=str(photo.id),
                    file_size=getattr(largest, "size", 0),
                    mime_type="image/jpeg",
                    width=getattr(largest, "w", None),
                    height=getattr(largest, "h", None),
                    dc_id=photo.dc_id,
                )

            else:
                raise ValueError(f"Unsupported media type: {type(message.media)}")

    async def validate_file_access(
        self,
        ref: TelegramMediaRef,
        file_size: Optional[int] = None,
    ) -> None:
        """
        Validate that the session can access the file before streaming.

        This makes a small test request to verify the file_reference is valid
        and the session has access. This should be called before streaming to
        avoid mid-stream errors.

        Args:
            ref: TelegramMediaRef pointing to the media
            file_size: Optional file size for file_id mode

        Raises:
            FileReferenceExpiredError: If file_id belongs to different session
            Various Telegram errors: For access issues
        """
        client = await self.get_client()

        if ref.file_id and not ref.message_id:
            media, dc_id = self.resolve_file_id(ref.file_id)

            if isinstance(media, Document):
                file_location = InputDocumentFileLocation(
                    id=media.id,
                    access_hash=media.access_hash,
                    file_reference=media.file_reference,
                    thumb_size="",
                )
            elif isinstance(media, Photo):
                largest = max(
                    media.sizes,
                    key=lambda s: getattr(s, "size", 0) if hasattr(s, "size") else 0,
                )
                file_location = InputPhotoFileLocation(
                    id=media.id,
                    access_hash=media.access_hash,
                    file_reference=media.file_reference,
                    thumb_size=getattr(largest, "type", "x"),
                )
            else:
                raise ValueError(f"Unsupported media type from file_id: {type(media)}")

            # Make a small test request to validate access
            # Use ParallelTransferrer which handles DC migration properly
            transferrer = ParallelTransferrer(self, dc_id)
            try:
                # Just request a tiny amount to validate - the download method handles DC connections
                download_gen = transferrer.download(
                    file_location, file_size or 4096, offset=0, limit=4096
                )
                try:
                    await download_gen.__anext__()  # Get first chunk to validate
                except StopAsyncIteration:
                    pass  # Empty file is still valid
                finally:
                    # Properly close the generator
                    await download_gen.aclose()
                logger.debug(
                    "[validate_file_access] file_id access validated on DC %d", dc_id
                )
            except Exception as e:
                logger.warning(f"[validate_file_access] file_id validation failed: {e}")
                raise
            finally:
                # Clean up transferrer connections
                await transferrer._cleanup()

    async def _resolve_file_location(
        self,
        ref: TelegramMediaRef,
        file_size: Optional[int] = None,
    ) -> tuple["TypeLocation", int, int]:
        """
        Resolve a ``TelegramMediaRef`` into a Telegram file location.

        Returns:
            ``(file_location, dc_id, actual_file_size)``
        """
        # Handle file_id reference (no message needed, fast local parse)
        if ref.file_id and not ref.message_id:
            media, dc_id = self.resolve_file_id(ref.file_id)

            if isinstance(media, Document):
                actual_file_size = file_size or media.size
                if actual_file_size == 0:
                    raise ValueError(
                        "file_size parameter is required when streaming by file_id. "
                        "The file_id doesn't contain size information."
                    )
                file_location = InputDocumentFileLocation(
                    id=media.id,
                    access_hash=media.access_hash,
                    file_reference=media.file_reference,
                    thumb_size="",
                )
                return file_location, dc_id, actual_file_size

            elif isinstance(media, Photo):
                largest = max(
                    media.sizes,
                    key=lambda s: getattr(s, "size", 0) if hasattr(s, "size") else 0,
                )
                actual_file_size = file_size or getattr(largest, "size", 0)
                if actual_file_size == 0:
                    raise ValueError(
                        "file_size parameter is required when streaming by file_id. "
                        "The file_id doesn't contain size information."
                    )
                file_location = InputPhotoFileLocation(
                    id=media.id,
                    access_hash=media.access_hash,
                    file_reference=media.file_reference,
                    thumb_size=getattr(largest, "type", "x"),
                )
                return file_location, dc_id, actual_file_size

            else:
                raise ValueError(f"Unsupported media type from file_id: {type(media)}")

        # Handle message-based reference (requires Telegram API call)
        message = await self.get_message(ref)

        if not message.media:
            raise ValueError(f"Message {ref.message_id} does not contain media")

        if isinstance(message.media, MessageMediaDocument):
            doc = message.media.document
            if not isinstance(doc, Document):
                raise ValueError("Invalid document")

            file_location = InputDocumentFileLocation(
                id=doc.id,
                access_hash=doc.access_hash,
                file_reference=doc.file_reference,
                thumb_size="",
            )
            return file_location, doc.dc_id, doc.size

        elif isinstance(message.media, MessageMediaPhoto):
            photo = message.media.photo
            if not photo:
                raise ValueError("Invalid photo")

            largest = max(
                photo.sizes,
                key=lambda s: getattr(s, "size", 0) if hasattr(s, "size") else 0,
            )
            file_location = InputPhotoFileLocation(
                id=photo.id,
                access_hash=photo.access_hash,
                file_reference=photo.file_reference,
                thumb_size=getattr(largest, "type", ""),
            )
            return file_location, photo.dc_id, getattr(largest, "size", 0)

        else:
            raise ValueError(f"Unsupported media type: {type(message.media)}")

    async def stream_media(
        self,
        ref: TelegramMediaRef,
        offset: int = 0,
        limit: Optional[int] = None,
        file_size: Optional[int] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream media content with **parallel** downloads (fast Telethon).

        Creates multiple MTProtoSender connections to the file's DC for
        maximum throughput.  Best suited for large/full-file downloads
        (e.g. the non-transcode ``/proxy/telegram/stream`` endpoint).

        For small byte-range fetches (HLS segments) use
        ``stream_media_single`` instead.

        Args:
            ref: TelegramMediaRef pointing to the media
            offset: Byte offset to start from
            limit: Number of bytes to download (None for entire file)
            file_size: Optional file size (required for file_id streaming)

        Yields:
            Chunks of media data
        """
        client = await self.get_client()
        file_location, dc_id, actual_file_size = await self._resolve_file_location(
            ref, file_size
        )

        transferrer = ParallelTransferrer(self, dc_id)
        try:
            async for chunk in transferrer.download(
                file_location,
                actual_file_size,
                offset=offset,
                limit=limit,
            ):
                yield chunk
        finally:
            await transferrer._cleanup()

    async def stream_media_single(
        self,
        ref: TelegramMediaRef,
        offset: int = 0,
        limit: Optional[int] = None,
        file_size: Optional[int] = None,
    ) -> AsyncGenerator[bytes, None]:
        """
        Stream media content over a **pooled** single MTProto connection.

        Borrows a persistent ``MTProtoSender`` from ``_SingleSenderPool``
        for the target DC.  The sender is returned to the pool after the
        download completes so the next request reuses the same TCP
        connection (no handshake, no ``ExportAuthorizationRequest``).

        This is ideal for small byte-range fetches (HLS segments, probe
        headers) where spinning up connections per request is wasteful.

        Args:
            ref: TelegramMediaRef pointing to the media
            offset: Byte offset to start from
            limit: Number of bytes to download (None for entire file)
            file_size: Optional file size (required for file_id streaming)

        Yields:
            Chunks of media data
        """
        client = await self.get_client()
        file_location, dc_id, actual_file_size = await self._resolve_file_location(
            ref, file_size
        )

        if offset >= actual_file_size:
            return

        if limit is None:
            limit = actual_file_size - offset

        part_size = int(utils.get_appropriated_part_size(actual_file_size) * 1024)
        aligned_offset = (offset // part_size) * part_size
        skip_bytes = offset - aligned_offset
        part_count = math.ceil((limit + skip_bytes) / part_size)

        logger.debug(
            "[single] DC %d: offset=%d, limit=%d, parts=%d, part_size=%d",
            dc_id,
            offset,
            limit,
            part_count,
            part_size,
        )

        sender, auth_key = await self._sender_pool.acquire(client, dc_id)
        sender_ok = True  # track whether to return to pool or discard

        try:
            request = GetFileRequest(
                file_location, offset=aligned_offset, limit=part_size
            )
            bytes_yielded = 0

            for _ in range(part_count):
                if bytes_yielded >= limit:
                    break
                try:
                    result = await client._call(sender, request)
                except Exception:
                    sender_ok = False
                    raise
                data = result.bytes
                if not data:
                    break
                request.offset += part_size

                # Handle offset alignment
                if skip_bytes > 0:
                    if len(data) <= skip_bytes:
                        skip_bytes -= len(data)
                        continue
                    data = data[skip_bytes:]
                    skip_bytes = 0

                # Trim to limit
                remaining = limit - bytes_yielded
                if len(data) > remaining:
                    data = data[:remaining]

                bytes_yielded += len(data)
                yield data
        finally:
            if sender_ok:
                await self._sender_pool.release(client, dc_id, sender, auth_key)
            else:
                await self._sender_pool.discard(sender)

    @property
    def is_initialized(self) -> bool:
        """Check if any client is initialized and connected."""
        return self._initialized and any(
            client.is_connected() for client in self._clients
        )


# Global session manager instance
multi_session_manager = MultiSessionManager()
