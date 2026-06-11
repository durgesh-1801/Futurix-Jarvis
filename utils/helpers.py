"""
Futurix Jarvis — Shared Utility Helpers.

Small, pure-ish functions used across multiple modules.
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def sanitize_path(raw: str) -> Path:
    """Return a resolved, absolute ``Path`` from a raw user-supplied string.

    Expands ``~``, resolves ``.`` / ``..``, and strips surrounding whitespace.

    Args:
        raw: The raw path string (may include ``~`` or relative segments).

    Returns:
        A fully resolved ``Path``.
    """
    return Path(raw.strip()).expanduser().resolve()


def format_timestamp(
    dt: Optional[datetime] = None,
    fmt: str = "%Y-%m-%d %H:%M:%S",
) -> str:
    """Format a datetime as a human-readable string.

    Args:
        dt: The datetime to format. Defaults to ``datetime.now()``.
        fmt: ``strftime`` format string.

    Returns:
        Formatted timestamp string.
    """
    if dt is None:
        dt = datetime.now(timezone.utc)
    return dt.strftime(fmt)


def truncate_text(text: str, max_length: int = 200, suffix: str = "…") -> str:
    """Truncate *text* to at most *max_length* characters.

    Truncation happens at the last whitespace boundary before the limit so
    words are not sliced in half.

    Args:
        text: The input text.
        max_length: Maximum allowed character count (including suffix).
        suffix: String appended when truncation occurs.

    Returns:
        The (possibly truncated) string.
    """
    if len(text) <= max_length:
        return text
    cut = max_length - len(suffix)
    # Try to cut at a word boundary
    space_idx = text.rfind(" ", 0, cut)
    if space_idx > 0:
        cut = space_idx
    return text[:cut].rstrip() + suffix


def slugify(text: str, max_length: int = 60) -> str:
    """Convert *text* to a URL/filename-safe slug.

    Args:
        text: Input text.
        max_length: Maximum slug length.

    Returns:
        Lowercased, hyphenated slug string.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[-\s]+", "-", text)
    return text[:max_length].rstrip("-")


def human_readable_size(size_bytes: int) -> str:
    """Convert a byte count to a human-readable string (e.g. ``1.2 GB``).

    Args:
        size_bytes: Number of bytes.

    Returns:
        Formatted size string.
    """
    if size_bytes < 0:
        return "0 B"
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0  # type: ignore[assignment]
    return f"{size_bytes:.1f} PB"


def extract_code_blocks(text: str) -> list[dict[str, str]]:
    """Extract fenced code blocks from Markdown text.

    Args:
        text: Markdown-formatted text.

    Returns:
        List of dicts with ``language`` and ``code`` keys.
    """
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)
    return [{"language": lang or "text", "code": code.strip()} for lang, code in matches]
