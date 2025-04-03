import pytest
import pytest_asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from jackgram.utils.database import Database


@pytest_asyncio.fixture
async def test_db():
    # Setup: Create a test database instance
    uri = "mongodb://localhost:27017"
    database_name = "test_db"
    client = AsyncIOMotorClient(uri)
    db = Database(uri, database_name)
    yield db
    # Teardown: Drop the test database
    await client.drop_database(database_name)


@pytest.mark.asyncio
async def test_add_tmdb(test_db):
    # Test adding a TMDB entry
    tmdb_data = {"tmdb_id": 123, "title": "Test Movie"}
    await test_db.add_tmdb(tmdb_data)
    result = await test_db.get_tmdb(123)
    assert result is not None
    assert result["tmdb_id"] == 123
    assert result["title"] == "Test Movie"


@pytest.mark.asyncio
async def test_get_tmdb(test_db):
    # Test fetching a TMDB entry
    tmdb_data = {"tmdb_id": 456, "title": "Another Test Movie"}
    await test_db.add_tmdb(tmdb_data)
    result = await test_db.get_tmdb(456)
    assert result is not None
    assert result["tmdb_id"] == 456
    assert result["title"] == "Another Test Movie"


@pytest.mark.asyncio
async def test_update_tmdb(test_db):
    # Test updating a TMDB entry
    tmdb_data = {"tmdb_id": 789, "title": "Old Title", "file_info": []}
    await test_db.add_tmdb(tmdb_data)

    existing_media = await test_db.get_tmdb(789)
    print("Existing Media:", existing_media)  # Log the existing media

    updated_data = {
        "tmdb_id": 789,
        "title": "New Title",
        "file_info": [{"hash": "abc123"}],
    }
    await test_db.update_tmdb(existing_media, updated_data, media_type="movie")

    result = await test_db.get_tmdb(789)
    print("Updated Media:", result)  # Log the updated media

    assert result is not None
    assert len(result["file_info"]) == 1
    assert result["file_info"][0]["hash"] == "abc123"
