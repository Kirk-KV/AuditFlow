from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from string import Template
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise SystemExit("PyYAML is required. Install it with: pip install pyyaml") from exc


TEMPLATE_PACKAGE = "auditflow.templates"


def read_template(relative_path: str) -> str:
    """Read a text template bundled with the AuditFlow package."""

    template_path = files(TEMPLATE_PACKAGE).joinpath(relative_path)

    if not template_path.is_file():
        raise FileNotFoundError(f"Template not found: {relative_path}")

    return template_path.read_text(encoding="utf-8")


def render_template(relative_path: str, context: dict[str, Any]) -> str:
    """Render a bundled template using Python's simple string.Template syntax.

    Template placeholders use the $name / ${name} syntax. This intentionally avoids
    a heavy templating dependency while keeping document layouts out of Python code.
    """

    normalized_context = {
        key: "" if value is None else str(value)
        for key, value in context.items()
    }

    return Template(read_template(relative_path)).safe_substitute(normalized_context)


def load_yaml_template(relative_path: str, default: Any | None = None) -> Any:
    """Load a YAML template bundled with the package."""

    if default is None:
        default = {}

    return yaml.safe_load(read_template(relative_path)) or default


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


def write_yaml_if_missing(path: Path, data: Any, overwrite: bool = False) -> bool:
    """Write YAML unless the file already exists and overwrite=False."""

    if path.exists() and not overwrite:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )
    return True


def write_yaml_template(
    *,
    template_name: str,
    output_path: Path,
    overwrite: bool = False,
) -> bool:
    """Load a YAML template and write it to a target file.

    Returns True when a file was created or overwritten, False when the existing
    file was kept.
    """

    return write_yaml_if_missing(
        output_path,
        load_yaml_template(template_name),
        overwrite=overwrite,
    )


def write_rendered_template(
    *,
    template_name: str,
    output_path: Path,
    context: dict[str, Any],
    overwrite: bool = False,
) -> bool:
    """Render a text template and write it to a target file.

    Returns True when a file was created or overwritten, False when the existing
    file was kept.
    """

    return write_text_if_missing(
        output_path,
        render_template(template_name, context),
        overwrite=overwrite,
    )


def copy_template(
    *,
    template_name: str,
    output_path: Path,
    overwrite: bool = False,
) -> bool:
    """Copy a template without rendering placeholders.

    Returns True when a file was created or overwritten, False when the existing
    file was kept.
    """

    return write_text_if_missing(
        output_path,
        read_template(template_name),
        overwrite=overwrite,
    )
