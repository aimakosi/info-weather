"""Logging configuration for info-weather.

Supports stdout/stderr streaming and rotating or appending file logs in user data/cache dir.
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import sys
from pathlib import Path

DEFAULT_LOG_DIR = Path.home() / ".cache" / "info-weather"
DEFAULT_LOG_FILE = DEFAULT_LOG_DIR / "info-weather.log"

_initialized = False


def setup_logging(
    level: str | int = logging.INFO,
    log_file: Path | str | None = None,
    enable_console: bool = True,
) -> None:
    """Configure root logger with console and optional file handler."""
    global _initialized
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)

    root = logging.getLogger("info_weather")
    root.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    root.handlers.clear()

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if enable_console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(level)
        root.addHandler(console_handler)

    target_file = Path(log_file) if log_file else DEFAULT_LOG_FILE
    try:
        target_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            target_file, encoding="utf-8", maxBytes=1_000_000, backupCount=2
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
    except (OSError, PermissionError) as e:
        sys.stderr.write(f"Warning: Could not open log file {target_file}: {e}\n")

    _initialized = True


def get_logger(name: str) -> logging.Logger:
    """Get a named logger under the info_weather namespace."""
    if not _initialized:
        setup_logging(level=os.environ.get("INFO_WEATHER_LOG_LEVEL", "INFO"))
    if not name.startswith("info_weather"):
        name = f"info_weather.{name}"
    return logging.getLogger(name)
