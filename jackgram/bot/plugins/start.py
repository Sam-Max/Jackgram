import asyncio
from asyncio import sleep
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import jwt

from bson.objectid import ObjectId

from telethon import events, Button
from telethon.errors import FloodWaitError

from jackgram.bot.bot import BACKUP_DIR, SECRET_KEY, get_db, StreamBot, LOGS_CHANNELS
from jackgram.bot.auth import admin_only
from jackgram.bot.conversation_state import (
    is_conversation_active,
    mark_conversation_active,
    mark_conversation_inactive,
)
from jackgram.bot.i18n import t
from jackgram.bot.search_sessions import SearchSessionStore
from jackgram.bot.utils import index_channel
from jackgram.utils.telegram_stream import multi_session_manager
from jackgram.utils.utils import (
    get_readable_size,
)

from jackgram import __version__

db = get_db()

SEARCH_RESULTS_PER_PAGE = 6
SEARCH_ITEMS_PER_PAGE = 8
SEARCH_FETCH_PAGE_SIZE = 50
SEARCH_MAX_FETCH_PAGES = 4

search_sessions = SearchSessionStore(ttl_seconds=900)


def _truncate_text(text: str, max_len: int = 48) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) <= max_len:
        return cleaned
    return f"{cleaned[: max_len - 3]}..."


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_callback_int(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _chat_id_candidates(chat_id: int) -> List[int]:
    candidates: List[int] = []
    if chat_id:
        candidates.append(chat_id)

    raw = str(chat_id)
    if raw.startswith("-100"):
        stripped = _safe_int(raw[4:], 0)
        if stripped:
            candidates.append(stripped)
    elif chat_id > 0:
        maybe_channel = _safe_int(f"-100{chat_id}", 0)
        if maybe_channel:
            candidates.append(maybe_channel)

    unique: List[int] = []
    seen = set()
    for value in candidates:
        if value in seen:
            continue
        seen.add(value)
        unique.append(value)
    return unique


async def _resolve_input_entity(client, chat_id: int):
    for candidate in _chat_id_candidates(chat_id):
        try:
            return await client.get_input_entity(candidate)
        except Exception:
            continue

    try:
        await client.get_dialogs(limit=200)
    except Exception:
        pass

    for candidate in _chat_id_candidates(chat_id):
        try:
            return await client.get_input_entity(candidate)
        except Exception:
            continue

    return None


async def _fetch_source_message(client, chat_id: int, message_id: int):
    for candidate in _chat_id_candidates(chat_id):
        source_entity = await _resolve_input_entity(client, candidate)
        if source_entity is None:
            continue
        try:
            src_messages = await asyncio.wait_for(
                client.get_messages(source_entity, ids=[message_id]),
                timeout=15,
            )
        except Exception:
            continue
        src_message = src_messages[0] if src_messages else None
        if src_message:
            return src_message, source_entity
    return None, None


def _paginate_items(items: List[Dict[str, Any]], page: int, per_page: int) -> Tuple[List[Dict[str, Any]], int, int]:
    if not items:
        return [], 1, 0
    total_pages = max((len(items) + per_page - 1) // per_page, 1)
    page = max(1, min(page, total_pages))
    start_idx = (page - 1) * per_page
    return items[start_idx : start_idx + per_page], total_pages, start_idx


def _get_result_kind(item: Dict[str, Any]) -> str:
    item_type = item.get("type")
    if item_type == "movie":
        return "movie"
    if item_type == "tv":
        return "tv"
    return "raw"


def _extract_year(item: Dict[str, Any]) -> str:
    date_value = item.get("release_date") or item.get("first_air_date") or ""
    if isinstance(date_value, str) and "-" in date_value:
        return date_value.split("-")[0]
    return str(date_value) if date_value else ""


def _build_result_label(item: Dict[str, Any]) -> str:
    kind = _get_result_kind(item)
    if kind == "movie":
        title = item.get("title") or t("common.unknown_movie")
        year = _extract_year(item)
        suffix = f" ({year})" if year else ""
        return _truncate_text(f"🎬 {title}{suffix}")
    if kind == "tv":
        title = item.get("title") or item.get("name") or t("common.unknown_series")
        year = _extract_year(item)
        suffix = f" ({year})" if year else ""
        return _truncate_text(f"📺 {title}{suffix}")
    file_name = item.get("file_name") or t("common.unknown_file")
    return _truncate_text(f"📁 {file_name}")


def _build_quality_label(file_data: Dict[str, Any]) -> str:
    quality = file_data.get("quality") or t("common.unknown")
    size = get_readable_size(file_data.get("file_size", 0))
    codec = file_data.get("video_codec") or file_data.get("source") or ""
    if codec:
        return _truncate_text(f"{quality} • {size} • {codec}")
    return _truncate_text(f"{quality} • {size}")


def _callback_data(session_id: str, action: str, value: Optional[Any] = None) -> bytes:
    payload = f"sr:{session_id}:{action}"
    if value is not None:
        payload = f"{payload}:{value}"
    return payload.encode()


def _parse_callback_data(data: bytes) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    try:
        raw = data.decode()
    except Exception:
        return None, None, None
    parts = raw.split(":")
    if len(parts) < 3 or parts[0] != "sr":
        return None, None, None
    session_id = parts[1]
    action = parts[2]
    value = parts[3] if len(parts) > 3 else None
    return session_id, action, value


def _dedupe_search_results(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    unique_items: List[Dict[str, Any]] = []
    seen = set()
    for item in items:
        kind = _get_result_kind(item)
        if kind in {"movie", "tv"}:
            unique_key = f"{kind}:{item.get('tmdb_id')}"
        else:
            unique_key = f"raw:{item.get('hash')}"
        if unique_key in seen:
            continue
        seen.add(unique_key)
        unique_items.append(item)
    return unique_items


async def _fetch_search_results(search_query: str) -> List[Dict[str, Any]]:
    combined: List[Dict[str, Any]] = []
    for page in range(1, SEARCH_MAX_FETCH_PAGES + 1):
        page_results, _ = await db.search_tmdb(
            search_query,
            page=page,
            per_page=SEARCH_FETCH_PAGE_SIZE,
        )
        if not page_results:
            break
        combined.extend(page_results)

    return _dedupe_search_results(combined)


def _get_selected_result(session: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    idx = session.get("selected_result_idx")
    results = session.get("results", [])
    if idx is None or idx < 0 or idx >= len(results):
        return None
    return results[idx]


def _get_series_seasons(series_item: Dict[str, Any]) -> List[Dict[str, Any]]:
    seasons = []
    for season in series_item.get("seasons", []):
        episodes = [
            ep
            for ep in season.get("episodes", [])
            if ep.get("file_info") and len(ep.get("file_info", [])) > 0
        ]
        if not episodes:
            continue
        seasons.append(
            {
                "season_number": season.get("season_number"),
                "episodes": episodes,
            }
        )
    seasons.sort(key=lambda s: s.get("season_number") or 0)
    return seasons


def _get_season_episodes(series_item: Dict[str, Any], season_number: int) -> List[Dict[str, Any]]:
    for season in _get_series_seasons(series_item):
        if season.get("season_number") != season_number:
            continue
        episodes = season.get("episodes", [])
        episodes.sort(key=lambda ep: ep.get("episode_number") or 0)
        return episodes
    return []


def _normalize_quality_choice(file_info: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "chat_id": file_info.get("chat_id"),
        "message_id": file_info.get("message_id"),
        "file_name": file_info.get("file_name") or t("common.unknown_file"),
        "file_size": file_info.get("file_size") or 0,
        "quality": file_info.get("quality") or t("common.unknown"),
        "video_codec": file_info.get("video_codec"),
        "source": file_info.get("source"),
    }


def _get_quality_choices(session: Dict[str, Any]) -> List[Dict[str, Any]]:
    selected = _get_selected_result(session)
    if not selected:
        return []

    kind = _get_result_kind(selected)
    if kind == "movie":
        return [
            _normalize_quality_choice(file_info)
            for file_info in selected.get("file_info", [])
            if file_info.get("chat_id") and file_info.get("message_id")
        ]

    if kind == "raw":
        if selected.get("chat_id") and selected.get("message_id"):
            return [_normalize_quality_choice(selected)]
        return []

    season_number = session.get("selected_season")
    episode_idx = session.get("selected_episode_idx")
    if season_number is None or episode_idx is None:
        return []

    episodes = _get_season_episodes(selected, season_number)
    if episode_idx < 0 or episode_idx >= len(episodes):
        return []

    chosen_episode = episodes[episode_idx]
    return [
        _normalize_quality_choice(file_info)
        for file_info in chosen_episode.get("file_info", [])
        if file_info.get("chat_id") and file_info.get("message_id")
    ]


def _build_page_row(
    session_id: str,
    action: str,
    page: int,
    total_pages: int,
) -> List[Button]:
    nav_row: List[Button] = []
    if total_pages <= 1:
        return nav_row
    if page > 1:
        nav_row.append(Button.inline(t("common.prev"), _callback_data(session_id, action, page - 1)))
    if page < total_pages:
        nav_row.append(Button.inline(t("common.next"), _callback_data(session_id, action, page + 1)))
    return nav_row


def _render_results_view(session: Dict[str, Any], page: int) -> Tuple[str, List[List[Button]]]:
    results = session.get("results", [])
    page_items, total_pages, start_idx = _paginate_items(
        results,
        page,
        SEARCH_RESULTS_PER_PAGE,
    )

    text = t(
        "search.results_view",
        query=session.get("query", ""),
        page=max(1, min(page, total_pages)),
        total_pages=total_pages,
        total_results=len(results),
    )

    buttons: List[List[Button]] = []
    for idx, item in enumerate(page_items):
        global_idx = start_idx + idx
        buttons.append(
            [
                Button.inline(
                    _build_result_label(item),
                    _callback_data(session["session_id"], "ri", global_idx),
                )
            ]
        )

    nav_row = _build_page_row(session["session_id"], "rp", page, total_pages)
    if nav_row:
        buttons.append(nav_row)
    buttons.append([Button.inline(t("common.close"), _callback_data(session["session_id"], "close"))])
    return text, buttons


def _render_seasons_view(session: Dict[str, Any], page: int) -> Tuple[str, List[List[Button]]]:
    selected = _get_selected_result(session)
    if not selected or _get_result_kind(selected) != "tv":
        return t("search.series_not_found"), []

    seasons = _get_series_seasons(selected)
    page_items, total_pages, start_idx = _paginate_items(
        seasons,
        page,
        SEARCH_ITEMS_PER_PAGE,
    )

    title = selected.get("title") or selected.get("name") or t("common.series")
    text = t(
        "search.seasons_view",
        title=_truncate_text(title, 60),
        page=max(1, min(page, total_pages)),
        total_pages=total_pages,
    )

    buttons: List[List[Button]] = []
    for idx, season in enumerate(page_items):
        global_idx = start_idx + idx
        season_number = season.get("season_number")
        episode_count = len(season.get("episodes", []))
        label = t(
            "search.season_label",
            season_number=season_number,
            episode_count=episode_count,
        )
        buttons.append(
            [
                Button.inline(
                    _truncate_text(label),
                    _callback_data(session["session_id"], "si", global_idx),
                )
            ]
        )

    nav_row = _build_page_row(session["session_id"], "sp", page, total_pages)
    if nav_row:
        buttons.append(nav_row)
    buttons.append([Button.inline(t("common.back"), _callback_data(session["session_id"], "back", "r"))])
    buttons.append([Button.inline(t("common.close"), _callback_data(session["session_id"], "close"))])
    return text, buttons


def _render_episodes_view(session: Dict[str, Any], page: int) -> Tuple[str, List[List[Button]]]:
    selected = _get_selected_result(session)
    if not selected or _get_result_kind(selected) != "tv":
        return t("search.series_not_found"), []

    season_number = session.get("selected_season")
    if season_number is None:
        return t("search.season_not_selected"), []

    episodes = _get_season_episodes(selected, season_number)
    page_items, total_pages, start_idx = _paginate_items(
        episodes,
        page,
        SEARCH_ITEMS_PER_PAGE,
    )

    title = selected.get("title") or selected.get("name") or t("common.series")
    text = t(
        "search.episodes_view",
        title=_truncate_text(title, 60),
        season_number=season_number,
        page=max(1, min(page, total_pages)),
        total_pages=total_pages,
    )

    buttons: List[List[Button]] = []
    for idx, episode in enumerate(page_items):
        global_idx = start_idx + idx
        episode_number = episode.get("episode_number")
        episode_number_int = _safe_int(episode_number)
        episode_title = episode.get("title") or t(
            "search.episode_fallback_title", episode_number=episode_number
        )
        files_count = len(episode.get("file_info", []))
        label = t(
            "search.episode_label",
            episode_number=episode_number_int,
            episode_title=episode_title,
            files_count=files_count,
        )
        buttons.append(
            [
                Button.inline(
                    _truncate_text(label),
                    _callback_data(session["session_id"], "ei", global_idx),
                )
            ]
        )

    nav_row = _build_page_row(session["session_id"], "ep", page, total_pages)
    if nav_row:
        buttons.append(nav_row)
    buttons.append([Button.inline(t("common.back"), _callback_data(session["session_id"], "back", "s"))])
    buttons.append([Button.inline(t("common.close"), _callback_data(session["session_id"], "close"))])
    return text, buttons


def _render_quality_view(session: Dict[str, Any], page: int) -> Tuple[str, List[List[Button]]]:
    selected = _get_selected_result(session)
    if not selected:
        return t("search.selected_item_not_found"), []

    kind = _get_result_kind(selected)
    choices = _get_quality_choices(session)
    page_items, total_pages, start_idx = _paginate_items(
        choices,
        page,
        SEARCH_ITEMS_PER_PAGE,
    )

    if kind == "movie":
        title = selected.get("title") or t("common.movie")
        header = f"🎬 **{_truncate_text(title, 60)}**"
        back_target = "r"
    elif kind == "tv":
        title = selected.get("title") or selected.get("name") or t("common.series")
        season_number = session.get("selected_season")
        episode_idx = session.get("selected_episode_idx")
        episodes = _get_season_episodes(selected, season_number)
        episode_number = "?"
        if episode_idx is not None and 0 <= episode_idx < len(episodes):
            episode_number = episodes[episode_idx].get("episode_number", "?")
        season_number_int = _safe_int(season_number)
        episode_number_int = _safe_int(episode_number)
        header = f"📺 **{_truncate_text(title, 60)}** • S{season_number_int:02d}E{episode_number_int:02d}"
        back_target = "e"
    else:
        file_name = selected.get("file_name") or t("common.raw_file")
        header = f"📁 **{_truncate_text(file_name, 60)}**"
        back_target = "r"

    text = t(
        "search.quality_view",
        header=header,
        page=max(1, min(page, total_pages)),
        total_pages=total_pages,
    )

    buttons: List[List[Button]] = []
    for idx, choice in enumerate(page_items):
        global_idx = start_idx + idx
        buttons.append(
            [
                Button.inline(
                    _build_quality_label(choice),
                    _callback_data(session["session_id"], "qi", global_idx),
                )
            ]
        )

    nav_row = _build_page_row(session["session_id"], "qp", page, total_pages)
    if nav_row:
        buttons.append(nav_row)
    buttons.append([Button.inline(t("common.back"), _callback_data(session["session_id"], "back", back_target))])
    buttons.append([Button.inline(t("common.close"), _callback_data(session["session_id"], "close"))])
    return text, buttons


async def _start_search_flow(event, search_query: str) -> None:
    query = (search_query or "").strip()
    if not query:
        await event.reply(t("search.use_query"))
        return

    results = await _fetch_search_results(query)
    if not results:
        await event.reply(t("search.no_results", query=query))
        return

    session_id = search_sessions.create_session(event.sender_id, query, results)
    session = search_sessions.get_session(session_id)
    if not session:
        await event.reply(t("search.failed_session"))
        return

    text, buttons = _render_results_view(session, page=1)
    await event.reply(text, buttons=buttons)


@StreamBot.on(events.NewMessage(pattern=r"^/start(?: |$)", func=lambda e: e.is_private))
async def start(event):
    await event.reply(t("start.welcome", version=__version__))


@StreamBot.on(events.NewMessage(pattern=r"^/index(?: |$)", func=lambda e: e.is_private))
@admin_only
async def index(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]

    selected_log_channel = LOGS_CHANNELS[0]["id"]

    # Power user: direct command with args
    if len(args) >= 4:
        try:
            chat_id, first_id, count_msg = map(int, args[:3])
            client_type = args[3].lower()
            last_id = first_id + count_msg - 1

            if len(args) == 5:
                selected_log_channel = int(args[4])

            if client_type == "bot":
                client = StreamBot
            elif client_type == "user":
                client = await multi_session_manager.get_client()
            else:
                await event.reply(t("index.invalid_client_type"))
                return

            if count_msg <= 0:
                await event.reply(t("index.count_must_be_greater_than_zero"))
                return

            # Continue to indexing logic below (shared)
        except ValueError:
            await event.reply(t("index.invalid_ids"))
            return

    # User friendly: Interactive Wizard
    elif len(args) == 0:
        sender_id = event.sender_id
        mark_conversation_active(sender_id)
        try:
            async with StreamBot.conversation(event.chat_id, timeout=300) as conv:
                # Step 1: Chat ID
                await conv.send_message(
                    t("index.wizard_intro")
                )
                chat_reply = await conv.get_response()
                chat_id = chat_reply.text.strip()
                if chat_id.startswith("@"):
                    pass  # Telethon handles usernames
                elif chat_id.replace("-", "").isdigit():
                    chat_id = int(chat_id)
                else:
                    await conv.send_message(t("index.invalid_chat_id_or_username"))
                    return

                # Step 2: Range (First ID & Count)
                await conv.send_message(
                    t("index.range_prompt")
                )
                range_reply = await conv.get_response()
                try:
                    first_id, count_msg = map(int, range_reply.text.split())
                    if count_msg <= 0:
                        await conv.send_message(t("index.count_must_be_greater_than_zero"))
                        return
                    last_id = first_id + count_msg - 1
                except ValueError:
                    await conv.send_message(t("index.invalid_range_format"))
                    return

                # Step 2.5: Logs Channel
                if len(LOGS_CHANNELS) > 1:
                    log_buttons = []
                    for i, ch_info in enumerate(LOGS_CHANNELS):
                        log_buttons.append(
                            Button.inline(
                                f"{ch_info['name']}",
                                f"idx_log_{i}".encode(),
                            )
                        )

                    # split buttons in rows of 2
                    formatted_buttons = [
                        log_buttons[i : i + 2] for i in range(0, len(log_buttons), 2)
                    ]
                    formatted_buttons.append([Button.inline(t("common.cancel"), b"idx_cancel")])

                    log_prompt = await conv.send_message(
                        t("index.which_logs_channel"),
                        buttons=formatted_buttons,
                    )

                    res_log = await conv.wait_event(
                        events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
                    )
                    action_log = res_log.data.decode()

                    if action_log == "idx_cancel":
                        await res_log.edit(t("index.cancelled"))
                        return

                    if action_log.startswith("idx_log_"):
                        idx = int(action_log.split("_")[-1])
                        selected_log_channel = LOGS_CHANNELS[idx]["id"]
                        await res_log.edit(
                            t(
                                "index.selected_logs_channel",
                                channel_name=LOGS_CHANNELS[idx]["name"],
                            )
                        )

                # Step 3: Client Type Buttons
                prompt = await conv.send_message(
                    t("index.which_client"),
                    buttons=[
                        [
                            Button.inline(f"🤖 {t('common.bot')}", b"idx_bot"),
                            Button.inline(f"👤 {t('common.user')}", b"idx_user"),
                        ],
                        [Button.inline(t("common.cancel"), b"idx_cancel")],
                    ],
                )

                res = await conv.wait_event(
                    events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
                )
                action = res.data.decode()

                if action == "idx_cancel":
                    await res.edit(t("index.cancelled"))
                    return

                client_type = "bot" if action == "idx_bot" else "user"

                if client_type == "bot":
                    client = StreamBot
                else:
                    client = await multi_session_manager.get_client()

                await res.edit(
                    t(
                        "index.selected_client_starting",
                        client_type=t(
                            "common.bot" if client_type == "bot" else "common.user"
                        ),
                    )
                )

        except asyncio.TimeoutError:
            await event.reply(t("index.wizard_timed_out"))
            return
        except Exception as e:
            logging.error(f"Index wizard error: {e}")
            await event.reply(t("index.error", error=e))
            return
        finally:
            mark_conversation_inactive(sender_id)
    else:
        await event.reply(t("index.quick_usage"))
        return

    # Re-check client availability if selected via wizard/power user
    if not client:
        await event.reply(t("index.selected_client_unavailable"))
        return

    # Shared Indexing Logic
    total_range = last_id - first_id + 1
    try:
        start_message = t(
            "index.progress_start",
            chat_id=chat_id,
            first_id=first_id,
            last_id=last_id,
            total_range=total_range,
            selected_log_channel=selected_log_channel,
        )
        wait_msg = await event.reply(start_message)

        # Progress callback updates the message periodically
        async def on_progress(stats, current_id):
            processed = current_id - first_id
            pct = min(int(processed / total_range * 100), 100)
            bar_filled = pct // 5
            bar = "█" * bar_filled + "░" * (20 - bar_filled)
            try:
                await wait_msg.edit(
                    t(
                        "index.progress_update",
                        chat_id=chat_id,
                        bar=bar,
                        pct=pct,
                        indexed=stats.get("indexed", 0),
                        skipped=(
                            stats.get("skipped_no_media", 0)
                            + stats.get("skipped_size", 0)
                            + stats.get("skipped_keyword", 0)
                            + stats.get("skipped_ext", 0)
                        ),
                        errors=stats.get("errors", 0),
                        current_id=current_id,
                        last_id=last_id,
                    )
                )
            except Exception:
                pass  # Ignore edit failures (e.g. FloodWait)

        stats = await index_channel(
            client,
            chat_id,
            first_id,
            last_id,
            progress_callback=on_progress,
            logs_channel=selected_log_channel,
        )

        await wait_msg.delete()

        total_skipped = (
            stats.get("skipped_size", 0)
            + stats.get("skipped_keyword", 0)
            + stats.get("skipped_ext", 0)
        )
        summary = t(
            "index.complete_summary",
            indexed=stats.get("indexed", 0),
            skipped_size=stats.get("skipped_size", 0),
            skipped_keyword=stats.get("skipped_keyword", 0),
            skipped_ext=stats.get("skipped_ext", 0),
            skipped_no_media=stats.get("skipped_no_media", 0),
            errors=stats.get("errors", 0),
            total_skipped=total_skipped,
        )
        await event.reply(summary)

    except FloodWaitError as e:
        logging.warning(f"FloodWait during index: sleeping for {e.seconds}s")
        await sleep(e.seconds)
        await event.reply(t("index.floodwait", seconds=e.seconds))


@StreamBot.on(
    events.NewMessage(pattern=r"^/search(?: |$)", func=lambda e: e.is_private)
)
async def search(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if not args:
        await event.reply(t("search.use_query"))
        return
    await _start_search_flow(event, " ".join(args))


@StreamBot.on(
    events.NewMessage(
        func=lambda e: (
            e.is_private
            and bool(getattr(e, "raw_text", None))
            and not e.raw_text.startswith("/")
            and not e.media
        )
    )
)
async def search_text_message(event):
    if is_conversation_active(event.sender_id):
        return
    await _start_search_flow(event, event.raw_text)


@StreamBot.on(events.CallbackQuery(pattern=b"sr:"))
async def search_callback(event):
    session_id, action, value = _parse_callback_data(event.data)
    if not session_id or not action:
        await event.answer(t("common.invalid_action"), alert=True)
        return

    session = search_sessions.touch(session_id)
    if not session:
        await event.answer(t("search.this_search_expired_retry"), alert=True)
        return

    if session.get("sender_id") != event.sender_id:
        await event.answer(t("search.these_buttons_not_for_you"), alert=True)
        return

    try:
        if action == "close":
            search_sessions.delete_session(session_id)
            await event.edit(t("search.closed"), buttons=None)
            await event.answer()
            return

        if action == "rp":
            page = _parse_callback_int(value)
            if page is None:
                await event.answer(t("search.invalid_page"), alert=True)
                return
            session = search_sessions.update_session(session_id, results_page=page)
            if not session:
                await event.answer(t("search.this_search_expired"), alert=True)
                return
            text, buttons = _render_results_view(session, page)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "ri":
            idx = _parse_callback_int(value)
            if idx is None:
                await event.answer(t("search.invalid_selection"), alert=True)
                return
            results = session.get("results", [])
            if idx < 0 or idx >= len(results):
                await event.answer(t("search.invalid_selection"), alert=True)
                return
            selected_item = results[idx]
            kind = _get_result_kind(selected_item)
            session = search_sessions.update_session(
                session_id,
                selected_result_idx=idx,
                selected_season=None,
                selected_episode_idx=None,
                seasons_page=1,
                episodes_page=1,
                quality_page=1,
            )
            if not session:
                await event.answer(t("search.this_search_expired"), alert=True)
                return

            if kind == "tv":
                text, buttons = _render_seasons_view(session, page=1)
            else:
                text, buttons = _render_quality_view(session, page=1)

            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "sp":
            page = _parse_callback_int(value)
            if page is None:
                await event.answer(t("search.invalid_page"), alert=True)
                return
            session = search_sessions.update_session(session_id, seasons_page=page)
            if not session:
                await event.answer(t("search.this_search_expired"), alert=True)
                return
            text, buttons = _render_seasons_view(session, page)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "si":
            idx = _parse_callback_int(value)
            if idx is None:
                await event.answer(t("search.invalid_season"), alert=True)
                return
            selected = _get_selected_result(session)
            if not selected or _get_result_kind(selected) != "tv":
                await event.answer(t("search.invalid_series_selection"), alert=True)
                return
            seasons = _get_series_seasons(selected)
            if idx < 0 or idx >= len(seasons):
                await event.answer(t("search.invalid_season"), alert=True)
                return

            season_number = seasons[idx].get("season_number")
            session = search_sessions.update_session(
                session_id,
                selected_season=season_number,
                selected_episode_idx=None,
                episodes_page=1,
                quality_page=1,
            )
            if not session:
                await event.answer(t("search.this_search_expired"), alert=True)
                return
            text, buttons = _render_episodes_view(session, page=1)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "ep":
            page = _parse_callback_int(value)
            if page is None:
                await event.answer(t("search.invalid_page"), alert=True)
                return
            session = search_sessions.update_session(session_id, episodes_page=page)
            if not session:
                await event.answer(t("search.this_search_expired"), alert=True)
                return
            text, buttons = _render_episodes_view(session, page)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "ei":
            idx = _parse_callback_int(value)
            if idx is None:
                await event.answer(t("search.invalid_episode"), alert=True)
                return
            selected = _get_selected_result(session)
            if not selected or _get_result_kind(selected) != "tv":
                await event.answer(t("search.invalid_episode_selection"), alert=True)
                return
            season_number = session.get("selected_season")
            episodes = _get_season_episodes(selected, season_number)
            if idx < 0 or idx >= len(episodes):
                await event.answer(t("search.invalid_episode"), alert=True)
                return

            session = search_sessions.update_session(
                session_id,
                selected_episode_idx=idx,
                quality_page=1,
            )
            if not session:
                await event.answer(t("search.this_search_expired"), alert=True)
                return
            text, buttons = _render_quality_view(session, page=1)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "qp":
            page = _parse_callback_int(value)
            if page is None:
                await event.answer(t("search.invalid_page"), alert=True)
                return
            session = search_sessions.update_session(session_id, quality_page=page)
            if not session:
                await event.answer(t("search.this_search_expired"), alert=True)
                return
            text, buttons = _render_quality_view(session, page)
            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        if action == "qi":
            idx = _parse_callback_int(value)
            if idx is None:
                await event.answer(t("search.invalid_file_selection"), alert=True)
                return
            choices = _get_quality_choices(session)
            if idx < 0 or idx >= len(choices):
                await event.answer(t("search.invalid_file_selection"), alert=True)
                return

            selected_file = choices[idx]
            chat_id = _safe_int(selected_file.get("chat_id"), 0)
            message_id = _safe_int(selected_file.get("message_id"), 0)
            if not chat_id or not message_id:
                await event.answer(t("search.file_source_not_found"), alert=True)
                return

            logging.warning(
                "Starting file send from search callback (sender_id=%s, chat_id=%s, message_id=%s)",
                event.sender_id,
                chat_id,
                message_id,
            )
            await event.answer(t("search.preparing_file"), alert=False)
            logging.warning("Fetching source message with bot client")
            src_message, source_entity = await _fetch_source_message(
                event.client,
                chat_id,
                message_id,
            )

            if not src_message or source_entity is None:
                await event.answer(
                    t("search.source_channel_inaccessible"),
                    alert=True,
                )
                return

            target_entity = await event.get_input_chat()
            forwarded = await event.client.forward_messages(
                entity=target_entity,
                messages=[message_id],
                from_peer=source_entity,
            )
            if not forwarded:
                await event.answer(
                    t("search.telegram_did_not_forward"),
                    alert=True,
                )
                return

            logging.info(
                "Forwarded file via search callback (sender_id=%s, chat_id=%s, message_id=%s)",
                event.sender_id,
                chat_id,
                message_id,
            )
            await event.answer(t("search.file_sent"), alert=False)
            return

        if action == "back":
            target = value or "r"
            if target == "r":
                page = _safe_int(session.get("results_page", 1), 1)
                text, buttons = _render_results_view(session, page)
            elif target == "s":
                page = _safe_int(session.get("seasons_page", 1), 1)
                text, buttons = _render_seasons_view(session, page)
            elif target == "e":
                page = _safe_int(session.get("episodes_page", 1), 1)
                text, buttons = _render_episodes_view(session, page)
            else:
                await event.answer(t("search.invalid_navigation"), alert=True)
                return

            await event.edit(text, buttons=buttons)
            await event.answer()
            return

        await event.answer(t("search.unknown_action"), alert=True)

    except FloodWaitError as e:
        await event.answer(t("search.floodwait", seconds=e.seconds), alert=True)
    except Exception as e:
        logging.exception(
            "Search callback error: %s (sender_id=%s, callback=%s)",
            e,
            event.sender_id,
            event.data,
        )
        await event.answer(t("common.error_processing_action"), alert=True)


@StreamBot.on(events.NewMessage(pattern=r"^/del(?: |$)", func=lambda e: e.is_private))
@admin_only
async def delete(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 1:
        try:
            tmdb_id = int(args[0])
        except ValueError:
            await event.reply(t("delete.invalid_tmdb_id"))
            return
    else:
        await event.reply(t("delete.use_del"))
        return

    result = await db.del_tmdb(tmdb_id=tmdb_id)

    if result.deleted_count > 0:
        await event.reply(t("delete.entry_deleted"))
    else:
        await event.reply(t("delete.no_document"))


@StreamBot.on(
    events.NewMessage(pattern=r"^/del_channel(?: |$)", func=lambda e: e.is_private)
)
@admin_only
async def delete_channel(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 1:
        try:
            chat_id = int(args[0])
        except ValueError:
            await event.reply(t("delete_channel.invalid_chat_id"))
            return
    else:
        await event.reply(t("delete_channel.use_del_channel"))
        return

    # Add confirmation
    await event.reply(
        t("delete_channel.confirm", chat_id=chat_id),
        buttons=[
            [
                Button.inline(
                    t("common.yes_delete"),
                    f"delch_confirm:{chat_id}".encode(),
                ),
            ],
            [Button.inline(t("common.cancel"), b"delch_cancel")],
        ],
    )


@StreamBot.on(events.CallbackQuery(pattern=b"delch_"))
async def delete_channel_callback(event):
    # Auth check
    from jackgram.bot.bot import ADMIN_IDS

    if ADMIN_IDS and event.sender_id not in ADMIN_IDS:
        await event.answer(t("common.not_authorized"), alert=True)
        return

    data = event.data.decode()
    if data == "delch_cancel":
        await event.edit(t("delete_channel.deletion_cancelled"))
        return

    if data.startswith("delch_confirm:"):
        chat_id = int(data.split(":", 1)[1])
        await event.edit(t("delete_channel.deleting", chat_id=chat_id))

        stats = await db.del_by_chat_id(chat_id)

        summary = t(
            "delete_channel.summary",
            raw_deleted=stats["raw_deleted"],
            movies_modified=stats["movies_modified"],
            tv_modified=stats["tv_modified"],
        )
        await event.edit(summary)


@StreamBot.on(events.NewMessage(pattern=r"^/count(?: |$)", func=lambda e: e.is_private))
@admin_only
async def count(event):
    movies = await db.count_movies()
    tv = await db.count_tv()
    files = await db.count_media_files()
    total = movies + tv + files

    total_storage = await db.get_total_storage()
    storage_str = get_readable_size(total_storage)

    await event.reply(
        t(
            "count.summary",
            movies=movies,
            tv=tv,
            files=files,
            total=total,
            storage=storage_str,
        )
    )


@StreamBot.on(
    events.NewMessage(pattern=r"^/save_db(?: |$)", func=lambda e: e.is_private)
)
@admin_only
async def save_database(event):
    status_msg = await event.reply(t("backup.starting"))
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except PermissionError:
        await status_msg.edit(t("backup.permission_denied", backup_dir=BACKUP_DIR))
        return

    backup_data = {}
    collections = await db.list_collections()
    total_collections = len(collections)

    for i, collection_name in enumerate(collections):
        await status_msg.edit(
            t(
                "backup.progress",
                collection_name=collection_name,
                current=i + 1,
                total=total_collections,
            )
        )
        collection = db.db[collection_name]
        cursor = collection.find({})
        data = await cursor.to_list(length=None)

        serialized = []
        for doc in data:
            doc_copy = doc.copy()
            doc_copy["_id"] = str(doc_copy["_id"])
            serialized.append(doc_copy)

        backup_data[collection_name] = serialized

    await status_msg.edit(t("backup.writing_file"))
    backup_file = os.path.join(BACKUP_DIR, "database_backup.json")
    try:
        with open(backup_file, "w") as file:
            json.dump(backup_data, file, indent=4)
    except OSError as e:
        await status_msg.edit(t("backup.write_failed", error=e))
        return

    import time

    await status_msg.edit(t("backup.starting_upload"))

    last_edit = time.time()

    async def upload_progress(current, total):
        nonlocal last_edit
        now = time.time()
        if now - last_edit >= 2.0 or current == total:
            pct = min(int(current / total * 100), 100) if total else 0
            bar_filled = pct // 5
            bar = "█" * bar_filled + "░" * (20 - bar_filled)

            curr_str = get_readable_size(current)
            total_str = get_readable_size(total)

            try:
                await status_msg.edit(
                    t(
                        "backup.upload_progress",
                        bar=bar,
                        pct=pct,
                        current_size=curr_str,
                        total_size=total_str,
                    )
                )
                last_edit = now
            except Exception:
                pass

    try:
        await event.client.send_file(
            event.chat_id,
            file=backup_file,
            caption=t("backup.completed_caption"),
            progress_callback=upload_progress,
        )
    finally:
        await status_msg.delete()


@StreamBot.on(
    events.NewMessage(pattern=r"^/load_db(?: |$)", func=lambda e: e.is_private)
)
@admin_only
async def load_database(event):
    if not event.is_reply:
        await event.reply(t("restore.reply_with_json"))
        return

    reply_msg = await event.get_reply_message()
    if not reply_msg.document:
        await event.reply(t("restore.reply_with_json"))
        return

    file_path = await event.client.download_media(reply_msg)
    if not file_path or not file_path.endswith(".json"):
        await event.reply(t("restore.file_must_be_json"))
        return

    with open(file_path, "r") as file:
        try:
            backup_data = json.load(file)
        except json.JSONDecodeError:
            await event.reply(t("restore.invalid_json_file"))
            return

    if not isinstance(backup_data, dict):
        await event.reply(t("restore.invalid_json_structure"))
        return

    for collection_name, documents in backup_data.items():
        if not isinstance(documents, list):
            await event.reply(
                t("restore.invalid_collection_data", collection_name=collection_name)
            )
            continue

        collection = db.db[collection_name]
        for document in documents:
            if "_id" in document:
                try:
                    document["_id"] = ObjectId(document["_id"])
                except Exception:
                    # Invalid ObjectId — insert as new document instead
                    document.pop("_id")
                    await collection.insert_one(document)
                    continue
                await collection.update_one(
                    {"_id": document["_id"]},
                    {"$set": document},
                    upsert=True,
                )

    await event.reply(t("restore.success"))


@StreamBot.on(
    events.NewMessage(pattern=r"^/del_db(?: |$)", func=lambda e: e.is_private)
)
@admin_only
async def delete_database(event):
    if not event.message.text:
        return
    args = event.message.text.split()[1:]
    if len(args) == 1:
        database_name = args[0]
    else:
        await event.reply(t("delete_db.use_del_db"))
        return

    await event.reply(
        t("delete_db.confirm", database_name=database_name),
        buttons=[
            [
                Button.inline(
                    t("common.yes_delete_it"),
                    f"deldb_confirm:{database_name}".encode(),
                ),
            ],
            [Button.inline(t("common.cancel"), b"deldb_cancel")],
        ],
    )


@StreamBot.on(events.CallbackQuery(pattern=b"deldb_"))
async def delete_database_callback(event):
    # Auth check — reuse ADMIN_IDS
    from jackgram.bot.bot import ADMIN_IDS

    if ADMIN_IDS and event.sender_id not in ADMIN_IDS:
        await event.answer(t("common.not_authorized"), alert=True)
        return

    data = event.data.decode()
    if data == "deldb_cancel":
        await event.edit(t("delete_db.cancelled"))
        return

    if data.startswith("deldb_confirm:"):
        database_name = data.split(":", 1)[1]
        await db.client.drop_database(database_name)
        await event.edit(t("delete_db.deleted", database_name=database_name))


@StreamBot.on(events.NewMessage(pattern=r"^/token(?: |$)", func=lambda e: e.is_private))
@admin_only
async def generate_token(event):
    sender = await event.get_sender()
    payload = {
        "user_id": sender.id,
        "exp": datetime.now() + timedelta(days=7),
    }
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    await event.reply(token)


@StreamBot.on(events.NewMessage(pattern=r"^/log(?: |$)", func=lambda e: e.is_private))
@admin_only
async def send_log_file(event):
    log_file_path = os.path.join(os.getcwd(), "bot.log")
    if os.path.exists(log_file_path):
        await event.client.send_file(
            event.chat_id,
            file=log_file_path,
            caption=t("log.caption"),
        )
    else:
        await event.reply(t("log.not_found"))
