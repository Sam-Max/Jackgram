from jackgram.bot.bot import BASE_URL, get_db
import re
from jackgram.bot.bot import lock
import PTN
from jackgram.utils.tmdb import get_tmdb
from typing import Dict, List, Union, Optional

db = get_db()
tmdb = get_tmdb()


def get_file_title(file, message) -> str:
    title = file.file_name or message.caption or file.file_id
    return title.replace("_", " ").replace(".", " ")


def format_filename(title: str) -> str:
    title = re.sub(r"\s*[\[\(\{]?\s*@\w+\s*[\]\)\}]?\s*[-~]?\s*", "", title).strip()
    filename = re.sub(r"\.(?=[^.]*\.)", " ", title)
    return filename.replace(".", " ")


async def extract_file_info(file, message, filename: str) -> Dict[str, Union[str, int]]:
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
        "file_name": name,
        "file_size": size,
        "quality": resolution,
        "mime_type": mime_type,
        "file_id": file_id,
        "file_unique_id": file_unique_id,
        "hash": file_hash,
    }


async def get_media_details(
    data: Dict[str, Union[str, int]],
) -> Dict[str, Optional[Union[int, Dict]]]:
    title = data.get("title")
    year = data.get("year")
    details = {}
    episode_details = {}
    media_id = None

    if "season" in data and "episode" in data:
        media_id = tmdb.find_media_id(title=title, data_type="series", year=year)
        if media_id:
            episode_details = tmdb.get_episode_details(
                tmdb_id=media_id,
                episode_number=data.get("episode"),
                season_number=data.get("season"),
            )
    else:
        media_id = tmdb.find_media_id(title=title, data_type="movie", year=year)

    if media_id:
        details = tmdb.get_details(
            tmdb_id=media_id, data_type="movie" if "episode" not in data else "series"
        )

    return {
        "media_id": media_id,
        "media_details": details,
        "episode_details": episode_details,
    }


async def process_series(
    media_id: int,
    data: Dict[str, Union[str, int]],
    series_details: Dict,
    episode_details: Dict,
    file_info: Dict[str, Union[str, int]],
) -> None:
    genres = [genre["name"] for genre in series_details.get("genres", [])]
    series_doc = {
        "tmdb_id": series_details.get("id"),
        "title": series_details.get("name"),
        "rating": series_details.get("vote_average"),
        "release_date": series_details.get("first_air_date"),
        "origin_country": series_details.get("origin_country"),
        "original_language": series_details.get("original_language"),
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
                        "date": episode_details.get("air_date"),
                        "duration": episode_details.get("runtime"),
                        "title": episode_details.get("name"),
                        "rating": series_details.get("vote_average"),
                        "file_info": [file_info],
                    }
                ],
            }
        ],
    }

    async with lock:
        existing_media = await db.get_tmdb(tmdb_id=media_id)
        if existing_media:
            await db.update_tmdb(existing_media, series_doc, "series")
        else:
            await db.add_tmdb(series_doc)


async def process_files(file_info: Dict[str, Union[str, int]]) -> None:
    media_doc = {**file_info, "mode": "multi"}

    async with lock:
        existing_media = await db.get_media_file(hash=file_info["hash"])
        if existing_media:
            await db.update_media_file(media_doc)
        else:
            await db.add_media_file(media_doc)


async def process_movie(
    media_id: int,
    media_details: Dict,
    file_info: Dict[str, Union[str, int]],
) -> None:
    genres = [genre["name"] for genre in media_details.get("genres", [])]
    movie_doc = {
        "tmdb_id": media_details.get("id"),
        "title": media_details.get("title"),
        "rating": media_details.get("vote_average"),
        "runtime": media_details.get("runtime"),
        "release_date": media_details.get("release_date"),
        "origin_country": media_details.get("origin_country"),
        "original_language": media_details.get("original_language"),
        "genres": genres,
        "type": "movie",
        "file_info": [file_info],
    }

    async with lock:
        existing_media = await db.get_tmdb(tmdb_id=media_id)
        if existing_media:
            await db.update_tmdb(existing_media, movie_doc, "movie")
        else:
            await db.add_tmdb(movie_doc)


def extract_show_info_raw(data: Dict) -> Dict:
    show_info = {
        "tmdb_id": data.get("tmdb_id"),
        "title": data.get("title"),
        "type": data.get("type"),
        "country": data.get("origin_country"),
        "language": data.get("original_language"),
        "files": [],
    }
    for season in data.get("seasons", []):
        for episode in season.get("episodes", []):
            for info in episode["file_info"]:
                episode_info = {
                    "name": "Telegram",
                    "title": info.get("file_name"),
                    "mode": "tv",
                    "season": episode.get("season_number"),
                    "episode": episode.get("episode_number"),
                    "date": episode.get("date"),
                    "duration": episode.get("duration"),
                    "quality": info.get("quality"),
                    "size": info.get("file_size"),
                    "url": generate_stream_url(
                        tmdb_id=data.get("tmdb_id"), file_hash=info.get("hash")
                    ),
                }
                show_info["files"].append(episode_info)
    return show_info


def extract_movie_info_raw(data: Dict) -> Dict:
    movie_info = {
        "tmdb_id": data.get("tmdb_id"),
        "title": data.get("title"),
        "type": data.get("type"),
        "country": data.get("origin_country"),
        "language": data.get("original_language"),
        "date": data.get("release_date"),
        "duration": data.get("runtime"),
        "files": [],
    }
    for info in data["file_info"]:
        files_info = {
            "name": "Telegram",
            "title": info.get("file_name"),
            "mode": "movies",
            "quality": info.get("quality"),
            "size": info.get("file_size"),
            "url": generate_stream_url(
                tmdb_id=data.get("tmdb_id"), file_hash=info.get("hash")
            ),
        }
        movie_info["files"].append(files_info)
    return movie_info


def extract_show_info(
    data: Dict, season_num: int, episode_num: int, tmdb_id: int
) -> List[Dict]:
    show_info = []
    for season in data.get("seasons", []):
        if season.get("season_number") == int(season_num):
            for episode in season.get("episodes", []):
                if episode.get("episode_number") == int(episode_num):
                    for info in episode["file_info"]:
                        episode_info = {
                            "name": "Telegram",
                            "title": info.get("file_name"),
                            "season": episode.get("season_number"),
                            "episode": episode.get("episode_number"),
                            "date": episode.get("date"),
                            "duration": episode.get("duration"),
                            "quality": info.get("quality"),
                            "size": info.get("file_size"),
                            "url": generate_stream_url(
                                tmdb_id=tmdb_id, file_hash=info.get("hash")
                            ),
                        }
                        show_info.append(episode_info)
    return show_info


def extract_movie_info(data: Dict, tmdb_id: int) -> List[Dict]:
    movie_info = []
    release_date = data.get("release_date")
    runtime = data.get("runtime")

    for info in data["file_info"]:
        file_info = {
            "name": "Telegram",
            "title": info.get("file_name"),
            "date": release_date,
            "duration": runtime,
            "quality": info.get("quality"),
            "size": info.get("file_size"),
            "url": generate_stream_url(tmdb_id=tmdb_id, file_hash=info.get("hash")),
        }
        movie_info.append(file_info)
    return movie_info


async def extract_media_by_hash(data: Dict, file_hash: str) -> Optional[Dict]:
    if data.get("type") == "tv":
        for season in data.get("seasons", []):
            for episode in season.get("episodes", []):
                for info in episode["file_info"]:
                    if info.get("hash") == file_hash:
                        return info
    elif data.get("type") == "movie":
        for info in data["file_info"]:
            if info.get("hash") == file_hash:
                return info


def get_readable_size(size_in_bytes: Union[int, str]) -> str:
    size_in_bytes = int(size_in_bytes) if str(size_in_bytes).isdigit() else 0
    if not size_in_bytes:
        return "0B"
    index, SIZE_UNITS = 0, ["B", "KB", "MB", "GB", "TB", "PB"]

    while size_in_bytes >= 1024 and index < len(SIZE_UNITS) - 1:
        size_in_bytes /= 1024
        index += 1
    return (
        f"{size_in_bytes:.2f}{SIZE_UNITS[index]}"
        if index > 0
        else f"{size_in_bytes:.2f}B"
    )


def get_readable_time(seconds: int) -> str:
    count = 0
    readable_time = ""
    time_list = []
    time_suffix_list = ["s", "m", "h", " days"]
    while count < 4:
        count += 1
        if count < 3:
            remainder, result = divmod(seconds, 60)
        else:
            remainder, result = divmod(seconds, 24)
        if seconds == 0 and remainder == 0:
            break
        time_list.append(int(result))
        seconds = int(remainder)
    for x in range(len(time_list)):
        time_list[x] = str(time_list[x]) + time_suffix_list[x]
    if len(time_list) == 4:
        readable_time += time_list.pop() + ", "
    time_list.reverse()
    readable_time += ": ".join(time_list)
    return readable_time


def generate_stream_url(tmdb_id: int, file_hash: str) -> str:
    return f"{BASE_URL}/dl?tmdb_id={tmdb_id}&hash={file_hash}"


def generate_stream_url_file(file_hash: str) -> str:
    return f"{BASE_URL}/dl?file_id={file_hash}&hash={file_hash}"
