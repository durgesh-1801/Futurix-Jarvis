"""
Futurix Jarvis — System Command Tools.

LangChain tools for executing shell commands, shutdown, and restart.
All destructive operations require explicit confirmation (``confirmed=True``).
"""

from __future__ import annotations

import logging
import os
import subprocess

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def execute_command(command: str, confirmed: bool = False) -> str:
    """Execute a shell command and return its output.

    For safety, the ``confirmed`` flag must be explicitly set to True.
    If False, a confirmation prompt is returned instead.

    Args:
        command: The shell command to execute.
        confirmed: Must be True to actually execute the command.
    """
    if not confirmed:
        return (
            f"⚠️ **Confirmation required to execute command:**\n\n"
            f"```\n{command}\n```\n\n"
            f"Please confirm by saying: *\"Yes, run that command\"*"
        )

    try:
        logger.info("Executing command: %s", command)
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=os.path.expanduser("~"),
        )
        output = result.stdout.strip()
        error = result.stderr.strip()

        response = f"✅ **Command executed** (exit code: {result.returncode})\n"
        if output:
            response += f"\n**Output:**\n```\n{output[:3000]}\n```"
        if error:
            response += f"\n**Errors:**\n```\n{error[:1000]}\n```"
        if not output and not error:
            response += "\n(No output)"
        return response

    except subprocess.TimeoutExpired:
        return f"⏰ Command timed out after 30 seconds:\n```\n{command}\n```"
    except Exception as exc:
        return f"❌ Failed to execute command: {exc}"


@tool
def shutdown_system(confirmed: bool = False) -> str:
    """Shut down the computer. Requires explicit confirmation.

    Args:
        confirmed: Must be True to initiate shutdown.
    """
    if not confirmed:
        return (
            "⚠️ **Are you sure you want to shut down the computer?**\n\n"
            "All unsaved work will be lost.\n"
            "Confirm by saying: *\"Yes, shut down the computer\"*"
        )
    try:
        logger.warning("System shutdown initiated by user.")
        os.system("shutdown /s /t 30")
        return "🔴 **Shutdown initiated.** The computer will shut down in 30 seconds.\nRun `shutdown /a` to cancel."
    except Exception as exc:
        return f"❌ Failed to initiate shutdown: {exc}"


@tool
def restart_system(confirmed: bool = False) -> str:
    """Restart the computer. Requires explicit confirmation.

    Args:
        confirmed: Must be True to initiate restart.
    """
    if not confirmed:
        return (
            "⚠️ **Are you sure you want to restart the computer?**\n\n"
            "All unsaved work will be lost.\n"
            "Confirm by saying: *\"Yes, restart the computer\"*"
        )
    try:
        logger.warning("System restart initiated by user.")
        os.system("shutdown /r /t 30")
        return "🔄 **Restart initiated.** The computer will restart in 30 seconds.\nRun `shutdown /a` to cancel."
    except Exception as exc:
        return f"❌ Failed to initiate restart: {exc}"


@tool
def lock_screen() -> str:
    """Lock the Windows screen."""
    try:
        import ctypes
        ctypes.windll.user32.LockWorkStation()
        return "🔒 Screen locked."
    except Exception as exc:
        return f"❌ Failed to lock screen: {exc}"


def get_system_command_tools() -> list:
    """Return all system-command tools for agent registration."""
    return [execute_command, shutdown_system, restart_system, lock_screen]
