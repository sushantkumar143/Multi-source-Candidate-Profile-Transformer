"""
Structured logging setup for the pipeline.

Provides a consistent logging configuration with:
- Structured format including timestamp, module, level
- Configurable log level
- Both console and optional file output
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_configured = False


def setup_logging(
    level: str = "INFO",
    log_file: Path | None = None,
) -> None:
    """Configure logging for the entire pipeline.

    Args:
        level: Log level string (DEBUG, INFO, WARNING, ERROR).
        log_file: Optional path to write logs to a file.
    """
    global _configured
    if _configured:
        return

    log_level = getattr(logging, level.upper(), logging.INFO)

    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
    root_logger.addHandler(console_handler)

    # Optional file handler
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT))
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    logging.getLogger("pdfplumber").setLevel(logging.WARNING)
    logging.getLogger("pdfminer").setLevel(logging.WARNING)

    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger for a module.

    Args:
        name: Logger name, typically __name__ of the calling module.

    Returns:
        Configured logger instance.
    """
    return logging.getLogger(name)
