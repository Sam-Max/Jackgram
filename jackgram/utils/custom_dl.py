import asyncio
import logging
from typing import AsyncGenerator

from pyrogram import Client, raw
from pyrogram.session import Session, Auth
from pyrogram.errors import AuthBytesInvalid
from pyrogram.file_id import FileId

from jackgram.server.exceptions import FileNotFound
from jackgram.utils.file_properties import get_file_ids


class TelegramStreamer:
    def __init__(self, client: Client):
        self.clean_timer = 30 * 60
        self.client: Client = client
        self.__cached_file_ids = {}
        asyncio.create_task(self._clean_cache())

    async def get_file_properties(self, request, secure_hash: str) -> FileId:
        """
        Retrieves the properties of a media file using a secure hash.
        Uses cached results if available; otherwise, generates and caches the properties.
        """
        if secure_hash not in self.__cached_file_ids:
            file_id = await get_file_ids(request, secure_hash)
            logging.info(f"File ID: {file_id}")
            if not file_id:
                raise FileNotFound
            self.__cached_file_ids[secure_hash] = file_id
        return self.__cached_file_ids[secure_hash]

    async def yield_file(
        self,
        file_id: FileId,
        offset: int,
        first_part_cut: int,
        last_part_cut: int,
        part_count: int,
        chunk_size: int,
    ) -> AsyncGenerator[bytes, None]:
        """
        Custom generator that yields the bytes of a media file.
        """
        media_session = await self._generate_media_session(file_id)
        location = await self._get_location(file_id)
        current_part = 1

        try:
            while current_part <= part_count:
                response = await media_session.invoke(
                    raw.functions.upload.GetFile(
                        location=location, offset=offset, limit=chunk_size
                    )
                )

                if not isinstance(response, raw.types.upload.File):
                    break

                chunk = response.bytes
                if not chunk:
                    break

                if part_count == 1:
                    yield chunk[first_part_cut:last_part_cut]
                elif current_part == 1:
                    yield chunk[first_part_cut:]
                elif current_part == part_count:
                    yield chunk[:last_part_cut]
                else:
                    yield chunk

                current_part += 1
                offset += chunk_size

        except (TimeoutError, AttributeError):
            logging.error("Error occurred during file streaming.")
        except (asyncio.CancelledError, ConnectionResetError, BrokenPipeError):
            logging.warning("Streaming aborted by client")
        finally:
            logging.debug(f"Finished yielding file with {current_part} parts.")

    async def _clean_cache(self) -> None:
        """
        Periodically clears the cache to reduce memory usage.
        """
        while True:
            await asyncio.sleep(self.clean_timer)
            self.__cached_file_ids.clear()
            logging.debug("Cache cleared.")

    async def _generate_media_session(self, file_id: FileId) -> Session:
        """
        Creates or retrieves a media session for the data center containing the media file.
        """
        media_session = self.client.media_sessions.get(file_id.dc_id)

        if media_session is None:
            is_test_mode = await self.client.storage.test_mode()

            if file_id.dc_id != await self.client.storage.dc_id():
                media_session = await self._create_remote_session(
                    file_id.dc_id, is_test_mode
                )
            else:
                media_session = await self._create_local_session(
                    file_id.dc_id, is_test_mode
                )

            self.client.media_sessions[file_id.dc_id] = media_session

        logging.debug(f"Using media session for DC: {file_id.dc_id}")
        return media_session

    async def _create_remote_session(self, dc_id: int, is_test_mode: bool) -> Session:
        """
        Creates a remote media session and handles authorization.
        """
        media_session = Session(
            self.client,
            dc_id,
            await Auth(self.client, dc_id, is_test_mode).create(),
            is_test_mode,
            is_media=True,
        )
        await media_session.start()

        for _ in range(6):
            exported_auth = await self.client.invoke(
                raw.functions.auth.ExportAuthorization(dc_id=dc_id)
            )

            try:
                await media_session.invoke(
                    raw.functions.auth.ImportAuthorization(
                        id=exported_auth.id, bytes=exported_auth.bytes
                    )
                )
                return media_session
            except AuthBytesInvalid:
                logging.warning(f"Invalid authorization bytes for DC {dc_id}")

        await media_session.stop()
        raise AuthBytesInvalid

    async def _create_local_session(self, dc_id: int, is_test_mode: bool) -> Session:
        """
        Creates a local media session.
        """
        media_session = Session(
            self.client,
            dc_id,
            await self.client.storage.auth_key(),
            is_test_mode,
            is_media=True,
        )
        await media_session.start()
        return media_session

    @staticmethod
    async def _get_location(file_id: FileId):
        """
        Determines the file location for the specified file ID.
        """
        return raw.types.InputDocumentFileLocation(
            id=file_id.media_id,
            access_hash=file_id.access_hash,
            file_reference=file_id.file_reference,
            thumb_size=file_id.thumbnail_size,
        )
