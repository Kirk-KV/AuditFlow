
from __future__ import annotations

from pathlib import Path
from typing import Optional


PROJECT_MARKER_FILE = "initial_data.yml"


class AuditFlowProjectNotFound(FileNotFoundError):
    """Raised when a command cannot locate an AuditFlow project root."""


def is_project_root(path: Path) -> bool:
    path = path.resolve()
    return (path / PROJECT_MARKER_FILE).exists() and (path / "00_admin").exists()


def find_project_root(start: Path | None = None) -> Path:
    """Find the nearest AuditFlow project root by walking up from start."""
    current = (start or Path.cwd()).resolve()

    if current.is_file():
        current = current.parent

    while current != current.parent:
        if is_project_root(current):
            return current
        current = current.parent

    if is_project_root(current):
        return current

    raise AuditFlowProjectNotFound(
        "No AuditFlow project found. Run this command inside an AuditFlow project "
        "or pass --project PATH."
    )


def resolve_project(project: Optional[Path] = None) -> Path:
    """Resolve explicit --project path or infer the project from the current directory."""
    if project is not None:
        resolved = project.resolve()
        if not resolved.exists():
            raise AuditFlowProjectNotFound(f"Project path does not exist: {resolved}")
        if not is_project_root(resolved):
            raise AuditFlowProjectNotFound(
                f"Not an AuditFlow project: {resolved}\n"
                "Expected initial_data.yml and 00_admin/."
            )
        return resolved

    return find_project_root(Path.cwd())


def relative_to_cwd(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd().resolve()))
    except ValueError:
        return str(path.resolve())
