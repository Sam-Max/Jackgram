"""Tests for scraping filters applied during /index channel crawling."""

import pytest
from jackgram.utils.scraping_filters import ScrapingFilters, get_file_extension


# ── Helpers ─────────────────────────────────────────────────────────────────

MB = 1024 * 1024  # 1 megabyte in bytes


def _make_filters(**overrides) -> ScrapingFilters:
    """Build a ScrapingFilters with sensible test defaults."""
    defaults = {
        "min_size_mb": 50,
        "adult_keywords": None,  # use built-in list
        "allowed_extensions": None,  # use built-in list
    }
    defaults.update(overrides)
    return ScrapingFilters(**defaults)


# ── get_file_extension ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "filename, expected_ext",
    [
        ("movie.mkv", ".mkv"),
        ("Movie.Name.2022.1080p.WEB-DL.mp4", ".mp4"),
        ("subtitles.srt", ".srt"),
        ("INFO.nfo", ".nfo"),
        ("noextension", ""),
        ("archive.tar.gz", ".gz"),
    ],
)
def test_get_file_extension(filename, expected_ext):
    assert get_file_extension(filename) == expected_ext


# ── Minimum file size ───────────────────────────────────────────────────────


class TestMinimumSize:
    def test_below_minimum_is_skipped(self):
        f = _make_filters(min_size_mb=50)
        skip, reason = f.should_skip("movie.mkv", 10 * MB)
        assert skip is True
        assert "too small" in reason.lower()

    def test_exactly_minimum_passes(self):
        f = _make_filters(min_size_mb=50)
        skip, _ = f.should_skip("movie.mkv", 50 * MB)
        assert skip is False

    def test_above_minimum_passes(self):
        f = _make_filters(min_size_mb=50)
        skip, _ = f.should_skip("movie.mkv", 100 * MB)
        assert skip is False

    def test_custom_minimum(self):
        f = _make_filters(min_size_mb=10)
        skip, _ = f.should_skip("movie.mkv", 5 * MB)
        assert skip is True
        skip, _ = f.should_skip("movie.mkv", 15 * MB)
        assert skip is False


# ── Adult keyword filtering ─────────────────────────────────────────────────


class TestAdultKeywords:
    def test_filename_with_adult_keyword_is_skipped(self):
        f = _make_filters()
        skip, reason = f.should_skip("Some.XXX.Movie.2022.mkv", 100 * MB)
        assert skip is True
        assert "Adult keyword" in reason

    def test_case_insensitive_matching(self):
        f = _make_filters()
        skip, reason = f.should_skip("Movie.PORN.Edition.mkv", 100 * MB)
        assert skip is True
        assert "porn" in reason

    def test_clean_filename_passes(self):
        f = _make_filters()
        skip, _ = f.should_skip("Avatar.2022.1080p.WEB-DL.mkv", 100 * MB)
        assert skip is False

    def test_custom_keyword_list(self):
        f = _make_filters(adult_keywords=["banned", "blocked"])
        # Default keywords should NOT match
        skip, _ = f.should_skip("Some.XXX.Movie.mkv", 100 * MB)
        assert skip is False
        # Custom keywords should match
        skip, reason = f.should_skip("Movie.Banned.Edition.mkv", 100 * MB)
        assert skip is True
        assert "banned" in reason


# ── Extension whitelist ──────────────────────────────────────────────────────


class TestExtensionFilter:
    def test_allowed_extension_passes(self):
        f = _make_filters()
        for ext in (".mkv", ".mp4", ".avi", ".mov", ".webm", ".ts"):
            skip, _ = f.should_skip(f"movie{ext}", 100 * MB)
            assert skip is False, f"Extension {ext} should be allowed"

    def test_disallowed_extension_is_skipped(self):
        f = _make_filters()
        for ext in (".srt", ".nfo", ".txt", ".jpg", ".png", ".exe"):
            skip, reason = f.should_skip(f"file{ext}", 100 * MB)
            assert skip is True, f"Extension {ext} should be blocked"
            assert "extension" in reason.lower()

    def test_no_extension_passes(self):
        """Files with no extension are let through (caption-only messages)."""
        f = _make_filters()
        skip, _ = f.should_skip("noextension", 100 * MB)
        assert skip is False

    def test_custom_extensions(self):
        f = _make_filters(allowed_extensions=[".custom", ".test"])
        skip, _ = f.should_skip("movie.mkv", 100 * MB)
        assert skip is True  # .mkv not in the custom list
        skip, _ = f.should_skip("movie.custom", 100 * MB)
        assert skip is False

    def test_extensions_without_dot_are_normalised(self):
        f = _make_filters(allowed_extensions=["mkv", "mp4"])
        skip, _ = f.should_skip("movie.mkv", 100 * MB)
        assert skip is False


# ── Filter priority / combined ───────────────────────────────────────────────


class TestCombinedFilters:
    def test_size_checked_before_keywords(self):
        """Size filter fires first, so the reason should be about size."""
        f = _make_filters(min_size_mb=50)
        skip, reason = f.should_skip("Some.XXX.Movie.mkv", 1 * MB)
        assert skip is True
        assert "too small" in reason.lower()

    def test_keyword_checked_before_extension(self):
        """Keyword filter fires before extension check."""
        f = _make_filters()
        skip, reason = f.should_skip("Some.PORN.Movie.mkv", 100 * MB)
        assert skip is True
        assert "Adult keyword" in reason

    def test_all_pass(self):
        f = _make_filters()
        skip, reason = f.should_skip("Avatar.2022.1080p.mkv", 200 * MB)
        assert skip is False
        assert reason is None
