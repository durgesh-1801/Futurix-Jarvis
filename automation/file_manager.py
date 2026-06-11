"""
Futurix Jarvis — File Management Tools.

LangChain tools for creating, listing, and reading files and folders.
Delete operations include a safety mechanism requiring explicit confirmation.
"""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


@tool
def create_folder(path: str) -> str:
    """Create a new folder at the specified path.

    Args:
        path: Absolute or relative path for the new folder.
              Parent directories are created automatically.
    """
    try:
        folder = Path(path).expanduser().resolve()
        folder.mkdir(parents=True, exist_ok=True)
        return f"✅ Folder created: {folder}"
    except Exception as exc:
        return f"❌ Failed to create folder: {exc}"


@tool
def create_text_file(path: str, content: str = "") -> str:
    """Create a text file with optional content.

    Args:
        path: The file path to create.
        content: Text content to write into the file.
    """
    try:
        file_path = Path(path).expanduser().resolve()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content, encoding="utf-8")
        return f"✅ File created: {file_path} ({len(content)} characters)"
    except Exception as exc:
        return f"❌ Failed to create file: {exc}"


@tool
def read_text_file(path: str) -> str:
    """Read and return the contents of a text file.

    Args:
        path: Path to the text file to read.
    """
    try:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            return f"❌ File not found: {file_path}"
        if not file_path.is_file():
            return f"❌ Path is not a file: {file_path}"
        content = file_path.read_text(encoding="utf-8")
        if len(content) > 5000:
            return f"📄 File: {file_path.name} (showing first 5000 chars)\n\n{content[:5000]}…"
        return f"📄 File: {file_path.name}\n\n{content}"
    except Exception as exc:
        return f"❌ Failed to read file: {exc}"


@tool
def list_directory(path: str = ".") -> str:
    """List the contents of a directory.

    Args:
        path: Directory path to list. Defaults to current directory.
    """
    try:
        dir_path = Path(path).expanduser().resolve()
        if not dir_path.exists():
            return f"❌ Directory not found: {dir_path}"
        if not dir_path.is_dir():
            return f"❌ Path is not a directory: {dir_path}"

        items = sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
        lines = [f"📁 Contents of: {dir_path}\n"]
        for item in items[:100]:  # Cap at 100 items
            if item.is_dir():
                lines.append(f"  📂 {item.name}/")
            else:
                size = item.stat().st_size
                lines.append(f"  📄 {item.name}  ({_format_size(size)})")
        if len(items) > 100:
            lines.append(f"\n  … and {len(items) - 100} more items")
        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Failed to list directory: {exc}"


@tool
def delete_file(path: str, confirmed: bool = False) -> str:
    """Delete a file. Requires explicit confirmation for safety.

    Args:
        path: Path to the file to delete.
        confirmed: Must be True to actually perform the deletion.
                   If False, returns a confirmation prompt.
    """
    try:
        file_path = Path(path).expanduser().resolve()
        if not file_path.exists():
            return f"❌ File not found: {file_path}"

        if not confirmed:
            return (
                f"⚠️ **Confirmation required.**\n\n"
                f"You are about to delete: `{file_path}`\n\n"
                f"Please confirm by saying: *\"Yes, delete {file_path.name}\"*"
            )

        file_path.unlink()
        return f"✅ File deleted: {file_path}"
    except Exception as exc:
        return f"❌ Failed to delete file: {exc}"


@tool
def delete_folder(path: str, confirmed: bool = False) -> str:
    """Delete a folder and all its contents. Requires explicit confirmation.

    Args:
        path: Path to the folder to delete.
        confirmed: Must be True to actually perform the deletion.
    """
    try:
        folder = Path(path).expanduser().resolve()
        if not folder.exists():
            return f"❌ Folder not found: {folder}"

        if not confirmed:
            item_count = sum(1 for _ in folder.rglob("*"))
            return (
                f"⚠️ **Confirmation required.**\n\n"
                f"You are about to delete: `{folder}`\n"
                f"This folder contains **{item_count}** items.\n\n"
                f"Please confirm by saying: *\"Yes, delete the folder\"*"
            )

        shutil.rmtree(folder)
        return f"✅ Folder deleted: {folder}"
    except Exception as exc:
        return f"❌ Failed to delete folder: {exc}"


@tool
def move_file(source: str, destination: str) -> str:
    """Move a file or folder to a new location.

    Args:
        source: Current path of the file or folder.
        destination: New path for the file or folder.
    """
    try:
        src = Path(source).expanduser().resolve()
        dst = Path(destination).expanduser().resolve()
        if not src.exists():
            return f"❌ Source not found: {src}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(src), str(dst))
        return f"✅ Moved: {src.name} → {dst}"
    except Exception as exc:
        return f"❌ Failed to move: {exc}"


@tool
def copy_file(source: str, destination: str) -> str:
    """Copy a file or folder to a new location.

    Args:
        source: Path of the file or folder to copy.
        destination: Destination path.
    """
    try:
        src = Path(source).expanduser().resolve()
        dst = Path(destination).expanduser().resolve()
        if not src.exists():
            return f"❌ Source not found: {src}"
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(str(src), str(dst))
        else:
            shutil.copy2(str(src), str(dst))
        return f"✅ Copied: {src.name} → {dst}"
    except Exception as exc:
        return f"❌ Failed to copy: {exc}"


def _format_size(size_bytes: int) -> str:
    """Format byte count to human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.0f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def get_file_manager_tools() -> list:
    """Return all file-management tools for agent registration."""
    return [
        create_folder,
        create_text_file,
        read_text_file,
        list_directory,
        delete_file,
        delete_folder,
        move_file,
        copy_file,
    ]
