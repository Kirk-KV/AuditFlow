from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from auditflow.template_utils import load_yaml_template, read_template


EVIDENCE_SUBFOLDERS = [
    "01_regulations",
    "02_raw_data",
    "03_correspondence",
    "04_reference_materials",
    "05_screenshots",
    "99_generated",
]


def write_yaml_if_missing(path: Path, data: dict[str, Any], overwrite: bool = False) -> bool:
    if path.exists() and not overwrite:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=100),
        encoding="utf-8",
    )
    return True


def write_text_if_missing(path: Path, text: str, overwrite: bool = False) -> bool:
    if path.exists() and not overwrite:
        return False

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return True


def read_external_text(path: Path, label: str = "Text file") -> str:
    if not path.exists():
        raise FileNotFoundError(f"{label} not found: {path}")

    if not path.is_file():
        raise ValueError(f"{label} path is not a file: {path}")

    return path.read_text(encoding="utf-8")


def resolve_brand_css(brand_css: Path | None = None) -> str:
    """Return project brand CSS.

    Priority:
    1. explicit brand_css argument;
    2. AUDITFLOW_BRAND_CSS environment variable;
    3. bundled default template.
    """

    if brand_css is not None:
        return read_external_text(brand_css.expanduser().resolve(), "Brand CSS file")

    env_brand_css = os.environ.get("AUDITFLOW_BRAND_CSS")
    if env_brand_css:
        return read_external_text(Path(env_brand_css).expanduser().resolve(), "Brand CSS file")

    return read_template("styles/brand.css")


def resolve_report_css(report_css: Path | None = None) -> str:
    """Return project report CSS.

    Priority:
    1. explicit report_css argument;
    2. AUDITFLOW_REPORT_CSS environment variable;
    3. bundled default template.
    """

    if report_css is not None:
        return read_external_text(report_css.expanduser().resolve(), "Report CSS file")

    env_report_css = os.environ.get("AUDITFLOW_REPORT_CSS")
    if env_report_css:
        return read_external_text(Path(env_report_css).expanduser().resolve(), "Report CSS file")

    return read_template("styles/report.css")


def create_initial_project(
    path: Path,
    overwrite: bool = False,
    brand_css: Path | None = None,
    report_css: Path | None = None,
) -> dict[str, Any]:
    """Create the staged AuditFlow starter structure."""
    project_root = path.resolve()
    project_root.mkdir(parents=True, exist_ok=True)

    created_files: list[str] = []
    created_dirs: list[str] = []

    def record_file(result: bool, file_path: Path) -> None:
        if result:
            created_files.append(str(file_path.relative_to(project_root)))

    def ensure_dir(dir_path: Path) -> None:
        existed = dir_path.exists()
        dir_path.mkdir(parents=True, exist_ok=True)
        if not existed:
            created_dirs.append(str(dir_path.relative_to(project_root)))

    for directory in [
        project_root / "00_admin",
        project_root / "04_evidence",
        project_root / "styles",
        project_root / ".vscode",
    ]:
        ensure_dir(directory)

    for subfolder in EVIDENCE_SUBFOLDERS:
        ensure_dir(project_root / "04_evidence" / subfolder)

    starter_yaml_templates = {
        "initial_data.yml": project_root / "initial_data.yml",
        "stakeholders.yml": project_root / "00_admin" / "stakeholders.yml",
        "team.yml": project_root / "00_admin" / "team.yml",
        "decisions.yml": project_root / "00_admin" / "decisions.yml",
        "timeline.yml": project_root / "00_admin" / "timeline.yml",
        "ai.yml": project_root / "00_admin" / "ai.yml",
    }

    for template_name, target_path in starter_yaml_templates.items():
        record_file(
            write_yaml_if_missing(
                target_path,
                load_yaml_template(template_name),
                overwrite=overwrite,
            ),
            target_path,
        )

    project_text_templates = {
        ".gitignore": project_root / ".gitignore",
        "_quarto.yml": project_root / "_quarto.yml",
        "styles/auditflow.css": project_root / "styles" / "auditflow.css",
    }

    for template_name, target_path in project_text_templates.items():
        record_file(
            write_text_if_missing(
                target_path,
                read_template(template_name),
                overwrite=overwrite,
            ),
            target_path,
        )

    record_file(
        write_text_if_missing(
            project_root / "styles" / "brand.css",
            resolve_brand_css(brand_css),
            overwrite=overwrite,
        ),
        project_root / "styles" / "brand.css",
    )

    record_file(
        write_text_if_missing(
            project_root / "styles" / "report.css",
            resolve_report_css(report_css),
            overwrite=overwrite,
        ),
        project_root / "styles" / "report.css",
    )

    record_file(
        write_text_if_missing(
            project_root / "04_evidence" / "README.md",
            """# Evidence folder

Use this folder during pre-planning, planning, and fieldwork.

- `01_regulations/` — policies, procedures, process descriptions.
- `02_raw_data/` — raw exports received from systems or management.
- `03_correspondence/` — important emails and written confirmations.
- `04_reference_materials/` — background materials, org charts, prior reports.
- `05_screenshots/` — screenshots used as evidence.
- `99_generated/` — generated outputs from analysis scripts or notebooks.
""",
            overwrite=overwrite,
        ),
        project_root / "04_evidence" / "README.md",
    )

    for file_name in ["settings.json", "tasks.json", "extensions.json"]:
        target_path = project_root / ".vscode" / file_name
        record_file(
            write_text_if_missing(
                target_path,
                read_template(f".vscode/{file_name}"),
                overwrite=overwrite,
            ),
            target_path,
        )

    return {
        "project_root": project_root,
        "created_files": created_files,
        "created_dirs": created_dirs,
    }
