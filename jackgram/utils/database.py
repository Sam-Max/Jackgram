import logging
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import DuplicateKeyError
from pymongo import DESCENDING
from typing import Any, Dict, List, Optional, Tuple


class Database:
    def __init__(self, uri: str, database_name: str) -> None:
        self.client = AsyncIOMotorClient(uri, maxPoolSize=10)
        self.db = self.client[database_name]
        self.tmdb_collection = self.db.tmdb
        self.media_file_collection = self.db.media_file_collection

    async def add_media_file(self, media_doc: Dict[str, Any]) -> None:
        await self.media_file_collection.insert_one(media_doc)

    async def del_media_file(self, hash: str) -> Any:
        return await self.tmdb_collection.delete_one({"hash": hash})

    async def get_media_file(self, hash: str) -> Optional[Dict[str, Any]]:
        return await self.media_file_collection.find_one({"hash": hash})

    async def get_media_files(
        self, page: int, per_page: int = 11
    ) -> List[Dict[str, Any]]:
        skip = (page - 1) * per_page
        mydoc = (
            self.media_file_collection.find().sort("_id", -1).skip(skip).limit(per_page)
        )
        mydoc_results = await mydoc.to_list(length=per_page)
        return mydoc_results

    async def update_media_file(self, media_doc: Dict[str, Any]) -> None:
        await self.media_file_collection.replace_one(
            {"hash": media_doc["hash"]}, media_doc
        )

    async def add_tmdb(self, data: Dict[str, Any]) -> None:
        logging.info(f"Adding TMDB data: {data}")
        try:
            if data.get("tmdb_id") == "null":
                return
            await self.tmdb_collection.insert_one(data)
            logging.info(f"Inserted new TMDB entry with ID {data.get('tmdb_id')}")
        except DuplicateKeyError:
            logging.error(f"TMDB entry with ID {data.get('tmdb_id')} already exists")

    async def get_tmdb(self, tmdb_id: int) -> Optional[Dict[str, Any]]:
        logging.info(f"Fetching TMDB data for ID: {tmdb_id}")
        tmdb_data= await self.tmdb_collection.find_one({"tmdb_id": tmdb_id})
        logging.info(f"TMDB data: {tmdb_data}")
        return tmdb_data
    
    async def update_tmdb(
        self, existing_media: Dict[str, Any], media_doc: Dict[str, Any], media_type: str
    ) -> None:
        logging.info(f"Updating TMDB data for ID: {media_doc['tmdb_id']}")

        tmdb_id = media_doc["tmdb_id"]

        if media_type == "series":
            logging.info(f"Updating series for TMDB ID: {tmdb_id}")
            await self._update_series(existing_media, media_doc)
        elif media_type == "movie":
            logging.info(f"Updating movie for TMDB ID: {tmdb_id}")
            await self._update_movie(existing_media, media_doc)

        await self.tmdb_collection.replace_one({"tmdb_id": tmdb_id}, existing_media)
    
    async def del_tdmb(self, tmdb_id: int) -> Any:
        return await self.tmdb_collection.delete_one({"tmdb_id": tmdb_id})

    async def count_tmdb(self) -> int:
        return await self.tmdb_collection.count_documents(
            {"tmdb_id": {"$exists": True}}
        )

    async def get_tmdb_latest(
        self, page: int = 1, per_page: int = 12
    ) -> List[Dict[str, Any]]:
        skip = (page - 1) * per_page
        mydoc = self.tmdb_collection.find().sort("_id", -1).skip(skip).limit(per_page)
        mydoc_results = await mydoc.to_list(length=per_page)
        return mydoc_results

    async def search_tmdb(
        self, query: str, page: int = 1, per_page: int = 50
    ) -> Tuple[List[Dict[str, Any]], int]:
        words = query.split()
        regex_query = {
            "title": {"$regex": ".*" + ".*".join(words) + ".*", "$options": "i"}
        }
        skip = (int(page) - 1) * per_page

        mydoc = (
            self.tmdb_collection.find(regex_query)
            .sort("msg_id", DESCENDING)
            .skip(skip)
            .limit(per_page)
        )

        results = await mydoc.to_list(length=per_page)

        total_count = await self.tmdb_collection.count_documents(regex_query)

        return results, total_count

    

    async def _update_series(
        self, existing_media: Dict[str, Any], media_doc: Dict[str, Any]
    ) -> None:
        for season in media_doc["seasons"]:
            existing_season = await self._get_existing_season(existing_media, season)

            if existing_season:
                await self._update_season(existing_season, season)
            else:
                existing_media["seasons"].append(season)

    async def _get_existing_season(
        self, existing_media: Dict[str, Any], season: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return next(
            (
                s
                for s in existing_media["seasons"]
                if s["season_number"] == season["season_number"]
            ),
            None,
        )

    async def _update_season(
        self, existing_season: Dict[str, Any], season: Dict[str, Any]
    ) -> None:
        for episode in season["episodes"]:
            existing_episode = await self._get_existing_episode(
                existing_season, episode
            )

            if existing_episode:
                await self._update_episode(existing_episode, episode)
            else:
                existing_season["episodes"].append(episode)

    async def _get_existing_episode(
        self, existing_season: Dict[str, Any], episode: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        return next(
            (
                e
                for e in existing_season["episodes"]
                if e["episode_number"] == episode["episode_number"]
            ),
            None,
        )

    async def _update_episode(
        self, existing_episode: Dict[str, Any], episode: Dict[str, Any]
    ) -> None:
        for info in episode["file_info"]:
            if matched_file_episode := next(
                (q for q in existing_episode["file_info"] if q["hash"] == info["hash"]),
                None,
            ):
                matched_file_episode.update(info)
            else:
                existing_episode["file_info"].append(info)

    async def _update_movie(
        self, existing_media: Dict[str, Any], media_doc: Dict[str, Any]
    ) -> None:
        for info in media_doc["file_info"]:
            if matched_file_movie := next(
                (q for q in existing_media["file_info"] if q["hash"] == info["hash"]),
                None,
            ):
                matched_file_movie.update(info)
            else:
                existing_media["file_info"].append(info)

    async def list_collections(self) -> List[str]:
        return await self.db.list_collection_names()
