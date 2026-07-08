from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml

from auditflow.template_utils import render_template


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")


def text_value(value: Any) -> str:
    return "" if value is None else str(value).strip()


def workpaper_title(row: dict[str, Any]) -> str:
    workpaper_ref = text_value(row.get("workpaper_ref", ""))
    control_description = text_value(row.get("control_description", ""))
    risk_title = text_value(row.get("risk_title", ""))
    test_id = text_value(row.get("test_id", ""))

    subject = control_description or risk_title or test_id or "Workpaper"

    if workpaper_ref:
        return f"{workpaper_ref} — {subject}"

    return subject


def build_workpaper_qmd(row: dict[str, Any]) -> str:
    workpaper_ref = text_value(row.get("workpaper_ref", ""))

    if not workpaper_ref:
        raise ValueError("Program row is missing workpaper_ref.")

    return render_template(
        "workpaper.qmd",
        {
            "title": workpaper_title(row).replace('"', "'"),
            "workpaper_ref": workpaper_ref,
        },
    )


def generate_workpapers(project_root: Path, overwrite: bool = False) -> dict[str, Any]:
    audit_program_path = project_root / "03_audit_program" / "audit_program.yml"
    workpapers_dir = project_root / "05_workpapers"
    workpapers_dir.mkdir(parents=True, exist_ok=True)

    audit_program = load_yaml(audit_program_path)
    rows = audit_program.get("program_rows", [])

    if not isinstance(rows, list):
        raise ValueError("Expected audit_program.yml to contain a list field: program_rows")

    created = 0
    skipped = 0
    missing_workpaper_ref = 0

    for row in rows:
        if not isinstance(row, dict):
            continue

        workpaper_ref = text_value(row.get("workpaper_ref", ""))

        if not workpaper_ref:
            missing_workpaper_ref += 1
            continue

        target = workpapers_dir / f"{safe_filename(workpaper_ref)}.qmd"

        if target.exists() and not overwrite:
            skipped += 1
            continue

        target.write_text(build_workpaper_qmd(row), encoding="utf-8")
        created += 1

    return {
        "created": created,
        "skipped": skipped,
        "missing_workpaper_ref": missing_workpaper_ref,
        "workpapers_dir": str(workpapers_dir),
    }
