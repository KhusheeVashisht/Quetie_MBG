"""
Quetie_mbg - Production-ready Twitch Queue Management Bot
Version: 1.0.0
"""

__version__ = "1.0.0"
__author__ = "miss_brain_glitch"

from quetie.config.settings import settings
from quetie.db.database import Database
from quetie.utils.logger import setup_logger

logger = setup_logger(__name__)

__all__ = ["settings", "Database", "logger"]
