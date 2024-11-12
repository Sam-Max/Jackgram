import re
from streamtg.utils.bot_utils import generate_link

def extract_show_info_raw(data):
    show_info = []
    for season in data.get("seasons", []):
        for episode in season.get("episodes", []):
            channel_id = episode["file_info"][0].get("chn_id")
            message_id = episode["file_info"][0].get("msg_id")
            hash = episode["file_info"][0].get("hash")
            title = episode["file_info"][0].get("original_title")

            url = generate_link(channel_id, message_id, hash)

            # season_number = season.get("season_number")
            # episode_number = episode.get("episode_number")

            episode_info = {
                "tracker": "Telegram",
                "title": title,
                "date": episode.get("date"),
                "duration": episode.get("duration"),
                "quality": episode["file_info"][0].get("quality"),
                "size": episode["file_info"][0].get("size"),
                "link": url,
            }

            show_info.append(episode_info)
    return show_info


def extract_show_info(data, season_num, episode_num):
    show_info = []
    for season in data.get("seasons", []):
        if season.get("season_number") == int(season_num):
            for episode in season.get("episodes", []):
                if episode.get("episode_number") == int(episode_num):

                    channel_id = episode["file_info"][0].get("chn_id")
                    message_id = episode["file_info"][0].get("msg_id")
                    hash = episode["file_info"][0].get("hash")
                    title = episode["file_info"][0].get("original_title")

                    url = generate_link(channel_id, message_id, hash)

                    # season_number = season.get("season_number")
                    # episode_number = episode.get("episode_number")

                    episode_info = {
                        "tracker": "Telegram",
                        "title": title,
                        "date": episode.get("date"),
                        "duration": episode.get("duration"),
                        "quality": episode["file_info"][0].get("quality"),
                        "size": episode["file_info"][0].get("size"),
                        "link": url,
                    }
                show_info.append(episode_info)
    return show_info


def extract_movie_info(data):
    movie_info = []

    release_date = data.get("release_date")
    runtime = data.get("runtime")

    for file in data["file_info"]:
        channel_id = file.get("chn_id")
        message_id = file.get("msg_id")
        hash = file.get("hash")
        title = file.get("original_title")

        url = generate_link(channel_id, message_id, hash)

        file_info = {
            "tracker": "Telegram",
            "title": title,
            "date": release_date,
            "duration": runtime,
            "quality": file.get("quality"),
            "size": file.get("size"),
            "link": url,
        }
        movie_info.append(file_info)
    return movie_info


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
