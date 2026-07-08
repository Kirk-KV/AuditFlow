from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import yaml


OBSERVATION_SECTION_PATTERN = re.compile(
    r"^##[ \t]+(?:Observation proposal|Potential observation)[ \t]*$",
    re.IGNORECASE | re.MULTILINE,
)

FENCED_YAML_PATTERN = re.compile(
    r"```(?:yaml|yml)\s*\n(.*?)\n```",
    re.IGNORECASE | re.DOTALL,
)

OBS_ID_PATTERN = re.compile(r"^OBS-(\d{3,})$", re.IGNORECASE)


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")

    return data


def load_yaml_text(text: str, source: Path) -> dict[str, Any]:
    data = yaml.safe_load(text) or {}

    if not isinstance(data, dict):
        raise ValueError(f"Observation block must be a YAML mapping: {source}")

    return data


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as file:
        yaml.safe_dump(
            data,
            file,
            sort_keys=False,
            allow_unicode=True,
            width=120,
        )


def safe_obs_id(value: Any) -> str | None:
    if value is None:
        return None

    text = str(value).strip().upper()

    if not text:
        return None

    match = OBS_ID_PATTERN.match(text)
    if not match:
        return None

    return f"OBS-{int(match.group(1)):03d}"


def workpaper_ref_from_path(path: Path) -> str:
    return path.stem


def extract_observation_block(workpaper_path: Path) -> dict[str, Any] | None:
    text = workpaper_path.read_text(encoding="utf-8")
    section_match = OBSERVATION_SECTION_PATTERN.search(text)

    if not section_match:
        return None

    section_start = section_match.end()
    next_heading_match = re.search(
        r"^##[ \t]+",
        text[section_start:],
        re.MULTILINE,
    )

    if next_heading_match:
        section_text = text[
            section_start : section_start + next_heading_match.start()
        ]
    else:
        section_text = text[section_start:]

    yaml_match = FENCED_YAML_PATTERN.search(section_text)

    if not yaml_match:
        return None

    return load_yaml_text(yaml_match.group(1), workpaper_path)


def proposed_title(block: dict[str, Any]) -> str:
    """Return proposed observation title, supporting both current and older block styles."""

    proposal = block.get("proposed_observation")

    if isinstance(proposal, dict):
        return str(proposal.get("title", "") or "").strip()

    if isinstance(proposal, str):
        value = proposal.strip().lower()
        if value in {"no", "false", "none", "not_required", "not required"}:
            return ""
        if value in {"yes", "true", "proposed"}:
            return str(block.get("title", "") or "").strip()

    status = str(block.get("status", "") or "").strip().lower()
    if status in {"not_required", "none", "no_observation"}:
        return ""

    if status == "proposed":
        return str(block.get("title", "") or "").strip()

    return ""


def index_program_rows(audit_program: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = audit_program.get("program_rows", [])

    if not isinstance(rows, list):
        raise ValueError("audit_program.yml: program_rows must be a list")

    result = {}

    for row in rows:
        if not isinstance(row, dict):
            continue

        workpaper_ref = row.get("workpaper_ref")
        if workpaper_ref:
            result[str(workpaper_ref)] = row

    return result


def existing_observation_files(observations_dir: Path) -> list[Path]:
    if not observations_dir.exists():
        return []

    return sorted(observations_dir.glob("OBS-*.yml"))


def read_existing_observations(
    observations_dir: Path,
) -> tuple[dict[str, dict[str, Any]], set[str]]:
    by_workpaper: dict[str, dict[str, Any]] = {}
    used_ids: set[str] = set()

    for path in existing_observation_files(observations_dir):
        try:
            obs = load_yaml(path)
        except Exception:
            continue

        obs_id = safe_obs_id(obs.get("observation_id")) or safe_obs_id(path.stem)
        if obs_id:
            used_ids.add(obs_id)

        source_workpaper = obs.get("source_workpaper")
        if source_workpaper:
            by_workpaper[str(source_workpaper)] = {
                "path": path,
                "data": obs,
                "observation_id": obs_id,
            }

    return by_workpaper, used_ids


def next_observation_id(used_ids: set[str]) -> str:
    used_numbers = []

    for obs_id in used_ids:
        match = OBS_ID_PATTERN.match(obs_id)
        if match:
            used_numbers.append(int(match.group(1)))

    next_number = (max(used_numbers) + 1) if used_numbers else 1

    while True:
        candidate = f"OBS-{next_number:03d}"
        if candidate not in used_ids:
            used_ids.add(candidate)
            return candidate
        next_number += 1


def default_management_action_plan() -> list[dict[str, Any]]:
    return [
        {
            "action_id": "MAP-001",
            "action": "",
            "responsible_name": "",
            "due_date": "",
        }
    ]


def build_observation(
    *,
    observation_id: str,
    workpaper_path: Path,
    workpaper_ref: str,
    program_row: dict[str, Any],
    title: str,
) -> dict[str, Any]:
    return {
        "observation_id": observation_id,
        "status": "draft",
        "source_workpaper": workpaper_ref,
        "source_file": f"05_workpapers/{workpaper_path.name}",
        "test_id": program_row.get("test_id", ""),
        "risk_id": program_row.get("risk_id", ""),
        "risk_title": program_row.get("risk_title", ""),
        "control_id": program_row.get("control_id"),
        "control_description": program_row.get("control_description", ""),
        "control_owner": program_row.get("control_owner", ""),
        "title": title,
        "severity": "",
        "condition": "",
        "criteria": "",
        "cause": "",
        "risk_effect": "",
        "recommendation": "",
        "management_action_plan": default_management_action_plan(),
    }


def generate_observations(
    *,
    audit_project_root: Path,
    overwrite: bool,
    clean_stale: bool,
) -> dict[str, Any]:
    audit_program_path = audit_project_root / "03_audit_program" / "audit_program.yml"
    workpapers_dir = audit_project_root / "05_workpapers"
    observations_dir = audit_project_root / "06_observations"

    audit_program = load_yaml(audit_program_path)
    program_rows_by_workpaper = index_program_rows(audit_program)
    observations_dir.mkdir(parents=True, exist_ok=True)

    existing_by_workpaper, used_ids = read_existing_observations(observations_dir)

    created = 0
    updated = 0
    skipped_existing = 0
    skipped_not_required = 0
    missing_block: list[str] = []
    stale_candidates: list[Path] = []
    generated_workpapers: set[str] = set()

    for workpaper_path in sorted(workpapers_dir.glob("*.qmd")):
        workpaper_ref = workpaper_ref_from_path(workpaper_path)
        block = extract_observation_block(workpaper_path)

        if block is None:
            missing_block.append(workpaper_path.name)
            continue

        title = proposed_title(block)

        if not title:
            skipped_not_required += 1
            continue

        program_row = program_rows_by_workpaper.get(workpaper_ref)
        if program_row is None:
            raise ValueError(
                f"Workpaper {workpaper_ref} has a proposed observation, but no matching "
                "workpaper_ref was found in 03_audit_program/audit_program.yml."
            )

        existing = existing_by_workpaper.get(workpaper_ref)

        if existing:
            observation_id = existing["observation_id"] or safe_obs_id(existing["path"].stem)
            if not observation_id:
                observation_id = next_observation_id(used_ids)
        else:
            observation_id = next_observation_id(used_ids)

        target_path = observations_dir / f"{observation_id}.yml"
        generated_workpapers.add(workpaper_ref)

        if target_path.exists() and not overwrite:
            skipped_existing += 1
            continue

        observation = build_observation(
            observation_id=observation_id,
            workpaper_path=workpaper_path,
            workpaper_ref=workpaper_ref,
            program_row=program_row,
            title=title,
        )

        write_yaml(target_path, observation)

        if existing:
            updated += 1
        else:
            created += 1

    for source_workpaper, existing in existing_by_workpaper.items():
        if source_workpaper not in generated_workpapers:
            stale_candidates.append(existing["path"])

    deleted_stale = 0
    if clean_stale:
        for path in stale_candidates:
            path.unlink(missing_ok=True)
            deleted_stale += 1

    return {
        "created": created,
        "updated": updated,
        "skipped_existing": skipped_existing,
        "skipped_not_required": skipped_not_required,
        "missing_block": missing_block,
        "stale_candidates": [str(path) for path in stale_candidates],
        "deleted_stale": deleted_stale,
        "observations_dir": str(observations_dir),
    }
