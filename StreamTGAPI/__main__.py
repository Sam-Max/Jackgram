import sys
import asyncio
import logging
import traceback
import logging.handlers as handlers
from StreamTGAPI.server import web_server
from StreamTGAPI.bot import BIND_ADDRESS, PORT, stream_bot
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

server = web.AppRunner(web_server())

loop = asyncio.get_event_loop()


async def start_services():
    print("Initializing Client...")
    await stream_bot.start()
    
    print("Initializing Web Server...")
    await server.setup()
    await web.TCPSite(server, BIND_ADDRESS, PORT).start()
    
    print("Service Started")
    await idle()


async def cleanup():
    await server.cleanup()
    await stream_bot.stop()


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
