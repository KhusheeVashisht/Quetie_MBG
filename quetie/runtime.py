"""
Runtime process state for Quetie_mbg.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock
from typing import Optional

from quetie.utils.time import utc_now_iso


@dataclass
class AppRuntimeState:
    """Mutable in-process runtime status for health and diagnostics."""

    bot_enabled: bool = False
    bot_connected: bool = False
    bot_last_error: Optional[str] = None
    bot_last_connected_at: Optional[str] = None
    startup_completed_at: Optional[str] = None
    startup_error: Optional[str] = None
    _lock: Lock = field(default_factory=Lock, repr=False)

    def mark_startup_completed(self) -> None:
        with self._lock:
            self.startup_completed_at = utc_now_iso()
            self.startup_error = None

    def mark_startup_error(self, message: str) -> None:
        with self._lock:
            self.startup_error = message

    def set_bot_status(self, *, enabled: bool, connected: bool, error: Optional[str] = None) -> None:
        with self._lock:
            self.bot_enabled = enabled
            self.bot_connected = connected
            self.bot_last_error = error
            if connected:
                self.bot_last_connected_at = utc_now_iso()

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "bot_enabled": self.bot_enabled,
                "bot_connected": self.bot_connected,
                "bot_last_error": self.bot_last_error,
                "bot_last_connected_at": self.bot_last_connected_at,
                "startup_completed_at": self.startup_completed_at,
                "startup_error": self.startup_error,
            }


runtime_state = AppRuntimeState()
