"""
Lightweight in-memory diagnostics buffer.
"""

from __future__ import annotations

from collections import deque
from threading import Lock
from typing import Deque, Dict, List, Optional

from quetie.utils.time import utc_now_iso


class DiagnosticsBuffer:
    """Rolling event buffer for production-safe diagnostics."""

    def __init__(self, max_events: int = 250):
        self.max_events = max_events
        self._events: Deque[Dict] = deque(maxlen=max_events)
        self._lock = Lock()

    def add(self, category: str, event: str, *, level: str = "INFO", details: Optional[dict] = None) -> None:
        payload = {
            "timestamp": utc_now_iso(),
            "category": category,
            "event": event,
            "level": level,
            "details": details or {},
        }
        with self._lock:
            self._events.append(payload)

    def snapshot(self) -> List[Dict]:
        with self._lock:
            return list(self._events)


diagnostics_buffer = DiagnosticsBuffer()


def record_diagnostic(category: str, event: str, *, level: str = "INFO", **details) -> None:
    diagnostics_buffer.add(category, event, level=level, details=details)
