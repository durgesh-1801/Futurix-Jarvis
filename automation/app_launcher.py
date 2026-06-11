"""
Futurix Jarvis — Application Launcher Tools.

LangChain-compatible tools for opening and closing desktop applications
on Windows.  Each function is decorated with ``@tool`` so the agent can
invoke them via tool-calling.
"""

from __future__ import annotations

import logging
import os
import subprocess
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# ── Known application paths (Windows) ────────────────────────────────────────

_APP_PATHS: dict[str, list[str]] = {
    "chrome": [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ],
    "vscode": [
        r"C:\Users\{user}\AppData\Local\Programs\Microsoft VS Code\Code.exe",
        r"C:\Program Files\Microsoft VS Code\Code.exe",
    ],
    "calculator": ["calc.exe"],
    "notepad": ["notepad.exe"],
    "explorer": ["explorer.exe"],
    "cmd": ["cmd.exe"],
    "powershell": ["powershell.exe"],
    "task_manager": ["taskmgr.exe"],
    "paint": ["mspaint.exe"],
    "snipping_tool": ["SnippingTool.exe"],
    "settings": ["ms-settings:"],
    "edge": [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ],
}


def _find_app_path(app_name: str) -> Optional[str]:
    """Resolve an app name to an executable path.

    Args:
        app_name: The normalised application name.

    Returns:
        The first existing path, or None.
    """
    username = os.getenv("USERNAME", "user")
    candidates = _APP_PATHS.get(app_name, [])
    for path in candidates:
        resolved = path.replace("{user}", username)
        if os.path.exists(resolved) or not os.path.sep in resolved:
            return resolved
    return None


# ── LangChain Tools ──────────────────────────────────────────────────────────

@tool
def open_chrome() -> str:
    """Open the Google Chrome web browser."""
    path = _find_app_path("chrome")
    if path:
        subprocess.Popen([path], shell=False)
        return "✅ Google Chrome opened successfully."
    # Fallback: try system default
    try:
        os.startfile("chrome")  # type: ignore[attr-defined]
        return "✅ Chrome opened via system default."
    except Exception:
        return "❌ Chrome not found. Is it installed?"


@tool
def open_vscode() -> str:
    """Open Visual Studio Code editor."""
    path = _find_app_path("vscode")
    if path and os.path.exists(path):
        subprocess.Popen([path], shell=False)
        return "✅ VS Code opened successfully."
    # Fallback: try 'code' command
    try:
        subprocess.Popen(["code"], shell=True)
        return "✅ VS Code opened via PATH."
    except Exception:
        return "❌ VS Code not found. Is it installed?"


@tool
def open_calculator() -> str:
    """Open the Windows Calculator application."""
    try:
        subprocess.Popen(["calc.exe"])
        return "✅ Calculator opened successfully."
    except Exception as exc:
        return f"❌ Could not open Calculator: {exc}"


@tool
def open_file_explorer(path: str = "") -> str:
    """Open Windows File Explorer, optionally at a specific path.

    Args:
        path: Optional directory path to open. Opens default location if empty.
    """
    try:
        if path and os.path.exists(path):
            subprocess.Popen(["explorer.exe", path])
            return f"✅ File Explorer opened at: {path}"
        else:
            subprocess.Popen(["explorer.exe"])
            return "✅ File Explorer opened."
    except Exception as exc:
        return f"❌ Could not open File Explorer: {exc}"


@tool
def open_notepad(file_path: str = "") -> str:
    """Open Notepad, optionally with a specific file.

    Args:
        file_path: Optional file path to open in Notepad.
    """
    try:
        cmd = ["notepad.exe"]
        if file_path:
            cmd.append(file_path)
        subprocess.Popen(cmd)
        return "✅ Notepad opened successfully."
    except Exception as exc:
        return f"❌ Could not open Notepad: {exc}"


@tool
def open_application(app_name: str) -> str:
    """Open a Windows application by name.

    Args:
        app_name: Name of the application to open (e.g., 'chrome', 'vscode',
                  'calculator', 'notepad', 'paint', 'cmd', 'powershell').
    """
    normalised = app_name.lower().strip().replace(" ", "_")
    path = _find_app_path(normalised)

    if path:
        try:
            if path.startswith("ms-"):
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen([path], shell=False)
            return f"✅ {app_name} opened successfully."
        except Exception as exc:
            return f"❌ Could not open {app_name}: {exc}"

    # Try launching directly (for apps in PATH)
    try:
        subprocess.Popen([normalised], shell=True)
        return f"✅ {app_name} opened via system PATH."
    except Exception as exc:
        return f"❌ Could not find or open '{app_name}': {exc}"


@tool
def close_application(app_name: str) -> str:
    """Close a running application by name.

    Args:
        app_name: The process name to terminate (e.g., 'chrome', 'notepad').
    """
    import psutil

    normalised = app_name.lower().strip()
    # Map friendly names to process names
    process_map = {
        "chrome": "chrome.exe",
        "vscode": "Code.exe",
        "vs code": "Code.exe",
        "calculator": "CalculatorApp.exe",
        "notepad": "notepad.exe",
        "edge": "msedge.exe",
        "paint": "mspaint.exe",
    }
    target = process_map.get(normalised, f"{normalised}.exe")
    killed = 0

    for proc in psutil.process_iter(["name"]):
        try:
            if proc.info["name"] and proc.info["name"].lower() == target.lower():
                proc.terminate()
                killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    if killed > 0:
        return f"✅ Closed {killed} instance(s) of {app_name}."
    return f"⚠️ No running instances of {app_name} found."


# ── Convenience: collect all tools ───────────────────────────────────────────

def get_app_launcher_tools() -> list:
    """Return all application-launcher tools for agent registration."""
    return [
        open_chrome,
        open_vscode,
        open_calculator,
        open_file_explorer,
        open_notepad,
        open_application,
        close_application,
    ]
