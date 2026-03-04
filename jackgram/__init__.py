__version__ = "1.1.0"

import os
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from jackgram.bot.bot import SECRET_KEY
from jackgram.server.routes import routes
from jackgram.server.api.bot_api import stream_routes, search_routes
from jackgram.server.api.admin_api import admin_routes
from jackgram.server.api.stremio_api import stremio_routes
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import jwt


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if (
            request.url.path == "/admin/login"
            or not request.url.path.startswith("/admin/")
            or request.url.path.startswith("/stremio/")
        ):
            return await call_next(request)

        token = request.headers.get("Authorization")
        if not token:
            return JSONResponse(status_code=401, content={"detail": "Token is missing"})

        try:
            token = token.replace("Bearer ", "")
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.state.user = decoded  # Attach user info to the request
        except jwt.ExpiredSignatureError:
            return JSONResponse(
                status_code=401, content={"detail": "Token has expired"}
            )
        except jwt.InvalidTokenError:
            return JSONResponse(status_code=401, content={"detail": "Invalid token"})

        return await call_next(request)  # Continue processing the request


app = FastAPI(title="Jackgram", description="Jackgram API + Admin")

app.include_router(routes)
app.include_router(stream_routes)
app.include_router(search_routes)
app.include_router(admin_routes)
app.include_router(stremio_routes)
app.add_middleware(AuthMiddleware)

# Serve admin web dashboard
_web_dir = os.path.join(os.path.dirname(__file__), "web")
if os.path.isdir(_web_dir):
    app.mount("/web", StaticFiles(directory=_web_dir, html=True), name="web")


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/web/index.html")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    return RedirectResponse(url="/web/favicon.svg")
