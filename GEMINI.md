# Jackgram Development Guide

## Project Overview
Jackgram is a dual-purpose application acting as both a Telegram Bot and a REST API Server. It indexes media files from Telegram channels and serves them via HTTP, allowing for streaming and downloading.

**Key Technologies:**
-   **Language:** Python 3.11+
-   **Web Framework:** FastAPI (with Uvicorn)
-   **Telegram Client:** Telethon (with cryptg for speed and FastTelethon for parallel chunk downloading)
-   **Database:** MongoDB (Motor async driver)
-   **Containerization:** Docker & Docker Compose

## Architecture
The application runs two main asynchronous services concurrently within the same event loop:
1.  **FastAPI Server**: Handles HTTP requests for streaming, searching, and API access.
2.  **Telegram Bot (StreamBot)**: Handles Telegram events, indexing commands, and file management.

## Codebase Structure

### Root Directory
-   `jackgram/`: Main source code package.
-   `Dockerfile`: Multi-stage Docker build file.
-   `docker-compose.yml`: Defines `app` (Jackgram) and `mongo` services.
-   `requirements.txt`: Python dependencies.
-   `config.env` / `sample_config.env`: Environment configuration.
-   `movie.py`: Contains movie metadata (appears to be a data dump or testing file).

### `jackgram/` Package
-   `__main__.py`: Application entry point. Initializes logging, config, and starts both `StreamBot` and `uvicorn.Server`.
-   `bot/`: Contains Telegram bot logic, command handlers, and indexing mechanisms.
-   `server/`: Contains FastAPI routes and API logic.
    -   `routes.py`: Main routes.
    -   `api/`: Sub-modules for specific API features (search, stream).
-   `utils/`: Utility functions (formatting, hashing, parsing). Includes `telegram_stream.py` for parallel chunk downloads over MTProto.

## Setup & Development

### Environment Configuration
Copy `sample_config.env` to `config.env` and populate:
-   `API_ID`, `API_HASH`: From my.telegram.org.
-   `BOT_TOKEN`: From BotFather.
-   `DATABASE_URL`: MongoDB connection string.
-   `LOGS_CHANNEL`: Channel ID for storing index data.

### Running Locally
1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
2.  **Run MongoDB:**
    Ensure MongoDB is running locally or via Docker (`docker-compose up mongo -d`).
3.  **Start Application:**
    ```bash
    python -m jackgram
    ```

### Running with Docker
```bash
docker-compose up -d --build
```

## Testing

The project uses `pytest` for testing.
To run tests, make sure you have the dependencies installed and a local MongoDB instance running (or updated uri in tests).

```bash
pytest
```

## Key Workflows

### Indexing
-   User sends `/index` command to the bot.
-   Bot crawls the specified channel.
-   Files are processed and metadata is stored in MongoDB.
-   TMDb is queried for movie/series metadata.

### Streaming
-   External client requests a stream URL (e.g., `/dl?hash={id}`).
-   FastAPI server retrieves file info from MongoDB, identifying the chat and message.
-   Server leverages `ParallelTransferrer` and a `TelegramSessionManager` to download segments in parallel, supporting HTTP Range requests for seeking seamlessly and quickly.
