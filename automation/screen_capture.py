"""
Futurix Jarvis — Screen Capture & Analysis Tools.

LangChain tools for taking screenshots, capturing specific windows,
and preparing images for LLM analysis.
"""

from __future__ import annotations

import base64
import io
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _take_screenshot_pil(region: Optional[tuple] = None):
    """Capture a screenshot using PIL/Pillow.

    Args:
        region: Optional (left, top, width, height) tuple.

    Returns:
        A PIL Image object, or None on failure.
    """
    try:
        import pyautogui
        if region:
            img = pyautogui.screenshot(region=region)
        else:
            img = pyautogui.screenshot()
        return img
    except Exception as exc:
        logger.error("Screenshot failed: %s", exc)
        return None


def _image_to_base64(img) -> str:
    """Convert a PIL Image to a base64-encoded PNG string."""
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("utf-8")


@tool
def capture_screenshot(save_path: str = "") -> str:
    """Capture a full-screen screenshot and save it to disk.

    Args:
        save_path: Optional file path to save the screenshot.
                   If empty, saves to a timestamped file in the screenshots folder.
    """
    img = _take_screenshot_pil()
    if img is None:
        return "❌ Failed to capture screenshot."

    try:
        if not save_path:
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = str(screenshots_dir / f"screenshot_{timestamp}.png")

        path = Path(save_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(path))
        logger.info("Screenshot saved: %s", path)
        return f"📸 Screenshot saved to: `{path}`"
    except Exception as exc:
        return f"❌ Failed to save screenshot: {exc}"


@tool
def capture_screen_region(left: int, top: int, width: int, height: int) -> str:
    """Capture a specific region of the screen.

    Args:
        left: X coordinate of the top-left corner.
        top: Y coordinate of the top-left corner.
        width: Width of the capture region in pixels.
        height: Height of the capture region in pixels.
    """
    img = _take_screenshot_pil(region=(left, top, width, height))
    if img is None:
        return "❌ Failed to capture screen region."

    try:
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = screenshots_dir / f"region_{timestamp}.png"
        img.save(str(save_path))
        return f"📸 Region captured and saved to: `{save_path}`"
    except Exception as exc:
        return f"❌ Failed to save region capture: {exc}"


@tool
def get_screen_resolution() -> str:
    """Get the current screen resolution."""
    try:
        import pyautogui
        width, height = pyautogui.size()
        return f"🖥️ Screen resolution: **{width} × {height}** pixels"
    except Exception as exc:
        return f"❌ Failed to get screen resolution: {exc}"


@tool
def analyse_screenshot(description: str = "Describe what you see on screen") -> str:
    """Capture a screenshot and prepare it for LLM analysis.

    This tool captures the current screen and returns a description request.
    The actual analysis should be performed by the LLM using the captured image.

    Args:
        description: What to look for or describe in the screenshot.
    """
    img = _take_screenshot_pil()
    if img is None:
        return "❌ Failed to capture screenshot for analysis."

    try:
        # Save the screenshot
        screenshots_dir = Path("screenshots")
        screenshots_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        save_path = screenshots_dir / f"analysis_{timestamp}.png"
        img.save(str(save_path))

        # Also create base64 for potential multimodal LLM use
        b64 = _image_to_base64(img)

        return (
            f"📸 Screenshot captured for analysis.\n"
            f"**Saved to:** `{save_path}`\n"
            f"**Resolution:** {img.size[0]}×{img.size[1]}\n"
            f"**Analysis request:** {description}\n\n"
            f"_Note: For full visual analysis, use a multimodal model like LLaVA._"
        )
    except Exception as exc:
        return f"❌ Screenshot analysis failed: {exc}"


def get_screen_capture_tools() -> list:
    """Return all screen-capture tools for agent registration."""
    return [
        capture_screenshot,
        capture_screen_region,
        get_screen_resolution,
        analyse_screenshot,
    ]
