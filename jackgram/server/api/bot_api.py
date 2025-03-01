from jackgram.bot import get_db
from jackgram.utils.utils import (
    extract_movie_info,
    extract_movie_info_raw,
    extract_show_info,
    extract_show_info_raw,
    generate_stream_url_file,
)
from quart import Blueprint, jsonify, request

stream_routes = Blueprint("stream", __name__, url_prefix="/stream")

db = get_db()


@stream_routes.route("/latest", methods=["GET"])
async def stream_latest():
    page = int(request.args.get("page", 1))
    if page < 1:
        return jsonify({"error": "Page must be positive integers"}), 400

    data = await db.get_tmdb_latest(page=page)
    if data is None:
        return jsonify({"error": "Item not found"}), 404

    media_info = []
    for item in data:
        if item["type"] == "movie":
            media_info.append(extract_movie_info_raw(item))
        elif item["type"] == "tv":
            media_info.append(extract_show_info_raw(item))

    return media_info


@stream_routes.route("/files", methods=["GET"])
async def stream_files():
    page = int(request.args.get("page", 1))
    if page < 1:
        return jsonify({"error": "Page must be positive integers"}), 400

    data = await db.get_media_files(page=page)
    if data is None:
        return jsonify({"error": "Item not found"}), 404

    for item in data:
        del item["_id"]
        item["name"] = "Telegram"
        item["url"] = generate_stream_url_file(hash=item.get("hash"))

    return data


@stream_routes.route(
    "/series/<int:tmdb_id>:<int:season>:<int:episode>.json", methods=["GET"]
)
async def stream_series(tmdb_id, season, episode):
    if not tmdb_id:
        return jsonify({"stream": []})

    data = await db.get_tmdb(tmdb_id)
    if data is None:
        return jsonify({"error": "Item not found"}), 404

    if data.get("type") == "tv":
        return jsonify(
            {
                "tmdb_id": tmdb_id,
                "streams": extract_show_info(data, season, episode, tmdb_id),
            }
        )


@stream_routes.route("/movie/<int:tmdb_id>.json")
async def stream_movie(tmdb_id):
    if not tmdb_id:
        return jsonify({"stream": []})

    data = await db.get_tmdb(tmdb_id)
    if data is None:
        return jsonify({"error": "Item not found"}), 404

    if data.get("type") == "movie":
        info = extract_movie_info(data, tmdb_id)

        return jsonify(
            {
                "tmdb_id": tmdb_id,
                "streams": info,
            }
        )


@stream_routes.route("/search", methods=["GET"])
async def stream_search():
    try:
        search_query = request.args.get("query")
        page = int(request.args.get("page", 1))

        if not search_query:
            return jsonify({"error": "Search query (q) is required"}), 400

        if page < 1:
            return jsonify({"error": "Page must be positive integers"}), 400

        results, total_count = await db.search_tmdb(search_query, page)

        if not results:
            return jsonify({"error": "Item not found"}), 404

        media_info = [
            (
                extract_movie_info_raw(result)
                if result["type"] == "movie"
                else extract_show_info_raw(result)
            )
            for result in results
        ]

        return jsonify(
            {
                "page": page,
                "total_count": total_count,
                "results": media_info,
            }
        )

    except Exception as e:
        return jsonify({"error": str(e)}), 500
