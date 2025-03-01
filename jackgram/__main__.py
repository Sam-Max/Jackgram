import sys
import asyncio
import logging
import traceback
import logging.handlers as handlers

from jackgram.bot import BIND_ADDRESS, PORT, SESSION_STRING, StreamBot, StreamUser
from jackgram import app

from pyrogram import idle


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
    logging.info("Initializing Web Server...")
    web_task = asyncio.create_task(
        app.run_task(host=BIND_ADDRESS, port=PORT, debug=False)
    )

    logging.info("Initializing Bot Client...")
    await StreamBot.start()

    if len(SESSION_STRING) != 0:
        logging.info(f"Initializing User Client...")
        await StreamUser.start()

    logging.info("Services Started")

    await idle()

    logging.info("Cleaning up...")
    await cleanup(web_task)


async def cleanup(web_task):
    await StreamBot.stop()
    await StreamUser.stop()
    web_task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(start_services())
    except KeyboardInterrupt:
        logging.info("Shutting down due to KeyboardInterrupt")
    except Exception as err:
        logging.error(traceback.format_exc())
