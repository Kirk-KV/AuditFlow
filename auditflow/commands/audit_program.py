from __future__ import annotations

import argparse
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml


MANUAL_FIELDS = [
    "test_hypothesis",
    "test_script",
]


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            data,
            file,
            sort_keys=False,
            allow_unicode=True,
            width=120,
            default_flow_style=False,
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


def make_workpaper_ref(entity_id: str | None, fallback_test_id: str) -> str:
    normalized = normalize_id(entity_id)
    if normalized:
        return f"WP-{normalized}"

    return f"WP-{fallback_test_id}"


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
) -> dict[str, Any]:
    control_id = get_control_id(control)
    test_id = make_test_id(index)
    workpaper_entity_id = control_id or f"{risk['id']}-NO-CONTROL"
    default_design_assessment = ""

    if not control_id:
        default_design_assessment = "No control is identified in planning_decision.yml."

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
        "workpaper_ref": make_workpaper_ref(workpaper_entity_id, test_id),
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
) -> list[dict[str, Any]]:
    included_risks = planning_decision.get("included_risks", [])
    risks_by_id = index_by(included_risks, "id")
    included_risk_ids = set(risks_by_id)
    existing_by_key = existing_rows_by_key(existing_program)
    controls_by_risk: dict[str, list[dict[str, Any]]] = {}

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
                "design_assessment": "No control is identified in planning_decision.yml.",
            }
        ]

        for control in controls:
            temp_row = {
                "control_id": get_control_id(control),
                "risk_id": risk_id,
            }
            existing_row = existing_by_key.get(row_key(temp_row))
            row = build_control_program_row(
                index=test_index,
                control=control,
                risk=risks_by_id[risk_id],
                existing_row=existing_row,
            )

            rows.append(row)
            test_index += 1

    return rows


def build_planning_warnings(planning_decision: dict[str, Any]) -> dict[str, Any]:
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
                "message": "No valid control id is identified for this included risk in planning_decision.yml.",
            }
        )

    return {
        "included_risks_without_valid_controls": risks_without_controls,
    }


def build_audit_program(
    planning_decision: dict[str, Any],
    existing_program: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "program": {
            "status": "draft",
            "source": {
                "planning_decision": "01_planning/planning_decision.yml",
            },
            "note": (
                "This audit program is a working matrix generated from planning_decision.yml. "
                "The auditor completes or adjusts test_hypothesis and test_script here. "
                "Conclusions and evidence evaluation are documented in workpapers."
            ),
        },
        "program_rows": build_program_rows(
            planning_decision=planning_decision,
            existing_program=existing_program,
        ),
        "planning_warnings": build_planning_warnings(planning_decision),
    }


def create_audit_program(project_root: Path, overwrite: bool = False) -> dict[str, Any]:
    planning_decision_path = project_root / "01_planning" / "planning_decision.yml"
    audit_program_path = project_root / "03_audit_program" / "audit_program.yml"

    planning_decision = load_yaml(planning_decision_path)

    existing_program = None
    if audit_program_path.exists() and not overwrite:
        existing_program = load_yaml(audit_program_path)

    audit_program = build_audit_program(
        planning_decision=planning_decision,
        existing_program=existing_program,
    )

    write_yaml(audit_program_path, audit_program)

    return {
        "path": str(audit_program_path),
        "rows": len(audit_program["program_rows"]),
        "manual_fields_preserved": bool(existing_program and not overwrite),
    }
