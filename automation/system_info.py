"""
Futurix Jarvis — System Information Tools.

LangChain tools powered by ``psutil`` for reading battery, CPU, RAM,
disk, and general system information.
"""

from __future__ import annotations

import ctypes
import logging
import os
import platform
import socket
from datetime import datetime, timezone

import psutil
from dotenv import load_dotenv
from langchain_core.tools import tool

logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class SYSTEM_POWER_STATUS(ctypes.Structure):
    _fields_ = [
        ('ACLineStatus', ctypes.c_byte),
        ('BatteryFlag', ctypes.c_byte),
        ('BatteryLifePercent', ctypes.c_byte),
        ('SystemStatusFlag', ctypes.c_byte),
        ('BatteryLifeTime', ctypes.c_ulong),
        ('BatteryFullLifeTime', ctypes.c_ulong),
    ]



@tool
def get_system_info() -> str:
    """Get general system information including OS, hostname, CPU, and memory."""
    try:
        uname = platform.uname()
        mem = psutil.virtual_memory()
        boot = datetime.fromtimestamp(psutil.boot_time(), tz=timezone.utc)

        info = (
            f"🖥️ **System Information**\n\n"
            f"| Property | Value |\n"
            f"|----------|-------|\n"
            f"| Hostname | {socket.gethostname()} |\n"
            f"| OS | {uname.system} {uname.release} |\n"
            f"| Version | {uname.version} |\n"
            f"| Architecture | {uname.machine} |\n"
            f"| Processor | {uname.processor or platform.processor()} |\n"
            f"| CPU Cores | {psutil.cpu_count(logical=False)} physical, "
            f"{psutil.cpu_count(logical=True)} logical |\n"
            f"| Total RAM | {mem.total / (1024**3):.1f} GB |\n"
            f"| Python | {platform.python_version()} |\n"
            f"| Boot Time | {boot.strftime('%Y-%m-%d %H:%M UTC')} |\n"
        )
        return info
    except Exception as exc:
        return f"❌ Failed to get system info: {exc}"


@tool
def get_battery_status() -> str:
    """Get the current battery percentage, power status, and estimated time remaining."""
    try:
        battery = psutil.sensors_battery()

        logger.info(
            f"Raw battery object: "
            f"percent={battery.percent if battery else None}, "
            f"secsleft={battery.secsleft if battery else None}, "
            f"power_plugged={battery.power_plugged if battery else None}"
        )

        win_status = SYSTEM_POWER_STATUS()
        win_api_success = False
        if platform.system() == "Windows":
            try:
                win_api_success = bool(ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(win_status)))
            except Exception as e:
                logger.error(f"Failed to query GetSystemPowerStatus: {e}")

        if win_api_success:
            logger.info(
                f"Raw Windows API: "
                f"ACLineStatus={win_status.ACLineStatus}, "
                f"BatteryFlag={win_status.BatteryFlag}, "
                f"BatteryLifePercent={win_status.BatteryLifePercent}, "
                f"SystemStatusFlag={win_status.SystemStatusFlag}, "
                f"BatteryLifeTime={win_status.BatteryLifeTime}, "
                f"BatteryFullLifeTime={win_status.BatteryFullLifeTime}"
            )
        else:
            logger.info("Raw Windows API: Not available or failed to query")

        if battery is None:
            debug_mode = os.environ.get("DEBUG_BATTERY_TOOL", "false").lower() == "true"
            msg = "🔌 No battery detected — this may be a desktop computer."
            if debug_mode:
                msg += f"\n\nRaw Battery:\npercent=None\nsecsleft=None\npower_plugged=None"
                if win_api_success:
                    msg += (
                        f"\n\nRaw Windows API:\n"
                        f"ACLineStatus={win_status.ACLineStatus}\n"
                        f"BatteryFlag={win_status.BatteryFlag}\n"
                        f"BatteryLifePercent={win_status.BatteryLifePercent}\n"
                        f"SystemStatusFlag={win_status.SystemStatusFlag}\n"
                        f"BatteryLifeTime={win_status.BatteryLifeTime}\n"
                        f"BatteryFullLifeTime={win_status.BatteryFullLifeTime}"
                    )
            return msg

        percent = battery.percent
        plugged = "🔌 Plugged in" if battery.power_plugged else "🔋 On battery"
        time_left = ""
        if battery.secsleft > 0 and not battery.power_plugged:
            hours, remainder = divmod(battery.secsleft, 3600)
            minutes = remainder // 60
            time_left = f"\n⏱️ Estimated time remaining: {int(hours)}h {int(minutes)}m"

        # Emoji indicator
        if percent > 80:
            icon = "🟢"
        elif percent > 40:
            icon = "🟡"
        else:
            icon = "🔴"

        result = f"{icon} **Battery: {percent}%** — {plugged}{time_left}"

        # Diagnostic output in debug mode
        debug_mode = os.environ.get("DEBUG_BATTERY_TOOL", "false").lower() == "true"
        if debug_mode:
            result += (
                f"\n\nRaw Battery:\n"
                f"percent={battery.percent}\n"
                f"secsleft={battery.secsleft}\n"
                f"power_plugged={battery.power_plugged}"
            )
            if win_api_success:
                result += (
                    f"\n\nRaw Windows API:\n"
                    f"ACLineStatus={win_status.ACLineStatus}\n"
                    f"BatteryFlag={win_status.BatteryFlag}\n"
                    f"BatteryLifePercent={win_status.BatteryLifePercent}\n"
                    f"SystemStatusFlag={win_status.SystemStatusFlag}\n"
                    f"BatteryLifeTime={win_status.BatteryLifeTime}\n"
                    f"BatteryFullLifeTime={win_status.BatteryFullLifeTime}"
                )

        return result
    except Exception as exc:
        return f"❌ Failed to get battery status: {exc}"


@tool
def get_resource_usage() -> str:
    """Get current CPU, RAM, and disk usage statistics."""
    try:
        cpu_percent = psutil.cpu_percent(interval=1)
        cpu_freq = psutil.cpu_freq()
        mem = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        freq_str = f"{cpu_freq.current:.0f} MHz" if cpu_freq else "N/A"

        info = (
            f"📊 **Resource Usage**\n\n"
            f"| Resource | Usage | Details |\n"
            f"|----------|-------|---------|\n"
            f"| CPU | {cpu_percent}% | {freq_str} |\n"
            f"| RAM | {mem.percent}% | "
            f"{mem.used / (1024**3):.1f} / {mem.total / (1024**3):.1f} GB |\n"
            f"| Disk (C:) | {disk.percent}% | "
            f"{disk.used / (1024**3):.0f} / {disk.total / (1024**3):.0f} GB |\n"
        )
        return info
    except Exception as exc:
        return f"❌ Failed to get resource usage: {exc}"


@tool
def get_running_processes(top_n: int = 10) -> str:
    """List the top processes by memory usage.

    Args:
        top_n: Number of top processes to display (default: 10).
    """
    try:
        processes = []
        for proc in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
            try:
                info = proc.info
                if info["memory_percent"] is not None:
                    processes.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        # Sort by memory usage
        processes.sort(key=lambda x: x["memory_percent"] or 0, reverse=True)
        top = processes[:top_n]

        lines = [f"📋 **Top {top_n} Processes by Memory**\n"]
        lines.append("| PID | Name | Memory % | CPU % |")
        lines.append("|-----|------|----------|-------|")
        for p in top:
            lines.append(
                f"| {p['pid']} | {p['name'][:30]} | "
                f"{p['memory_percent']:.1f}% | {p['cpu_percent']:.1f}% |"
            )
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Failed to list processes: {exc}"


def get_system_info_tools() -> list:
    """Return all system-information tools for agent registration."""
    return [
        get_system_info,
        get_battery_status,
        get_resource_usage,
        get_running_processes,
    ]
