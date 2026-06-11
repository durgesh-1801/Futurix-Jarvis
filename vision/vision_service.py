"""
Futurix Jarvis — Vision Service.

Coordinates screenshot captures and links them to the active Vision Provider
to perform visual review, terminal output analysis, and error diagnosis.
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from vision.vision_provider import VisionProviderInterface
from automation.screen_capture import _take_screenshot_pil

logger = logging.getLogger(__name__)


class VisionService:
    """Orchestrator for Jarvis's Visual Capabilities.

    Integrates standard capture commands with a swappable visual model backend.
    """

    def __init__(self, provider: VisionProviderInterface) -> None:
        self._provider = provider

    def capture_and_analyse(self, prompt: str, filename_prefix: str = "analysis") -> str:
        """Capture screen and request analysis from active vision provider."""
        img = _take_screenshot_pil()
        if img is None:
            return "❌ Vision Service: Failed to capture screen."

        try:
            screenshots_dir = Path("screenshots")
            screenshots_dir.mkdir(exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = screenshots_dir / f"{filename_prefix}_{timestamp}.png"
            img.save(str(save_path))
            
            logger.info("Captured screenshot for analysis: %s", save_path)
            
            # Send to visual provider
            result = self._provider.analyse_image(save_path, prompt)
            return (
                f"📸 **[Screenshot Saved to `{save_path}`]**\n\n"
                f"**Vision Analysis:**\n{result}"
            )
        except Exception as exc:
            logger.exception("Error during screen capture and analysis")
            return f"❌ Screen capture analysis failed: {exc}"


# ── LangChain Tools ──────────────────────────────────────────────────────────

# Module-level instance initialized by the controller
_vision_service_instance: Optional[VisionService] = None


def set_vision_service(service: VisionService) -> None:
    """Set the singleton vision service instance for tool access."""
    global _vision_service_instance
    _vision_service_instance = service


@tool
def analyse_screen(prompt: str = "Describe what you see on the screen.") -> str:
    """Capture a screenshot of the entire screen and analyze it.

    Use this when the user asks you to describe what is currently visible on their screen.

    Args:
        prompt: Question or instruction for visual evaluation.
    """
    if _vision_service_instance is None:
        return "❌ Vision service is not initialised."
    return _vision_service_instance.capture_and_analyse(prompt, "screen")


@tool
def analyse_error_screenshot(error_message: str, prompt: str = "Diagnose the visual error.") -> str:
    """Capture a screenshot and diagnose an error using the visual context and stack trace.

    Use this when an action fails with a stack trace or visual error to diagnose the cause.

    Args:
        error_message: The text of the error message or traceback.
        prompt: Specific check instructions for the vision model.
    """
    if _vision_service_instance is None:
        return "❌ Vision service is not initialised."
    combined_prompt = (
        f"The application encountered the following error:\n"
        f"```\n{error_message}\n```\n\n"
        f"Examine this screenshot and provide a diagnostic explanation: {prompt}"
    )
    return _vision_service_instance.capture_and_analyse(combined_prompt, "error")


@tool
def analyse_terminal_output(prompt: str = "Explain the compiler or shell outputs shown.") -> str:
    """Capture a screenshot and analyze terminal outputs, build logs, or compiler errors.

    Use this when you need to understand build errors, logs, or execution output in a terminal window.

    Args:
        prompt: Specific instructions for reading the terminal output.
    """
    if _vision_service_instance is None:
        return "❌ Vision service is not initialised."
    combined_prompt = f"Identify the terminal window and interpret the command output/logs: {prompt}"
    return _vision_service_instance.capture_and_analyse(combined_prompt, "terminal")


@tool
def review_ui(prompt: str = "Review the user interface design and alignment.") -> str:
    """Capture a screenshot and review the UI layout, alignment, color harmony, and formatting.

    Use this to perform visual QA or reviews on GUI windows, web designs, or applications.

    Args:
        prompt: Focus area or guidelines for UI audit.
    """
    if _vision_service_instance is None:
        return "❌ Vision service is not initialised."
    combined_prompt = f"Audit the user interface. Analyze spacing, alignments, component styling, and contrast: {prompt}"
    return _vision_service_instance.capture_and_analyse(combined_prompt, "ui_review")


def get_vision_tools() -> list:
    """Return all visual-agent tools for registration."""
    return [analyse_screen, analyse_error_screenshot, analyse_terminal_output, review_ui]
