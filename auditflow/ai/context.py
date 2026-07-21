from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


WORKPAPER_REF_PATTERN = re.compile(r"^WP-[A-Za-z0-9_-]+$")
OBSERVATION_ID_PATTERN = re.compile(r"^OBS-\d{3,}$")
H2_PATTERN = re.compile(r"^##[ \t]+(.+?)[ \t]*$", re.MULTILINE)

WORKPAPER_SECTIONS = {
    "work performed": "Work performed",
    "evidence used": "Evidence used",
    "evidence used and evaluated": "Evidence used and evaluated",
    "results": "Results",
    "conclusion": "Conclusion",
    "observation proposal": "Observation proposal",
    "potential observation": "Observation proposal",
}


class AIContextError(ValueError):
    """Raised when a safe observation context cannot be assembled."""


@dataclass(frozen=True)
class SourceFragment:
    path: str
    selection: str
    content: Any
    sha256: str
    character_count: int


@dataclass(frozen=True)
class ObservationContext:
    workpaper_ref: str
    test_id: str
    risk_id: str
    risk_text: str
    control_id: str | None
    fragments: tuple[SourceFragment, ...]
    workpaper_sections: dict[str, str]

    @property
    def character_count(self) -> int:
        return sum(fragment.character_count for fragment in self.fragments)


@dataclass(frozen=True)
class ObservationReviewContext:
    observation_id: str
    observation: dict[str, Any]
    audit_context: ObservationContext

    @property
    def fragments(self) -> tuple[SourceFragment, ...]:
        return self.audit_context.fragments


@dataclass(frozen=True)
class AuditProgramReviewContext:
    fragments: tuple[SourceFragment, ...]
    risks: tuple[dict[str, Any], ...]
    controls: tuple[dict[str, Any], ...]
    recommended_tests: tuple[dict[str, Any], ...]
    program_rows: tuple[dict[str, Any], ...]

    @property
    def character_count(self) -> int:
        return sum(fragment.character_count for fragment in self.fragments)


def _load_yaml(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise AIContextError(f"Missing {label}: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise AIContextError(f"Cannot read {label} {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise AIContextError(f"{label} must contain a YAML mapping: {path}")
    return data


def _prune_empty(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: cleaned
            for key, item in value.items()
            if (cleaned := _prune_empty(item)) not in (None, "", [], {})
        }
    if isinstance(value, list):
        return [
            cleaned
            for item in value
            if (cleaned := _prune_empty(item)) not in (None, "", [], {})
        ]
    return value


def _matching_items(value: Any, key: str, expected: str | None) -> list[dict[str, Any]]:
    if not expected or not isinstance(value, list):
        return []
    return [
        item
        for item in value
        if isinstance(item, dict) and str(item.get(key) or "") == expected
    ]


def _risk_text(title: str, records: tuple[dict[str, Any], ...]) -> str:
    description = ""
    for risk_record in records:
        description = str(
            risk_record.get("rationale")
            or risk_record.get("description")
            or risk_record.get("reasoning")
            or ""
        ).strip()
        if description:
            break
    if description and description.lower() != title.lower():
        return f"{title} - {description}" if title else description
    return title


def _serialize_content(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    return yaml.safe_dump(content, allow_unicode=True, sort_keys=True, width=120).strip()


def _fragment(path: str, selection: str, content: Any) -> SourceFragment | None:
    cleaned = _prune_empty(content)
    if cleaned in (None, "", [], {}):
        return None
    serialized = _serialize_content(cleaned)
    return SourceFragment(
        path=path,
        selection=selection,
        content=cleaned,
        sha256=hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        character_count=len(serialized),
    )


def make_source_fragment(path: str, selection: str, content: Any) -> SourceFragment:
    fragment = _fragment(path, selection, content)
    if fragment is None:
        raise AIContextError(f"Selected AI source is empty: {path} ({selection})")
    return fragment


def extract_workpaper_sections(text: str) -> dict[str, str]:
    matches = list(H2_PATTERN.finditer(text))
    sections: dict[str, str] = {}

    for index, match in enumerate(matches):
        heading = re.sub(r"[ \t]+", " ", match.group(1).strip()).lower()
        canonical_name = WORKPAPER_SECTIONS.get(heading)
        if not canonical_name:
            continue

        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        content = text[start:end].strip()
        if canonical_name in sections and sections[canonical_name]:
            continue
        sections[canonical_name] = content

    return sections


def _find_program_row(audit_program: dict[str, Any], workpaper_ref: str) -> dict[str, Any]:
    rows = audit_program.get("program_rows", [])
    if not isinstance(rows, list):
        raise AIContextError("audit_program.yml: program_rows must be a list")

    matches = [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("workpaper_ref") or "") == workpaper_ref
    ]
    if not matches:
        raise AIContextError(
            f"No audit program row references workpaper {workpaper_ref}"
        )
    if len(matches) > 1:
        raise AIContextError(
            f"Multiple audit program rows reference workpaper {workpaper_ref}"
        )
    return matches[0]


def build_observation_context(project_root: Path, workpaper_ref: str) -> ObservationContext:
    workpaper_ref = workpaper_ref.strip().upper()
    if not WORKPAPER_REF_PATTERN.fullmatch(workpaper_ref):
        raise AIContextError(
            "Workpaper reference must match WP-[A-Za-z0-9_-]+, for example WP-C-001"
        )

    initial_data = _load_yaml(project_root / "initial_data.yml", "initial data")
    planning = _load_yaml(
        project_root / "01_planning" / "planning_decision.yml",
        "planning decision",
    )
    audit_program = _load_yaml(
        project_root / "03_audit_program" / "audit_program.yml",
        "audit program",
    )
    program_row = _find_program_row(audit_program, workpaper_ref)

    test_id = str(program_row.get("test_id") or "").strip()
    risk_id = str(program_row.get("risk_id") or "").strip()
    risk_title = str(program_row.get("risk_title") or "").strip()
    control_id = str(program_row.get("control_id") or "").strip() or None

    workpaper_path = project_root / "05_workpapers" / f"{workpaper_ref}.qmd"
    if not workpaper_path.exists():
        raise AIContextError(f"Missing workpaper: {workpaper_path}")
    try:
        workpaper_text = workpaper_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise AIContextError(f"Cannot read workpaper {workpaper_path}: {exc}") from exc
    workpaper_sections = extract_workpaper_sections(workpaper_text)

    initial_risks = _matching_items(initial_data.get("risks"), "id", risk_id)
    planning_risks = _matching_items(planning.get("included_risks"), "id", risk_id)
    risk_text = _risk_text(risk_title, (*initial_risks, *planning_risks))

    initial_selection = {
        "audit": initial_data.get("audit"),
        "objectives": initial_data.get("objectives"),
        "period": initial_data.get("period"),
        "scope": initial_data.get("scope"),
        "risk": initial_risks,
    }
    planning_selection = {
        "overall_conclusion": planning.get("overall_conclusion"),
        "scope": planning.get("scope"),
        "included_risk": planning_risks,
        "control": _matching_items(planning.get("controls"), "id", control_id),
        "recommended_test": _matching_items(
            planning.get("recommended_tests"), "id", test_id
        ),
    }

    fragments = [
        _fragment(
            "initial_data.yml",
            f"audit, objectives, period, scope, risk {risk_id}",
            initial_selection,
        ),
        _fragment(
            "01_planning/planning_decision.yml",
            f"scope and linked risk/control/test for {workpaper_ref}",
            planning_selection,
        ),
        _fragment(
            "03_audit_program/audit_program.yml",
            f"program row with workpaper_ref {workpaper_ref}",
            program_row,
        ),
        _fragment(
            f"05_workpapers/{workpaper_ref}.qmd",
            "Work performed, Evidence used, Results, Conclusion, Observation proposal",
            workpaper_sections,
        ),
    ]

    return ObservationContext(
        workpaper_ref=workpaper_ref,
        test_id=test_id,
        risk_id=risk_id,
        risk_text=risk_text,
        control_id=control_id,
        fragments=tuple(fragment for fragment in fragments if fragment is not None),
        workpaper_sections=workpaper_sections,
    )


def build_observation_review_context(
    project_root: Path,
    observation_id: str,
) -> ObservationReviewContext:
    observation_id = observation_id.strip().upper()
    if not OBSERVATION_ID_PATTERN.fullmatch(observation_id):
        raise AIContextError(
            "Observation ID must match OBS-[0-9]{3,}, for example OBS-001"
        )

    observation_path = project_root / "06_observations" / f"{observation_id}.yml"
    observation = _load_yaml(observation_path, "observation")
    source_workpaper = str(observation.get("source_workpaper") or "").strip().upper()
    if not source_workpaper:
        raise AIContextError(f"Observation {observation_id} has no source_workpaper")

    audit_context = build_observation_context(project_root, source_workpaper)
    observation_fragment = make_source_fragment(
        f"06_observations/{observation_id}.yml",
        "complete observation draft",
        observation,
    )
    audit_context = ObservationContext(
        workpaper_ref=audit_context.workpaper_ref,
        test_id=audit_context.test_id,
        risk_id=audit_context.risk_id,
        risk_text=audit_context.risk_text,
        control_id=audit_context.control_id,
        fragments=(*audit_context.fragments, observation_fragment),
        workpaper_sections=audit_context.workpaper_sections,
    )
    return ObservationReviewContext(
        observation_id=observation_id,
        observation=observation,
        audit_context=audit_context,
    )


def build_audit_program_review_context(project_root: Path) -> AuditProgramReviewContext:
    initial_data = _load_yaml(project_root / "initial_data.yml", "initial data")
    planning = _load_yaml(
        project_root / "01_planning" / "planning_decision.yml",
        "planning decision",
    )
    audit_program = _load_yaml(
        project_root / "03_audit_program" / "audit_program.yml",
        "audit program",
    )

    initial_risks = initial_data.get("risks", [])
    planning_risks = planning.get("included_risks", [])
    program_rows = audit_program.get("program_rows", [])
    if not isinstance(initial_risks, list):
        raise AIContextError("initial_data.yml: risks must be a list")
    if not isinstance(planning_risks, list):
        raise AIContextError("planning_decision.yml: included_risks must be a list")
    if not isinstance(program_rows, list):
        raise AIContextError("audit_program.yml: program_rows must be a list")

    controls = planning.get("controls", [])
    recommended_tests = planning.get("recommended_tests", [])
    if not isinstance(controls, list):
        raise AIContextError("planning_decision.yml: controls must be a list")
    if not isinstance(recommended_tests, list):
        raise AIContextError("planning_decision.yml: recommended_tests must be a list")

    initial_risks_by_id = {
        str(item.get("id") or ""): item
        for item in initial_risks
        if isinstance(item, dict) and item.get("id")
    }
    selected_risks = planning_risks or initial_risks
    review_risks = []
    for selected_risk in selected_risks:
        if not isinstance(selected_risk, dict):
            continue
        risk_id = str(selected_risk.get("id") or "").strip()
        initial_risk = initial_risks_by_id.get(risk_id, {})
        title = str(
            initial_risk.get("title") or selected_risk.get("title") or ""
        ).strip()
        review_risks.append(
            _prune_empty(
                {
                    "risk_id": risk_id,
                    "title": title,
                    "risk_text": _risk_text(title, (initial_risk, selected_risk)),
                    "planning_reasoning": selected_risk.get("reasoning"),
                }
            )
        )

    safe_program_rows = [
        {key: value for key, value in row.items() if key != "test_script"}
        for row in program_rows
        if isinstance(row, dict)
    ]
    safe_audit_program = {
        key: value for key, value in audit_program.items() if key != "program_rows"
    }
    safe_audit_program["program_rows"] = safe_program_rows

    initial_selection = {
        "audit": initial_data.get("audit"),
        "objectives": initial_data.get("objectives"),
        "scope": initial_data.get("scope"),
        "risks": initial_risks,
    }
    planning_selection = {
        "overall_conclusion": planning.get("overall_conclusion"),
        "scope": planning.get("scope"),
        "included_risks": planning_risks,
        "excluded_risks": planning.get("excluded_risks"),
        "controls": planning.get("controls"),
        "recommended_tests": planning.get("recommended_tests"),
    }
    fragments = (
        make_source_fragment(
            "initial_data.yml",
            "audit, objectives, scope, and risk register",
            initial_selection,
        ),
        make_source_fragment(
            "01_planning/planning_decision.yml",
            "scope, included/excluded risks, controls, and recommended tests",
            planning_selection,
        ),
        make_source_fragment(
            "03_audit_program/audit_program.yml",
            "audit program metadata and rows excluding test_script",
            safe_audit_program,
        ),
    )
    return AuditProgramReviewContext(
        fragments=fragments,
        risks=tuple(review_risks),
        controls=tuple(item for item in controls if isinstance(item, dict)),
        recommended_tests=tuple(
            item for item in recommended_tests if isinstance(item, dict)
        ),
        program_rows=tuple(safe_program_rows),
    )
