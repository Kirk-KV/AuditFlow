from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from auditflow.template_utils import load_yaml_template, render_template, write_text_if_missing


def load_yaml(path: Path, default: Any | None = None) -> Any:
    if default is None:
        default = {}
    if not path.exists():
        return default
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or default


def write_yaml_if_missing(path: Path, data: dict[str, Any], overwrite: bool = False) -> bool:
    if path.exists() and not overwrite:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
    return True


def get_nested(data: dict[str, Any], *keys: str, default: str = "") -> str:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)
    return default if current is None else str(current)


def get_nested_dict(data: dict[str, Any], *keys: str) -> dict[str, Any]:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return {}
        current = current.get(key)
    return current if isinstance(current, dict) else {}


def first_person_name(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("name") or "")
    return ""


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def markdown_list(items: Any, empty_text: str = "_Not documented._") -> str:
    if not isinstance(items, list):
        return empty_text
    values = [text(item) for item in items if text(item)]
    return "\n".join(f"- {item}" for item in values) if values else empty_text


def markdown_table(headers: list[str], rows: list[list[Any]], empty_text: str = "_Not documented._") -> str:
    cleaned_rows = [[text(cell).replace("\n", "<br>") for cell in row] for row in rows if any(text(cell) for cell in row)]
    if not cleaned_rows:
        return empty_text
    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join("| " + " | ".join(row) + " |" for row in cleaned_rows)
    return "\n".join([header, separator, body])


def build_annual_plan_context(initial_data: dict[str, Any]) -> str:
    annual_plan = initial_data.get("annual_plan", {})
    audit = initial_data.get("audit", {})
    rows = [
        ["Audit source", audit.get("source", "")],
        ["Annual plan year", annual_plan.get("year", "")],
        ["Original topic", annual_plan.get("original_topic", "")],
        ["Why included", annual_plan.get("why_included", "")],
        ["Expected value", annual_plan.get("expected_value", "")],
    ]
    return markdown_table(["Field", "Value"], rows)


def build_objectives_block(initial_data: dict[str, Any]) -> str:
    objectives = initial_data.get("objectives", [])
    if not isinstance(objectives, list):
        return "_Not documented._"
    rows = []
    for objective in objectives:
        if isinstance(objective, dict):
            rows.append([objective.get("id", ""), objective.get("statement", "")])
        else:
            rows.append(["", objective])
    return markdown_table(["Objective ID", "Statement"], rows)


def build_risks_block(initial_data: dict[str, Any]) -> str:
    risks = initial_data.get("risks", [])
    if not isinstance(risks, list):
        return "_Not documented._"
    rows = []
    for risk in risks:
        if isinstance(risk, dict):
            rows.append([risk.get("id", ""), risk.get("title", ""), risk.get("source", ""), risk.get("preliminary_rating", ""), risk.get("rationale", "")])
    return markdown_table(["Risk ID", "Title", "Source", "Preliminary rating", "Rationale"], rows)


def build_scope_block(initial_data: dict[str, Any]) -> str:
    scope = initial_data.get("scope", {})
    if not isinstance(scope, dict):
        return "_Not documented._"
    return f"""**In scope**

{markdown_list(scope.get("in_scope", []))}

**Out of scope**

{markdown_list(scope.get("out_of_scope", []))}

**Rationale**

{markdown_list(scope.get("rationale", []))}
"""


def build_notes_block(initial_data: dict[str, Any]) -> str:
    notes = initial_data.get("notes", {})
    if not isinstance(notes, dict):
        return None
    required_attention = notes.get("required_attention") or notes.get("necessary_to_take") or []
    keep_in_mind = notes.get("keep_in_mind") or []
    if not required_attention and not keep_in_mind:
        return None
    parts = []
    if required_attention:
        parts.append("**Required attention**\n\n" + markdown_list(required_attention))
    if keep_in_mind:
        parts.append("**Keep in mind**\n\n" + markdown_list(keep_in_mind))
    return "\n\n".join(parts)


def create_planning_files(project_root: Path, overwrite: bool = False) -> dict[str, Any]:
    planning_dir = project_root / "01_planning"
    planning_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    kept: list[str] = []

    initial_data = load_yaml(project_root / "initial_data.yml", default={})
    stakeholders = load_yaml(project_root / "00_admin" / "stakeholders.yml", default={})
    team = load_yaml(project_root / "00_admin" / "team.yml", default={})

    context = {
        "audit_id": get_nested(initial_data, "audit", "id"),
        "audit_title": get_nested(initial_data, "audit", "title", default="Audit"),
        "company": get_nested(initial_data, "audit", "company"),
        "audit_type": get_nested(initial_data, "audit", "type"),
        "audit_source": get_nested(initial_data, "audit", "source"),
        "period_from": get_nested(initial_data, "period", "from"),
        "period_to": get_nested(initial_data, "period", "to"),
        "sponsor_name": first_person_name(stakeholders.get("sponsor")),
        "engagement_lead": first_person_name(team.get("engagement_lead")),
        "reviewer": first_person_name(team.get("reviewer")),
        "annual_plan_context": build_annual_plan_context(initial_data),
        "objectives_block": build_objectives_block(initial_data),
        "risks_block": build_risks_block(initial_data),
        "scope_block": build_scope_block(initial_data),
        "notes_block": build_notes_block(initial_data),
    }

    planning_document = planning_dir / "planning_document.qmd"
    planning_decision = planning_dir / "planning_decision.yml"
    rendered_planning_document = render_template("planning_document.qmd", context)

    if write_text_if_missing(planning_document, rendered_planning_document, overwrite=overwrite):
        created.append(str(planning_document.relative_to(project_root)))
    else:
        kept.append(str(planning_document.relative_to(project_root)))

    decision_template = load_yaml_template("planning_decision.yml")
    if write_yaml_if_missing(planning_decision, decision_template, overwrite=overwrite):
        created.append(str(planning_decision.relative_to(project_root)))
    else:
        kept.append(str(planning_decision.relative_to(project_root)))

    return {"planning_dir": planning_dir, "created": created, "kept": kept}
