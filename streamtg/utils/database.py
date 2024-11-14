import time
import motor.motor_asyncio
from bson.objectid import ObjectId
from bson.errors import InvalidId
from streamtg.server.exceptions import FileNotFound
from pymongo.errors import DuplicateKeyError
from pymongo import DESCENDING


class Database:
    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.file_collection = self.db.file
        self.tmdb_collection = self.db.tmdb

    async def add_file(self, file_info):
        return (await self.file_collection.insert_one(file_info)).inserted_id

    async def get_file(self, _id):
        try:
            file_info = await self.file_collection.find_one({"_id": ObjectId(_id)})
            if not file_info:
                raise FileNotFound
            return file_info
        except InvalidId:
            raise FileNotFound

    # TDMB
    async def add_tmdb(self, data):
        try:
            if data.get("tmdb_id") == "null":
                return
            await self.tmdb_collection.insert_one(data)
            print(f"Inserted new TMDB entry with ID {data.get('tmdb_id')}")
            print(data)
        except DuplicateKeyError:
            print(f"TMDB entry with ID {data.get('tmdb_id')} already exists")

    async def get_tmdb(self, tmdb_id):
        return await self.tmdb_collection.find_one({"tmdb_id": int(tmdb_id)})

    async def del_tdmb(self, tmdb_id):
        return await self.tmdb_collection.delete_one({"tmdb_id": int(tmdb_id)})

    async def search_tmdb(self, query, page=1, per_page=50):
        words = query.split()
        regex_query = {
            "title": {"$regex": ".*" + ".*".join(words) + ".*", "$options": "i"}
        }
        offset = (int(page) - 1) * per_page

        mydoc = (
            self.tmdb_collection.find(regex_query)
            .sort("msg_id", DESCENDING)
            .skip(offset)
            .limit(per_page)
        )

        results = await mydoc.to_list(length=per_page)

        total_count = await self.tmdb_collection.count_documents(regex_query)

        return results, total_count

    async def update_tmdb(self, media_doc, media_type):
        tmdb_id = media_doc["tmdb_id"]
        existing_media = await self.tmdb_collection.find_one({"tmdb_id": tmdb_id})

        if existing_media:
            if media_type == "series":
                await self._update_series(existing_media, media_doc)
            elif media_type == "movie":
                await self._update_movie(existing_media, media_doc)

            print(existing_media)
            await self.tmdb_collection.replace_one({"tmdb_id": tmdb_id}, existing_media)
        else:
            await self.tmdb_collection.insert_one(media_doc)

    async def _update_series(self, existing_media, media_doc):
        for season in media_doc["seasons"]:
            existing_season = await self._get_existing_season(existing_media, season)

            if existing_season:
                await self._update_season(existing_season, season)
            else:
                existing_media["seasons"].append(season)

    async def _get_existing_season(self, existing_media, season):
        return next(
            (
                s
                for s in existing_media["seasons"]
                if s["season_number"] == season["season_number"]
            ),
            None,
        )

    async def _update_season(self, existing_season, season):
        for episode in season["episodes"]:
            existing_episode = await self._get_existing_episode(
                existing_season, episode
            )

            if existing_episode:
                await self._update_episode(existing_episode, episode)
            else:
                existing_season["episodes"].append(episode)

    async def _get_existing_episode(self, existing_season, episode):
        return next(
            (
                e
                for e in existing_season["episodes"]
                if e["episode_number"] == episode["episode_number"]
            ),
            None,
        )

    async def _update_episode(self, existing_episode, episode):
        for info in episode["file_info"]:
            if matched_file_episode := next(
                (q for q in existing_episode["file_info"] if q["hash"] == info["hash"]),
                None,
            ):
                matched_file_episode.update(info)
            else:
                existing_episode["file_info"].append(info)

    async def _update_movie(self, existing_media, media_doc):
        for info in media_doc["file_info"]:
            if matched_file_movie := next(
                (q for q in existing_media["file_info"] if q["hash"] == info["hash"]),
                None,
            ):
                matched_file_movie.update(info)
            else:
                existing_media["file_info"].append(info)
