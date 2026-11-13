from __future__ import annotations

from html import escape
from pathlib import Path

import pytest
import yaml

from auditflow.blocks import observations_digest, read_front_matter, stamped_observations_digest
from auditflow.commands.archive import update_archive, build_evidence_map
from auditflow.commands.audit_program import create_audit_program
from auditflow.commands.init_project import create_initial_project
from auditflow.commands.observations import generate_observations
from auditflow.commands.planning import create_planning_files
from auditflow.commands.report import update_report_qmd
from auditflow.commands.validate import validate_project
from auditflow.commands.workpapers import generate_workpapers
from auditflow.errors import AuditFlowFileError
from auditflow.yaml_io import read_yaml_mapping, write_yaml


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


@pytest.mark.parametrize("language", ["en", "ru"])
def test_planning_and_program_tables_refresh_without_replacing_manual_text(
    tmp_path: Path, language: str,
) -> None:
    create_initial_project(tmp_path, language=language)
    create_planning_files(tmp_path)
    decision_path = tmp_path / "01_planning" / "planning_decision.yml"
    assert "planning_approach" in read_yaml_mapping(decision_path)["controls"][0]
    plan = decision_path.with_name("planning_document.qmd")
    plan.write_bytes(plan.read_bytes() + b"\nManual planning note\r\n")
    assert create_audit_program(tmp_path)["rows"] == 0
    write_yaml(decision_path, {
        "included_risks": [{"id": "R-001", "title": "Approval risk"}],
        "excluded_risks": [{"id": "R-002", "title": "Outside scope"}],
        "controls": [{
            "control_id": "C-001", "risk_id": "R-001",
            "description": "Approval <tag>", "planning_approach": "Review a sample",
        }],
        "recommended_tests": [{"id": "T-001", "test_objective": "Check dates"}],
    })
    assert create_planning_files(tmp_path)["updated"]
    for expected in ("Approval risk", "Outside scope", "Review a sample", "Check dates", "&lt;tag&gt;"):
        assert expected in plan.read_text(encoding="utf-8")
    assert plan.read_bytes().endswith(b"Manual planning note\r\n")
    assert not create_planning_files(tmp_path)["updated"]
    program = create_audit_program(tmp_path)
    program_path, document_path = Path(program["path"]), Path(program["document_path"])
    data = read_yaml_mapping(program_path)
    data["program_rows"][0]["test_script"] = ["Check sample", "Record result"]
    write_yaml(program_path, data)
    document_path.write_bytes(document_path.read_bytes() + b"\nManual program note\n")
    create_audit_program(tmp_path)
    rendered = document_path.read_text(encoding="utf-8")
    assert "Review a sample" in rendered
    assert "Check sample<br>Record result" in rendered
    assert "Approval &lt;tag&gt;" in rendered
    assert "Manual program note" in rendered


def test_refreshing_workpaper_title_preserves_other_metadata_and_body(tmp_path: Path) -> None:
    project = make_reported_project(tmp_path)
    workpaper = project / "05_workpapers" / "WP-C-001.qmd"
    suffix = b"# keep comment\r\nauditflow:\r\n  workpaper_ref: WP-C-001\r\n---\r\n\r\nManual body\r\n"
    workpaper.write_bytes(b"---\r\ntitle: >-\r\n  Old title\r\n" + suffix)
    program = project / "03_audit_program" / "audit_program.yml"
    data = read_yaml_mapping(program)
    description = 'Review "approval": C:\\Audit'
    data["program_rows"][0]["control_description"] = description
    write_yaml(program, data)
    assert generate_workpapers(project)["updated"] == 1
    actual = workpaper.read_bytes()
    assert actual.endswith(suffix)
    assert read_front_matter(workpaper.read_text(encoding="utf-8"))["title"] == f"WP-C-001 — {description}"
    assert generate_workpapers(project)["skipped"] == 1
    assert workpaper.read_bytes() == actual


def test_planning_tables_show_procurement_example_field_aliases(tmp_path: Path) -> None:
    create_initial_project(tmp_path)
    create_planning_files(tmp_path)
    example = (
        Path(__file__).resolve().parents[1] / "examples" / "procurement_audit"
        / "01_planning" / "planning_decision.yml"
    )
    decision = read_yaml_mapping(example)
    planning = tmp_path / "01_planning"
    write_yaml(planning / "planning_decision.yml", decision)
    create_planning_files(tmp_path)
    rendered = (planning / "planning_document.qmd").read_text(encoding="utf-8")

    for section, field in (
        ("included_risks", "reasoning"), ("excluded_risks", "reasoning"),
        ("controls", "control"), ("recommended_tests", "title"),
    ):
        for row in decision[section]:
            assert f"<td>{escape(row[field].strip())}</td>" in rendered


def test_observation_refresh_and_markdown_keep_manual_findings(tmp_path: Path) -> None:
    project = make_reported_project(tmp_path)
    workpaper = project / "05_workpapers" / "WP-C-001.qmd"
    workpaper.write_text(workpaper.read_text(encoding="utf-8").replace(
        "title: Approval was absent", "title: Approval was late",
    ), encoding="utf-8")
    path = project / "06_observations" / "OBS-001.yml"
    data = read_yaml_mapping(path)
    assert data["title"] == "Approval was absent"
    data["title"] = "Late approval after release"
    data["status"] = "final"
    data["risk_effect"] = "- **First risk**\n- Second risk"
    data["condition"] = "First line\nSecond line\n\n<em>Plain text</em>"
    data["management_action_plan"] = [{"action": "Review approvals"}]
    data["custom_field"] = "Reviewer note"
    write_yaml(path, data)
    program_path = project / "03_audit_program" / "audit_program.yml"
    program = read_yaml_mapping(program_path)
    program["program_rows"][0]["control_owner"] = "Accounts payable"
    write_yaml(program_path, program)
    options = {"audit_project_root": project, "overwrite": False, "clean_stale": False}
    assert generate_observations(**options)["updated"] == 1
    assert read_yaml_mapping(path) == {**data, "control_owner": "Accounts payable"}
    assert generate_observations(**options)["skipped_existing"] == 1
    report = update_report_qmd(project).path.read_text(encoding="utf-8")
    assert "Late approval after release" in report
    assert "<li><strong>First risk</strong></li>" in report
    assert "<li>Second risk</li>" in report
    assert "First line<br />\nSecond line" in report
    assert "&lt;em&gt;Plain text&lt;/em&gt;" in report
    assert "<p><p>" not in report


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
