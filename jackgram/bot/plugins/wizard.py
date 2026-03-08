import asyncio
import logging
import re
import PTN

from telethon import events, Button
from telethon.tl.types import Message

from jackgram.bot.bot import StreamBot, LOGS_CHANNELS
from jackgram.bot.conversation_state import (
    mark_conversation_active,
    mark_conversation_inactive,
)
from jackgram.bot.i18n import t
from jackgram.bot.utils import send_message
from jackgram.utils.utils import (
    extract_file_info,
    format_filename,
    get_file_title,
    process_movie,
    process_series,
)
from jackgram.utils.tmdb import get_tmdb

tmdb = get_tmdb()


@StreamBot.on(
    events.NewMessage(
        func=lambda e: e.is_private and (e.document or getattr(e, "video", None))
    )
)
async def wizard_start(event: Message):
    # Ignore commands disguised as captions
    if event.text and event.text.startswith("/"):
        return

    chat_id = event.chat_id
    sender_id = event.sender_id

    # Fast-fail for multipart/split files
    filename = getattr(event.file, "name", "") or getattr(event.message, "message", "")
    if filename:
        multipart_pattern = re.compile(
            r"(?:part|cd|disc|disk)[s._-]*\d+(?=\.\w+$)", re.IGNORECASE
        )
        if multipart_pattern.search(filename):
            await event.reply(t("wizard.multipart_rejected"))
            return

    # Auto-detect IMDb ID from caption
    caption_text = event.text or ""
    imdb_match = re.search(r"tt\d{7,8}", caption_text)
    detected_imdb_id = imdb_match.group(0) if imdb_match else None

    mark_conversation_active(sender_id)
    try:
        async with StreamBot.conversation(chat_id, timeout=120) as conv:
            # Step 1: Ask for media type
            if detected_imdb_id:
                prompt_text = t("wizard.prompt_with_imdb", imdb_id=detected_imdb_id)
            else:
                prompt_text = t("wizard.prompt_without_imdb")

            prompt_msg = await conv.send_message(
                prompt_text,
                buttons=[
                    [
                        Button.inline(f"🎬 {t('common.movie')}", b"movie"),
                        Button.inline(f"📺 {t('common.tv_show')}", b"series"),
                    ],
                    [Button.inline(t("common.cancel"), b"cancel")],
                ],
            )

            res = await conv.wait_event(
                events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
            )
            action = res.data.decode()

            if action == "cancel":
                await res.edit(t("wizard.cancelled"))
                return

            media_type = action
            type_str = t("common.movie") if media_type == "movie" else t("common.tv_show")
            await res.edit(t("wizard.selected_type", type_name=type_str))

            # Step 2: Source TMDb ID (Auto or Manual)
            tmdb_id = None
            if detected_imdb_id:
                wait_msg = await conv.send_message(
                    t("wizard.fetching_tmdb", imdb_id=detected_imdb_id)
                )
                tmdb_id = await asyncio.to_thread(
                    tmdb.find_media_id, detected_imdb_id, media_type
                )
                await wait_msg.delete()
            else:
                await conv.send_message(
                    t("wizard.ask_tmdb_or_title", type_name=type_str)
                )
                reply = await conv.get_response()
                query = reply.text.strip()

                if query.isdigit():
                    tmdb_id = int(query)
                else:
                    wait_msg = await conv.send_message(t("wizard.searching_tmdb"))
                    tmdb_id = await asyncio.to_thread(
                        tmdb.find_media_id, query, media_type
                    )
                    await wait_msg.delete()

            if not tmdb_id:
                await conv.send_message(t("wizard.tmdb_match_not_found"))
                return

            # Fetch details
            details = await asyncio.to_thread(tmdb.get_details, tmdb_id, media_type)
            if not details or "id" not in details:
                await conv.send_message(t("wizard.tmdb_details_failed"))
                return

            title = details.get("title") or details.get("name")
            year = (
                details.get("release_date")
                or details.get("first_air_date")
                or t("common.unknown_year")
            )
            if year and "-" in year:
                year = year.split("-")[0]

            # Step 3: Handle TV Show specific data (Season/Episode)
            season, episode = None, None
            if media_type == "series":
                # Try to parse from filename first
                filename = format_filename(get_file_title(event))
                ptn_data = PTN.parse(filename)
                season = ptn_data.get("season")
                episode = ptn_data.get("episode")

                if season is None or episode is None:
                    await conv.send_message(t("wizard.ask_season_episode"))
                    se_reply = await conv.get_response()
                    se_text = se_reply.text.strip().upper()

                    match = re.match(r"S(\d+)E(\d+)", se_text)
                    if match:
                        season = int(match.group(1))
                        episode = int(match.group(2))
                    else:
                        await conv.send_message(t("wizard.invalid_format_cancelled"))
                        return

            # Step 3.5: Logs Channel
            selected_log_channel = LOGS_CHANNELS[0]["id"]
            if len(LOGS_CHANNELS) > 1:
                log_buttons = []
                for i, ch_info in enumerate(LOGS_CHANNELS):
                    log_buttons.append(
                        Button.inline(
                            f"{ch_info['name']}",
                            f"wiz_log_{i}".encode(),
                        )
                    )

                formatted_buttons = [
                    log_buttons[i : i + 2] for i in range(0, len(log_buttons), 2)
                ]
                formatted_buttons.append([Button.inline(t("common.cancel"), b"cancel")])

                log_prompt = await conv.send_message(
                    t("wizard.which_logs_channel"),
                    buttons=formatted_buttons,
                )

                res_log = await conv.wait_event(
                    events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
                )
                action_log = res_log.data.decode()

                if action_log == "cancel":
                    await res_log.edit(t("wizard.cancelled"))
                    return

                if action_log.startswith("wiz_log_"):
                    idx = int(action_log.split("_")[-1])
                    selected_log_channel = LOGS_CHANNELS[idx]["id"]
                    await res_log.edit(
                        t(
                            "wizard.selected_logs_channel",
                            channel_name=LOGS_CHANNELS[idx]["name"],
                        )
                    )

            # Step 4: Confirmation
            confirm_text = t(
                "wizard.confirm_indexing",
                title=title,
                year=year,
                type_name=type_str,
            )
            if media_type == "series":
                confirm_text += t(
                    "wizard.confirm_indexing_series_extra",
                    season=season,
                    episode=episode,
                )

            confirm_msg = await conv.send_message(
                confirm_text,
                buttons=[
                    [Button.inline(t("common.confirm_and_index"), b"confirm")],
                    [Button.inline(t("common.cancel"), b"cancel")],
                ],
            )

            res_confirm = await conv.wait_event(
                events.CallbackQuery(func=lambda e: e.sender_id == sender_id)
            )
            if res_confirm.data.decode() != "confirm":
                await res_confirm.edit(t("wizard.cancelled"))
                return

            await res_confirm.edit(t("wizard.indexing"))

            # Step 5: Process and Index
            # Forward the message to the logs channel to safely store it
            log_msg = await send_message(StreamBot, event, selected_log_channel)

            # Extract file info from the new log message
            final_filename = format_filename(get_file_title(log_msg))
            file_info = await extract_file_info(log_msg, final_filename)

            # Save to Database
            if media_type == "movie":
                await process_movie(tmdb_id, details, file_info)
            else:
                ep_details = await asyncio.to_thread(
                    tmdb.get_episode_details, tmdb_id, episode, season
                )
                data = {"season": season, "episode": episode}
                await process_series(tmdb_id, data, details, ep_details, file_info)

            await conv.send_message(t("wizard.success"))

    except asyncio.TimeoutError:
        await event.reply(t("wizard.timed_out_restart"))
    except Exception as e:
        logging.error(f"Wizard error: {e}")
        await event.reply(t("wizard.unexpected_error"))
    finally:
        mark_conversation_inactive(sender_id)
