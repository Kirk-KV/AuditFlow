from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from auditflow.blocks import observations_digest, stamped_observations_digest
from auditflow.commands.archive import update_archive, build_evidence_map
from auditflow.commands.audit_program import create_audit_program
from auditflow.commands.init_project import create_initial_project
from auditflow.commands.observations import generate_observations
from auditflow.commands.report import update_report_qmd
from auditflow.commands.validate import validate_project
from auditflow.commands.workpapers import generate_workpapers
from auditflow.errors import AuditFlowFileError


def make_reported_project(tmp_path: Path) -> Path:
    project = tmp_path / "audit"
    create_initial_project(project)
    (project / "01_planning").mkdir(parents=True, exist_ok=True)
    (project / "01_planning" / "planning_decision.yml").write_text(
        yaml.safe_dump(
            {
                "included_risks": [
                    {"id": "R-001", "title": "Risk one", "rationale": "Because."}
                ],
                "controls": [
                    {"control_id": "C-001", "risk_id": "R-001", "description": "Approval"}
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    create_audit_program(project)
    generate_workpapers(project)

    workpaper = project / "05_workpapers" / "WP-C-001.qmd"
    workpaper.write_text(
        workpaper.read_text(encoding="utf-8").replace(
            'proposed_observation:\n  title: ""',
            "proposed_observation:\n  title: Approval was absent",
        ),
        encoding="utf-8",
    )
    result = generate_observations(
        audit_project_root=project,
        overwrite=True,
        clean_stale=False,
    )
    assert result["created"] == 1
    return project


def test_report_records_which_observations_it_was_built_from(tmp_path: Path) -> None:
    project = make_reported_project(tmp_path)

    result = update_report_qmd(project)
    content = result.path.read_text(encoding="utf-8")

    assert result.missing_blocks == ()
    assert stamped_observations_digest(content) == observations_digest(project)


def test_observation_stamp_survives_checkout_line_endings(tmp_path: Path) -> None:
    project = make_reported_project(tmp_path)
    update_report_qmd(project)
    before = observations_digest(project)
    for path in (project / "06_observations").glob("OBS-*.yml"):
        content = path.read_bytes().replace(b"\r\n", b"\n")
        path.write_bytes(content.replace(b"\n", b"\r\n"))
    assert observations_digest(project) == before
    assert not any("observations changed" in warning for warning in validate_project(project).warnings)


def test_archive_map_keeps_sources_but_excludes_local_artifacts(tmp_path: Path) -> None:
    create_initial_project(tmp_path)
    for relative in (
        "02_raw_data/scripts/analysis.py", "02_raw_data/scripts/query.sql",
        "02_raw_data/scripts/__pycache__/analysis.pyc", "02_raw_data/stray.pyc",
        "02_raw_data/Thumbs.db", "99_generated/result.csv",
    ):
        path = tmp_path / "04_evidence" / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("test", encoding="utf-8")
    content = build_evidence_map(tmp_path)
    assert "04_evidence/02_raw_data/scripts/analysis.py |" in content
    assert "04_evidence/02_raw_data/scripts/query.sql" in content
    assert "04_evidence/99_generated/result.csv" in content
    assert all(unwanted not in content for unwanted in ("__pycache__", ".pyc", ".gitkeep", "Thumbs.db"))


def test_validation_reports_a_report_that_predates_the_observations(tmp_path: Path) -> None:
    """A report built before the observations changed must not pass silently.

    Rebuilding reports from structured artifacts is the point of the framework,
    so an out-of-date report is a traceability defect, not a formatting detail.
    """

    project = make_reported_project(tmp_path)
    update_report_qmd(project)
    update_archive(project)

    # The starter project is deliberately incomplete, so only the staleness
    # warnings are asserted here.
    assert not any(
        "observations changed" in item for item in validate_project(project).warnings
    )

    observation = next((project / "06_observations").glob("OBS-*.yml"))
    data = yaml.safe_load(observation.read_text(encoding="utf-8"))
    data["severity"] = "High"
    observation.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    warnings = validate_project(project).warnings

    assert any("07_reporting/report.qmd: observations changed" in item for item in warnings)
    assert any("09_archive/audit_story.qmd: observations changed" in item for item in warnings)


def test_deleted_auto_marker_is_reported_instead_of_silently_skipped(
    tmp_path: Path,
) -> None:
    project = make_reported_project(tmp_path)
    report_path = update_report_qmd(project).path

    content = report_path.read_text(encoding="utf-8")
    content = content.replace("<!-- AUTO:DETAILED_OBSERVATIONS START -->", "")
    content = content.replace("<!-- AUTO:DETAILED_OBSERVATIONS END -->", "")
    report_path.write_text(content, encoding="utf-8")

    result = update_report_qmd(project)

    assert result.missing_blocks == ("DETAILED_OBSERVATIONS",)
    assert any(
        "AUTO:DETAILED_OBSERVATIONS has no marker" in error
        for error in validate_project(project).errors
    )


def test_archive_reports_missing_markers(tmp_path: Path) -> None:
    project = make_reported_project(tmp_path)
    archive_path = update_archive(project).path

    content = archive_path.read_text(encoding="utf-8")
    content = content.replace("<!-- AUTO:EVIDENCE_MAP START -->", "")
    content = content.replace("<!-- AUTO:EVIDENCE_MAP END -->", "")
    archive_path.write_text(content, encoding="utf-8")

    assert update_archive(project).missing_blocks == ("EVIDENCE_MAP",)


def test_prerequisites_are_reported_as_plain_errors(tmp_path: Path) -> None:
    """Running a command out of order is an auditor mistake, not a crash."""

    project = tmp_path / "audit"
    create_initial_project(project)

    with pytest.raises(AuditFlowFileError, match="auditflow create planning"):
        create_audit_program(project)

    with pytest.raises(AuditFlowFileError, match="auditflow create audit-program"):
        generate_workpapers(project)

    with pytest.raises(AuditFlowFileError, match="auditflow create audit-program"):
        generate_observations(
            audit_project_root=project,
            overwrite=False,
            clean_stale=False,
        )
