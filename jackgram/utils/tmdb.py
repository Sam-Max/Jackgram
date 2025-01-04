import logging
from math import ceil
import re
from typing import Optional
from requests.sessions import Session
from jackgram.bot import TMDB_API, TMDB_LANGUAGE


class TMDBClient:
    def __init__(self):
        self.client = Session()
        self.api_key = TMDB_API
        self.language = TMDB_LANGUAGE

    def get_episode_details(
        self, tmdb_id: int, episode_number: int, season_number: int = 1
    ) -> dict:
        """Get the details of a specific episode from the API"""
        url = f"https://api.themoviedb.org/3/tv/{tmdb_id}/season/{season_number}/episode/{episode_number}"
        response = self.client.get(
            url, params={"api_key": self.api_key, "language": self.language}
        )
        if response.status_code == 200:
            return response.json()
        else:
            logging.error(
                f"Failed to fetch episode details for TMDB ID {tmdb_id}, season {season_number}, episode {episode_number}. Status code: {response.status_code}"
            )
            return {}

    def find_media_id(
        self,
        title: str,
        data_type: str,
        use_api: bool = True,
        year: Optional[int] = None,
        adult: bool = False,
    ) -> Optional[int]:
        """Get TMDB ID for a title"""

        title = title.lower().strip()
        original_title = title
        title = clean_file_name(title)

        if not title:
            logging.error("The parsed title returned an empty string. Skipping...")
            logging.info("Original Title: %s", original_title)
            return None

        if use_api:
            logging.info("Searching using Tmdb API for: '%s'", title)
            type_name = "tv" if data_type == "series" else "movie"

            def search_tmdb(query_year):
                params = {
                    "query": title,
                    "include_adult": adult,
                    "page": 1,
                    "language": self.language,
                    "api_key": self.api_key,
                }
                if query_year:
                    params["primary_release_year"] = query_year

                resp = self.client.get(f"https://api.themoviedb.org/3/search/{type_name}", params=params)
                return resp

            # Attempt to search with year
            resp = search_tmdb(year)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                if not results and year:
                    # Retry without year if no results are found
                    logging.error(
                        f"No results found for '{title}' with year {year}. Retrying without year."
                    )
                    resp = search_tmdb(None)
                    results = resp.json().get("results", [])

                if results:
                    logging.info(f"Results found for {title}")
                    return results[0]["id"]

                else:
                    logging.error(
                        f"No results found for '{title}' - The API said '{resp.json().get('errors', 'No error message provided')}' with status code {resp.status_code}"
                    )
            else:
                logging.error(
                    f"API search failed for '{title}' - The API said '{resp.json().get('errors', 'No error message provided')}' with status code {resp.status_code}"
                )
        return

    def get_details(self, tmdb_id: int, data_type: str) -> dict:
        """Get the details of a movie/series from the API"""
        type_name = "tv" if data_type == "series" else "movie"
        url = f"https://api.themoviedb.org/3/{type_name}/{tmdb_id}"
        if type_name == "tv":
            params = {
                "include_image_language": self.language,
                "append_to_response": "credits,images,external_ids,videos,reviews,content_ratings",
                "api_key": self.api_key,
                "language": self.language,
            }
        else:
            params = {
                "include_image_language": self.language,
                "append_to_response": "credits,images,external_ids,videos,reviews",
                "api_key": self.api_key,
                "language": self.language,
            }
        response = self.client.get(url, params=params).json()

        if type_name == "tv":
            self._extract_from_get_details(response, url)

        return response

    def _extract_from_get_details(self, response, url):
        seasons = response.get("seasons", [])
        length = len(seasons)
        append_seasons = []
        n_of_appends = ceil(length / 20)
        for x in range(n_of_appends):
            append_season = ",".join(
                f"season/{n}" for n in range(x * 20, min((x + 1) * 20, length))
            )
            append_seasons.append(append_season)

        for append_season in append_seasons:
            tmp_response = self.client.get(
                url,
                params={"append_to_response": append_season, "api_key": self.api_key},
            ).json()
            season_keys = [k for k in tmp_response.keys() if "season/" in k]
            for key in season_keys:
                response[key] = tmp_response[key]


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



def get_tmdb():
    return TMDBClient()