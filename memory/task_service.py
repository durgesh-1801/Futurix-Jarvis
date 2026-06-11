"""
Futurix Jarvis — Task Memory Service.

Manages task entities, priorities, status tracking, logging notes, linking files,
and persisting everything to SQLite across restarts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

from database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class TaskService:
    """Manages project tasks, linking notes and files, and persisting states."""

    def __init__(self, db: DatabaseManager) -> None:
        self._db = db

    def add_task(
        self,
        title: str,
        description: Optional[str] = None,
        priority: str = "medium",
        due_date: Optional[str] = None,
    ) -> int:
        """Create a task. Validates priority limits."""
        clean_priority = priority.strip().lower()
        if clean_priority not in ("low", "medium", "high"):
            logger.warning("Invalid priority '%s', defaulting to 'medium'", priority)
            clean_priority = "medium"

        clean_due = due_date.strip() if due_date else None

        task_id = self._db.create_task(
            title=title,
            description=description,
            priority=clean_priority,
            due_date=clean_due,
        )
        return task_id

    def update_status(self, task_id: int, status: str, progress_note: Optional[str] = None) -> bool:
        """Transition task completion state and log status changes."""
        clean_status = status.strip().lower()
        if clean_status not in ("pending", "in_progress", "completed"):
            logger.error("Invalid status transition: %s", status)
            return False

        # Verify task exists
        task = self._db.get_task(task_id)
        if not task:
            logger.error("Task not found: %d", task_id)
            return False

        self._db.update_task_status(task_id, clean_status)

        # Log automatically
        note_text = f"Status changed to '{clean_status}'."
        if progress_note:
            note_text += f" Note: {progress_note}"
        self._db.add_task_note(task_id, note_text)
        return True


# ── LangChain Tools ──────────────────────────────────────────────────────────

# Singleton service instance set by the controller
_task_service_instance: Optional[TaskService] = None


def set_task_service(service: TaskService) -> None:
    global _task_service_instance
    _task_service_instance = service


@tool
def create_task(title: str, description: str = "", priority: str = "medium", due_date: str = "") -> str:
    """Create a new task to track progress.

    Args:
        title: Brief title representing the task.
        description: Details or instructions for the task.
        priority: Task importance level ('low', 'medium', or 'high'). Defaults to 'medium'.
        due_date: Optional due date string (e.g. YYYY-MM-DD). Defaults to empty (no due date).
    """
    if _task_service_instance is None:
        return "❌ Task service is not initialised."

    t_id = _task_service_instance.add_task(
        title=title,
        description=description,
        priority=priority,
        due_date=due_date or None,
    )
    return f"✅ **Task #{t_id} Created Successfully!**\n**Title:** {title}\n**Priority:** {priority}\n**Due Date:** {due_date or 'none'}"


@tool
def update_task_status(task_id: int, status: str, progress_note: str = "") -> str:
    """Update the status of an existing task.

    Args:
        task_id: The unique integer ID of the task.
        status: The new status state ('pending', 'in_progress', or 'completed').
        progress_note: Optional description or notes explaining what was completed.
    """
    if _task_service_instance is None:
        return "❌ Task service is not initialised."

    success = _task_service_instance.update_status(
        task_id=task_id,
        status=status,
        progress_note=progress_note or None,
    )
    if success:
        return f"✅ **Task #{task_id} status updated to '{status}'!**"
    return f"❌ Failed to update task #{task_id}. Make sure the ID exists and status is valid."


@tool
def link_file_to_task(task_id: int, file_path: str) -> str:
    """Link a specific file or document to a task.

    Args:
        task_id: The unique integer ID of the task.
        file_path: Relative or absolute path to the file.
    """
    if _task_service_instance is None:
        return "❌ Task service is not initialised."

    # Verify task exists
    task = _task_service_instance._db.get_task(task_id)
    if not task:
        return f"❌ Task #{task_id} not found."

    path = Path(file_path)
    _task_service_instance._db.add_task_file(task_id, str(path))
    # Log progress note
    _task_service_instance._db.add_task_note(task_id, f"Linked file: `{path.name}`")
    return f"✅ Linked `{file_path}` to Task #{task_id}."


@tool
def list_tasks(status: str = "", search_query: str = "") -> str:
    """List current tasks with filters.

    Args:
        status: Optional status filter ('pending', 'in_progress', or 'completed').
        search_query: Optional search keyword to filter by title or description.
    """
    if _task_service_instance is None:
        return "❌ Task service is not initialised."

    db = _task_service_instance._db
    tasks = db.get_tasks(
        status=status.strip().lower() or None,
        search_query=search_query.strip() or None,
    )
    if not tasks:
        return "📋 No tasks found matching current filters."

    lines = ["📋 **Task Board**\n"]
    lines.append("| ID | Title | Status | Priority | Due Date | Updated |")
    lines.append("|----|-------|--------|----------|----------|---------|")
    for t in tasks:
        status_emoji = "⏳"
        if t.status == "in_progress":
            status_emoji = "⚙️"
        elif t.status == "completed":
            status_emoji = "✅"
            
        due = t.due_date or "-"
        # Parse timestamp for simple layout
        try:
            dt = datetime.fromisoformat(t.updated_at)
            updated_str = dt.strftime("%Y-%m-%d %H:%M")
        except Exception:
            updated_str = t.updated_at[:16]

        lines.append(f"| #{t.id} | {t.title} | {status_emoji} *{t.status}* | **{t.priority}** | {due} | {updated_str} |")

    return "\n".join(lines)


@tool
def get_task_details(task_id: int) -> str:
    """Fetch complete details, history logs, and linked files for a task.

    Args:
        task_id: The unique integer ID of the task.
    """
    if _task_service_instance is None:
        return "❌ Task service is not initialised."

    db = _task_service_instance._db
    task = db.get_task(task_id)
    if not task:
        return f"❌ Task #{task_id} not found."

    notes = db.get_task_notes(task_id)
    files = db.get_task_files(task_id)

    lines = [f"📋 **Task #{task.id}: {task.title}**"]
    if task.description:
        lines.append(f"\n*Description:*\n{task.description}\n")
    
    lines.append(f"- **Status**: *{task.status}*")
    lines.append(f"- **Priority**: **{task.priority}**")
    lines.append(f"- **Due Date**: {task.due_date or 'none'}")
    lines.append(f"- **Created**: {task.created_at[:16]}")
    lines.append(f"- **Updated**: {task.updated_at[:16]}")

    if files:
        lines.append("\n📁 **Linked Files:**")
        for f in files:
            lines.append(f"- `{f}`")

    lines.append("\n📜 **Task History Log:**")
    if not notes:
        lines.append("*No logs recorded yet.*")
    for n in notes:
        lines.append(f"- *{n.created_at[:16]}*: {n.note}")

    return "\n".join(lines)


def get_task_tools() -> list:
    """Return all task management tools."""
    return [create_task, update_task_status, link_file_to_task, list_tasks, get_task_details]
