<div align="center">

# 🚀 Jackgram

### A Telegram Bot and REST API Server for indexing and streaming Telegram files.

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8+-3776AB.svg?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Telethon](https://img.shields.io/badge/Telethon-1.24+-3171A5.svg?logo=telegram&logoColor=white)](https://docs.telethon.dev/)
[![Docker](https://img.shields.io/badge/Docker-Supported-2496ED.svg?logo=docker&logoColor=white)](https://www.docker.com/)

---

Jackgram allows you to index media files from public and private Telegram channels, storing them in a searchable database and serving them via a high-performance REST API. Built with FastAPI and Telethon, it's designed for speed, scalability, and ease of use. Leveraging FastTelethon for parallel chunky downloads, it ensures high-speed streaming even for large files.

[Features](#-features) • [Installation](#-getting-started) • [API Documentation](#-api-endpoints) • [Contact](#-contact-info)

</div>

---

## ✨ Features

- 📂 **Channel Indexing**: Automatically index video files from public and private Telegram channels.
- ⚡ **FastAPI Powered**: High-performance REST API for lightning-fast data retrieval and streaming.
- 🔐 **Secure Authentication**: Optional token-based authentication system to protect your API.
- 📺 **Seamless Streaming**: Direct stream and download support with HTTP Range (Partial Content) support.
- 🗄️ **MongoDB Integration**: Efficiently store and manage thousands of indexed files with ease.
- 🎬 **TMDb Integration**: Automatically fetches rich metadata (titles, posters, plot) via The Movie Database API.
- 🐳 **Docker Ready**: Deploy in seconds using Docker and Docker Compose.
- 🔄 **Backup & Restore**: Easily backup your entire database to JSON and restore it whenever needed.

---

## 🛠️ Getting Started

### 🐳 Using Docker (Recommended)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Sam-Max/Jackgram.git
   cd Jackgram
   ```

2. **Configure Environment:**
   ```bash
   cp sample_config.env config.env
   # Open config.env and fill in your credentials
   ```

3. **Deploy:**
   ```bash
   docker-compose up -d
   ```

### 🐍 Local Installation

1. **Install Requirements:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Setup MongoDB:**
   Ensure you have a MongoDB instance running and accessible.

3. **Run the application:**
   ```bash
   python3 -m jackgram
   ```

---

## ⚙️ Configuration

Fill your `config.env` with these essential variables. You can get Telegram API credentials from [my.telegram.org](https://my.telegram.org/apps).

| Variable | Description | Default |
| :--- | :--- | :--- |
| `API_ID` | Your Telegram API ID | Required |
| `API_HASH` | Your Telegram API Hash | Required |
| `BOT_TOKEN` | Telegram Bot Token ([@BotFather](https://t.me/BotFather)) | Required |
| `TMDB_API` | TMDb API Key | Required |
| `LOGS_CHANNEL` | Channel ID where indexed data is stored | Required |
| `BASE_URL` | Public IP/Domain of your server | Required |
| `DATABASE_URL` | MongoDB connection string | `mongodb://admin:admin@mongo:27017` |
| `SESSION_STRING` | Telethon session string (for private channels) | Optional |
| `USE_TOKEN_SYSTEM` | Enable/Disable API token system | `True` |
| `SECRET_KEY` | Secret key for JWT encryption | `your-secret-token` |
| `PORT` | Web server port | `5000` |
| `WORKERS` | Number of concurrent workers | `10` |

---

## 🤖 Bot Commands

The bot provides a set of admin commands to manage your index:

| Command | Description |
| :--- | :--- |
| `/start` | Show welcome message and available commands. |
| `/index` | Start indexing a specific Telegram channel. |
| `/search` | Search indexed files directly via the bot. |
| `/token` | Generate a new API authentication token. |
| `/count` | Display total number of indexed files. |
| `/save_db` | Export the current database to a JSON backup. |
| `/load_db` | Restore the database from a JSON backup file. |
| `/del_db` | Wipe the entire database index. |

---

## 📡 API Endpoints

All API requests require the `Authorization: Bearer <token>` header if `USE_TOKEN_SYSTEM` is enabled.

### 📽️ Media Streaming
- **Series:** `GET /stream/series/{tmdb_id}:{season}:{episode}.json`
  ```json
  {
    "tmdb_id": "77163",
    "streams": [
      {
        "name": "Telegram",
        "title": "TV Show Title",
        "quality": "720p",
        "size": 263039472,
        "hash": "XXXXXX"
      }
    ]
  }
  ```
- **Movie:** `GET /stream/movie/{tmdb_id}.json`
  ```json
  {
    "tmdb_id": "592831",
    "streams": [
      {
        "name": "Telegram",
        "title": "Movie Name",
        "quality": "1080p",
        "size": 1189639567,
        "hash": "XXXXXX"
      }
    ]
  }
  ```
- **Download:** `GET /dl?hash={file_hash}` (Supports Range headers for seeking)

### 🔍 Discovery & Search
- **Search:** `GET /search?query={q}&page={n}`
- **Latest:** `GET /stream/latest?page={n}`
- **Raw Files:** `GET /stream/files?page={n}`

### 📊 System
- **Status:** `GET /status` (Check if server and bot are online)

---

## ❤️ Support & Donation

If you like this project and want to support its development, consider buying me a coffee!

[![Ko-fi](https://img.shields.io/badge/Ko--fi-F16061?style=for-the-badge&logo=ko-fi&logoColor=white)](https://ko-fi.com/sammax)

---

## 📞 Contact Info

Join our Telegram for updates, support, and discussions:

[![Telegram Channel](https://img.shields.io/badge/Telegram-26A6E2?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/samysosa08)

---

## ⚖️ License & Disclaimer

Index and serve at your own risk. This tool is for educational purposes only and the author is not responsible for what you index.

Distributed under the **GNU GPL v3 License**.

> **Disclaimer:** This bot should only be used to access movies and TV series not protected by copyright.
