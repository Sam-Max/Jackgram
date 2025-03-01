from jackgram.bot import SECRET_KEY
from jackgram.server.routes import routes
from jackgram.server.api.bot_api import stream_routes

from quart import Quart, jsonify, request, g
import jwt


app = Quart(__name__)

app.register_blueprint(routes)
app.register_blueprint(stream_routes)


# @app.before_request
async def auth_middleware():
    token = request.headers.get("Authorization")
    if not token:
        return jsonify({"error": "Token is missing"}), 401

    try:
        token = token.replace("Bearer ", "")
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        g.user = decoded  # Attach user info to the request
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Token has expired"}), 401
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid token"}), 401




