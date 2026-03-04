from fastapi import APIRouter, HTTPException
from jackgram.bot.bot import get_db, BASE_URL, USE_TOKEN_SYSTEM

stremio_routes = APIRouter(prefix="/stremio")
db = get_db()


# ------------- Token validation helper for Stremio routes -------------


async def _validate_stremio_token(token: str):
    """
    Validate the API token embedded in the Stremio URL path.
    If USE_TOKEN_SYSTEM is disabled, any token (even a placeholder) is accepted.
    """
    if not USE_TOKEN_SYSTEM:
        return True

    user = await db.get_api_user(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or missing Stremio token")
    return user


def _stream_url(file_hash: str, token: str) -> str:
    """Generate a stream URL that includes the user's API token."""
    return f"{BASE_URL}/dl?hash={file_hash}&token={token}"


# ----------------- STREMIO ENDPOINTS -----------------


@stremio_routes.get("/{token}/manifest.json")
async def get_manifest(token: str):
    """
    Returns the Stremio Addon manifest.
    The token is embedded in the URL so Stremio can reuse it across all requests.
    """
    await _validate_stremio_token(token)

    return {
        "id": "com.jackgram.stremio",
        "version": "1.0.0",
        "name": "Jackgram",
        "description": "Stream your Jackgram indexed media directly in Stremio.",
        "logo": "https://telegram.org/img/t_logo.png",
        "resources": ["catalog", "meta", "stream"],
        "types": ["movie", "series"],
        "catalogs": [
            {"type": "movie", "id": "jackgram_movies", "name": "Jackgram Movies"},
            {"type": "series", "id": "jackgram_series", "name": "Jackgram Series"},
        ],
        "idPrefixes": ["tmdb:"],
        "behaviorHints": {"configurable": False, "configurationRequired": False},
    }


@stremio_routes.get("/{token}/catalog/{type}/{id}.json")
@stremio_routes.get("/{token}/catalog/{type}/{id}/{extra}.json")
async def get_catalog(token: str, type: str, id: str, extra: str = None):
    """
    Returns the catalog of available movies or series for Stremio.
    Handles optional extra parameters like skip for pagination.
    """
    await _validate_stremio_token(token)

    if type not in ["movie", "series"]:
        return {"metas": []}

    jackgram_type = "movie" if type == "movie" else "tv"

    page = 1
    if extra:
        from urllib.parse import unquote

        extra = unquote(extra)
        for part in extra.split("&"):
            if part.startswith("skip="):
                try:
                    skip = int(part.split("=")[1])
                    page = (skip // 25) + 1
                except ValueError:
                    pass

    data = await db.get_tmdb_latest(media_type=jackgram_type, page=page, per_page=25)

    if not data:
        return {"metas": []}

    metas = []
    for item in data:
        meta = {
            "id": f"tmdb:{item.get('tmdb_id')}",
            "type": type,
            "name": item.get("title") or item.get("name"),
            "poster": (
                f"https://image.tmdb.org/t/p/w500{item.get('poster_path')}"
                if item.get("poster_path")
                else None
            ),
            "description": item.get("overview", ""),
            "releaseInfo": str(
                item.get("release_date") or item.get("first_air_date", "")
            )[:4],
        }
        metas.append(meta)

    return {"metas": metas}


@stremio_routes.get("/{token}/meta/{type}/{id}.json")
async def get_meta(token: str, type: str, id: str):
    """
    Returns detailed metadata for a specific movie or series.
    """
    await _validate_stremio_token(token)

    if not id.startswith("tmdb:"):
        return {"meta": {}}

    tmdb_id = int(id.split(":")[1])
    data = await db.get_tmdb(tmdb_id)

    if not data:
        return {"meta": {}}

    meta = {
        "id": id,
        "type": type,
        "name": data.get("title") or data.get("name"),
        "poster": (
            f"https://image.tmdb.org/t/p/w500{data.get('poster_path')}"
            if data.get("poster_path")
            else None
        ),
        "background": (
            f"https://image.tmdb.org/t/p/original{data.get('backdrop_path')}"
            if data.get("backdrop_path")
            else None
        ),
        "description": data.get("overview", ""),
        "releaseInfo": str(data.get("release_date") or data.get("first_air_date", ""))[
            :4
        ],
        "genres": data.get("genres", []),
        "runtime": f"{data.get('runtime')} min" if data.get("runtime") else None,
    }

    # Add episodes if it's a TV show
    if type == "series" and data.get("type") == "tv":
        videos = []
        for season in data.get("seasons", []):
            for episode in season.get("episodes", []):
                videos.append(
                    {
                        "id": f"{id}:{episode.get('season_number')}:{episode.get('episode_number')}",
                        "title": episode.get(
                            "title", f"Episode {episode.get('episode_number')}"
                        ),
                        "season": episode.get("season_number"),
                        "episode": episode.get("episode_number"),
                        "released": episode.get("date"),
                    }
                )
        meta["videos"] = videos

    return {"meta": meta}


@stremio_routes.get("/{token}/stream/{type}/{id}.json")
async def get_streams(token: str, type: str, id: str):
    """
    Returns available streams for a movie or an episode.
    The token is appended to each stream URL so /dl can authorize the request.
    id formats:
    - movie: tmdb:12345
    - series: tmdb:12345:1:2 (tmdb_id:season:episode)
    """
    await _validate_stremio_token(token)

    parts = id.split(":")
    if len(parts) < 2 or parts[0] != "tmdb":
        return {"streams": []}

    try:
        tmdb_id = int(parts[1])
    except ValueError:
        return {"streams": []}

    data = await db.get_tmdb(tmdb_id)
    if not data:
        return {"streams": []}

    streams = []

    if type == "movie" and data.get("type") == "movie":
        for info in data.get("file_info", []):
            streams.append(
                {
                    "name": f"Jackgram\n{info.get('quality', 'Unknown')}",
                    "title": f"{info.get('file_name')} | {round(info.get('file_size', 0) / (1024 * 1024 * 1024), 2)} GB",
                    "url": _stream_url(info.get("hash"), token),
                }
            )

    elif type == "series" and data.get("type") == "tv" and len(parts) == 4:
        try:
            season_num = int(parts[2])
            episode_num = int(parts[3])
        except ValueError:
            return {"streams": []}

        for season in data.get("seasons", []):
            if season.get("season_number") == season_num:
                for episode in season.get("episodes", []):
                    if episode.get("episode_number") == episode_num:
                        for info in episode.get("file_info", []):
                            streams.append(
                                {
                                    "name": f"Jackgram\n{info.get('quality', 'Unknown')}",
                                    "title": f"{info.get('file_name')} | {round(info.get('file_size', 0) / (1024 * 1024 * 1024), 2)} GB",
                                    "url": _stream_url(info.get("hash"), token),
                                }
                            )

    return {"streams": streams}
