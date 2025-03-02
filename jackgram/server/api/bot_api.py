import logging
from fastapi import APIRouter, HTTPException, Query
from jackgram.bot.bot import get_db
from jackgram.utils.utils import (
    extract_movie_info,
    extract_movie_info_raw,
    extract_show_info,
    extract_show_info_raw,
    generate_stream_url_file,
)

stream_routes = APIRouter(prefix="/stream")

db = get_db()


@stream_routes.get("/latest")
async def stream_latest(page: int = Query(1)):
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be positive integers")

    data = await db.get_tmdb_latest(page=page)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found")

    media_info = []
    for item in data:
        if item["type"] == "movie":
            media_info.append(extract_movie_info_raw(item))
        elif item["type"] == "tv":
            media_info.append(extract_show_info_raw(item))

    return media_info


@stream_routes.get("/files")
async def stream_files(page: int = Query(1)):
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be positive integers")

    data = await db.get_media_files(page=page)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found")

    for item in data:
        del item["_id"]
        item["name"] = "Telegram"
        item["url"] = generate_stream_url_file(hash=item.get("hash"))

    return data


@stream_routes.get("/series/{tmdb_id}:{season}:{episode}.json")
async def stream_series(tmdb_id, season, episode):
    if not tmdb_id:
        return {"stream": []}

    data = await db.get_tmdb(tmdb_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found")

    if data.get("type") == "tv":
        return {
            "tmdb_id": tmdb_id,
            "streams": extract_show_info(data, season, episode, tmdb_id),
        }


@stream_routes.get("/movie/{tmdb_id}.json")
async def stream_movie(tmdb_id):
    if not tmdb_id:
        return {"stream": []}

    data = await db.get_tmdb(tmdb_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found")

    if data.get("type") == "movie":
        info = extract_movie_info(data, tmdb_id)

        return {
            "tmdb_id": tmdb_id,
            "streams": info,
        }


@stream_routes.get("/search")
async def stream_search(search_query: str = Query(..., alias="q"), page: int = Query(1)):
    try:
        if not search_query:
            raise HTTPException(status_code=400, detail="Search query (q) is required")

        if page < 1:
            raise HTTPException(status_code=400, detail="Page must be positive integers")

        results, total_count = await db.search_tmdb(search_query, page)

        if not results:
            raise HTTPException(status_code=404, detail="Item not found")

        media_info = [
            (
                extract_movie_info_raw(result)
                if result["type"] == "movie"
                else extract_show_info_raw(result)
            )
            for result in results
        ]

        return {
                "page": page,
                "total_count": total_count,
                "results": media_info,
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
