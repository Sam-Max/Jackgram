from aiohttp import web
from streamtg.bot import BASE_URL, get_db

routes = web.RouteTableDef()

db = get_db()

# http://127.0.0.1:8080/stream/movie/4343434.json
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


@routes.get("/search", allow_head=True)
async def handle_get_item(request):
    return web.json_response({"error": "Item not found"}, status=404)


def extract_show_info(data, season_num, episode_num):
    for season in data.get("seasons", []):
        if season.get("season_number") == int(season_num):
            for episode in season.get("episodes", []):
                if episode.get("episode_number") == int(episode_num):

                    channel_id = episode["file_info"][0].get("chn_id")
                    message_id = episode["file_info"][0].get("msg_id")
                    hash = episode["file_info"][0].get("hash")
                    title = episode.get("title")

                    url = generate_link(channel_id, message_id, hash)

                    season_number = season.get("season_number")
                    episode_number = episode.get("episode_number")

                    episode_info = {
                        "name": "Telegram",
                        "title": f"{title}.S{season_number}.E{episode_number}",
                        "date": episode.get("date"),
                        "duration": episode.get("duration"),
                        "quality": episode["file_info"][0].get("quality"),
                        "size": episode["file_info"][0].get("size"),
                        "link": url,
                    }
                    return episode_info
    return None


def extract_movie_info(data):
    movie_info = []
    
    title = data.get("title")
    release_date = data.get("release_date")
    runtime= data.get("runtime")

    for file in data["file_info"]:
        channel_id = file.get("chn_id")
        message_id = file.get("msg_id")
        hash = file.get("hash")
        
        url = generate_link(channel_id, message_id, hash)

        file_info = {
            "name": "Telegram",
            "title": title,
            "date": release_date,
            "duration": runtime,
            "quality": file.get("quality"),
            "size": file.get("size"),
            "link": url,
        }
        movie_info.append(file_info)
    return movie_info


def generate_link(chat_id, msg_id, hash):
    return f"{BASE_URL}dl/{chat_id}?id={msg_id}&hash={hash}"
