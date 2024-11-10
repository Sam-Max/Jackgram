import sys
import asyncio
import logging
import traceback
import logging.handlers as handlers
from streamtg.server import web_server
from streamtg.bot import BIND_ADDRESS, PORT, StreamBot
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

bot_logger = logging.getLogger("streamtg").setLevel(logging.DEBUG)

server = web.AppRunner(web_server())

loop = asyncio.get_event_loop()


async def start_services():
    print("Initializing Client...")
    await StreamBot.start()
    
    print("Initializing Web Server...")
    await server.setup()
    await web.TCPSite(server, BIND_ADDRESS, PORT).start()
    
    print("Service Started")
    await idle()


async def cleanup():
    await server.cleanup()
    await StreamBot.stop()


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
