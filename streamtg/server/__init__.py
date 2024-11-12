from streamtg.server.routes import routes
from streamtg.server.api.streamtg_api import routes as api
from aiohttp import web

def web_server():
    web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    web_app.add_routes(api)
    return web_app
