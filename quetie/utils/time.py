"""
UTC time helpers for consistent, timezone-aware timestamps.
"""

from __future__ import annotations

from datetime import UTC, datetime


def utc_now() -> datetime:
    """Return the current timezone-aware UTC timestamp."""
    return datetime.now(UTC)


def utc_now_iso() -> str:
    """Return the current timezone-aware UTC timestamp as ISO-8601 text."""
    return utc_now().isoformat()
