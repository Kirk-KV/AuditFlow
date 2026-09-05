from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auditflow.blocks import (
    REPORT_BLOCK_NAMES,
    missing_block_names,
    observations_digest,
    replace_auto_blocks,
    stamp_observations_digest,
    update_front_matter,
)
from auditflow.localization import (
    load_messages,
    message,
    project_messages,
    read_localized_template,
    read_project_language,
    translated_term,
)
from auditflow.yaml_io import read_optional_yaml_mapping


@dataclass(frozen=True)
class ReportUpdate:
    path: Path
    missing_blocks: tuple[str, ...]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def first_non_empty(item: dict[str, Any], *keys: str, default: str = "") -> str:
    for key in keys:
        value = item.get(key)
        if text(value):
            return text(value)

    return default


def nested_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    return value if isinstance(value, dict) else {}


def list_items_html(
    items: Any,
    class_name: str = "scope-list",
    not_documented: str = "Not documented.",
) -> str:
    if not isinstance(items, list):
        return f"<p><em>{esc(not_documented)}</em></p>"

    values = [text(item) for item in items if text(item)]
    if not values:
        return f"<p><em>{esc(not_documented)}</em></p>"

    items_html = "".join(f"<li>{esc(item)}</li>" for item in values)
    return f'<ul class="{class_name}">{items_html}</ul>'


def severity_badge(severity: Any, messages: dict[str, Any] | None = None) -> str:
    messages = messages or load_messages("en")
    value = text(severity) or message(messages, "report.not_assessed")
    css_value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "not-assessed"
    display_value = translated_term(messages, "severity", value)
    return f'<span class="severity-badge severity-{esc(css_value)}">{esc(display_value)}</span>'


def person_value(item: dict[str, Any], default_role: str = "") -> tuple[str, str, str]:
    name = first_non_empty(item, "name")
    role = first_non_empty(
        item,
        "role",
        "title",
        "position",
        "job_title",
        default=default_role,
    )
    email = first_non_empty(item, "email")
    return name, role, email


def person_card(
    item: dict[str, Any],
    default_role: str = "",
    not_documented: str = "Not documented",
) -> str:
    name, role, email = person_value(item, default_role=default_role)
    if not name and not role and not email:
        return ""

    meta = " · ".join(part for part in [role, email] if part)
    meta_html = f'<div class="person-meta">{esc(meta)}</div>' if meta else ""
    return (
        '<div class="person-card">'
        f'<div class="person-name">{esc(name) or esc(not_documented)}</div>'
        f"{meta_html}"
        "</div>"
    )


def ensure_report_css_reference(content: str, *, generated_from: str = "") -> str:
    def update(front_matter: dict[str, Any]) -> None:
        _apply_report_front_matter(front_matter, generated_from=generated_from)

    return update_front_matter(content, update)


def _apply_report_front_matter(
    front_matter: dict[str, Any],
    *,
    generated_from: str = "",
) -> None:
    metadata_path = "../styles/quarto-html.yml"
    metadata_files = front_matter.get("metadata-files")
    if isinstance(metadata_files, str):
        metadata_files = [metadata_files]
    elif not isinstance(metadata_files, list):
        metadata_files = []
    if metadata_path not in metadata_files:
        metadata_files.insert(0, metadata_path)
    front_matter["metadata-files"] = metadata_files

    report_format = front_matter.get("format")
    if not isinstance(report_format, dict):
        report_format = {}
        front_matter["format"] = report_format

    html_format = report_format.get("html")
    if not isinstance(html_format, dict):
        html_format = {}
        report_format["html"] = html_format

    html_format.setdefault("smooth-scroll", True)
    html_format["css"] = "../styles/report.css"

    if generated_from:
        stamp_observations_digest(front_matter, generated_from)


def read_observations(project_root: Path) -> list[dict[str, Any]]:
    observations = []
    observations_dir = project_root / "06_observations"

    if not observations_dir.exists():
        return observations

    for path in sorted(observations_dir.glob("OBS-*.yml")):
        data = read_optional_yaml_mapping(path)
        if data:
            data["_path"] = path
            observations.append(data)

    return observations


def read_audit_program_rows(project_root: Path) -> list[dict[str, Any]]:
    data = read_optional_yaml_mapping(project_root / "03_audit_program" / "audit_program.yml")
    rows = data.get("program_rows", [])
    return rows if isinstance(rows, list) else []


def read_initial_data(project_root: Path) -> dict[str, Any]:
    return read_optional_yaml_mapping(project_root / "initial_data.yml")


def read_team(project_root: Path) -> dict[str, Any]:
    return read_optional_yaml_mapping(project_root / "00_admin" / "team.yml")


def read_stakeholders(project_root: Path) -> dict[str, Any]:
    return read_optional_yaml_mapping(project_root / "00_admin" / "stakeholders.yml")


def audit_title(
    initial_data: dict[str, Any],
    messages: dict[str, Any] | None = None,
) -> str:
    messages = messages or load_messages("en")
    audit = initial_data.get("audit", {})
    return text(audit.get("title")) or message(messages, "report.internal_audit")


def audit_id(initial_data: dict[str, Any]) -> str:
    audit = initial_data.get("audit", {})
    return text(audit.get("id"))


def company(initial_data: dict[str, Any]) -> str:
    audit = initial_data.get("audit", {})
    return text(audit.get("company"))


def period(initial_data: dict[str, Any]) -> str:
    data = initial_data.get("period", {})
    start = text(data.get("from"))
    end = text(data.get("to"))
    if start and end:
        return f"{start} — {end}"
    return start or end


def build_cover(project_root: Path) -> str:
    initial = read_initial_data(project_root)
    messages = project_messages(project_root)
    logo_path = project_root / "07_reporting" / "assets" / "company_logo.svg"
    logo_html = ""
    if logo_path.exists():
        logo_html = (
            '<div class="cover-logo"><img class="report-logo" '
            f'src="assets/company_logo.svg" alt="{esc(message(messages, "report.company_logo_alt"))}"></div>'
        )

    return f"""```{{=html}}
<div class="report-cover">
<div class="cover-top">
{logo_html}
<div class="cover-company">{esc(company(initial))}</div>
</div>
<div class="cover-title-block">
<h1><span>{esc(audit_title(initial, messages))}</span></h1>
</div>
</div>
```"""


def build_audit_facts(project_root: Path) -> str:
    initial = read_initial_data(project_root)
    messages = project_messages(project_root)
    not_documented = message(messages, "report.not_documented")
    objectives = initial.get("objectives", [])
    scope = initial.get("scope", {})
    scope = scope if isinstance(scope, dict) else {}

    objective_items = []
    if isinstance(objectives, list):
        for obj in objectives:
            if isinstance(obj, dict):
                statement = text(obj.get("statement"))
                if statement:
                    objective_items.append(statement)
            elif text(obj):
                objective_items.append(text(obj))

    return f"""```{{=html}}
<div class="executive-facts-card">
<div class="fact-row">
<div class="fact-label">{esc(message(messages, "report.audit_objective"))}</div>
<div class="fact-value">{list_items_html(objective_items, not_documented=not_documented)}</div>
</div>
<div class="fact-row">
<div class="fact-label">{esc(message(messages, "report.scope"))}</div>
<div class="fact-value">
<div class="scope-block">
<div><strong>{esc(message(messages, "report.in_scope"))}</strong>{list_items_html(scope.get("in_scope", []), not_documented=not_documented)}</div>
<div><strong>{esc(message(messages, "report.out_of_scope"))}</strong>{list_items_html(scope.get("out_of_scope", []), not_documented=not_documented)}</div>
</div>
</div>
</div>
<div class="fact-row">
<div class="fact-label">{esc(message(messages, "report.period_reviewed"))}</div>
<div class="fact-value">{esc(period(initial))}</div>
</div>
<div class="fact-row">
<div class="fact-label">{esc(message(messages, "report.audit_id"))}</div>
<div class="fact-value">{esc(audit_id(initial))}</div>
</div>
</div>
```"""


def build_summary_observations(project_root: Path) -> str:
    observations = read_observations(project_root)
    messages = project_messages(project_root)

    if not observations:
        return message(messages, "report.no_observations")

    items = []
    for obs in observations:
        title = text(obs.get("title")) or message(messages, "report.untitled_observation")
        summary = text(obs.get("executive_summary")) or message(
            messages,
            "report.executive_summary_placeholder",
        )
        items.append(
            '<li class="summary-observation-item">'
            '<div class="summary-observation-main">'
            f'<div class="summary-observation-title">{esc(title)}</div>'
            f'<div class="summary-observation-meta">{severity_badge(obs.get("severity"), messages)}</div>'
            '</div>'
            f'<div class="summary-observation-text">{esc(summary)}</div>'
            '</li>'
        )

    return "```{=html}\n<ol class=\"summary-observation-list\">\n" + "\n".join(items) + "\n</ol>\n```"


def build_detailed_observations(project_root: Path) -> str:
    observations = read_observations(project_root)
    messages = project_messages(project_root)

    if not observations:
        return message(messages, "report.no_observations")

    blocks = []

    for obs in observations:
        obs_id = text(obs.get("observation_id"))
        title = text(obs.get("title")) or message(messages, "report.untitled_observation")
        severity = severity_badge(obs.get("severity"), messages)

        map_items = []
        for action in obs.get("management_action_plan", []) or []:
            if isinstance(action, dict):
                action_text = text(action.get("action"))
                responsible = text(action.get("responsible_name"))
                due_date = text(action.get("due_date"))
                if action_text or responsible or due_date:
                    meta = " · ".join(part for part in [responsible, due_date] if part)
                    map_items.append(
                        "<li>"
                        f"<strong>{esc(text(action.get('action_id')))}</strong>: {esc(action_text)}"
                        + (f" <em>{esc(meta)}</em>" if meta else "")
                        + "</li>"
                    )

        if map_items:
            map_html = (
                '<div class="map-box map-agreed">'
                f'<div class="map-title">{esc(message(messages, "report.action_plan"))}</div>'
                f'<ul class="scope-list">{"".join(map_items)}</ul>'
                "</div>"
            )
        else:
            map_html = (
                '<div class="map-box map-not-agreed">'
                f'<div class="map-title">{esc(message(messages, "report.action_plan"))}</div>'
                f'<p><em>{esc(message(messages, "report.action_plan_missing"))}</em></p>'
                "</div>"
            )

        blocks.append(
            f"""<section class="observation-card">
<div class="observation-header">
<h3>{esc(title)}</h3>
<div>{severity}</div>
</div>
<div class="observation-body">
<div class="observation-meta">
<strong>ID:</strong> {esc(obs_id)} ·
<strong>{esc(message(messages, "report.status"))}:</strong> {esc(translated_term(messages, "status", obs.get("status")))} ·
<strong>{esc(message(messages, "report.risk"))}:</strong> {esc(text(obs.get("risk_id")))} — {esc(text(obs.get("risk_title")))} ·
<strong>{esc(message(messages, "report.workpaper"))}:</strong> {esc(text(obs.get("source_workpaper")))}
</div>
<h4>{esc(message(messages, "report.criteria"))}</h4>
<p>{esc(text(obs.get("criteria")) or message(messages, "report.to_be_completed"))}</p>
<h4>{esc(message(messages, "report.condition"))}</h4>
<p>{esc(text(obs.get("condition")) or message(messages, "report.to_be_completed"))}</p>
<div class="two-column-section">
<div>
<h4>{esc(message(messages, "report.cause"))}</h4>
<p>{esc(text(obs.get("cause")) or message(messages, "report.to_be_completed"))}</p>
</div>
<div>
<h4>{esc(message(messages, "report.risk_effect"))}</h4>
<p>{esc(text(obs.get("risk_effect")) or message(messages, "report.to_be_completed"))}</p>
</div>
</div>
<h4>{esc(message(messages, "report.recommendation"))}</h4>
<div class="recommendation-box">
<p>{esc(text(obs.get("recommendation")) or message(messages, "report.to_be_completed"))}</p>
</div>
{map_html}
</div>
</section>"""
        )

    return "```{=html}\n" + "\n\n".join(blocks) + "\n```"


def build_distribution_team(project_root: Path) -> str:
    stakeholders = read_stakeholders(project_root)
    team = read_team(project_root)
    messages = project_messages(project_root)
    not_documented = message(messages, "report.not_documented")

    recipients = stakeholders.get("report_recipients", [])
    recipient_cards = []
    for item in recipients or []:
        if isinstance(item, dict):
            card = person_card(item, not_documented=not_documented)
            if card:
                recipient_cards.append(card)
        else:
            recipient_cards.append(
                person_card({"name": item}, not_documented=not_documented)
            )

    team_data = nested_dict(team, "team") or team
    lead = team_data.get("engagement_lead", {})
    members = team_data.get("members", []) or []
    review = nested_dict(team, "review")
    reviewer = review.get("reviewer") or team.get("reviewer", {})

    team_cards = []
    if lead:
        card = person_card(
            lead,
            default_role=message(messages, "report.engagement_lead"),
            not_documented=not_documented,
        )
        if card:
            team_cards.append(card)

    for member in members:
        if isinstance(member, dict):
            card = person_card(member, not_documented=not_documented)
            if card:
                team_cards.append(card)

    if reviewer:
        card = person_card(
            reviewer,
            default_role=message(messages, "report.reviewer"),
            not_documented=not_documented,
        )
        if card:
            team_cards.append(card)

    recipients_html = "\n".join(recipient_cards) or (
        f'<p><em>{esc(message(messages, "report.no_recipients"))}</em></p>'
    )
    team_html = "\n".join(team_cards) or (
        f'<p><em>{esc(message(messages, "report.no_team"))}</em></p>'
    )

    return f"""```{{=html}}
<section class="distribution-section">
<h2>{esc(message(messages, "report.report_recipients"))}</h2>
<div class="people-grid">
{recipients_html}
</div>
<h2>{esc(message(messages, "report.audit_team"))}</h2>
<div class="people-grid">
{team_html}
</div>
</section>
```"""


def build_blocks(project_root: Path) -> dict[str, str]:
    return {
        "COVER": build_cover(project_root),
        "AUDIT_FACTS": build_audit_facts(project_root),
        "SUMMARY_OBSERVATIONS": build_summary_observations(project_root),
        "DETAILED_OBSERVATIONS": build_detailed_observations(project_root),
        "DISTRIBUTION_TEAM": build_distribution_team(project_root),
    }


def update_report_qmd(project_root: Path, reset_report: bool = False) -> ReportUpdate:
    reporting_dir = project_root / "07_reporting"
    reporting_dir.mkdir(parents=True, exist_ok=True)
    report_path = reporting_dir / "report.qmd"

    if reset_report or not report_path.exists():
        report_path.write_text(
            read_localized_template("report.qmd", read_project_language(project_root)),
            encoding="utf-8",
        )

    content = report_path.read_text(encoding="utf-8")
    missing = missing_block_names(content, REPORT_BLOCK_NAMES)
    content = ensure_report_css_reference(
        content,
        generated_from=observations_digest(project_root),
    )
    content = replace_auto_blocks(content, build_blocks(project_root))
    report_path.write_text(content, encoding="utf-8")

    return ReportUpdate(path=report_path, missing_blocks=missing)
