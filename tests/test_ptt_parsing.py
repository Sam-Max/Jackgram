"""Tests for PTT (Parse Torrent Title) metadata extraction and API surface."""

import PTN
import pytest

from jackgram.utils.utils import (
    extract_movie_info_raw,
    extract_show_info_raw,
    extract_media_file_raw,
    extract_movie_info,
    extract_show_info,
)

# ── PTN parsing unit tests ──────────────────────────────────────────────────


SAMPLE_FILENAMES = [
    (
        "Avatar.The.Way.Of.Water.2022.2160p.WEB-DL.DDP5.1.Atmos.DV.HDR10.HEVC-CMRG.mkv",
        {
            "title": "Avatar The Way Of Water",
            "year": 2022,
            "resolution": "2160p",
            "quality": "WEB-DL",
            "codec": "H.265",
            "audio": "Dolby Atmos",
            "encoder": "CMRG",
            "hdr": True,
        },
    ),
    (
        "The.Matrix.1999.1080p.BluRay.x264-Group.mkv",
        {
            "title": "The Matrix",
            "year": 1999,
            "resolution": "1080p",
            "quality": "Blu-ray",
            "codec": "H.264",
        },
    ),
    (
        "Breaking.Bad.S05E16.Felina.720p.WEBRip.x265-MiNX.mkv",
        {
            "title": "Breaking Bad",
            "season": 5,
            "episode": 16,
            "resolution": "720p",
            "codec": "H.265",
        },
    ),
]


@pytest.mark.parametrize("filename,expected", SAMPLE_FILENAMES)
def test_ptn_parse_extracts_expected_fields(filename, expected):
    parsed = PTN.parse(filename)
    for key, value in expected.items():
        assert parsed.get(key) == value, (
            f"PTN field '{key}' mismatch for '{filename}': "
            f"expected {value!r}, got {parsed.get(key)!r}"
        )


# ── file_info shape helper ──────────────────────────────────────────────────

PTT_FIELDS = ("quality", "source", "video_codec", "audio_codec", "encoder", "hdr")


def _make_file_info(**overrides):
    """Build a minimal file_info dict with all PTT fields."""
    base = {
        "file_name": "Test.File.mkv",
        "file_size": 1_000_000,
        "quality": "1080p",
        "source": "WEB-DL",
        "video_codec": "H.265",
        "audio_codec": "DD5.1",
        "encoder": "GROUP",
        "hdr": True,
        "mime_type": "video/x-matroska",
        "chat_id": -100123456,
        "message_id": 42,
        "hash": "abc123",
    }
    base.update(overrides)
    return base


# ── API extraction function tests ───────────────────────────────────────────


def test_extract_movie_info_raw_includes_ptt_fields():
    data = {
        "tmdb_id": 1,
        "title": "Test Movie",
        "type": "movie",
        "origin_country": ["US"],
        "original_language": "en",
        "release_date": "2022-01-01",
        "runtime": 120,
        "file_info": [_make_file_info()],
    }
    result = extract_movie_info_raw(data)
    fi = result["files"][0]
    for field in PTT_FIELDS:
        assert field in fi, f"Missing PTT field '{field}' in extract_movie_info_raw"


def test_extract_show_info_raw_includes_ptt_fields():
    data = {
        "tmdb_id": 2,
        "title": "Test Show",
        "type": "tv",
        "origin_country": ["US"],
        "original_language": "en",
        "seasons": [
            {
                "season_number": 1,
                "episodes": [
                    {
                        "series": "Test Show",
                        "season_number": 1,
                        "episode_number": 1,
                        "date": "2022-01-01",
                        "duration": 45,
                        "title": "Pilot",
                        "rating": 8.0,
                        "file_info": [_make_file_info()],
                    }
                ],
            }
        ],
    }
    result = extract_show_info_raw(data)
    fi = result["files"][0]
    for field in PTT_FIELDS:
        assert field in fi, f"Missing PTT field '{field}' in extract_show_info_raw"


def test_extract_media_file_raw_includes_ptt_fields():
    result = extract_media_file_raw(_make_file_info())
    for field in PTT_FIELDS:
        assert field in result, f"Missing PTT field '{field}' in extract_media_file_raw"


def test_extract_movie_info_includes_ptt_fields():
    data = {
        "release_date": "2022-01-01",
        "runtime": 120,
        "file_info": [_make_file_info()],
    }
    items = extract_movie_info(data, tmdb_id=1)
    assert len(items) == 1
    for field in PTT_FIELDS:
        assert field in items[0], f"Missing PTT field '{field}' in extract_movie_info"


def test_extract_show_info_includes_ptt_fields():
    data = {
        "seasons": [
            {
                "season_number": 1,
                "episodes": [
                    {
                        "episode_number": 1,
                        "date": "2022-01-01",
                        "duration": 45,
                        "file_info": [_make_file_info()],
                    }
                ],
            }
        ],
    }
    items = extract_show_info(data, season_num=1, episode_num=1, tmdb_id=2)
    assert len(items) == 1
    for field in PTT_FIELDS:
        assert field in items[0], f"Missing PTT field '{field}' in extract_show_info"
