import logging
import httpx
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any, Dict, List, Optional
import uuid
import time
import jwt
from telethon.sync import TelegramClient
from telethon.sessions import StringSession
from telethon.errors import SessionPasswordNeededError
from jackgram.bot.bot import (
    get_db,
    TMDB_API,
    TMDB_LANGUAGE,
    API_ID,
    API_HASH,
    AUTH_USERS,
    SECRET_KEY,
)

admin_routes = APIRouter(prefix="/admin")
db = get_db()


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Remove MongoDB ObjectId so the document is JSON-serialisable."""
    doc.pop("_id", None)
    return doc


# ---------------------------------------------------------------------------
# Auth / Login
# ---------------------------------------------------------------------------


class LoginPayload(BaseModel):
    username: str
    password: str


@admin_routes.post("/login")
async def admin_login(payload: LoginPayload):
    if (
        payload.username not in AUTH_USERS
        or AUTH_USERS[payload.username] != payload.password
    ):
        return JSONResponse(status_code=401, content={"detail": "Invalid credentials"})

    payload_data = {
        "user": payload.username,
        "exp": time.time() + (7 * 24 * 3600),  # Valid for 7 days
    }
    token = jwt.encode(payload_data, SECRET_KEY, algorithm="HS256")
    response = JSONResponse(content={"status": "ok", "token": token})
    # Set cookie for browser-based streaming (admin bypass)
    response.set_cookie(
        key="jg-token",
        value=token,
        httponly=True,
        max_age=7 * 24 * 3600,
        samesite="lax",
        path="/",
    )
    return response


@admin_routes.post("/logout")
async def admin_logout():
    response = JSONResponse(content={"status": "ok"})
    response.delete_cookie(key="jg-token")
    return response


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


@admin_routes.get("/stats")
async def get_stats():
    movies = await db.count_movies()
    tv = await db.count_tv()
    files = await db.count_media_files()
    storage = await db.get_total_storage()
    return {
        "movies": movies,
        "tv_shows": tv,
        "raw_files": files,
        "total_storage_bytes": storage,
    }


# ---------------------------------------------------------------------------
# Movies
# ---------------------------------------------------------------------------


class MovieUpdate(BaseModel):
    title: Optional[str] = None
    rating: Optional[float] = None
    release_date: Optional[str] = None
    runtime: Optional[int] = None
    genres: Optional[List[str]] = None


@admin_routes.get("/movies")
async def list_movies(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("date", pattern="^(date|title|rating|size)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    data = await db.get_movies(
        page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order
    )
    total = await db.count_movies()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "results": [_clean(d) for d in data],
    }


@admin_routes.get("/movies/{tmdb_id}")
async def get_movie(tmdb_id: int):
    data = await db.get_tmdb(tmdb_id)
    if not data or data.get("type") != "movie":
        raise HTTPException(status_code=404, detail="Movie not found")
    return _clean(data)


@admin_routes.put("/movies/{tmdb_id}")
async def update_movie(tmdb_id: int, payload: MovieUpdate):
    existing = await db.get_tmdb(tmdb_id)
    if not existing or existing.get("type") != "movie":
        raise HTTPException(status_code=404, detail="Movie not found")

    update_fields: Dict[str, Any] = {
        k: v for k, v in payload.dict().items() if v is not None
    }
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    existing.update(update_fields)
    await db.tmdb_collection.replace_one({"tmdb_id": tmdb_id}, existing)
    return _clean(existing)


@admin_routes.delete("/movies/{tmdb_id}")
async def delete_movie(tmdb_id: int):
    existing = await db.get_tmdb(tmdb_id)
    if not existing or existing.get("type") != "movie":
        raise HTTPException(status_code=404, detail="Movie not found")
    await db.del_tmdb(tmdb_id)
    return {"deleted": True, "tmdb_id": tmdb_id}


# ---------------------------------------------------------------------------
# TV Shows
# ---------------------------------------------------------------------------


class TVUpdate(BaseModel):
    title: Optional[str] = None
    rating: Optional[float] = None
    release_date: Optional[str] = None
    genres: Optional[List[str]] = None


@admin_routes.get("/tv")
async def list_tv(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort_by: str = Query("date", pattern="^(date|title|rating)$"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),
):
    data = await db.get_tv(
        page=page, per_page=per_page, sort_by=sort_by, sort_order=sort_order
    )
    total = await db.count_tv()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "results": [_clean(d) for d in data],
    }


@admin_routes.get("/tv/{tmdb_id}")
async def get_tv_show(tmdb_id: int):
    data = await db.get_tmdb(tmdb_id)
    if not data or data.get("type") != "tv":
        raise HTTPException(status_code=404, detail="TV show not found")
    return _clean(data)


@admin_routes.put("/tv/{tmdb_id}")
async def update_tv_show(tmdb_id: int, payload: TVUpdate):
    existing = await db.get_tmdb(tmdb_id)
    if not existing or existing.get("type") != "tv":
        raise HTTPException(status_code=404, detail="TV show not found")

    update_fields: Dict[str, Any] = {
        k: v for k, v in payload.dict().items() if v is not None
    }
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    existing.update(update_fields)
    await db.tmdb_collection.replace_one({"tmdb_id": tmdb_id}, existing)
    return _clean(existing)


@admin_routes.delete("/tv/{tmdb_id}")
async def delete_tv_show(tmdb_id: int):
    existing = await db.get_tmdb(tmdb_id)
    if not existing or existing.get("type") != "tv":
        raise HTTPException(status_code=404, detail="TV show not found")
    await db.del_tmdb(tmdb_id)
    return {"deleted": True, "tmdb_id": tmdb_id}


# ---------------------------------------------------------------------------
# Raw Media Files
# ---------------------------------------------------------------------------


@admin_routes.get("/files")
async def list_files(
    page: int = Query(1, ge=1), per_page: int = Query(20, ge=1, le=100)
):
    data = await db.get_media_files(page=page, per_page=per_page)
    total = await db.count_media_files()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "results": [_clean(d) for d in data],
    }


@admin_routes.delete("/files/{file_hash}")
async def delete_file(file_hash: str):
    existing = await db.get_media_file(file_hash)
    if not existing:
        raise HTTPException(status_code=404, detail="File not found")
    await db.del_media_file(file_hash)
    return {"deleted": True, "hash": file_hash}


# ---------------------------------------------------------------------------
# TMDb Poster Proxy
# ---------------------------------------------------------------------------

_poster_cache: Dict[str, Optional[str]] = {}


@admin_routes.get("/poster/{tmdb_id}")
async def get_poster(tmdb_id: int, type: str = Query("movie", pattern="^(movie|tv)$")):
    """Proxy TMDb API to return poster URL without exposing the API key."""
    cache_key = f"{type}:{tmdb_id}"
    if cache_key in _poster_cache:
        return {"poster_url": _poster_cache[cache_key]}

    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(
                f"https://api.themoviedb.org/3/{type}/{tmdb_id}",
                params={"api_key": TMDB_API, "language": TMDB_LANGUAGE},
            )
            if resp.status_code == 200:
                data = resp.json()
                poster_path = data.get("poster_path")
                overview = data.get("overview", "")
                backdrop_path = data.get("backdrop_path")
                poster_url = (
                    f"https://image.tmdb.org/t/p/w300{poster_path}"
                    if poster_path
                    else None
                )
                backdrop_url = (
                    f"https://image.tmdb.org/t/p/w780{backdrop_path}"
                    if backdrop_path
                    else None
                )
                _poster_cache[cache_key] = poster_url
                return {
                    "poster_url": poster_url,
                    "backdrop_url": backdrop_url,
                    "overview": overview,
                }
            else:
                _poster_cache[cache_key] = None
                return {"poster_url": None, "backdrop_url": None, "overview": ""}
    except Exception as e:
        logging.warning(f"Failed to fetch poster for {type}/{tmdb_id}: {e}")
        return {"poster_url": None, "backdrop_url": None, "overview": ""}


# ---------------------------------------------------------------------------
# Session Generator
# ---------------------------------------------------------------------------


class SessionRequestCodePayload(BaseModel):
    phone_number: str


class SessionVerifyCodePayload(BaseModel):
    phone_number: str
    phone_code_hash: str
    code: str
    password: Optional[str] = None


# Temporary in-memory storage for clients during the auth flow
_session_clients: Dict[str, TelegramClient] = {}


@admin_routes.post("/session/request_code")
async def session_request_code(payload: SessionRequestCodePayload):
    if not API_ID or not API_HASH:
        raise HTTPException(
            status_code=500, detail="API_ID and API_HASH must be configured."
        )

    phone = payload.phone_number.strip()
    if not phone:
        raise HTTPException(status_code=400, detail="Phone number is required.")

    # Clean up any existing client for this phone
    if phone in _session_clients:
        try:
            await _session_clients[phone].disconnect()
        except:
            pass
        del _session_clients[phone]

    client = TelegramClient(StringSession(), API_ID, API_HASH)
    await client.connect()

    try:
        sent_code = await client.send_code_request(phone)
        _session_clients[phone] = client
        return {
            "status": "ok",
            "phone_code_hash": sent_code.phone_code_hash,
            "is_password_required": False,  # We don't know yet until verification
        }
    except Exception as e:
        await client.disconnect()
        logging.error(f"Error requesting code for {phone}: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@admin_routes.post("/session/verify_code")
async def session_verify_code(payload: SessionVerifyCodePayload):
    phone = payload.phone_number.strip()
    client = _session_clients.get(phone)

    if not client or not client.is_connected():
        raise HTTPException(
            status_code=400,
            detail="Session expired or not found. Please request a new code.",
        )

    try:
        try:
            await client.sign_in(
                phone=phone,
                code=payload.code,
                phone_code_hash=payload.phone_code_hash,
            )
        except SessionPasswordNeededError:
            if not payload.password:
                return JSONResponse(
                    status_code=401,
                    content={
                        "password_required": True,
                        "detail": "2FA password required",
                    },
                )
            await client.sign_in(password=payload.password)

        session_string = client.session.save()
        return {"status": "ok", "session_string": session_string}

    except Exception as e:
        logging.error(f"Error verifying code for {phone}: {e}")
        # Only raise error, don't disconnect immediately in case they need to type password
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        # If successfully authorized, or if a fatal error occurred (not just missing password),
        # we cleanup. Note: This could be refined.
        if await client.is_user_authorized():
            await client.disconnect()
            if phone in _session_clients:
                del _session_clients[phone]


# ---------------------------------------------------------------------------
# System Health & Bot Load Dashboard
# ---------------------------------------------------------------------------

from jackgram.server.routes import active_streams
from jackgram.utils.telegram_stream import multi_session_manager


@admin_routes.get("/system-stats")
async def get_system_stats():
    clients = []
    # Count connected sessions and their DC id safely
    for client in multi_session_manager._clients:
        is_conn = client.is_connected()
        dc_id = getattr(client.session, "dc_id", 0) if is_conn else 0
        clients.append({"connected": is_conn, "dc_id": dc_id})

    return {
        "clients_total": len(multi_session_manager._clients),
        "clients_connected": sum(1 for c in clients if c["connected"]),
        "clients_info": clients,
        "active_streams": list(active_streams.values()),
        "cache_size": len(multi_session_manager._media_info_cache),
    }


@admin_routes.delete("/stream/{stream_id}")
async def cancel_stream(stream_id: str):
    if stream_id in active_streams:
        active_streams[stream_id]["cancelled"] = True
        return {"success": True, "message": "Stream cancelled successfully."}
    raise HTTPException(status_code=404, detail="Stream ID not found.")


# ---------------------------------------------------------------------------
# API Users Management
# ---------------------------------------------------------------------------


class APIUserCreatePayload(BaseModel):
    name: str


@admin_routes.get("/api-users")
async def list_api_users():
    users = await db.get_api_users()
    return {"results": users}


@admin_routes.post("/api-users")
async def create_api_user(payload: APIUserCreatePayload):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Name is required")

    # Generate a unique token
    token = f"jack_{uuid.uuid4().hex}"
    await db.add_api_user(name, token)
    return {"status": "ok", "name": name, "token": token}


@admin_routes.delete("/api-users/{token}")
async def delete_api_user(token: str):
    success = await db.delete_api_user(token)
    if not success:
        raise HTTPException(status_code=404, detail="Token not found")
    return {"status": "ok", "deleted": True}


@admin_routes.post("/system-stats/clear-cache")
async def clear_system_cache():
    multi_session_manager._media_info_cache.clear()
    return {"status": "ok", "cleared": True}
