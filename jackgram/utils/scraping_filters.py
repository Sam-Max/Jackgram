"""
Scraping filters for the indexing pipeline.

Applies automatic exclusion rules to skip junk files (samples, intros,
adult content, non-streamable extensions) *before* they hit MongoDB or
the TMDb API.
"""

import logging
import os
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)

# ── Defaults ────────────────────────────────────────────────────────────────

DEFAULT_MIN_SIZE_MB = 50

DEFAULT_ADULT_KEYWORDS: List[str] = [
    "xxx",
    "porn",
    "hentai",
    "adult",
    "18+",
    "erotic",
    "playboy",
    "brazzers",
    "bangbros",
    "naughty",
    "xvideos",
    "pornhub",
]

DEFAULT_ALLOWED_EXTENSIONS: List[str] = [
    ".mkv",
    ".mp4",
    ".avi",
    ".mov",
    ".wmv",
    ".flv",
    ".webm",
    ".m4v",
    ".ts",
    ".mpg",
    ".mpeg",
]


def _parse_csv(value: str) -> List[str]:
    """Split a comma-separated string into a trimmed, non-empty list."""
    return [item.strip() for item in value.split(",") if item.strip()]


class ScrapingFilters:
    """Configurable filter rules applied during channel indexing."""

    def __init__(
        self,
        min_size_mb: int = DEFAULT_MIN_SIZE_MB,
        adult_keywords: Optional[List[str]] = None,
        allowed_extensions: Optional[List[str]] = None,
    ):
        self.min_size_bytes: int = min_size_mb * 1024 * 1024
        self.adult_keywords: List[str] = [
            kw.lower() for kw in (adult_keywords or DEFAULT_ADULT_KEYWORDS)
        ]
        self.allowed_extensions: List[str] = [
            ext.lower() if ext.startswith(".") else f".{ext.lower()}"
            for ext in (allowed_extensions or DEFAULT_ALLOWED_EXTENSIONS)
        ]

    # ── public API ──────────────────────────────────────────────────────

    def should_skip(self, filename: str, file_size: int) -> Tuple[bool, Optional[str]]:
        """Return ``(True, reason)`` if the file should be excluded.

        Checks are applied in order:
        1. Minimum file size
        2. Adult keyword in filename
        3. File extension whitelist
        """
        # 1. Size check
        if file_size < self.min_size_bytes:
            reason = (
                f"File too small ({_readable_size(file_size)} < "
                f"{_readable_size(self.min_size_bytes)})"
            )
            return True, reason

        # 2. Adult keyword check
        name_lower = filename.lower()
        for keyword in self.adult_keywords:
            if keyword in name_lower:
                return True, f"Adult keyword detected: '{keyword}'"

        # 3. Extension check
        ext = get_file_extension(filename)
        if ext and ext not in self.allowed_extensions:
            return True, f"Disallowed extension: '{ext}'"
        # If there is no extension at all, let it through (caption-only
        # messages, etc.) — the rest of the pipeline will handle it.

        return False, None


# ── Helpers ─────────────────────────────────────────────────────────────────


def get_file_extension(filename: str) -> str:
    """Extract the lowercase file extension including the leading dot."""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def _readable_size(size_bytes: int) -> str:
    """Quick human-readable size for log messages."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"
