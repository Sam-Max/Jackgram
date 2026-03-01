import logging
import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
from jackgram.bot.bot import get_db, TMDB_API, TMDB_LANGUAGE

admin_routes = APIRouter(prefix="/admin")
db = get_db()


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Remove MongoDB ObjectId so the document is JSON-serialisable."""
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@admin_routes.get("/stats")
async def get_stats():
    movies = await db.count_movies()
    tv = await db.count_tv()
    files = await db.count_media_files()
    storage = await db.get_total_storage()
    return {
        "movies": movies,
        "tv_shows": tv,
        "raw_files": files,
        "total_storage_bytes": storage,
    }


# ---------------------------------------------------------------------------
# Movies
# ---------------------------------------------------------------------------


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    rating: Optional[float] = None
    release_date: Optional[str] = None
    runtime: Optional[int] = None
    genres: Optional[List[str]] = None


@admin_routes.get("/movies")
async def list_movies(
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)
):
    data = await db.get_movies(page=page, per_page=per_page)
    total = await db.count_movies()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "results": [_clean(d) for d in data],
    }


@admin_routes.get("/movies/{tmdb_id}")
async def get_movie(tmdb_id: int):
    data = await db.get_tmdb(tmdb_id)
    if not data or data.get("type") != "movie":
        raise HTTPException(status_code=404, detail="Movie not found")
    return _clean(data)


@admin_routes.put("/movies/{tmdb_id}")
async def update_movie(tmdb_id: int, payload: MovieUpdate):
    existing = await db.get_tmdb(tmdb_id)
    if not existing or existing.get("type") != "movie":
        raise HTTPException(status_code=404, detail="Movie not found")

    update_fields: Dict[str, Any] = {
        k: v for k, v in payload.dict().items() if v is not None
    }
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    existing.update(update_fields)
    await db.tmdb_collection.replace_one({"tmdb_id": tmdb_id}, existing)
    return _clean(existing)


@admin_routes.delete("/movies/{tmdb_id}")
async def delete_movie(tmdb_id: int):
    existing = await db.get_tmdb(tmdb_id)
    if not existing or existing.get("type") != "movie":
        raise HTTPException(status_code=404, detail="Movie not found")
    await db.del_tdmb(tmdb_id)
    return {"deleted": True, "tmdb_id": tmdb_id}


# ---------------------------------------------------------------------------
# TV Shows
# ---------------------------------------------------------------------------


class TVUpdate(BaseModel):
    title: Optional[str] = None
    rating: Optional[float] = None
    release_date: Optional[str] = None
    genres: Optional[List[str]] = None


@admin_routes.get("/tv")
async def list_tv(page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)):
    data = await db.get_tv(page=page, per_page=per_page)
    total = await db.count_tv()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "results": [_clean(d) for d in data],
    }


@admin_routes.get("/tv/{tmdb_id}")
async def get_tv_show(tmdb_id: int):
    data = await db.get_tmdb(tmdb_id)
    if not data or data.get("type") != "tv":
        raise HTTPException(status_code=404, detail="TV show not found")
    return _clean(data)


@admin_routes.put("/tv/{tmdb_id}")
async def update_tv_show(tmdb_id: int, payload: TVUpdate):
    existing = await db.get_tmdb(tmdb_id)
    if not existing or existing.get("type") != "tv":
        raise HTTPException(status_code=404, detail="TV show not found")

    update_fields: Dict[str, Any] = {
        k: v for k, v in payload.dict().items() if v is not None
    }
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    existing.update(update_fields)
    await db.tmdb_collection.replace_one({"tmdb_id": tmdb_id}, existing)
    return _clean(existing)


@admin_routes.delete("/tv/{tmdb_id}")
async def delete_tv_show(tmdb_id: int):
    existing = await db.get_tmdb(tmdb_id)
    if not existing or existing.get("type") != "tv":
        raise HTTPException(status_code=404, detail="TV show not found")
    await db.del_tdmb(tmdb_id)
    return {"deleted": True, "tmdb_id": tmdb_id}


# ---------------------------------------------------------------------------
# Raw Media Files
# ---------------------------------------------------------------------------


@admin_routes.get("/files")
async def list_files(
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)
):
    data = await db.get_media_files(page=page, per_page=per_page)
    total = await db.count_media_files()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "results": [_clean(d) for d in data],
    }


@admin_routes.delete("/files/{file_hash}")
async def delete_file(file_hash: str):
    existing = await db.get_media_file(file_hash)
    if not existing:
        raise HTTPException(status_code=404, detail="File not found")
    await db.del_media_file(file_hash)
    return {"deleted": True, "hash": file_hash}


# ---------------------------------------------------------------------------
# TMDb Poster Proxy
# ---------------------------------------------------------------------------

_poster_cache: Dict[str, Optional[str]] = {}


@admin_routes.get("/poster/{tmdb_id}")
async def get_poster(tmdb_id: int, type: str = Query("movie", pattern="^(movie|tv)$")):
    """Proxy TMDb API to return poster URL without exposing the API key."""
    cache_key = f"{type}:{tmdb_id}"
    if cache_key in _poster_cache:
        return {"poster_url": _poster_cache[cache_key]}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"https://api.themoviedb.org/3/{type}/{tmdb_id}",
                params={"api_key": TMDB_API, "language": TMDB_LANGUAGE},
            )
            if resp.status_code == 200:
                data = resp.json()
                poster_path = data.get("poster_path")
                overview = data.get("overview", "")
                backdrop_path = data.get("backdrop_path")
                poster_url = (
                    f"https://image.tmdb.org/t/p/w300{poster_path}"
                    if poster_path
                    else None
                )
                backdrop_url = (
                    f"https://image.tmdb.org/t/p/w780{backdrop_path}"
                    if backdrop_path
                    else None
                )
                _poster_cache[cache_key] = poster_url
                return {
                    "poster_url": poster_url,
                    "backdrop_url": backdrop_url,
                    "overview": overview,
                }
            else:
                _poster_cache[cache_key] = None
                return {"poster_url": None, "backdrop_url": None, "overview": ""}
    except Exception as e:
        logging.warning(f"Failed to fetch poster for {type}/{tmdb_id}: {e}")
        return {"poster_url": None, "backdrop_url": None, "overview": ""}
