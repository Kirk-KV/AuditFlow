from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from auditflow.blocks import missing_block_names
from auditflow.document_tables import html_table, refresh_table_document
from auditflow.ids import build_workpaper_ref, is_safe_workpaper_ref
from auditflow.localization import (
    load_messages,
    message,
    read_project_language,
    render_localized_template,
)
from auditflow.yaml_io import read_optional_yaml_mapping, read_yaml_mapping, write_yaml


MANUAL_FIELDS = [
    "test_hypothesis",
    "test_script",
]

PROGRAM_TABLE_FIELDS = (
    "test_id", "risk_id", "risk_title", "risk_reasoning", "control_id",
    "control_description", "control_owner", "design_assessment", "planning_approach",
    "test_hypothesis", "test_script", "workpaper_ref",
)


def normalize_id(value: Any) -> str | None:
    if value is None:
        return None

    result = str(value).strip()

    if result == "" or result.upper() in {"N/A", "NA", "NONE", "NULL"}:
        return None

    return result


def first_non_empty(item: dict[str, Any], *keys: str, default: Any = "") -> Any:
    for key in keys:
        value = item.get(key)
        if value not in (None, "", [], {}):
            return value

    return default


def get_risk_id(item: dict[str, Any]) -> str:
    risk_id = first_non_empty(item, "risk_id", "risk")

    if not risk_id:
        raise ValueError(f"Item has no risk_id/risk: {item}")

    return str(risk_id)


def get_control_id(control: dict[str, Any]) -> str | None:
    return normalize_id(first_non_empty(control, "control_id", "id"))


def get_risk_title(risk: dict[str, Any]) -> str:
    return str(first_non_empty(risk, "title", "risk_title", default=""))


def get_risk_reasoning(risk: dict[str, Any]) -> str:
    return str(first_non_empty(risk, "reasoning", "rationale", default=""))


def get_description(item: dict[str, Any]) -> str:
    return str(
        first_non_empty(
            item,
            "control_description",
            "description",
            "control",
            default="",
        )
    )


def get_owner(item: dict[str, Any]) -> str:
    return str(first_non_empty(item, "control_owner", "owner", default=""))


def index_by(items: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    return {
        str(item[key]): item
        for item in items
        if item.get(key) is not None
    }


def make_test_id(index: int) -> str:
    return f"T-{index:03d}"


def make_workpaper_ref(
    entity_id: str | None,
    fallback_test_id: str,
    *,
    taken: set[str],
    preferred: str | None = None,
) -> str:
    """Return the file-name-safe workpaper reference for one program row.

    The reference is written into audit_program.yml and used verbatim as the
    workpaper file name, so it is normalized here, at the point it is created,
    rather than by each consumer.
    """

    return build_workpaper_ref(
        control_id=normalize_id(entity_id),
        test_id=fallback_test_id,
        taken=taken,
        preferred=preferred,
    )


def row_key(row: dict[str, Any]) -> str:
    control_id = normalize_id(row.get("control_id"))
    if control_id:
        return f"control:{control_id}"

    risk_id = normalize_id(row.get("risk_id"))
    if risk_id:
        return f"risk-without-control:{risk_id}"

    raise ValueError(f"Cannot build stable row key for row: {row}")


def merge_manual_fields(
    new_row: dict[str, Any],
    existing_row: dict[str, Any] | None,
) -> dict[str, Any]:
    if existing_row is None:
        return new_row

    merged = deepcopy(new_row)

    for field in MANUAL_FIELDS:
        existing_value = existing_row.get(field)
        if existing_value not in (None, "", [], {}):
            merged[field] = existing_value

    return merged


def build_control_program_row(
    *,
    index: int,
    control: dict[str, Any],
    risk: dict[str, Any],
    existing_row: dict[str, Any] | None,
    no_control_design: str,
    taken_workpaper_refs: set[str],
) -> dict[str, Any]:
    control_id = get_control_id(control)
    test_id = make_test_id(index)
    workpaper_entity_id = control_id or f"{risk['id']}-NO-CONTROL"
    default_design_assessment = ""

    if not control_id:
        default_design_assessment = no_control_design

    new_row = {
        "test_id": test_id,
        "risk_id": risk["id"],
        "risk_title": get_risk_title(risk),
        "risk_reasoning": get_risk_reasoning(risk),
        "control_id": control_id,
        "control_description": get_description(control),
        "control_owner": get_owner(control),
        "design_assessment": str(first_non_empty(control, "design_assessment", default=default_design_assessment)),
        "planning_approach": str(first_non_empty(control, "planning_approach", default="")),
        "test_hypothesis": "",
        "test_script": [],
        "workpaper_ref": make_workpaper_ref(
            workpaper_entity_id,
            test_id,
            taken=taken_workpaper_refs,
            preferred=str((existing_row or {}).get("workpaper_ref") or "") or None,
        ),
    }

    return merge_manual_fields(new_row, existing_row)


def existing_rows_by_key(existing_program: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    existing_rows = []

    if existing_program:
        existing_rows = existing_program.get("program_rows", [])

    result = {}

    for row in existing_rows:
        if not isinstance(row, dict):
            continue

        try:
            result[row_key(row)] = row
        except ValueError:
            continue

    return result


def build_program_rows(
    planning_decision: dict[str, Any],
    existing_program: dict[str, Any] | None,
    messages: dict[str, Any],
) -> list[dict[str, Any]]:
    included_risks = planning_decision.get("included_risks", [])
    risks_by_id = index_by(included_risks, "id")
    included_risk_ids = set(risks_by_id)
    existing_by_key = existing_rows_by_key(existing_program)
    controls_by_risk: dict[str, list[dict[str, Any]]] = {}
    taken_workpaper_refs: set[str] = set()
    # Reserve existing identities before new controls can claim their names.
    preserved_refs: dict[str, str] = {}
    for key, existing in existing_by_key.items():
        ref = str(existing.get("workpaper_ref") or "")
        if is_safe_workpaper_ref(ref) and ref.casefold() not in taken_workpaper_refs:
            preserved_refs[key] = ref
            taken_workpaper_refs.add(ref.casefold())

    rows = []
    test_index = 1

    for control in planning_decision.get("controls", []):
        if not isinstance(control, dict):
            continue

        risk_id = normalize_id(first_non_empty(control, "risk_id", "risk"))

        if not risk_id or risk_id not in included_risk_ids:
            continue

        controls_by_risk.setdefault(risk_id, []).append(control)

    for risk in included_risks:
        if not isinstance(risk, dict):
            continue

        risk_id = normalize_id(risk.get("id"))

        if not risk_id:
            continue

        controls = controls_by_risk.get(risk_id) or [
            {
                "risk_id": risk_id,
                "description": "",
                "owner": "",
                "design_assessment": message(messages, "audit_program.no_control_design"),
            }
        ]

        for control in controls:
            temp_row = {
                "control_id": get_control_id(control),
                "risk_id": risk_id,
            }
            key = row_key(temp_row)
            existing_row = existing_by_key.get(key)
            preserved_ref = preserved_refs.pop(key, None)
            if preserved_ref:
                taken_workpaper_refs.remove(preserved_ref.casefold())
            row = build_control_program_row(
                index=test_index,
                control=control,
                risk=risks_by_id[risk_id],
                existing_row=existing_row,
                no_control_design=message(messages, "audit_program.no_control_design"),
                taken_workpaper_refs=taken_workpaper_refs,
            )

            rows.append(row)
            test_index += 1

    return rows


def build_planning_warnings(
    planning_decision: dict[str, Any],
    messages: dict[str, Any],
) -> dict[str, Any]:
    included_risks = planning_decision.get("included_risks", [])
    risks_by_id = index_by(included_risks, "id")
    included_risk_ids = set(risks_by_id)
    risk_ids_with_controls: set[str] = set()

    for control in planning_decision.get("controls", []):
        if not isinstance(control, dict):
            continue

        risk_id = normalize_id(first_non_empty(control, "risk_id", "risk"))
        control_id = get_control_id(control)

        if risk_id in included_risk_ids and control_id:
            risk_ids_with_controls.add(risk_id)

    risks_without_controls = []

    for risk_id in sorted(included_risk_ids - risk_ids_with_controls):
        risk = risks_by_id[risk_id]
        risks_without_controls.append(
            {
                "risk_id": risk_id,
                "risk_title": get_risk_title(risk),
                "message": message(messages, "audit_program.no_control_warning"),
            }
        )

    return {
        "included_risks_without_valid_controls": risks_without_controls,
    }


def build_audit_program(
    planning_decision: dict[str, Any],
    existing_program: dict[str, Any] | None,
    messages: dict[str, Any] | None = None,
) -> dict[str, Any]:
    messages = messages or load_messages("en")
    return {
        "program": {
            "status": "draft",
            "source": {
                "planning_decision": "01_planning/planning_decision.yml",
            },
            "note": message(messages, "audit_program.note"),
        },
        "program_rows": build_program_rows(
            planning_decision=planning_decision,
            existing_program=existing_program,
            messages=messages,
        ),
        "planning_warnings": build_planning_warnings(planning_decision, messages),
    }


def create_audit_program(project_root: Path, overwrite: bool = False) -> dict[str, Any]:
    planning_decision_path = project_root / "01_planning" / "planning_decision.yml"
    audit_program_path = project_root / "03_audit_program" / "audit_program.yml"
    document_path = audit_program_path.with_suffix(".qmd")
    language = read_project_language(project_root)
    messages = load_messages(language)

    planning_decision = read_yaml_mapping(
        planning_decision_path,
        label="Planning decision (run 'auditflow create planning' first)",
    )

    existing_program = None
    if audit_program_path.exists() and not overwrite:
        existing_program = read_yaml_mapping(audit_program_path, label="Audit program")

    audit_program = build_audit_program(
        planning_decision=planning_decision,
        existing_program=existing_program,
        messages=messages,
    )

    if document_path.exists():
        content = document_path.read_bytes().decode("utf-8")
    else:
        initial = read_optional_yaml_mapping(project_root / "initial_data.yml")
        audit = initial.get("audit")
        title = audit.get("title") if isinstance(audit, dict) else None
        title = str(title or message(messages, "planning.audit_default"))
        document_title = f"{message(messages, 'audit_program.document_title')} — {title}"
        content = render_localized_template(
            "audit_program.qmd",
            {"title": json.dumps(document_title, ensure_ascii=False)},
            language,
        )
    rows = audit_program["program_rows"]
    table = html_table(
        message(messages, "audit_program.table_headers"),
        [[row.get(field) for field in PROGRAM_TABLE_FIELDS] for row in rows],
        message(messages, "planning.approach.empty"),
    )
    write_yaml(audit_program_path, audit_program)
    refresh_table_document(document_path, content, "AUDIT_PROGRAM", table)

    return {
        "path": str(audit_program_path),
        "document_path": str(document_path),
        "missing_blocks": missing_block_names(content, ("AUDIT_PROGRAM",)),
        "rows": len(audit_program["program_rows"]),
        "manual_fields_preserved": bool(existing_program and not overwrite),
    }
