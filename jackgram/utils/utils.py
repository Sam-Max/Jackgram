from jackgram.bot import BASE_URL
import re


def extract_show_info_raw(data):
    show_info = {
        "tmdb_id": data.get("tmdb_id"),
        "title": data.get("title"),
        "type": data.get("type"),
        "country": data.get("origin_country")[0],
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
                        tmdb_id=data.get("tmdb_id"), hash=info.get("hash")
                    ),
                }
                show_info["files"].append(episode_info)
    return show_info

def extract_movie_info_raw(data):
    movie_info = {
        "tmdb_id": data.get("tmdb_id"),
        "title": data.get("title"),
        "type": data.get("type"),
        "country": data.get("origin_country")[0],
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
                tmdb_id=data.get("tmdb_id"), hash=info.get("hash")
            ),
        }
        movie_info["files"].append(files_info)
    return movie_info


def extract_show_info(data, season_num, episode_num, tmdb_id):
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
                                tmdb_id=tmdb_id, hash=info.get("hash")
                            ),
                        }
                        show_info.append(episode_info)
    return show_info

def extract_movie_info(data, tmdb_id):
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
            "url": generate_stream_url(tmdb_id=tmdb_id, hash=info.get("hash")),
        }
        movie_info.append(file_info)
    return movie_info


async def extract_media_by_hash(data, hash):
    if data.get("type") == "tv":
        for season in data.get("seasons", []):
            for episode in season.get("episodes", []):
                for info in episode["file_info"]:
                    if info.get("hash") == hash:
                        return info
    else:
        for info in data["file_info"]:
            if info.get("hash") == hash:
                return info


def clean_file_name(name: str) -> str:
    """Removes common and unnecessary strings from file names"""
    reg_exps = [
        r"\((?:\D.+?|.+?\D)\)|\[(?:\D.+?|.+?\D)\]",  # (2016), [2016], etc
        r"\(?(?:240|360|480|720|1080|1440|2160)p?\)?",  # 1080p, 720p, etc
        r"\b(?:mp4|mkv|wmv|m4v|mov|avi|flv|webm|flac|mka|m4a|aac|ogg)\b",  # file types
        r"season ?\d+?",  # season 1, season 2, etc
        # more stuffs
        r"(?:S\d{1,3}|\d+?bit|dsnp|web\-dl|ddp\d+? ? \d|hevc|hdrip|\-?Vyndros)",
        # URLs in filenames
        r"^(?:https?:\/\/)?(?:www.)?[a-z0-9]+\.[a-z]+(?:\/[a-zA-Z0-9#]+\/?)*$",
    ]
    for reg in reg_exps:
        name = re.sub(reg, "", name)
    return name.strip().rstrip(".-_")


def get_readable_size(size_in_bytes):
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


def generate_stream_url(tmdb_id, hash):
    return f"{BASE_URL}/dl/{tmdb_id}?hash={hash}"
