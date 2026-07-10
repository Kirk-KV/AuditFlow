from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import yaml


TIMELINE_PATH = Path("00_admin") / "timeline.yml"

EVENT_FACTS: dict[str, list[str]] = {
    "project_initialized": ["start"],
    "audit_program_created": ["planning_completed", "audit_program_initiated", "audit_program"],
    "workpapers_created": ["fieldwork_started"],
    "report_created": ["fieldwork_completed", "draft_report_created", "fieldwork_end", "draft_report"],
    "feedback_requested": ["feedback_requested"],
    "archive_created": ["archive_created"],
}


def today_iso() -> str:
    return date.today().isoformat()


def load_timeline(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file) or {}

    return data if isinstance(data, dict) else {}


def write_timeline(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def ensure_timeline_shape(data: dict[str, Any]) -> dict[str, Any]:
    timeline = data.get("timeline")
    if not isinstance(timeline, dict):
        timeline = {}
        data["timeline"] = timeline

    plan = timeline.get("plan")
    if not isinstance(plan, dict):
        timeline["plan"] = {}

    fact = timeline.get("fact")
    if not isinstance(fact, dict):
        timeline["fact"] = {}

    events = data.get("events")
    if not isinstance(events, list):
        data["events"] = []

    return data


def event_exists(events: list[Any], candidate: dict[str, str]) -> bool:
    for event in events:
        if not isinstance(event, dict):
            continue

        if all(event.get(key) == value for key, value in candidate.items()):
            return True

    return False


def refresh_timeline(
    project_root: Path,
    *,
    overwrite_facts: bool = False,
) -> dict[str, Any]:
    timeline_path = project_root / TIMELINE_PATH
    data = ensure_timeline_shape(load_timeline(timeline_path))
    fact = data["timeline"]["fact"]

    for event in data["events"]:
        if not isinstance(event, dict):
            continue

        event_name = str(event.get("event") or "")
        event_date = str(event.get("date") or "")
        if not event_name or not event_date:
            continue

        for fact_key in EVENT_FACTS.get(event_name, []):
            if overwrite_facts or not fact.get(fact_key):
                fact[fact_key] = event_date

    write_timeline(timeline_path, data)
    return data


def record_event(
    project_root: Path,
    *,
    event: str,
    command: str,
    artifact: str | None = None,
    occurred_on: str | None = None,
) -> dict[str, Any]:
    timeline_path = project_root / TIMELINE_PATH
    data = ensure_timeline_shape(load_timeline(timeline_path))

    entry = {
        "event": event,
        "date": occurred_on or today_iso(),
        "command": command,
    }

    if artifact:
        entry["artifact"] = artifact

    events = data["events"]
    if not event_exists(events, entry):
        events.append(entry)

    write_timeline(timeline_path, data)
    return refresh_timeline(project_root)
