import sys
import asyncio
import logging
import traceback
import logging.handlers as handlers
from jackgram.server import web_server
from jackgram.bot import BIND_ADDRESS, PORT, SESSION_STRING, StreamBot, StreamUser
from aiohttp import web
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

server = web.AppRunner(web_server())

loop = asyncio.get_event_loop()


async def start_services():
    logging.info("Initializing Bot Client...")
    await StreamBot.start()

    if len(SESSION_STRING) != 0:
        logging.info(f"Initializing User Client...")
        await StreamUser.start()

    logging.info("Initializing Web Server...")
    await server.setup()
    await web.TCPSite(server, BIND_ADDRESS, PORT).start()

    logging.info("Services Started")
    await idle()


async def cleanup():
    await server.cleanup()
    await StreamBot.stop()
    await StreamUser.stop()


if __name__ == "__main__":
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        pass
    except Exception as err:
        logging.error(traceback.format_exc())
    finally:
        loop.run_until_complete(cleanup())
        loop.stop()
