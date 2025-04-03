### A telegram bot and web server with an API Rest, that indexes telegram channels videos files and serve the information through its API to build an url for stream or download.

## **Features**

- **Index Telegram Channel Files**: Index video files from public and private Telegram channels.
- **FastAPI-Powered API**: Provides a robust and scalable REST API for accessing indexed data.
- **Authentication System**: Secure API access using token-based authentication.
- **Stream and Download Support**: Stream or download video files directly via API endpoints.
- **MongoDB Integration**: Efficiently store and manage indexed data using MongoDB.
- **TMDb API Integration**: Fetch metadata like titles, descriptions, and more from The Movie Database (TMDb).

## **Api Endpoints**

### GET /stream/series

- **Request:**

  - Method: `GET`
  - URL: `/stream/series/{tmdb_id}:{season}:{episode}.json`
  - Headers:
    - `Authorization: Bearer <token>`

- **Response:**
  - Status: `200 OK`
  - Body:
    ```json
    {
      "tmdb_id": "77163",
      "streams": [
        {
          "name": "Telegram",
          "title": "TV Show Title",
          "date": "2021-12-31",
          "duration": 33,
          "quality": "720p",
          "size": 263039472,
          "hash": "XXXXXX"
        }
      ]
    }
    ```

### GET /stream/movie

- **Request:**

  - Method: `GET`
  - URL: `/stream/movie/{tmdb_id}.json`
  - Headers:
    - `Authorization: Bearer <token>`

- **Response:**
  - Status: `200 OK`
  - Body:
    ```json
    {
      "tmdb_id": "592831",
      "streams": [
        {
          "name": "Telegram",
          "title": "Movie Title",
          "date": "2024-09-25",
          "duration": 138,
          "quality": "720p",
          "size": 1189639567,
          "hash": "XXXXXX"
        }
      ]
    }
    ```

### GET /search

- **Request:**

  - Method: `GET`
  - URL: `/search?query=value1&page=value2`
  - Headers:
    - `Authorization: Bearer <token>`

- **Response:**
  - Status: `200 OK`
  - Body:
    ```json
    {
      "page": 1,
      "total_count": 1,
      "results": [
        {
          "tmdb_id": 118956,
          "type": "tv",
          "country": "US",
          "language": "en",
          "files": [
            {
              "name": "Telegram",
              "title": "TV Show or Movie Title",
              "date": "2022-01-18",
              "duration": 25,
              "quality": "720p",
              "size": 65661748,
              "hash": "XXXXXX"
            }
          ]
        }
      ]
    }
    ```

### GET /dl

- **Request:**

  - Method: `GET`
  - URL: `/dl/{tmdb_id}?hash=XXXXXX`
  - Headers:
    - `Authorization: Bearer <token>`

- **Response:**
  - Status:
    - `200 OK`: Full file download when no `Range` header is provided.
    - `206 Partial Content`: Partial file download when a valid `Range` header is included.
  - Body: Binary content of the requested media file or portion of it.

## Setting up config file.

cp config_sample.env config.env

## Fill up Env Variables.

Add the following environment variables to your config.env file.

- `API_ID`: (required) | Telegram api_id obtained from https://my.telegram.org/apps. `int`
- `API_HASH`: (required) | Telegram api_hash obtained from https://my.telegram.org/apps. `str`
- `BOT_TOKEN`: (required) | The Telegram Bot Token that you got from @BotFather `str`
- `DATABASE_URL`:(required) | Your Mongo Database URL (Connection string). `str`. Default: `mongodb://admin:admin@mongo:27017`.
- `BACKUP_DIR`: | Directory where to save the database file on json format. `str`. Default: `/app/database`.
- `SESSION_STRING`: | Use same account which is a participant of the channels to index (necessary to index private channels)
- `WORKERS` | Number of maximum concurrent workers for handling incoming updates, default is `10`. `int`
- `LOGS_CHANNEL`: | Channel where the indexed video files will be saved. `int`
- `TMDB_API`: | API token for tmdb authentification. `str`
- `TMDB_LANGUAGE`: | Language for tmdb metadata. Default: "en-US". `str`
- `BASE_URL`: (required) | Valid BASE URL where the bot is deployed. Format of URL should be `http://myip`, where myip is the IP/Domain(public) of your bot. `str`
- `PORT`: | Port on which app should listen to, defaults to `5000`. `int`
- `SECRET_KEY`: | Secret key for encrypt and decrypt authentification tokens. `str`
- `SLEEP_THRESHOLD`: | Set a sleep threshold for flood wait exceptions, defaut is `60`. `int`

### **Running using Docker Compose**

docker-compose up -d

### Bot Commands

```
start - Welcome message and commands help.
index - Index channel files into the database.
search - Search for files in the database.
del - Remove a file from the database.
count - Count all files in the database.
token - Generate an API auth token.
save_db - Backup the database to a JSON file.
load_db - Restore the database from a JSON file.
del_db - Delete the database.
```

## **Contact Info**

[![Telegram Username](https://img.shields.io/static/v1?label=&message=Telegram%20&color=blueviolet&style=for-the-badge&logo=telegram&logoColor=black)](https://t.me/sammax09)

## Disclaimer:

This bot should only be used to access movies and TV series not protected by copyright.
