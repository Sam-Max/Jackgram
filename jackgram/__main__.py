import sys
import asyncio
import logging
import traceback
import logging.handlers as handlers

from jackgram.bot.bot import (
    BIND_ADDRESS,
    PORT,
    BOT_TOKEN,
    StreamBot,
)
from jackgram.bot.i18n import t
from jackgram import app, __version__

import uvicorn


logging.basicConfig(
    level=logging.INFO,
    datefmt="%d/%m/%Y %H:%M:%S",
    format="[%(asctime)s] {%(pathname)s:%(lineno)d} %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(stream=sys.stdout),
        handlers.RotatingFileHandler(
            "bot.log",
            mode="a",
            maxBytes=104857600,
            backupCount=2,
            encoding="utf-8",
        ),
    ],
)

bot_logger = logging.getLogger("jackgram").setLevel(logging.DEBUG)


async def start_services():
    logging.info(f"Initializing Jackgram v{__version__}...")
    logging.info("Initializing Web Server...")
    config = uvicorn.Config(app, host=BIND_ADDRESS, port=PORT, log_level="info")
    server = uvicorn.Server(config)
    web_task = asyncio.create_task(server.serve())

    import jackgram.bot.plugins.start
    import jackgram.bot.plugins.stream
    import jackgram.bot.plugins.wizard
    from jackgram.utils.telegram_stream import multi_session_manager
    from jackgram.bot.utils import process_index_queue

    logging.info("Initializing Bot Client...")

    await StreamBot.start(bot_token=BOT_TOKEN)

    # Set the bot's commands
    from telethon.tl.functions.bots import SetBotCommandsRequest
    from telethon.tl.types import BotCommand, BotCommandScopeDefault

    try:
        commands = [
            BotCommand(command="start", description=t("command.start")),
            BotCommand(command="index", description=t("command.index")),
            BotCommand(command="search", description=t("command.search")),
            BotCommand(command="count", description=t("command.count")),
            BotCommand(command="save_db", description=t("command.save_db")),
            BotCommand(command="load_db", description=t("command.load_db")),
            BotCommand(command="del", description=t("command.del")),
            BotCommand(command="del_channel", description=t("command.del_channel")),
            BotCommand(command="del_db", description=t("command.del_db")),
            BotCommand(command="token", description=t("command.token")),
            BotCommand(command="log", description=t("command.log")),
        ]

        await StreamBot(
            SetBotCommandsRequest(
                scope=BotCommandScopeDefault(), lang_code="", commands=commands
            )
        )
        logging.info("Bot commands set successfully.")
    except Exception as e:
        logging.error(f"Failed to set bot commands: {e}")

    logging.info("Starting Async Indexing Queue Worker...")
    asyncio.create_task(process_index_queue())

    logging.info(f"Initializing User Clients...")
    await multi_session_manager.initialize_all()

    logging.info("Services Started")

    await StreamBot.run_until_disconnected()

    logging.info("Cleaning up...")
    await cleanup(web_task)


async def cleanup(web_task):
    from jackgram.utils.telegram_stream import multi_session_manager

    await StreamBot.disconnect()
    await multi_session_manager.close_all()
    web_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except KeyboardInterrupt:
        logging.info("Shutting down due to KeyboardInterrupt")
    except Exception as err:
        logging.error(traceback.format_exc())
