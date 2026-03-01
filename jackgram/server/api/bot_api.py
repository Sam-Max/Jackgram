import logging
import jwt
from fastapi import APIRouter, HTTPException, Query, Depends, Request
from jackgram.bot.bot import get_db, USE_TOKEN_SYSTEM, SECRET_KEY
from jackgram.utils.utils import (
    extract_media_file_raw,
    extract_movie_info,
    extract_movie_info_raw,
    extract_show_info,
    extract_show_info_raw,
    generate_stream_url_file,
)

stream_routes = APIRouter(prefix="/stream")
search_routes = APIRouter(prefix="")  # No prefix for search routes

db = get_db()


async def verify_api_token(request: Request, token: str = None):
    if not USE_TOKEN_SYSTEM:
        return True

    # 1. Try to get token from query param or Authorization header
    token_val = token or request.headers.get("Authorization")
    if token_val:
        token_val = token_val.replace("Bearer ", "")
        user = await db.get_api_user(token_val)
        if user:
            logging.debug(f"Authorized via API Token: {user.get('name')}")
            return user

        # 2. If it's not a valid API user token, try as a JWT admin token
        try:
            decoded = jwt.decode(token_val, SECRET_KEY, algorithms=["HS256"])
            logging.debug(f"Authorized via JWT Header: {decoded.get('user')}")
            return decoded
        except:
            pass

    # 3. Last fallback: Check for the admin cookie (for direct browser links)
    admin_cookie = request.cookies.get("jg-token")
    if admin_cookie:
        try:
            decoded = jwt.decode(admin_cookie, SECRET_KEY, algorithms=["HS256"])
            logging.debug(f"Authorized via Admin Cookie: {decoded.get('user')}")
            return decoded
        except Exception as e:
            logging.warning(f"Failed to decode admin cookie: {e}")

    if not token_val:
        logging.warning(
            "No API token provided and no valid admin session found in cookies."
        )
        raise HTTPException(status_code=401, detail="API Token is missing")

    logging.warning(f"Invalid token provided: {token_val[:10]}...")
    raise HTTPException(status_code=401, detail="Invalid token")


@stream_routes.get("/latest")
async def stream_latest(page: int = Query(1), _=Depends(verify_api_token)):
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
async def stream_files(
    request: Request, page: int = Query(1), _=Depends(verify_api_token)
):
    if page < 1:
        raise HTTPException(status_code=400, detail="Page must be positive integers")

    data = await db.get_media_files(page=page)
    if data is None:
        raise HTTPException(status_code=404, detail="Item not found")

    for item in data:
        del item["_id"]
        item["name"] = "Telegram"
        item["url"] = generate_stream_url_file(file_hash=item.get("hash"))

    return data


@stream_routes.get("/series/{tmdb_id}:{season}:{episode}.json")
async def stream_series(tmdb_id, season, episode, _=Depends(verify_api_token)):
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
async def stream_movie(tmdb_id, _=Depends(verify_api_token)):
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


@search_routes.get("/search")
async def stream_search(
    search_query: str = Query(..., alias="query"),
    page: int = Query(1),
    _=Depends(verify_api_token),
):
    try:

        logging.info(f"Search query: {search_query}, Page: {page}")

        if not search_query:
            raise HTTPException(status_code=400, detail="Search query (q) is required")

        if page < 1:
            raise HTTPException(
                status_code=400, detail="Page must be positive integers"
            )

        results, total_count = await db.search_tmdb(search_query, page)

        logging.info(f"Search results: {results}")

        if not results:
            raise HTTPException(status_code=404, detail="Item not found")

        media_info = []
        for result in results:
            if result.get("type") == "movie":
                media_info.append(extract_movie_info_raw(result))
            elif result.get("type") == "tv":
                media_info.append(extract_show_info_raw(result))
            else:  # Handle media_file_collection results
                media_info.append(extract_media_file_raw(result))

        return {
            "page": page,
            "total_count": total_count,
            "results": media_info,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
