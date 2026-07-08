from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

import yaml

from auditflow.template_utils import read_template


AUTO_BLOCK_RE = re.compile(
    r"<!-- AUTO:(?P<name>[A-Z0-9_]+) START -->.*?<!-- AUTO:(?P=name) END -->",
    re.DOTALL,
)

FRONT_MATTER_RE = re.compile(r"\A---\n(?P<yaml>.*?)\n---\n?", re.DOTALL)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    return data if isinstance(data, dict) else {}


def load_yaml_list(path: Path) -> list[dict[str, Any]]:
    data = load_yaml(path)
    if isinstance(data, list):
        return data
    return []


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


def list_items_html(items: Any, class_name: str = "scope-list") -> str:
    if not isinstance(items, list):
        return "<p><em>Not documented.</em></p>"

    values = [text(item) for item in items if text(item)]
    if not values:
        return "<p><em>Not documented.</em></p>"

    items_html = "".join(f"<li>{esc(item)}</li>" for item in values)
    return f'<ul class="{class_name}">{items_html}</ul>'


def severity_badge(severity: Any) -> str:
    value = text(severity) or "Not assessed"
    css_value = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "not-assessed"
    return f'<span class="severity-badge severity-{esc(css_value)}">{esc(value)}</span>'


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


def person_card(item: dict[str, Any], default_role: str = "") -> str:
    name, role, email = person_value(item, default_role=default_role)
    if not name and not role and not email:
        return ""

    meta = " · ".join(part for part in [role, email] if part)
    meta_html = f'<div class="person-meta">{esc(meta)}</div>' if meta else ""
    return (
        '<div class="person-card">'
        f'<div class="person-name">{esc(name) or "Not documented"}</div>'
        f"{meta_html}"
        "</div>"
    )


def md_table(headers: list[str], rows: list[list[Any]]) -> str:
    if not rows:
        return "_No data available._"

    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join(
        "| " + " | ".join(text(cell).replace("\n", "<br>") for cell in row) + " |"
        for row in rows
    )
    return "\n".join([header, separator, body])


def replace_auto_blocks(content: str, blocks: dict[str, str]) -> str:
    def repl(match: re.Match[str]) -> str:
        name = match.group("name")
        replacement = blocks.get(name, "").strip()
        return f"<!-- AUTO:{name} START -->\n{replacement}\n<!-- AUTO:{name} END -->"

    return AUTO_BLOCK_RE.sub(repl, content)


def ensure_report_css_reference(content: str) -> str:
    match = FRONT_MATTER_RE.match(content)
    if not match:
        return content

    front_matter = yaml.safe_load(match.group("yaml")) or {}
    if not isinstance(front_matter, dict):
        return content

    report_format = front_matter.get("format")
    if not isinstance(report_format, dict):
        report_format = {}
        front_matter["format"] = report_format

    html_format = report_format.get("html")
    if not isinstance(html_format, dict):
        html_format = {}
        report_format["html"] = html_format

    html_format.setdefault("toc", True)
    html_format.setdefault("toc-depth", 3)
    html_format.setdefault("number-sections", False)
    html_format.setdefault("smooth-scroll", True)
    html_format.setdefault("code-fold", True)
    html_format.setdefault("theme", "cosmo")
    html_format["css"] = "../styles/report.css"

    if "execute" not in front_matter:
        front_matter["execute"] = {
            "echo": False,
            "warning": False,
            "message": False,
        }

    body = content[match.end() :]
    updated_front_matter = yaml.safe_dump(
        front_matter,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    ).strip()

    return f"---\n{updated_front_matter}\n---\n\n{body.lstrip()}"


def read_observations(project_root: Path) -> list[dict[str, Any]]:
    observations = []
    observations_dir = project_root / "06_observations"

    if not observations_dir.exists():
        return observations

    for path in sorted(observations_dir.glob("OBS-*.yml")):
        data = load_yaml(path)
        if data:
            data["_path"] = path
            observations.append(data)

    return observations


def read_audit_program_rows(project_root: Path) -> list[dict[str, Any]]:
    data = load_yaml(project_root / "03_audit_program" / "audit_program.yml")
    rows = data.get("program_rows", [])
    return rows if isinstance(rows, list) else []


def read_initial_data(project_root: Path) -> dict[str, Any]:
    return load_yaml(project_root / "initial_data.yml")


def read_team(project_root: Path) -> dict[str, Any]:
    return load_yaml(project_root / "00_admin" / "team.yml")


def read_stakeholders(project_root: Path) -> dict[str, Any]:
    return load_yaml(project_root / "00_admin" / "stakeholders.yml")


def audit_title(initial_data: dict[str, Any]) -> str:
    audit = initial_data.get("audit", {})
    return text(audit.get("title")) or "Internal Audit"


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


def lead_name(team: dict[str, Any]) -> str:
    team_data = nested_dict(team, "team") or team
    lead = team_data.get("engagement_lead", {})
    return text(lead.get("name"))


def reviewer_name(team: dict[str, Any]) -> str:
    review = nested_dict(team, "review")
    reviewer = review.get("reviewer") or team.get("reviewer", {})
    return text(reviewer.get("name"))


def sponsor_name(stakeholders: dict[str, Any]) -> str:
    sponsor = stakeholders.get("sponsor", {})
    return text(sponsor.get("name"))


def build_cover(project_root: Path) -> str:
    initial = read_initial_data(project_root)
    logo_path = project_root / "07_reporting" / "assets" / "company_logo.svg"
    logo_html = ""
    if logo_path.exists():
        logo_html = '<div class="cover-logo"><img class="report-logo" src="assets/company_logo.svg" alt="Company logo"></div>'

    return f"""```{{=html}}
<div class="report-cover">
<div class="cover-top">
{logo_html}
<div class="cover-company">{esc(company(initial))}</div>
</div>
<div class="cover-title-block">
<h1><span>{esc(audit_title(initial))}</span></h1>
</div>
</div>
```"""


def build_audit_facts(project_root: Path) -> str:
    initial = read_initial_data(project_root)
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
<div class="fact-label">Audit objective</div>
<div class="fact-value">{list_items_html(objective_items)}</div>
</div>
<div class="fact-row">
<div class="fact-label">Scope</div>
<div class="fact-value">
<div class="scope-block">
<div><strong>In scope</strong>{list_items_html(scope.get("in_scope", []))}</div>
<div><strong>Out of scope</strong>{list_items_html(scope.get("out_of_scope", []))}</div>
</div>
</div>
</div>
<div class="fact-row">
<div class="fact-label">Period reviewed</div>
<div class="fact-value">{esc(period(initial))}</div>
</div>
<div class="fact-row">
<div class="fact-label">Audit ID</div>
<div class="fact-value">{esc(audit_id(initial))}</div>
</div>
</div>
```"""


def build_summary_observations(project_root: Path) -> str:
    observations = read_observations(project_root)

    if not observations:
        return "_No observations created yet._"

    items = []
    for obs in observations:
        title = text(obs.get("title")) or "Untitled observation"
        summary = text(obs.get("executive_summary")) or "Executive summary wording to be completed by auditor."
        items.append(
            '<li class="summary-observation-item">'
            '<div class="summary-observation-main">'
            f'<div class="summary-observation-title">{esc(title)}</div>'
            f'<div class="summary-observation-meta">{severity_badge(obs.get("severity"))}</div>'
            '</div>'
            f'<div class="summary-observation-text">{esc(summary)}</div>'
            '</li>'
        )

    return "```{=html}\n<ol class=\"summary-observation-list\">\n" + "\n".join(items) + "\n</ol>\n```"


def build_detailed_observations(project_root: Path) -> str:
    observations = read_observations(project_root)

    if not observations:
        return "_No observations created yet._"

    blocks = []

    for obs in observations:
        obs_id = text(obs.get("observation_id"))
        title = text(obs.get("title")) or "Untitled observation"
        severity = severity_badge(obs.get("severity"))

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
                '<div class="map-title">Management action plan</div>'
                f'<ul class="scope-list">{"".join(map_items)}</ul>'
                "</div>"
            )
        else:
            map_html = (
                '<div class="map-box map-not-agreed">'
                '<div class="map-title">Management action plan</div>'
                "<p><em>Management action plan has not yet been documented or agreed.</em></p>"
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
<strong>Status:</strong> {esc(text(obs.get("status")))} ·
<strong>Risk:</strong> {esc(text(obs.get("risk_id")))} — {esc(text(obs.get("risk_title")))} ·
<strong>Workpaper:</strong> {esc(text(obs.get("source_workpaper")))}
</div>
<h4>Criteria</h4>
<p>{esc(text(obs.get("criteria")) or "To be completed.")}</p>
<h4>Condition</h4>
<p>{esc(text(obs.get("condition")) or "To be completed.")}</p>
<div class="two-column-section">
<div>
<h4>Cause</h4>
<p>{esc(text(obs.get("cause")) or "To be completed.")}</p>
</div>
<div>
<h4>Risk / Effect</h4>
<p>{esc(text(obs.get("risk_effect")) or "To be completed.")}</p>
</div>
</div>
<h4>Internal audit recommendation</h4>
<div class="recommendation-box">
<p>{esc(text(obs.get("recommendation")) or "To be completed.")}</p>
</div>
{map_html}
</div>
</section>"""
        )

    return "```{=html}\n" + "\n\n".join(blocks) + "\n```"


def build_distribution_team(project_root: Path) -> str:
    stakeholders = read_stakeholders(project_root)
    team = read_team(project_root)

    recipients = stakeholders.get("report_recipients", [])
    recipient_cards = []
    for item in recipients or []:
        if isinstance(item, dict):
            card = person_card(item)
            if card:
                recipient_cards.append(card)
        else:
            recipient_cards.append(person_card({"name": item}))

    team_data = nested_dict(team, "team") or team
    lead = team_data.get("engagement_lead", {})
    members = team_data.get("members", []) or []
    review = nested_dict(team, "review")
    reviewer = review.get("reviewer") or team.get("reviewer", {})

    team_cards = []
    if lead:
        card = person_card(lead, default_role="Engagement Lead")
        if card:
            team_cards.append(card)

    for member in members:
        if isinstance(member, dict):
            card = person_card(member)
            if card:
                team_cards.append(card)

    if reviewer:
        card = person_card(reviewer, default_role="Reviewer")
        if card:
            team_cards.append(card)

    recipients_html = "\n".join(recipient_cards) or "<p><em>No report recipients documented.</em></p>"
    team_html = "\n".join(team_cards) or "<p><em>No audit team documented.</em></p>"

    return f"""```{{=html}}
<section class="distribution-section">
<h2>Report recipients</h2>
<div class="people-grid">
{recipients_html}
</div>
<h2>Audit team</h2>
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


def update_report_qmd(project_root: Path, reset_report: bool = False) -> Path:
    reporting_dir = project_root / "07_reporting"
    reporting_dir.mkdir(parents=True, exist_ok=True)
    report_path = reporting_dir / "report.qmd"

    if reset_report or not report_path.exists():
        report_path.write_text(read_template("report.qmd"), encoding="utf-8")

    content = report_path.read_text(encoding="utf-8")
    content = ensure_report_css_reference(content)
    content = replace_auto_blocks(content, build_blocks(project_root))
    report_path.write_text(content, encoding="utf-8")

    return report_path


def write_supporting_files(project_root: Path, overwrite_css: bool = False, overwrite_logo: bool = False) -> dict[str, str]:
    """Compatibility shim.

    Report styling is created by init_project.py in project-level styles/report.css.
    """
    return {
        "css_path": str(project_root / "styles" / "report.css"),
        "logo_path": "",
    }
