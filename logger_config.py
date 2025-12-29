"""
Logging configuration for Aphorium.

Sets up structured logging with file and console handlers.
"""

import logging
import os
import sys
from pathlib import Path
from typing import Optional


class UnicodeStreamHandler(logging.StreamHandler):
    """
    Stream handler that properly handles Unicode characters.
    
    Ensures UTF-8 encoding for console output on Windows.
    """
    
    def __init__(self, stream=None):
        super().__init__(stream)
        # Set UTF-8 encoding for the stream if possible
        if hasattr(stream, 'reconfigure'):
            try:
                stream.reconfigure(encoding='utf-8', errors='replace')
            except (AttributeError, ValueError):
                pass
    
    def emit(self, record):
        """
        Emit a record, ensuring Unicode is properly encoded.
        """
        try:
            msg = self.format(record)
            stream = self.stream
            # Write Unicode string directly (Python 3 handles this)
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[str] = None
) -> logging.Logger:
    """
    Configure application logging.

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional path to log file

    Returns:
        Configured logger instance
    """
    # Set UTF-8 encoding for stdout/stderr on Windows
    if sys.platform == 'win32':
        try:
            # Try to set console encoding to UTF-8
            if hasattr(sys.stdout, 'reconfigure'):
                sys.stdout.reconfigure(encoding='utf-8', errors='replace')
            if hasattr(sys.stderr, 'reconfigure'):
                sys.stderr.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError):
            pass
    
    # Create logs directory if log file is specified
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logger = logging.getLogger("aphorium")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler with Unicode support
    console_handler = UnicodeStreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level.upper()))
    console_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_format = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - "
            "%(module)s - %(funcName)s - %(message)s"
        )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


# Initialize logger
logger = setup_logging(
    log_level=os.getenv("LOG_LEVEL", "INFO"),
    log_file=os.getenv("LOG_FILE", "logs/aphorium.log")
)

