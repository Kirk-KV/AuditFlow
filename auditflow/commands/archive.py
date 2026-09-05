from __future__ import annotations

import html
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from auditflow.blocks import (
    ARCHIVE_BLOCK_NAMES,
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
from auditflow.commands.evidence import EXCLUDED_FILE_NAMES


@dataclass(frozen=True)
class ArchiveUpdate:
    path: Path
    missing_blocks: tuple[str, ...]


def esc(value: Any) -> str:
    return html.escape("" if value is None else str(value))


def text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def md_table(
    headers: list[str],
    rows: list[list[Any]],
    empty_text: str = "_No data available._",
) -> str:
    if not rows:
        return empty_text

    header = "| " + " | ".join(headers) + " |"
    separator = "| " + " | ".join(["---"] * len(headers)) + " |"
    body = "\n".join(
        "| " + " | ".join(text(cell).replace("\n", "<br>") for cell in row) + " |"
        for row in rows
    )
    return "\n".join([header, separator, body])


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
    return text(audit.get("title")) or message(messages, "archive.internal_audit")


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
    return f"""::: {{.audit-card}}
# {audit_title(initial, messages)}

**{message(messages, 'archive.company')}:** {company(initial)}<br>
**{message(messages, 'archive.audit_period')}:** {period(initial)}<br>
**{message(messages, 'archive.audit_id')}:** {audit_id(initial)}
:::"""


def build_one_page_story(project_root: Path) -> str:
    observations = read_observations(project_root)
    messages = project_messages(project_root)
    rows = [
        [message(messages, "archive.audit"), audit_title(read_initial_data(project_root), messages)],
        [message(messages, "archive.program_rows"), len(read_audit_program_rows(project_root))],
        [message(messages, "archive.observations"), len(observations)],
    ]

    return "\n".join(
        [
            md_table(
                [message(messages, "archive.item"), message(messages, "archive.value")],
                rows,
                empty_text=message(messages, "archive.no_data"),
            ),
            "",
            "::: {.manual-block}",
            message(messages, "archive.story_prompt"),
            ":::",
        ]
    )


def build_initial_assumptions(project_root: Path) -> str:
    initial = read_initial_data(project_root)
    messages = project_messages(project_root)
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

    return md_table(
        message(messages, "archive.risk_headers"),
        rows,
        empty_text=message(messages, "archive.no_data"),
    )


def build_planning_decisions(project_root: Path) -> str:
    planning = read_optional_yaml_mapping(project_root / "01_planning" / "planning_decision.yml")
    included = planning.get("included_risks", [])
    excluded = planning.get("excluded_risks", [])
    messages = project_messages(project_root)

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
            f"## {message(messages, 'archive.included_risks')}",
            md_table(
                message(messages, "archive.included_headers"),
                included_rows,
                empty_text=message(messages, "archive.no_data"),
            ),
            "",
            f"## {message(messages, 'archive.excluded_risks')}",
            md_table(
                message(messages, "archive.excluded_headers"),
                excluded_rows,
                empty_text=message(messages, "archive.no_data"),
            ),
        ]
    )


def build_scope_risk_evolution(project_root: Path) -> str:
    planning = read_optional_yaml_mapping(project_root / "01_planning" / "planning_decision.yml")
    scope = planning.get("scope", {})
    in_scope = scope.get("in_scope", []) or []
    out_scope = scope.get("out_of_scope", []) or []
    messages = project_messages(project_root)

    return "\n".join(
        [
            f"## {message(messages, 'archive.final_in_scope')}",
            "\n".join(f"- {text(item)}" for item in in_scope if text(item))
            or message(messages, "archive.not_documented"),
            "",
            f"## {message(messages, 'archive.final_out_of_scope')}",
            "\n".join(f"- {text(item)}" for item in out_scope if text(item))
            or message(messages, "archive.not_documented"),
        ]
    )


def build_testing_traceability(project_root: Path) -> str:
    messages = project_messages(project_root)
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

    return md_table(
        message(messages, "archive.testing_headers"),
        rows,
        empty_text=message(messages, "archive.no_data"),
    )


def build_observations_outcome(project_root: Path) -> str:
    observations = read_observations(project_root)
    messages = project_messages(project_root)
    rows = [
        [
            obs.get("observation_id", ""),
            obs.get("title", ""),
            translated_term(messages, "severity", obs.get("severity", "")),
            translated_term(messages, "status", obs.get("status", "")),
            obs.get("source_workpaper", ""),
        ]
        for obs in observations
    ]
    return md_table(
        message(messages, "archive.observation_headers"),
        rows,
        empty_text=message(messages, "archive.no_data"),
    )


def build_evidence_map(project_root: Path) -> str:
    evidence_dir = project_root / "04_evidence"
    rows = []
    messages = project_messages(project_root)
    if evidence_dir.exists():
        for path in sorted(evidence_dir.rglob("*")):
            if (
                path.is_file()
                and "__pycache__" not in path.relative_to(evidence_dir).parts
                and path.suffix.lower() not in {".pyc", ".pyo"}
                and path.name not in EXCLUDED_FILE_NAMES
            ):
                rows.append([path.relative_to(project_root).as_posix(), ""])

    return md_table(
        message(messages, "archive.evidence_headers"),
        rows,
        empty_text=message(messages, "archive.no_data"),
    )


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


def update_archive(project_root: Path, reset: bool = False) -> ArchiveUpdate:
    archive_dir = project_root / "09_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    archive_path = archive_dir / "audit_story.qmd"

    if reset or not archive_path.exists():
        archive_path.write_text(
            read_localized_template("audit_story.qmd", read_project_language(project_root)),
            encoding="utf-8",
        )

    content = archive_path.read_text(encoding="utf-8")
    missing = missing_block_names(content, ARCHIVE_BLOCK_NAMES)
    digest = observations_digest(project_root)
    content = update_front_matter(
        content,
        lambda front_matter: stamp_observations_digest(front_matter, digest),
    )
    content = replace_auto_blocks(content, build_blocks(project_root))
    archive_path.write_text(content, encoding="utf-8")

    return ArchiveUpdate(path=archive_path, missing_blocks=missing)
