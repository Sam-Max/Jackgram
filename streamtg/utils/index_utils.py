import re
from streamtg.bot import get_db
from streamtg.utils.tmdb import get_tmdb
from streamtg.utils.utils import get_readable_size
import PTN


db = get_db()
tmdb = get_tmdb()


async def get_auth_channel():
    AUTH_CHANNEL = await db.get_variable("auth_channel")
    if AUTH_CHANNEL is None or AUTH_CHANNEL.strip() == "":
        return [AUTH_CHANNEL]
    return [channel.strip() for channel in AUTH_CHANNEL.split(",")]


def get_file_title(file, message):
    title = file.file_name or message.caption or file.file_id
    return title.replace("_", " ").replace(".", " ")


def format_filename(title):
    title = re.sub(r"\s*[\[\(\{]?\s*@\w+\s*[\]\)\}]?\s*[-~]?\s*", "", title).strip()
    filename = re.sub(r"\.(?=[^.]*\.)", " ", title)
    return filename.replace(".", " ")


async def extract_file_info(file, message, filename):
    name = file.file_name
    size = file.file_size
    mime_type = file.mime_type
    file_id = file.file_id
    file_unique_id = file.file_unique_id
    file_hash = file.file_unique_id[:6]

    resolution = PTN.parse(filename).get("resolution") or (
        message.video.height if message.video else "other"
    )
    return {
        "quality": resolution,
        "file_name": name,
        "file_size": size,
        "mime_type": mime_type,
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "hash": file_hash,
    }


async def get_media_details(data, filename):
    title = data.get("title")
    year = data.get("year")

    if "season" in data and "episode" in data:
        media_id = tmdb.find_media_id(title=title, data_type="series", year=year)
    else:
        media_id = tmdb.find_media_id(title=title, data_type="movie", year=year)

    if "season" in data and "episode" in data:
        episode_details = tmdb.get_episode_details(
            tmdb_id=media_id,
            episode_number=data.get("episode"),
            season_number=data.get("season"),
        )
    else:
        episode_details = {}

    details = tmdb.get_details(
        tmdb_id=media_id, data_type="movie" if "episode" not in data else "series"
    )

    return media_id, details, episode_details


async def process_series(media_id, data, series_details, episode_details, file_info):
    genres = [genre["name"] for genre in series_details.get("genres", [])]
    series_doc = {
        "tmdb_id": series_details.get("id"),
        "title": series_details.get("name"),
        "rating": series_details.get("vote_average"),
        "description": series_details.get("overview"),
        "release_date": series_details.get("first_air_date"),
        "poster": series_details.get("poster_path"),
        "backdrop": series_details.get("backdrop_path"),
        "type": "tv",
        "genres": genres,
        "seasons": [
            {
                "season_number": data.get("season"),
                "episodes": [
                    {
                        "series": series_details.get("name"),
                        "season_number": data.get("season"),
                        "episode_number": data.get("episode"),
                        "date": series_details.get("air_date"),
                        "duration": series_details.get("runtime"),
                        "title": series_details.get("name"),
                        "description": series_details.get("overview"),
                        "poster": series_details.get("still_path"),
                        "rating": series_details.get("vote_average"),
                        "file_info": [file_info],
                    }
                ],
            }
        ],
    }

    if await db.get_tmdb(tmdb_id=media_id):
        await db.update_tmdb(series_doc, "series")
    else:
        await db.add_tmdb(series_doc)


async def process_movie(media_id, media_details, file_info):
    genres = [genre["name"] for genre in media_details.get("genres", [])]
    movie_doc = {
        "tmdb_id": media_details.get("id"),
        "title": media_details.get("title"),
        "rating": media_details.get("vote_average"),
        "description": media_details.get("overview"),
        "runtime": media_details.get("runtime"),
        "release_date": media_details.get("release_date"),
        "poster": media_details.get("poster_path"),
        "backdrop": media_details.get("backdrop_path"),
        "genres": genres,
        "type": "movie",
        "file_info": [file_info],
    }

    if await db.get_tmdb(tmdb_id=media_id):
        await db.update_tmdb(movie_doc, "movie")
    else:
        await db.add_tmdb(movie_doc)
