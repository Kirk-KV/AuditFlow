from __future__ import annotations

from pathlib import Path
from typing import Any

from auditflow.errors import AuditFlowDataError
from auditflow.ids import require_safe_workpaper_ref
from auditflow.localization import (
    message,
    project_messages,
    read_project_language,
    render_localized_template,
)
from auditflow.yaml_io import read_yaml_mapping


def text_value(value: Any) -> str:
    return "" if value is None else str(value).strip()


def workpaper_title(row: dict[str, Any], default_title: str = "Workpaper") -> str:
    workpaper_ref = text_value(row.get("workpaper_ref", ""))
    control_description = text_value(row.get("control_description", ""))
    risk_title = text_value(row.get("risk_title", ""))
    test_id = text_value(row.get("test_id", ""))

    subject = control_description or risk_title or test_id or default_title

    if workpaper_ref:
        return f"{workpaper_ref} — {subject}"

    return subject


def build_workpaper_qmd(
    row: dict[str, Any],
    *,
    language: str = "en",
    default_title: str = "Workpaper",
) -> str:
    workpaper_ref = text_value(row.get("workpaper_ref", ""))

    if not workpaper_ref:
        raise AuditFlowDataError("Program row is missing workpaper_ref.")

    return render_localized_template(
        "workpaper.qmd",
        {
            "title": workpaper_title(row, default_title=default_title).replace('"', "'"),
            "workpaper_ref": workpaper_ref,
        },
        language,
    )


def generate_workpapers(project_root: Path, overwrite: bool = False) -> dict[str, Any]:
    audit_program_path = project_root / "03_audit_program" / "audit_program.yml"
    workpapers_dir = project_root / "05_workpapers"
    workpapers_dir.mkdir(parents=True, exist_ok=True)

    audit_program = read_yaml_mapping(
        audit_program_path,
        label="Audit program (run 'auditflow create audit-program' first)",
    )
    rows = audit_program.get("program_rows", [])
    language = read_project_language(project_root)
    messages = project_messages(project_root)

    if not isinstance(rows, list):
        raise AuditFlowDataError(
            "Expected audit_program.yml to contain a list field: program_rows"
        )

    created = 0
    skipped = 0
    missing_workpaper_ref = 0
    seen_refs: dict[str, str] = {}
    validated_rows: list[tuple[dict[str, Any], str]] = []

    for row in rows:
        if not isinstance(row, dict):
            continue

        workpaper_ref = text_value(row.get("workpaper_ref", ""))
        test_id = text_value(row.get("test_id", "")) or "?"

        if not workpaper_ref:
            missing_workpaper_ref += 1
            continue

        # The reference is the workpaper's file name. Two rows sharing one
        # reference would overwrite each other's workpaper, so this is refused
        # rather than reported as a skip.
        require_safe_workpaper_ref(workpaper_ref, f"Program row {test_id}")
        ref_key = workpaper_ref.casefold()
        if ref_key in seen_refs:
            raise AuditFlowDataError(
                f"03_audit_program/audit_program.yml: rows {seen_refs[ref_key]} "
                f"and {test_id} share workpaper_ref {workpaper_ref}. "
                "Run 'auditflow create audit-program' to reassign unique references."
            )
        seen_refs[ref_key] = test_id
        validated_rows.append((row, workpaper_ref))

    # Validate all references before overwriting any auditor-owned file.
    for row, workpaper_ref in validated_rows:
        target = workpapers_dir / f"{workpaper_ref}.qmd"

        if target.exists() and not overwrite:
            skipped += 1
            continue

        target.write_text(
            build_workpaper_qmd(
                row,
                language=language,
                default_title=message(messages, "workpaper.default_title"),
            ),
            encoding="utf-8",
        )
        created += 1

    return {
        "created": created,
        "skipped": skipped,
        "missing_workpaper_ref": missing_workpaper_ref,
        "workpapers_dir": str(workpapers_dir),
    }
