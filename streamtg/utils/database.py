import time
import motor.motor_asyncio
from bson.objectid import ObjectId
from bson.errors import InvalidId
from StreamTGAPI.server.exceptions import FileNotFound
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
        file_info["time"] = time.time()
        fetch_old = await self.get_file_by_fileuniqueid(
            file_info["user_id"], file_info["file_unique_id"]
        )
        if fetch_old:
            return fetch_old["_id"]
        await self.count_links(file_info["user_id"], "+")
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
            self.tmdb_collection.insert_one(data)
            print(f"Inserted new TMDB entry with ID {data.get("tmdb_id")}")
        except DuplicateKeyError:
            print(f"TMDB entry with ID {data.get('tmdb_id')} already exists")

    async def get_tmdb(self, tmdb_id, type="movie", season=None, episode=None):
        return self.tmdb.find_one({"tmdb_id": tmdb_id})
    
    async def search_tmdb(self, query, page=1, per_page=50):
        words = query.split()
        regex_query = {'$regex': '.*' + '.*'.join(words) + '.*', '$options': 'i'}
        query = {'title': regex_query}
        offset = (int(page) - 1) * per_page

        total_count = self.tmdb.count_documents(query)

        mydoc = self.tmdb.find(query).sort('msg_id', DESCENDING).skip(offset).limit(per_page)
        return list(mydoc), total_count
    
    def update_tmdb(self, media_doc, media_type):
        tmdb_id = media_doc["tmdb_id"]
        existing_media = self.tmdb.find_one({"tmdb_id": tmdb_id})
        
        if existing_media:
            if media_type == "series":
                self._update_series(existing_media, media_doc)
            elif media_type == "movie":
                self._update_movie(existing_media, media_doc)
            
            self.tmdb.replace_one({"tmdb_id": tmdb_id}, existing_media)
        else:
            self.tmdb.insert_one(media_doc)

    def _update_series(self, existing_media, media_doc):
        for season in media_doc["seasons"]:
            existing_season = self._get_existing_season(existing_media, season)
            
            if existing_season:
                self._update_season(existing_season, season)
            else:
                existing_media["seasons"].append(season)

    def _get_existing_season(self, existing_media, season):
        return next(
            (s for s in existing_media["seasons"] if s["season_number"] == season["season_number"]),
            None
        )

    def _update_season(self, existing_season, season):
        for episode in season["episodes"]:
            existing_episode = self._get_existing_episode(existing_season, episode)
            
            if existing_episode:
                self._update_episode(existing_episode, episode)
            else:
                existing_season["episodes"].append(episode)

    def _get_existing_episode(self, existing_season, episode):
        return next(
            (e for e in existing_season["episodes"] if e["episode_number"] == episode["episode_number"]),
            None
        )

    def _update_episode(self, existing_episode, episode):
        for quality in episode["qualities"]:
            self._update_quality(existing_episode, quality)

    def _update_movie(self, existing_media, media_doc):
        for quality in media_doc["qualities"]:
            self._update_quality(existing_media, quality)

    def _update_quality(self, existing_episode, quality):
        existing_quality = next(
            (q for q in existing_episode["qualities"] if q["quality"] == quality["quality"]),
            None
        )
        
        if existing_quality:
            existing_quality.update(quality)
        else:
            existing_episode["qualities"].append(quality)

    