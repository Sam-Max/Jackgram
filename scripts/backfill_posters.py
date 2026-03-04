#!/usr/bin/env python3
"""
Backfill poster_path, backdrop_path, and overview for existing tmdb documents
in MongoDB by fetching from the TMDb API.

Usage:
    python3 backfill_posters.py          # dry-run (shows what would change)
    python3 backfill_posters.py --apply  # actually write to DB
"""

import asyncio
import argparse
import logging
import sys
from os import getenv

import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("config.env", override=True)

DATABASE_URL = getenv("DATABASE_URL", "mongodb://admin:admin@mongo:27017")
DATABASE_NAME = "jackgramdb"
TMDB_API_KEY = getenv("TMDB_API")
TMDB_LANGUAGE = getenv("TMDB_LANGUAGE", "en-US")

if not TMDB_API_KEY:
    print("ERROR: TMDB_API is not set in config.env")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)


async def fetch_tmdb_details(client: httpx.AsyncClient, tmdb_id: int, media_type: str):
    """Fetch poster_path, backdrop_path and overview from TMDb API."""
    type_name = "tv" if media_type == "tv" else "movie"
    url = f"https://api.themoviedb.org/3/{type_name}/{tmdb_id}"
    resp = await client.get(
        url, params={"api_key": TMDB_API_KEY, "language": TMDB_LANGUAGE}
    )
    if resp.status_code == 200:
        data = resp.json()
        return {
            "poster_path": data.get("poster_path"),
            "backdrop_path": data.get("backdrop_path"),
            "overview": data.get("overview", ""),
        }
    else:
        log.warning(
            "TMDb API returned %d for %s/%d", resp.status_code, type_name, tmdb_id
        )
        return None


async def backfill(apply: bool):
    client_db = AsyncIOMotorClient(DATABASE_URL)
    db = client_db[DATABASE_NAME]
    collection = db.tmdb

    # Find documents missing any of the three fields
    query = {
        "$or": [
            {"poster_path": {"$exists": False}},
            {"backdrop_path": {"$exists": False}},
            {"overview": {"$exists": False}},
        ]
    }

    total = await collection.count_documents(query)
    if total == 0:
        log.info(
            "All documents already have poster_path, backdrop_path, and overview. Nothing to do!"
        )
        return

    log.info("Found %d documents to backfill.", total)

    updated = 0
    skipped = 0

    async with httpx.AsyncClient(timeout=10.0) as http:
        cursor = collection.find(query, {"tmdb_id": 1, "type": 1, "title": 1})
        async for doc in cursor:
            tmdb_id = doc.get("tmdb_id")
            media_type = doc.get("type", "movie")
            title = doc.get("title", "unknown")

            if not tmdb_id:
                skipped += 1
                continue

            details = await fetch_tmdb_details(http, tmdb_id, media_type)
            if not details:
                log.warning("  SKIP  %-6d  %s (API error)", tmdb_id, title)
                skipped += 1
                continue

            poster = details["poster_path"] or "(none)"
            log.info(
                "  %s  %-6d  %-40s  poster=%s",
                "WRITE" if apply else "FOUND",
                tmdb_id,
                title,
                poster,
            )

            if apply:
                await collection.update_one(
                    {"_id": doc["_id"]},
                    {"$set": details},
                )

            updated += 1

            # Be nice to TMDb rate limits (~40 req/s for free tier)
            await asyncio.sleep(0.1)

    action = "Updated" if apply else "Would update"
    log.info("Done! %s %d documents, skipped %d.", action, updated, skipped)
    if not apply and updated > 0:
        log.info("Run again with --apply to write the changes.")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill poster_path/backdrop_path/overview for existing tmdb docs."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Actually write changes to the database (default is dry-run).",
    )
    args = parser.parse_args()
    asyncio.run(backfill(args.apply))


if __name__ == "__main__":
    main()
