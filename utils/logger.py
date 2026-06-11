"""
Futurix Jarvis — Logging Configuration.

Sets up a dual-handler logger (console + rotating file) with colour-coded
console output for easy debugging.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


# ── ANSI colour codes for console output ─────────────────────────────────────
class _Colours:
    GREY = "\033[38;5;245m"
    CYAN = "\033[36m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    BOLD_RED = "\033[1;31m"
    RESET = "\033[0m"


_LEVEL_COLOURS = {
    logging.DEBUG: _Colours.GREY,
    logging.INFO: _Colours.CYAN,
    logging.WARNING: _Colours.YELLOW,
    logging.ERROR: _Colours.RED,
    logging.CRITICAL: _Colours.BOLD_RED,
}


class _ColouredFormatter(logging.Formatter):
    """Formatter that injects ANSI colour codes per log level."""

    _BASE_FMT = "%(asctime)s | %(levelname)-8s | %(name)-25s | %(message)s"
    _DATE_FMT = "%H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        colour = _LEVEL_COLOURS.get(record.levelno, _Colours.RESET)
        formatter = logging.Formatter(
            f"{colour}{self._BASE_FMT}{_Colours.RESET}",
            datefmt=self._DATE_FMT,
        )
        return formatter.format(record)


_FILE_FMT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
_FILE_DATE_FMT = "%Y-%m-%d %H:%M:%S"

_is_configured = False


def setup_logging(
    level: str = "INFO",
    log_dir: Optional[Path] = None,
    log_filename: str = "jarvis.log",
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 3,
) -> None:
    """Configure the root logger with console + rotating-file handlers.

    Safe to call multiple times — subsequent calls are no-ops.

    Args:
        level: Logging level name (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files. Created if it doesn't exist.
        log_filename: Name of the rotating log file.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of rotated log files to retain.
    """
    global _is_configured
    if _is_configured:
        return
    _is_configured = True

    # Avoid UnicodeEncodeError on Windows command prompt
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="backslashreplace")
            except Exception:
                pass

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # ── Console handler ──────────────────────────────────────────────────
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(_ColouredFormatter())
    root_logger.addHandler(console_handler)

    # ── File handler ─────────────────────────────────────────────────────
    if log_dir is not None:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / log_filename,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(
            logging.Formatter(_FILE_FMT, datefmt=_FILE_DATE_FMT)
        )
        root_logger.addHandler(file_handler)

    # Suppress noisy third-party loggers
    for noisy in ("urllib3", "httpcore", "httpx", "asyncio"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger("futurix_jarvis").info(
        "Logging initialised — level=%s, log_dir=%s", level, log_dir
    )
