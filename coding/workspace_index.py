"""
Futurix Jarvis — Workspace Indexer.

Parses workspace files recursively, extracts Python AST symbol definitions,
computes codebase metrics (LOC, languages, frameworks, dependencies), and persists
them in SQLite to enable precise contextual coding assistance.
"""

from __future__ import annotations

import ast
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langchain_core.tools import tool

from database.db_manager import DatabaseManager
from llm.llm_service import LLMService

logger = logging.getLogger(__name__)


class WorkspaceIndexer:
    """Recursively indexes codebases, parses symbols, and stores summaries in SQLite."""

    def __init__(self, db: DatabaseManager, llm: Optional[LLMService] = None) -> None:
        self._db = db
        self._llm = llm

    def index_directory(self, root_dir: Path) -> dict[str, int]:
        """Index all files and parse Python symbols from the directory."""
        root_dir = Path(root_dir).resolve()
        if not root_dir.exists() or not root_dir.is_dir():
            logger.error("Workspace directory does not exist or is not a folder: %s", root_dir)
            return {"files_indexed": 0, "symbols_extracted": 0}

        # Clear existing cached symbols for files in this workspace
        self._db.clear_code_symbols()

        total_files = 0
        total_loc = 0
        total_symbols = 0

        # Stats for summary
        languages: set[str] = set()
        frameworks: set[str] = set()
        dependency_files: list[str] = []

        skip_dirs = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            ".tox", "dist", "build", "target", ".idea", ".vscode", "eggs"
        }

        # Extensions and files scanning
        for file_path in root_dir.rglob("*"):
            if any(part in skip_dirs for part in file_path.parts):
                continue

            if file_path.is_file():
                suffix = file_path.suffix.lower()
                name = file_path.name.lower()

                # Detect dependencies
                if name in ("requirements.txt", "package.json", "cargo.toml", "go.mod", "pyproject.toml", "setup.py"):
                    dependency_files.append(file_path.name)
                    self._parse_dependency_file(file_path, frameworks)

                # Count files & detect language
                lang = self._detect_language(suffix)
                if lang:
                    languages.add(lang)

                # Index lines of code (LOC)
                if suffix in (".py", ".js", ".ts", ".tsx", ".jsx", ".java", ".cpp", ".c", ".h", ".rs", ".go", ".sh", ".yaml", ".toml", ".sql", ".css", ".html", ".md"):
                    total_files += 1
                    try:
                        lines = file_path.read_text(encoding="utf-8", errors="replace").splitlines()
                        total_loc += len(lines)
                    except Exception:
                        pass

                # AST symbol extraction for Python
                if suffix == ".py":
                    symbols_count = self._index_python_ast(file_path, root_dir)
                    total_symbols += symbols_count

        # Fallback project name
        project_name = root_dir.name

        # Generate summary (use LLM if online, otherwise fallback to template)
        summary_text = self._generate_summary_text(
            project_name, len(languages), total_files, total_loc, list(languages), list(frameworks), dependency_files
        )

        # Cache in Database
        self._db.store_repository_summary(
            repo_path=str(root_dir),
            project_name=project_name,
            languages=list(languages),
            frameworks=list(frameworks),
            dependencies=dependency_files,
            total_files=total_files,
            total_lines=total_loc,
            summary=summary_text
        )

        logger.info(
            "Workspace indexing completed: %d files, %d LOC, %d symbols parsed.",
            total_files, total_loc, total_symbols
        )
        return {
            "files_indexed": total_files,
            "lines_of_code": total_loc,
            "symbols_extracted": total_symbols,
        }

    def _detect_language(self, suffix: str) -> Optional[str]:
        mapping = {
            ".py": "Python",
            ".js": "JavaScript",
            ".ts": "TypeScript",
            ".jsx": "React JS",
            ".tsx": "React TS",
            ".rs": "Rust",
            ".go": "Go",
            ".cpp": "C++",
            ".c": "C",
            ".h": "C/C++ Header",
            ".java": "Java",
            ".sh": "Shell Script",
            ".bat": "Batch Script",
            ".sql": "SQL Database",
            ".html": "HTML Layout",
            ".css": "CSS Styles",
        }
        return mapping.get(suffix)

    def _parse_dependency_file(self, file_path: Path, frameworks: set[str]) -> None:
        """Parse configuration files to identify frameworks used."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace").lower()
            # Basic matching rules
            rules = {
                "django": "Django",
                "flask": "Flask",
                "fastapi": "FastAPI",
                "pyqt": "PyQt",
                "py side": "PySide",
                "langchain": "LangChain",
                "react": "React",
                "next": "Next.js",
                "vue": "Vue.js",
                "angular": "Angular",
                "express": "Express.js",
                "actix": "Actix-web",
                "tokio": "Tokio",
                "gin": "Gin Gonic",
            }
            for key, val in rules.items():
                if key in content:
                    frameworks.add(val)
        except Exception:
            pass

    def _index_python_ast(self, file_path: Path, root_dir: Path) -> int:
        """Parse Python source file AST and insert classes, functions, and imports into SQLite."""
        try:
            code = file_path.read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(code, filename=str(file_path))
        except Exception as exc:
            logger.warning("AST parse failed for %s: %s", file_path.name, exc)
            return 0

        rel_path = str(file_path.relative_to(root_dir))
        symbols_added = 0

        class ASTVisitor(ast.NodeVisitor):
            def __init__(self, db: DatabaseManager, rel_path: str) -> None:
                self.db = db
                self.rel_path = rel_path
                self.current_class: Optional[str] = None
                self.count = 0

            def visit_ClassDef(self, node: ast.ClassDef) -> None:
                docstring = ast.get_docstring(node) or ""
                details = {
                    "base_classes": [ast.unparse(b) for b in node.bases],
                    "docstring": docstring[:200]
                }
                import json
                self.db.store_code_symbol(
                    file_path=self.rel_path,
                    symbol_name=node.name,
                    symbol_type="class",
                    line_number=node.lineno,
                    end_line_number=node.end_lineno,
                    parent_name=None,
                    details=json.dumps(details)
                )
                self.count += 1
                
                # Walk methods inside the class
                old_class = self.current_class
                self.current_class = node.name
                self.generic_visit(node)
                self.current_class = old_class

            def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
                docstring = ast.get_docstring(node) or ""
                # Parse function parameters
                args = [arg.arg for arg in node.args.args]
                ret = ast.unparse(node.returns) if node.returns else None
                details = {
                    "args": args,
                    "returns": ret,
                    "docstring": docstring[:200]
                }
                import json
                self.db.store_code_symbol(
                    file_path=self.rel_path,
                    symbol_name=node.name,
                    symbol_type="function",
                    line_number=node.lineno,
                    end_line_number=node.end_lineno,
                    parent_name=self.current_class,
                    details=json.dumps(details)
                )
                self.count += 1
                self.generic_visit(node)

            def visit_Import(self, node: ast.Import) -> None:
                names = [alias.name for alias in node.names]
                import json
                for name in names:
                    self.db.store_code_symbol(
                        file_path=self.rel_path,
                        symbol_name=name,
                        symbol_type="import",
                        line_number=node.lineno,
                        end_line_number=None,
                        parent_name=None,
                        details=json.dumps({"imported_from": None})
                    )
                    self.count += 1

            def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
                if node.module:
                    import json
                    for alias in node.names:
                        self.db.store_code_symbol(
                            file_path=self.rel_path,
                            symbol_name=alias.name,
                            symbol_type="import",
                            line_number=node.lineno,
                            end_line_number=None,
                            parent_name=None,
                            details=json.dumps({"imported_from": node.module})
                        )
                        self.count += 1

        visitor = ASTVisitor(self._db, rel_path)
        visitor.visit(tree)
        return visitor.count

    def _generate_summary_text(
        self,
        project_name: str,
        lang_count: int,
        files_count: int,
        loc: int,
        langs: list[str],
        frams: list[str],
        deps: list[str]
    ) -> str:
        """Call LLM to get a structural architecture description or return fallback template."""
        prompt = (
            f"Write a short, professional architectural repository summary for the project '{project_name}'.\n"
            f"Here are the code stats gathered:\n"
            f"- File count: {files_count}\n"
            f"- Total Lines of Code: {loc}\n"
            f"- Languages: {', '.join(langs)}\n"
            f"- Frameworks: {', '.join(frams) if frams else 'None detected'}\n"
            f"- Config/Dependency files found: {', '.join(deps) if deps else 'None'}\n\n"
            f"Focus on giving a neat developer description of the project structure and primary stack."
        )

        if self._llm and self._llm.is_available:
            try:
                response = self._llm.generate(prompt)
                if response:
                    return response.strip()
            except Exception as exc:
                logger.warning("LLM summary generation failed: %s", exc)

        # Safe static template fallback
        return (
            f"### Architectural Repository Summary for `{project_name}`\n\n"
            f"This project is structured around **{files_count} files** containing approximately **{loc:,} lines of code**.\n\n"
            f"- **Stack**: Primarily coded in **{', '.join(langs)}**.\n"
            f"- **Frameworks/Libs**: {', '.join(frams) if frams else 'No major web frameworks detected'}.\n"
            f"- **Configuration Files**: {', '.join(deps) if deps else 'No package manifests found'}.\n\n"
            f"The codebase contains recursive folder hierarchies. Python files are parsed for classes, "
            f"functions, and modular imports to assist with code symbol searches."
        )


# ── LangChain Tools ──────────────────────────────────────────────────────────

# Singleton indexer setup by the controller
_workspace_indexer_instance: Optional[WorkspaceIndexer] = None


def set_workspace_indexer(indexer: WorkspaceIndexer) -> None:
    global _workspace_indexer_instance
    _workspace_indexer_instance = indexer


@tool
def index_workspace(directory: str = ".") -> str:
    """Walk and parse all source files and python AST definitions recursively.

    Use this when the user asks you to analyze their project, look for classes/functions,
    or index a directory to understand the codebase.

    Args:
        directory: The local path of the project to index. Defaults to current dir.
    """
    if _workspace_indexer_instance is None:
        return "❌ Workspace indexer is not initialised."
    
    path = Path(directory)
    stats = _workspace_indexer_instance.index_directory(path)
    return (
        f"✅ **Workspace Indexed Successfully!**\n\n"
        f"| Metric | Value |\n"
        f"|--------|-------|\n"
        f"| Directory | `{path.resolve()}` |\n"
        f"| Code Files | {stats['files_indexed']} |\n"
        f"| Lines of Code | {stats['lines_of_code']:,} |\n"
        f"| AST Symbols Cached | {stats['symbols_extracted']} |"
    )


@tool
def search_code_symbols(query: str, symbol_type: str = "") -> str:
    """Query the indexed workspace database for symbols matching the query.

    Matches class names, function names, or imports across files.

    Args:
        query: Name or partial term of class/function/import.
        symbol_type: Optional filter: 'class', 'function', or 'import'.
    """
    if _workspace_indexer_instance is None:
        return "❌ Workspace indexer is not initialised."
    
    db = _workspace_indexer_instance._db
    records = db.search_code_symbols(query, symbol_type or None)
    if not records:
        return f"🔍 No code symbols found matching: **{query}** (type: {symbol_type or 'all'})"

    lines = [f"🔍 **Found {len(records)} matching symbol(s):**\n"]
    lines.append("| Name | Type | File | Line | Parent | Details |")
    lines.append("|------|------|------|------|--------|---------|")
    
    for r in records[:30]:  # limit to top 30
        parent = r.parent_name or "-"
        import json
        details_text = "-"
        if r.details:
            try:
                dt = json.loads(r.details)
                if r.symbol_type == "function":
                    details_text = f"args: {dt.get('args', [])}"
                elif r.symbol_type == "class":
                    details_text = f"bases: {dt.get('base_classes', [])}"
                elif r.symbol_type == "import":
                    details_text = f"from: {dt.get('imported_from', '-')}"
            except Exception:
                pass
        lines.append(f"| `{r.symbol_name}` | *{r.symbol_type}* | `{r.file_path}` | {r.line_number} | `{parent}` | {details_text} |")

    if len(records) > 30:
        lines.append(f"\n*Showed top 30 of {len(records)} symbols.*")
    return "\n".join(lines)


@tool
def get_repository_summary(directory: str = ".") -> str:
    """Fetch the cached statistics and architectural overview of the indexed workspace.

    Args:
        directory: Root path of the indexed codebase. Defaults to current dir.
    """
    if _workspace_indexer_instance is None:
        return "❌ Workspace indexer is not initialised."
    
    path = str(Path(directory).resolve())
    record = _workspace_indexer_instance._db.get_repository_summary(path)
    if not record:
        return f"❌ Repository summary not found for: `{path}`. Run `index_workspace` first."

    return (
        f"📊 **Project Summary: {record.project_name}**\n"
        f"**Directory:** `{record.repo_path}`\n"
        f"**Last Indexed:** {record.updated_at}\n\n"
        f"| Metric | Count |\n"
        f"|--------|-------|\n"
        f"| Code Files | {record.total_files} |\n"
        f"| Total LOC | {record.total_lines:,} |\n"
        f"| Languages | {record.languages_detected} |\n"
        f"| Frameworks | {record.frameworks_detected or 'None detected'} |\n"
        f"| Manifests | {record.dependency_files or 'None'} |\n\n"
        f"**Architecture & Module Structure:**\n"
        f"{record.summary}"
    )


def get_coding_tools() -> list:
    """Return all workspace coding tools (overrides basic file tools)."""
    return [index_workspace, search_code_symbols, get_repository_summary]
