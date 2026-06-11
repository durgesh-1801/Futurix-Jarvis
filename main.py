"""
Futurix Jarvis — Application Entry Point.

Initialises logging, loads settings, creates the PyQt6 application,
applies the dark theme, and launches the main window.
"""

from __future__ import annotations

import sys
import os

# Ensure the project root is on sys.path so imports work
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from config.settings import get_settings
from utils.logger import setup_logging


def main() -> int:
    """Application entry point.

    Returns:
        Exit code (0 = success).
    """
    # ── Load configuration ───────────────────────────────────────────────
    settings = get_settings()

    # ── Initialise logging ───────────────────────────────────────────────
    setup_logging(level=settings.log_level, log_dir=settings.log_dir)

    import logging
    logger = logging.getLogger("futurix_jarvis")
    logger.info("=" * 60)
    logger.info("  Futurix Jarvis — Starting Up")
    logger.info("=" * 60)
    logger.info("  Model: %s", settings.ollama_model)
    logger.info("  Ollama: %s", settings.ollama_base_url)
    logger.info("  DB: %s", settings.db_path)
    logger.info("=" * 60)

    # ── Create Qt Application ────────────────────────────────────────────
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from PyQt6.QtGui import QFont

    # Enable High DPI
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName("Futurix Jarvis")
    app.setApplicationDisplayName("⚡ Futurix Jarvis")
    app.setOrganizationName("Futurix")

    # Set default font
    font = QFont("Segoe UI", 10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    app.setFont(font)

    # ── Apply dark theme ─────────────────────────────────────────────────
    try:
        import qdarktheme
        qdarktheme.setup_theme("dark")
        logger.info("Applied qdarktheme.")
    except ImportError:
        logger.info("qdarktheme not installed — using custom stylesheet only.")

    # ── Create and show main window ──────────────────────────────────────
    from gui.main_window import MainWindow

    window = MainWindow(settings)
    window.show()

    logger.info("Main window displayed. Entering event loop.")

    # ── Run event loop ───────────────────────────────────────────────────
    exit_code = app.exec()

    logger.info("Application exited with code %d.", exit_code)
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
