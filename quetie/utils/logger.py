"""
Logging setup for Quetie_mbg
Provides structured logging with appropriate levels and formatting
"""

import logging
import sys
from quetie.config.settings import settings


def setup_logger(name: str, level: str = None) -> logging.Logger:
    """
    Setup a logger with consistent formatting
    
    Args:
        name: Logger name (typically __name__)
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    
    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger  # Already configured
    
    log_level = level or settings.LOG_LEVEL
    logger.setLevel(getattr(logging, log_level))
    
    # Console handler with formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    
    # Formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    # Avoid duplicate handlers
    logger.propagate = False
    
    return logger


# Application logger
logger = setup_logger(__name__)
