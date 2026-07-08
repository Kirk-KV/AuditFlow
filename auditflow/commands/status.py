
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def has_any(path: Path, pattern: str) -> bool:
    return path.exists() and any(path.glob(pattern))


def audit_title(project_root: Path) -> str:
    data = load_yaml(project_root / "initial_data.yml")
    audit = data.get("audit", {}) if isinstance(data, dict) else {}
    if isinstance(audit, dict):
        return str(audit.get("title") or audit.get("id") or project_root.name)
    return project_root.name


def stage_rows(project_root: Path) -> list[dict[str, Any]]:
    return [
        {
            "name": "Initial data",
            "done": (project_root / "initial_data.yml").exists(),
            "details": "initial_data.yml",
            "next": "auditflow init <project-folder>",
        },
        {
            "name": "Admin setup",
            "done": all(
                (project_root / "00_admin" / file_name).exists()
                for file_name in ["stakeholders.yml", "team.yml", "decisions.yml", "timeline.yml"]
            ),
            "details": "00_admin/",
            "next": "complete 00_admin/stakeholders.yml and 00_admin/team.yml",
        },
        {
            "name": "Evidence workspace",
            "done": all(
                (project_root / "04_evidence" / folder).exists()
                for folder in [
                    "01_regulations",
                    "02_raw_data",
                    "03_correspondence",
                    "04_reference_materials",
                    "05_screenshots",
                    "99_generated",
                ]
            ),
            "details": "04_evidence/",
            "next": "store pre-planning and planning evidence in 04_evidence/",
        },
        {
            "name": "Planning",
            "done": (project_root / "01_planning" / "planning_decision.yml").exists(),
            "details": "01_planning/planning_decision.yml",
            "next": "auditflow create planning",
        },
        {
            "name": "Audit program",
            "done": (project_root / "03_audit_program" / "audit_program.yml").exists(),
            "details": "03_audit_program/audit_program.yml",
            "next": "auditflow create audit-program",
        },
        {
            "name": "Workpapers",
            "done": has_any(project_root / "05_workpapers", "*.qmd"),
            "details": "05_workpapers/*.qmd",
            "next": "auditflow create workpapers",
        },
        {
            "name": "Observations",
            "done": has_any(project_root / "06_observations", "OBS-*.yml"),
            "details": "06_observations/OBS-*.yml",
            "next": "auditflow create observations",
        },
        {
            "name": "Report",
            "done": (project_root / "07_reporting" / "report.qmd").exists(),
            "details": "07_reporting/report.qmd",
            "next": "auditflow create report",
        },
        {
            "name": "Feedback requests",
            "done": has_any(project_root / "08_feedback" / "request", "*_request.txt"),
            "details": "08_feedback/request/",
            "next": "auditflow feedback request",
        },
        {
            "name": "Feedback summary",
            "done": (project_root / "08_feedback" / "feedback_summary.qmd").exists(),
            "details": "08_feedback/feedback_summary.qmd",
            "next": "auditflow feedback summary",
        },
        {
            "name": "Archive story",
            "done": (project_root / "09_archive" / "audit_story.qmd").exists(),
            "details": "09_archive/audit_story.qmd",
            "next": "auditflow create archive",
        },
    ]


def get_status(project_root: Path) -> dict[str, Any]:
    rows = stage_rows(project_root)
    next_command = ""
    for row in rows:
        if not row["done"]:
            next_command = row["next"]
            break

    return {
        "project_root": project_root,
        "audit_title": audit_title(project_root),
        "rows": rows,
        "next_command": next_command or "No next command. The main workflow appears complete.",
    }
