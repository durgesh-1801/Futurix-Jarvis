"""
Futurix Jarvis — Coding Agent Tools.

LangChain tools for code generation, Git operations, and repository
analysis — enabling a "coding assistant" mode within Jarvis.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Optional

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


# ── Git operations ───────────────────────────────────────────────────────────

def _run_git(args: list[str], cwd: Optional[str] = None) -> tuple[bool, str]:
    """Run a git command and return (success, output).

    Args:
        args: Git subcommand and arguments.
        cwd: Working directory for the git command.

    Returns:
        Tuple of (success_bool, stdout_or_stderr).
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd or os.getcwd(),
        )
        output = result.stdout.strip() or result.stderr.strip()
        return result.returncode == 0, output
    except FileNotFoundError:
        return False, "Git is not installed or not in PATH."
    except subprocess.TimeoutExpired:
        return False, "Git command timed out."
    except Exception as exc:
        return False, str(exc)


@tool
def git_status(repo_path: str = ".") -> str:
    """Get the Git status of a repository.

    Args:
        repo_path: Path to the Git repository. Defaults to current directory.
    """
    success, output = _run_git(["status", "--short"], cwd=repo_path)
    if not success:
        return f"❌ Git status failed: {output}"
    if not output:
        return "✅ Working tree is clean — no changes."
    return f"📋 **Git Status:**\n```\n{output}\n```"


@tool
def git_log(repo_path: str = ".", count: int = 10) -> str:
    """Show recent Git commit history.

    Args:
        repo_path: Path to the Git repository.
        count: Number of recent commits to display.
    """
    success, output = _run_git(
        ["log", f"-{count}", "--oneline", "--graph", "--decorate"],
        cwd=repo_path,
    )
    if not success:
        return f"❌ Git log failed: {output}"
    return f"📜 **Recent Commits:**\n```\n{output}\n```"


@tool
def git_diff(repo_path: str = ".") -> str:
    """Show the current unstaged changes in a repository.

    Args:
        repo_path: Path to the Git repository.
    """
    success, output = _run_git(["diff", "--stat"], cwd=repo_path)
    if not success:
        return f"❌ Git diff failed: {output}"
    if not output:
        return "✅ No unstaged changes."
    return f"📝 **Unstaged Changes:**\n```\n{output}\n```"


@tool
def git_branch(repo_path: str = ".") -> str:
    """List all branches in a repository.

    Args:
        repo_path: Path to the Git repository.
    """
    success, output = _run_git(["branch", "-a"], cwd=repo_path)
    if not success:
        return f"❌ Git branch failed: {output}"
    return f"🌿 **Branches:**\n```\n{output}\n```"


# ── Repository analysis ─────────────────────────────────────────────────────

@tool
def analyse_repository(repo_path: str = ".") -> str:
    """Analyse a code repository — file types, structure, and statistics.

    Args:
        repo_path: Path to the repository to analyse.
    """
    try:
        repo = Path(repo_path).resolve()
        if not repo.exists():
            return f"❌ Path not found: {repo}"

        # Collect stats
        extensions: dict[str, int] = {}
        total_files = 0
        total_lines = 0
        total_size = 0

        skip_dirs = {".git", "node_modules", "__pycache__", ".venv", "venv", ".tox", "dist", "build"}

        for file_path in repo.rglob("*"):
            if file_path.is_file():
                # Skip hidden/build directories
                if any(part in skip_dirs for part in file_path.parts):
                    continue
                total_files += 1
                ext = file_path.suffix.lower() or "(no ext)"
                extensions[ext] = extensions.get(ext, 0) + 1
                total_size += file_path.stat().st_size

                # Count lines for text files
                if ext in (".py", ".js", ".ts", ".java", ".cpp", ".c", ".h",
                           ".go", ".rs", ".rb", ".md", ".txt", ".json", ".yaml",
                           ".yml", ".toml", ".html", ".css", ".sql"):
                    try:
                        total_lines += len(file_path.read_text(encoding="utf-8", errors="replace").splitlines())
                    except Exception:
                        pass

        # Sort extensions by count
        sorted_exts = sorted(extensions.items(), key=lambda x: x[1], reverse=True)[:15]

        lines = [f"📊 **Repository Analysis: {repo.name}**\n"]
        lines.append(f"| Metric | Value |")
        lines.append(f"|--------|-------|")
        lines.append(f"| Total Files | {total_files} |")
        lines.append(f"| Total Lines | {total_lines:,} |")
        lines.append(f"| Total Size | {total_size / 1024 / 1024:.1f} MB |")
        lines.append(f"\n**File Types:**\n")
        lines.append("| Extension | Count |")
        lines.append("|-----------|-------|")
        for ext, count in sorted_exts:
            lines.append(f"| {ext} | {count} |")

        return "\n".join(lines)
    except Exception as exc:
        return f"❌ Repository analysis failed: {exc}"


# ── Code generation ──────────────────────────────────────────────────────────

@tool
def generate_code_file(file_path: str, description: str, language: str = "python") -> str:
    """Generate a code file based on a description.

    The actual code generation is handled by the LLM — this tool creates
    the file and returns instructions for the LLM to fill it.

    Args:
        file_path: Where to save the generated code file.
        description: What the code should do.
        language: Programming language (default: python).
    """
    try:
        path = Path(file_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        # Create a template file
        ext_map = {
            "python": ".py", "javascript": ".js", "typescript": ".ts",
            "java": ".java", "cpp": ".cpp", "c": ".c", "go": ".go",
            "rust": ".rs", "html": ".html", "css": ".css",
        }
        expected_ext = ext_map.get(language.lower(), f".{language}")
        if not path.suffix:
            path = path.with_suffix(expected_ext)

        # The LLM should generate the content — we create a placeholder
        header = f"# Generated by Futurix Jarvis\n# Description: {description}\n# Language: {language}\n\n"
        path.write_text(header, encoding="utf-8")

        return (
            f"✅ Code file created: `{path}`\n"
            f"**Language:** {language}\n"
            f"**Description:** {description}\n\n"
            f"_Fill this file with the appropriate implementation._"
        )
    except Exception as exc:
        return f"❌ Failed to create code file: {exc}"


@tool
def read_code_file(file_path: str) -> str:
    """Read a code file and return its contents with syntax highlighting info.

    Args:
        file_path: Path to the code file to read.
    """
    try:
        path = Path(file_path).resolve()
        if not path.exists():
            return f"❌ File not found: {path}"

        content = path.read_text(encoding="utf-8", errors="replace")
        lang = path.suffix.lstrip(".")
        line_count = len(content.splitlines())

        if len(content) > 8000:
            content = content[:8000] + "\n\n... (truncated)"

        return (
            f"📄 **{path.name}** ({line_count} lines, {lang})\n\n"
            f"```{lang}\n{content}\n```"
        )
    except Exception as exc:
        return f"❌ Failed to read code file: {exc}"


def get_coding_tools() -> list:
    """Return all coding-agent tools for agent registration."""
    return [
        git_status,
        git_log,
        git_diff,
        git_branch,
        analyse_repository,
        generate_code_file,
        read_code_file,
    ]
