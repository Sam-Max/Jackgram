import asyncio
import os
import sys
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    # Load environment variables
    load_dotenv("config.env")

    db_url = os.environ.get("DATABASE_URL")
    if not db_url:
        print("Error: DATABASE_URL is not set in config.env")
        sys.exit(1)

    db_name = os.environ.get("DATABASE_NAME", "jackgramdb")

    print(f"Connecting to database with URL: {db_url[:20]}...")
    client = AsyncIOMotorClient(db_url)
    db = client[db_name]

    media_collection = db["media_file_collection"]
    tmdb_collection = db["tmdb"]

    print(f"Connected to database: {db.name}")

    # 1. Clean raw media files
    print("\nCleaning 'media_file_collection'...")
    media_count = 0
    deleted_media = 0
    async for doc in media_collection.find():
        media_count += 1
        file_name = doc.get("file_name")
        if not file_name or str(file_name).strip().lower() in [
            "unknown",
            "none",
            "",
            "unknown media",
        ]:
            await media_collection.delete_one({"_id": doc["_id"]})
            deleted_media += 1

    print(
        f"Processed {media_count} raw media files. Deleted {deleted_media} documents."
    )

    # 2. Clean TMDB movies and series
    print("\nCleaning 'tmdb' collection...")
    tmdb_count = 0
    updated_tmdb = 0
    deleted_tmdb = 0
    async for doc in tmdb_collection.find():
        tmdb_count += 1
        changed = False
        media_type = doc.get("type")

        # Check top-level title
        title = doc.get("title")
        if not title or str(title).strip().lower() in [
            "unknown",
            "none",
            "",
            "unknown media",
        ]:
            await tmdb_collection.delete_one({"_id": doc["_id"]})
            deleted_tmdb += 1
            continue

        if media_type == "movie":
            original_files = doc.get("file_info", [])
            filtered_files = [
                info
                for info in original_files
                if info.get("file_name")
                and str(info.get("file_name")).strip().lower()
                not in ["unknown", "none", "", "unknown media"]
            ]
            if len(filtered_files) != len(original_files):
                doc["file_info"] = filtered_files
                changed = True

            if not doc.get("file_info"):
                await tmdb_collection.delete_one({"_id": doc["_id"]})
                deleted_tmdb += 1
                continue

        elif media_type in ["tv", "series"]:
            seasons = doc.get("seasons", [])
            new_seasons = []
            for season in seasons:
                episodes = season.get("episodes", [])
                new_episodes = []
                for episode in episodes:
                    original_files = episode.get("file_info", [])
                    filtered_files = [
                        info
                        for info in original_files
                        if info.get("file_name")
                        and str(info.get("file_name")).strip().lower()
                        not in ["unknown", "none", ""]
                    ]
                    if len(filtered_files) != len(original_files):
                        episode["file_info"] = filtered_files
                        changed = True

                    if episode.get("file_info"):
                        new_episodes.append(episode)
                    else:
                        changed = True

                if new_episodes:
                    season["episodes"] = new_episodes
                    new_seasons.append(season)
                else:
                    changed = True

            if not new_seasons:
                await tmdb_collection.delete_one({"_id": doc["_id"]})
                deleted_tmdb += 1
                continue

            if changed:
                doc["seasons"] = new_seasons

        if changed:
            await tmdb_collection.replace_one({"_id": doc["_id"]}, doc)
            updated_tmdb += 1

    print(
        f"Processed {tmdb_count} TMDB entries. Updated {updated_tmdb} (cleaned files), Deleted {deleted_tmdb} (now empty) entries."
    )

    print("\nCleanup completed.")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
