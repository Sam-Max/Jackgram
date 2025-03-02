from fastapi.responses import JSONResponse
from jackgram.bot.bot import SECRET_KEY
from jackgram.server.routes import routes
from jackgram.server.api.bot_api import stream_routes
from fastapi import FastAPI, Request
from starlette.middleware.base import BaseHTTPMiddleware
import jwt


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("Authorization")
        if not token:
            return JSONResponse(status_code=401, content="Token is missing")

        try:
            token = token.replace("Bearer ", "")
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.state.user = decoded  # Attach user info to the request
        except jwt.ExpiredSignatureError:
            return JSONResponse(status_code=401, content="Token has expired")
        except jwt.InvalidTokenError:
            return JSONResponse(status_code=401, content="Invalid token")

        return await call_next(request)  # Continue processing the request


app = FastAPI()

app.include_router(routes)
app.include_router(stream_routes)
# app.add_middleware(AuthMiddleware)
