from jackgram.bot import SECRET_KEY
from jackgram.server.routes import routes
from jackgram.server.api.bot_api import routes as api
from aiohttp import web
import jwt


async def auth_middleware(app, handler):
    async def middleware_handler(request):
        token = request.headers.get("Authorization")
        if not token:
            raise web.HTTPUnauthorized(reason="Token is missing")

        try:
            token = token.replace("Bearer ", "")
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user = decoded  # Add decoded user info to request
        except jwt.ExpiredSignatureError:
            raise web.HTTPUnauthorized(reason="Token has expired")
        except jwt.InvalidTokenError:
            raise web.HTTPUnauthorized(reason="Invalid token")

        return await handler(request)

    return middleware_handler


def web_server():
    web_app = web.Application(client_max_size=30000000, middlewares=[auth_middleware])
    #web_app = web.Application(client_max_size=30000000)
    web_app.add_routes(routes)
    web_app.add_routes(api)
    return web_app
