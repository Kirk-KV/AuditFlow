from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from auditflow.errors import AuditFlowDataError, AuditFlowFileError


def read_yaml(path: Path, *, label: str | None = None) -> Any:
    """Read YAML from a file that must exist.

    Raises AuditFlowFileError when the file is missing or unreadable and
    AuditFlowDataError when the content is not valid YAML.
    """

    name = label or str(path)
    if not path.exists():
        raise AuditFlowFileError(f"{name} not found: {path}")
    if not path.is_file():
        raise AuditFlowFileError(f"{name} is not a file: {path}")

    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError) as exc:
        raise AuditFlowFileError(f"Cannot read {name} {path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise AuditFlowDataError(f"Invalid YAML in {name} {path}: {exc}") from exc


def read_yaml_mapping(path: Path, *, label: str | None = None) -> dict[str, Any]:
    """Read a YAML mapping from a file that must exist."""

    data = read_yaml(path, label=label) or {}
    if not isinstance(data, dict):
        raise AuditFlowDataError(
            f"{label or str(path)} must contain a YAML mapping: {path}"
        )
    return data


def read_optional_yaml_mapping(path: Path, *, label: str | None = None) -> dict[str, Any]:
    """Read a YAML mapping, returning an empty mapping when the file is absent.

    A file that exists but is broken still raises, so a typo is never silently
    treated as an empty document.
    """

    if not path.exists():
        return {}
    return read_yaml_mapping(path, label=label)


def write_yaml(path: Path, data: Any, *, width: int = 120) -> None:
    """Write YAML with the layout AuditFlow uses for every generated file."""

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=width),
        encoding="utf-8",
    )


def write_text_if_missing(path: Path, text: str, overwrite: bool = False) -> bool:
    """Write text unless the file already exists and overwrite=False.

    Returns True when a file was created or overwritten, False when the existing
    file was kept.
    """

    if path.exists() and not overwrite:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def write_yaml_if_missing(
    path: Path,
    data: Any,
    overwrite: bool = False,
    *,
    width: int = 120,
) -> bool:
    """Write YAML unless the file already exists and overwrite=False."""

    if path.exists() and not overwrite:
        return False

    write_yaml(path, data, width=width)
    return True
