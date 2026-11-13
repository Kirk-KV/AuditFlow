from __future__ import annotations

from pathlib import Path
from typing import Any

from auditflow.blocks import missing_block_names
from auditflow.document_tables import html_table, html_text, mapping_rows, refresh_table_document
from auditflow.localization import message, project_messages, read_project_language, render_localized_template
from auditflow.template_utils import load_yaml_template
from auditflow.yaml_io import (
    read_optional_yaml_mapping,
    write_yaml_if_missing,
)


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


def build_annual_plan_context(initial_data: dict[str, Any], messages: dict[str, Any]) -> str:
    annual_plan = initial_data.get("annual_plan", {})
    audit = initial_data.get("audit", {})
    labels = message(messages, "planning.annual_plan_rows")
    rows = [
        [labels[0], audit.get("source", "")],
        [labels[1], annual_plan.get("year", "")],
        [labels[2], annual_plan.get("original_topic", "")],
        [labels[3], annual_plan.get("why_included", "")],
        [labels[4], annual_plan.get("expected_value", "")],
    ]
    return markdown_table(
        [message(messages, "planning.field_header"), message(messages, "planning.value_header")],
        rows,
        empty_text=message(messages, "planning.not_documented"),
    )


def build_objectives_block(initial_data: dict[str, Any], messages: dict[str, Any]) -> str:
    objectives = initial_data.get("objectives", [])
    if not isinstance(objectives, list):
        return message(messages, "planning.not_documented")
    rows = []
    for objective in objectives:
        if isinstance(objective, dict):
            rows.append([objective.get("id", ""), objective.get("statement", "")])
        else:
            rows.append(["", objective])
    return markdown_table(
        message(messages, "planning.objective_headers"),
        rows,
        empty_text=message(messages, "planning.not_documented"),
    )


def build_risks_block(initial_data: dict[str, Any], messages: dict[str, Any]) -> str:
    risks = initial_data.get("risks", [])
    if not isinstance(risks, list):
        return message(messages, "planning.not_documented")
    rows = []
    for risk in risks:
        if isinstance(risk, dict):
            rows.append([risk.get("id", ""), risk.get("title", ""), risk.get("source", ""), risk.get("preliminary_rating", ""), risk.get("rationale", "")])
    return markdown_table(
        message(messages, "planning.risk_headers"),
        rows,
        empty_text=message(messages, "planning.not_documented"),
    )


def build_scope_block(initial_data: dict[str, Any], messages: dict[str, Any]) -> str:
    scope = initial_data.get("scope", {})
    if not isinstance(scope, dict):
        return message(messages, "planning.not_documented")
    empty_text = message(messages, "planning.not_documented")
    return f"""**{message(messages, 'planning.in_scope')}**

{markdown_list(scope.get("in_scope", []), empty_text=empty_text)}

**{message(messages, 'planning.out_of_scope')}**

{markdown_list(scope.get("out_of_scope", []), empty_text=empty_text)}

**{message(messages, 'planning.rationale')}**

{markdown_list(scope.get("rationale", []), empty_text=empty_text)}
"""


def build_notes_block(initial_data: dict[str, Any], messages: dict[str, Any]) -> str | None:
    notes = initial_data.get("notes", {})
    if not isinstance(notes, dict):
        return None
    required_attention = notes.get("required_attention") or notes.get("necessary_to_take") or []
    keep_in_mind = notes.get("keep_in_mind") or []
    if not required_attention and not keep_in_mind:
        return None
    parts = []
    if required_attention:
        parts.append(
            f"**{message(messages, 'planning.required_attention')}**\n\n"
            + markdown_list(required_attention)
        )
    if keep_in_mind:
        parts.append(
            f"**{message(messages, 'planning.keep_in_mind')}**\n\n"
            + markdown_list(keep_in_mind)
        )
    return "\n\n".join(parts)


def planning_approach_table(decision: dict[str, Any], messages: dict[str, Any]) -> str:
    labels = message(messages, "planning.approach")
    empty = labels["empty"]
    risks = [
        [row.get("id"), row.get("title"), labels[scope], row.get("rationale")]
        for scope in ("included", "excluded")
        for row in mapping_rows(decision.get(f"{scope}_risks"))
        if any(row.get(key) for key in ("id", "title", "rationale"))
    ]
    controls = [
        [row.get("control_id") or row.get("id"), row.get("risk_id") or row.get("risk"),
         row.get("control_description") or row.get("description"), row.get("control_owner") or row.get("owner"),
         row.get("design_assessment"), row.get("planning_approach")]
        for row in mapping_rows(decision.get("controls"))
    ]
    tests = [
        [row.get(key) for key in ("id", "risk_id", "control_id", "test_objective")]
        for row in mapping_rows(decision.get("recommended_tests"))
    ]
    sections = [(labels["risks"], risks), (labels["controls"], controls), (labels["tests"], tests)]
    parts = [f'<p><strong>{html_text(labels["conclusion"])}</strong> '
             f'{html_text(decision.get("overall_conclusion") or empty)}</p>']
    for section, rows in sections:
        parts.append(f'<h3>{html_text(section["title"])}</h3>')
        parts.append(html_table(section["headers"], rows, empty))
    return "\n".join(parts)


def create_planning_files(project_root: Path, overwrite: bool = False) -> dict[str, Any]:
    planning_dir = project_root / "01_planning"
    planning_dir.mkdir(parents=True, exist_ok=True)
    created: list[str] = []
    kept: list[str] = []

    initial_data = read_optional_yaml_mapping(project_root / "initial_data.yml")
    stakeholders = read_optional_yaml_mapping(project_root / "00_admin" / "stakeholders.yml")
    team = read_optional_yaml_mapping(project_root / "00_admin" / "team.yml")
    language = read_project_language(project_root)
    messages = project_messages(project_root)

    context = {
        "audit_id": get_nested(initial_data, "audit", "id"),
        "audit_title": get_nested(
            initial_data,
            "audit",
            "title",
            default=message(messages, "planning.audit_default"),
        ),
        "company": get_nested(initial_data, "audit", "company"),
        "audit_type": get_nested(initial_data, "audit", "type"),
        "audit_source": get_nested(initial_data, "audit", "source"),
        "period_from": get_nested(initial_data, "period", "from"),
        "period_to": get_nested(initial_data, "period", "to"),
        "sponsor_name": first_person_name(stakeholders.get("sponsor")),
        "engagement_lead": first_person_name(team.get("engagement_lead")),
        "reviewer": first_person_name(team.get("reviewer")),
        "annual_plan_context": build_annual_plan_context(initial_data, messages),
        "objectives_block": build_objectives_block(initial_data, messages),
        "risks_block": build_risks_block(initial_data, messages),
        "scope_block": build_scope_block(initial_data, messages),
        "notes_block": build_notes_block(initial_data, messages),
    }

    planning_document = planning_dir / "planning_document.qmd"
    planning_decision = planning_dir / "planning_decision.yml"
    decision_template = load_yaml_template("planning_decision.yml")
    if write_yaml_if_missing(planning_decision, decision_template, overwrite=overwrite):
        created.append(str(planning_decision.relative_to(project_root)))
    else:
        kept.append(str(planning_decision.relative_to(project_root)))

    decision = read_optional_yaml_mapping(planning_decision)
    new_document = overwrite or not planning_document.exists()
    if new_document:
        content = render_localized_template("planning_document.qmd", context, language)
    else:
        content = planning_document.read_bytes().decode("utf-8")
        if content.rstrip().endswith(message(messages, "planning.approach.legacy_footer")):
            approach_heading = message(messages, "planning.approach.heading")
            content += f"\n\n{approach_heading}\n\n"
            content += "<!-- AUTO:PLANNING_APPROACH START -->\n<!-- AUTO:PLANNING_APPROACH END -->\n"
    changed = refresh_table_document(
        planning_document, content, "PLANNING_APPROACH", planning_approach_table(decision, messages),
    )
    relative = str(planning_document.relative_to(project_root))
    updated = []
    if new_document:
        created.append(relative)
    elif changed:
        updated.append(relative)
    else:
        kept.append(relative)
    return {
        "planning_dir": planning_dir,
        "created": created,
        "updated": updated,
        "kept": kept,
        "missing_blocks": missing_block_names(content, ("PLANNING_APPROACH",)),
    }
