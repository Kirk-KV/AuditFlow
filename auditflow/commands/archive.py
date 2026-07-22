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
    team_data = team.get("team", {})
    lead = team_data.get("engagement_lead", {})
    return text(lead.get("name"))


def reviewer_name(team: dict[str, Any]) -> str:
    review = team.get("review", {})
    reviewer = review.get("reviewer", {})
    return text(reviewer.get("name"))


def sponsor_name(stakeholders: dict[str, Any]) -> str:
    sponsor = stakeholders.get("sponsor", {})
    return text(sponsor.get("name"))

def build_cover(project_root: Path) -> str:
    initial = read_initial_data(project_root)
    return f"""::: {{.audit-card}}
# {audit_title(initial)}

**Company:** {company(initial)}<br>
**Audit period:** {period(initial)}<br>
**Audit ID:** {audit_id(initial)}
:::"""


def build_one_page_story(project_root: Path) -> str:
    observations = read_observations(project_root)
    rows = [
        ["Audit", audit_title(read_initial_data(project_root))],
        ["Program rows", len(read_audit_program_rows(project_root))],
        ["Observations", len(observations)],
    ]

    return "\n".join(
        [
            md_table(["Item", "Value"], rows),
            "",
            "::: {.manual-block}",
            "Add a short narrative explaining what changed from initial plan to final conclusion.",
            ":::",
        ]
    )


def build_initial_assumptions(project_root: Path) -> str:
    initial = read_initial_data(project_root)
    risks = initial.get("risks", [])
    rows = []
    if isinstance(risks, list):
        for risk in risks:
            if isinstance(risk, dict):
                rows.append([
                    risk.get("id", ""),
                    risk.get("title", ""),
                    risk.get("rationale", ""),
                    risk.get("preliminary_rating", ""),
                ])

    return md_table(["Risk ID", "Title", "Initial rationale", "Preliminary rating"], rows)


def build_planning_decisions(project_root: Path) -> str:
    planning = load_yaml(project_root / "01_planning" / "planning_decision.yml")
    included = planning.get("included_risks", [])
    excluded = planning.get("excluded_risks", [])

    included_rows = []
    for risk in included or []:
        if isinstance(risk, dict):
            included_rows.append([
                risk.get("id", ""),
                risk.get("title", ""),
                risk.get("rationale", ""),
                risk.get("planned_response", ""),
            ])

    excluded_rows = []
    for risk in excluded or []:
        if isinstance(risk, dict):
            excluded_rows.append([
                risk.get("id", ""),
                risk.get("title", ""),
                risk.get("rationale", ""),
            ])

    return "\n\n".join(
        [
            "## Included risks",
            md_table(["Risk ID", "Title", "Rationale", "Planned response"], included_rows),
            "",
            "## Excluded risks",
            md_table(["Risk ID", "Title", "Rationale"], excluded_rows),
        ]
    )


def build_scope_risk_evolution(project_root: Path) -> str:
    planning = load_yaml(project_root / "01_planning" / "planning_decision.yml")
    scope = planning.get("scope", {})
    in_scope = scope.get("in_scope", []) or []
    out_scope = scope.get("out_of_scope", []) or []

    return "\n".join(
        [
            "## Final in-scope areas",
            "\n".join(f"- {text(item)}" for item in in_scope if text(item)) or "_Not documented._",
            "",
            "## Final out-of-scope areas",
            "\n".join(f"- {text(item)}" for item in out_scope if text(item)) or "_Not documented._",
        ]
    )


def build_testing_traceability(project_root: Path) -> str:
    rows = []
    for row in read_audit_program_rows(project_root):
        if isinstance(row, dict):
            rows.append([
                row.get("test_id", ""),
                row.get("risk_id", ""),
                row.get("control_id") or "",
                row.get("test_hypothesis", ""),
                row.get("workpaper_ref", ""),
            ])

    return md_table(["Test ID", "Risk", "Control", "Hypothesis", "Workpaper"], rows)


def build_observations_outcome(project_root: Path) -> str:
    observations = read_observations(project_root)
    rows = [
        [
            obs.get("observation_id", ""),
            obs.get("title", ""),
            obs.get("severity", ""),
            obs.get("status", ""),
            obs.get("source_workpaper", ""),
        ]
        for obs in observations
    ]
    return md_table(["ID", "Title", "Severity", "Status", "Workpaper"], rows)


def build_evidence_map(project_root: Path) -> str:
    evidence_dir = project_root / "04_evidence"
    rows = []
    if evidence_dir.exists():
        for path in sorted(evidence_dir.rglob("*")):
            if path.is_file():
                rows.append([str(path.relative_to(project_root)), ""])

    return md_table(["File", "Notes"], rows)


def build_blocks(project_root: Path) -> dict[str, str]:
    return {
        "COVER": build_cover(project_root),
        "ONE_PAGE_STORY": build_one_page_story(project_root),
        "INITIAL_ASSUMPTIONS": build_initial_assumptions(project_root),
        "PLANNING_DECISIONS": build_planning_decisions(project_root),
        "SCOPE_RISK_EVOLUTION": build_scope_risk_evolution(project_root),
        "TESTING_TRACEABILITY": build_testing_traceability(project_root),
        "OBSERVATIONS_OUTCOME": build_observations_outcome(project_root),
        "EVIDENCE_MAP": build_evidence_map(project_root),
    }


def update_archive(project_root: Path, reset: bool = False) -> Path:
    archive_dir = project_root / "09_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "audit_story.qmd"

    if reset or not archive_path.exists():
        archive_path.write_text(read_template("audit_story.qmd"), encoding="utf-8")

    content = archive_path.read_text(encoding="utf-8")
    content = replace_auto_blocks(content, build_blocks(project_root))
    archive_path.write_text(content, encoding="utf-8")

    return archive_path


def write_css(project_root: Path, overwrite_css: bool = False) -> Path:
    """Compatibility shim.

    Archive styling now comes from project-level _quarto.yml and styles/*.css.
    """
    return project_root / "styles" / "auditflow.css"
