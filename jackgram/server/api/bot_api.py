from aiohttp import web
from jackgram.bot import get_db
from jackgram.utils.utils import (
    extract_movie_info,
    extract_movie_info_raw,
    extract_show_info,
    extract_show_info_raw,
)

routes = web.RouteTableDef()

db = get_db()


# http://127.0.0.1:8080/stream/series/4343434:1:1.json
@routes.get("/stream/series/{tmdb_id}:{season}:{episode}.json")
async def stream_series(request):
    tmdb_id = request.match_info["tmdb_id"]
    if not tmdb_id:
        return web.json_response({"stream": []})

    season = request.match_info["season"]
    episode = request.match_info["episode"]

    data = await db.get_tmdb(tmdb_id)
    if data is None:
        return web.json_response({"error": "Item not found"}, status=404)

    if data.get("type") == "tv":
        info = extract_show_info(data, season, episode, tmdb_id)

        return web.json_response(
            {
                "tmdb_id": tmdb_id,
                "streams": info,
            }
        )


# http://127.0.0.1:8080/stream/movie/4343434.json
@routes.get("/stream/movie/{tmdb_id}.json")
async def stream_series(request):
    tmdb_id = request.match_info["tmdb_id"]
    if not tmdb_id:
        return web.json_response({"stream": []})

    data = await db.get_tmdb(tmdb_id)
    if data is None:
        return web.json_response({"error": "Item not found"}, status=404)

    if data.get("type") == "movie":
        info = extract_movie_info(data, tmdb_id)

        return web.json_response(
            {
                "tmdb_id": tmdb_id,
                "streams": info,
            }
        )


# http://127.0.0.1:8080/search?query="From"&page=1
@routes.get("/search", allow_head=True)
async def search_handler(request: web.Request):
    try:
        search_query = request.query.get("query")
        page = int(request.query.get("page", 1))

        if not search_query:
            return web.json_response(
                {"error": "Search query (q) is required"}, status=400
            )

        if page < 1:
            return web.json_response(
                {"error": "Page must be positive integers"}, status=400
            )

        results, total_count = await db.search_tmdb(search_query, page)
        if results:
            media_info = []
            for result in results:
                if result["type"] == "movie":
                    data = extract_movie_info_raw(result)
                else:
                    data = extract_show_info_raw(result)
                media_info.append(data)

            return web.json_response(
                {
                    "page": page,
                    "total_count": total_count,
                    "results": media_info,
                }
            )
        else:
            return web.json_response({"error": "Item not found"}, status=404)
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)
