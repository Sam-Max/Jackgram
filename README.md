### A telegram bot and web server with an API Rest, that indexes telegram channels videos files and serve the information through its API to build an url for stream or download.

## **Features**

- Index files of public and private channel
- API Rest with auth token system.
- Stream and download video files using an API endpoint
- Database support
- Tmdb API support

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
            },
          ]
        }
      ]
    }
    ```

## **Env Variables**

Add the following environment variables to your config.env file.

- `API_ID`: (required) | Telegram api_id obtained from https://my.telegram.org/apps. `int`
- `API_HASH`: (required) | Telegram api_hash obtained from https://my.telegram.org/apps. `str`
- `BOT_TOKEN`: (required) | The Telegram Bot Token that you got from @BotFather `str`
- `DATABASE_URL`:(required) | Your Mongo Database URL (Connection string). `str`
- `SESSION_STRING`: | Use same account which is a participant of the channels to index.
- `LOGS_CHANNEL`: | Channel where the indexed video files will be saved. `int`
- `TMDB_API`: | API token for tmdb authentification. `str`
- `TMDB_LANGUAGE`: | Language for tmdb metadata. Default: "en-US". `str`
- `BASE_URL`: (required) | Valid BASE URL where the bot is deployed. Format of URL should be `http://myip`, where myip is the IP/Domain(public) of your bot. `str`
- `PORT`: | Port on which app should listen to, defaults to `8080`. `int`
- `SECRET_KEY`: | Secret key for encrypt and decrypt authentification tokens. `str`
- `SLEEP_THRESHOLD`: | Set a sleep threshold for flood wait exceptions, defaut is `60`. `int`

### **Generate Database**

1. Go to `https://mongodb.com/` and sign-up.
2. Create Shared Cluster.
3. Press on `Database` under `Deployment` Header, your created cluster will be there.
4. Press on connect, choose `Allow Access From Anywhere` and press on `Add IP Address` without editing the ip, then
   create user.
5. After creating user press on `Choose a connection`, then press on `Connect your application`. Choose `Driver`
   **python** and `version` **3.6 or later**.
6. Copy your `connection string` and replace `<password>` with the password of your user, then press close.

### Bot Commands

```
start - Welcome message
index - Store files of a channel in the db
search - Search a file on db by name
del - Delete a file on the db
count - Count all files on the db
token - Generate a token to authorize using API
save_db - Save the db
del_db - Delete a db by name

```

## **Contact Info**

[![Telegram Username](https://img.shields.io/static/v1?label=&message=Telegram%20&color=blueviolet&style=for-the-badge&logo=telegram&logoColor=black)](https://t.me/sammax09)


## Disclaimer:

This bot should only be used to access movies and TV series not protected by copyright.