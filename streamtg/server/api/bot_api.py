from aiohttp import web
from streamtg.bot import get_db
from streamtg.utils.utils import extract_movie_info, extract_show_info, extract_show_info_raw

routes = web.RouteTableDef()

db = get_db()


# http://127.0.0.1:8080/stream/series/4343434:1:1.json
@routes.get("/stream/series/{imdb_id}:{season}:{episode}.json")
async def stream_series(request):
    imdb_id = request.match_info["imdb_id"]
    if not imdb_id:
        return web.json_response({"stream": []})

    season = request.match_info["season"]
    episode = request.match_info["episode"]

    data = await db.get_tmdb(imdb_id)
    if data is None:
        return web.json_response({"error": "Item not found"}, status=404)

    if data.get("type") == "tv":
        info = extract_show_info(data, season, episode)

        return web.json_response(
            {
                "imdb_id": imdb_id,
                "streams": info,
            }
        )

# http://127.0.0.1:8080/stream/movie/4343434.json
@routes.get("/stream/movie/{imdb_id}.json")
async def stream_series(request):
    imdb_id = request.match_info["imdb_id"]
    if not imdb_id:
        return web.json_response({"stream": []})

    data = await db.get_tmdb(imdb_id)
    if data is None:
        return web.json_response({"error": "Item not found"}, status=404)

    if data.get("type") == "movie":
        info = extract_movie_info(data)

        return web.json_response(
            {
                "imdb_id": imdb_id,
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

        results_list = []
        for result in results:
            if result["type"] == "movie":
                result = extract_movie_info(result)
            else:
                result = extract_show_info_raw(result)
            results_list.append(result)

        return web.json_response(
            {"total_count": total_count, "page": page, "results": results_list}
        )
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)




