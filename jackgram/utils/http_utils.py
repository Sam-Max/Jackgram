import re
from urllib.parse import quote
from typing import Optional


def _content_disposition_inline(filename: str) -> str:
    """
    Build a Content-Disposition header value that is always latin-1 safe.

    Starlette/FastAPI requires header values to be latin-1 encodable. Telegram filenames
    may contain unicode (e.g. Cyrillic), so we use RFC 6266 `filename*` when needed.
    """
    # Sanitize newlines and carriage returns
    sanitized = (filename or "").strip().replace("\n", " ").replace("\r", " ")
    if not sanitized:
        return "inline"

    try:
        # Try if the filename is latin-1 encodable
        sanitized.encode("latin-1")
        # For the filename= parameter, we must escape backslashes and double quotes
        escaped = sanitized.replace("\\", "\\\\").replace('"', '\\"')
        return f'inline; filename="{escaped}"'
    except UnicodeEncodeError:
        # For filename*, use percent-encoding with the original (unescaped) sanitized name
        encoded = quote(sanitized, encoding="utf-8", safe="")
        return f"inline; filename*=UTF-8''{encoded}"


def get_content_type(mime_type: str, file_name: Optional[str] = None) -> str:
    """Determine content type from mime type or filename."""
    if mime_type:
        return mime_type

    if file_name:
        ext = file_name.rsplit(".", 1)[-1].lower() if "." in file_name else ""
        mime_map = {
            "mp4": "video/mp4",
            "mkv": "video/x-matroska",
            "avi": "video/x-msvideo",
            "webm": "video/webm",
            "mov": "video/quicktime",
            "mp3": "audio/mpeg",
            "m4a": "audio/mp4",
            "flac": "audio/flac",
            "ogg": "audio/ogg",
            "jpg": "image/jpeg",
            "jpeg": "image/jpeg",
            "png": "image/png",
            "gif": "image/gif",
            "webp": "image/webp",
        }
        return mime_map.get(ext, "application/octet-stream")

    return "application/octet-stream"


def parse_range_header(range_header: Optional[str], file_size: int) -> tuple[int, int]:
    """
    Parse HTTP Range header.

    Args:
        range_header: The Range header value (e.g., "bytes=0-999")
        file_size: Total file size

    Returns:
        Tuple of (start, end) byte positions
    """
    if not range_header:
        return 0, file_size - 1

    # Parse "bytes=start-end" format
    match = re.match(r"bytes=(\d*)-(\d*)", range_header)
    if not match:
        return 0, file_size - 1

    start_str, end_str = match.groups()

    if start_str and end_str:
        start = int(start_str)
        end = min(int(end_str), file_size - 1)
    elif start_str:
        start = int(start_str)
        end = file_size - 1
    elif end_str:
        # Suffix range: last N bytes
        suffix_length = int(end_str)
        start = max(0, file_size - suffix_length)
        end = file_size - 1
    else:
        start = 0
        end = file_size - 1

    # Validate start <= end (handle malformed ranges like "bytes=999-0")
    if start > end:
        return 0, file_size - 1

    return start, end
