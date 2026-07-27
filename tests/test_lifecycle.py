from __future__ import annotations

from pathlib import Path

import yaml
from typer.testing import CliRunner

from auditflow.cli import app
from auditflow.commands.validate import validate_project


def write_yaml(path: Path, data: dict) -> None:
    path.write_text(
        yaml.safe_dump(data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def invoke(runner: CliRunner, *args: str) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == 0, f"{result.output}\n{result.exception!r}"
    return result.output


def test_cli_lifecycle_preserves_manual_work_and_validates_strictly(
    tmp_path: Path,
) -> None:
    runner = CliRunner()
    project = tmp_path / "sample_audit"
    project_arg = str(project)

    invoke(runner, "init", project_arg)

    write_yaml(
        project / "initial_data.yml",
        {
            "audit": {
                "id": "2026-001",
                "title": "Sample Process Audit",
                "company": "Example Company",
                "type": "assurance",
                "source": "annual_audit_plan",
            },
            "objectives": [
                {
                    "id": "OBJ-001",
                    "statement": "Assess whether transactions are approved before release.",
                }
            ],
            "period": {
                "from": "2026-01-01",
                "to": "2026-03-31",
            },
            "scope": {
                "in_scope": ["Transaction approval"],
                "out_of_scope": [],
                "rationale": ["Approval is the key preventive control."],
            },
            "risks": [
                {
                    "id": "R-001",
                    "title": "Transactions released before approval",
                    "rationale": "Premature release may result in unauthorized commitments.",
                }
            ],
        },
    )
    write_yaml(
        project / "00_admin" / "stakeholders.yml",
        {
            "sponsor": {
                "name": "Sam Sponsor",
                "role": "Process Sponsor",
                "email": "sponsor@example.test",
            },
            "auditees": [
                {
                    "name": "Alex Owner",
                    "role": "Process Owner",
                    "email": "owner@example.test",
                }
            ],
            "additional_stakeholders": [],
            "report_recipients": [],
        },
    )

    invoke(runner, "create", "planning", "--project", project_arg)
    write_yaml(
        project / "01_planning" / "planning_decision.yml",
        {
            "overall_conclusion": "Proceed with focused control testing.",
            "scope": {
                "in_scope": ["Transaction approval"],
                "out_of_scope": [],
                "rationale": ["The control addresses the primary engagement risk."],
            },
            "included_risks": [
                {
                    "id": "R-001",
                    "title": "Transactions released before approval",
                    "rationale": "The control is significant and testable.",
                }
            ],
            "excluded_risks": [],
            "controls": [
                {
                    "id": "C-001",
                    "risk_id": "R-001",
                    "description": "Transactions require approval before release.",
                    "owner": "Process Owner",
                    "design_assessment": "Adequately designed",
                    "planning_approach": "Test operating effectiveness.",
                }
            ],
            "recommended_tests": [
                {
                    "id": "T-001",
                    "risk_id": "R-001",
                    "control_id": "C-001",
                    "test_objective": "Identify releases recorded before approval.",
                }
            ],
        },
    )

    invoke(runner, "create", "audit-program", "--project", project_arg)
    program_path = project / "03_audit_program" / "audit_program.yml"
    program = yaml.safe_load(program_path.read_text(encoding="utf-8"))
    program["program_rows"][0]["test_hypothesis"] = (
        "Some transactions may have been released before approval."
    )
    program["program_rows"][0]["test_script"] = [
        "Load the transaction and approval records.",
        "Compare release timestamps with approval timestamps.",
    ]
    write_yaml(program_path, program)

    invoke(runner, "create", "audit-program", "--project", project_arg)
    regenerated_program = yaml.safe_load(program_path.read_text(encoding="utf-8"))
    regenerated_row = regenerated_program["program_rows"][0]
    assert regenerated_row["test_hypothesis"] == (
        "Some transactions may have been released before approval."
    )
    assert regenerated_row["test_script"] == [
        "Load the transaction and approval records.",
        "Compare release timestamps with approval timestamps.",
    ]
    regenerated_program["program"]["status"] = "approved"
    write_yaml(program_path, regenerated_program)

    invoke(runner, "create", "workpapers", "--project", project_arg)
    workpaper_path = project / "05_workpapers" / "WP-C-001.qmd"

    template_validation = validate_project(project)
    assert template_validation.errors == []
    assert any(
        "no local Markdown links" in warning
        for warning in template_validation.warnings
    )

    evidence_path = project / "04_evidence" / "02_raw_data" / "transactions.csv"
    evidence_path.write_text(
        "transaction_id,release_date,approval_date\n"
        "TX-001,2026-02-01,2026-02-02\n",
        encoding="utf-8",
    )

    workpaper = workpaper_path.read_text(encoding="utf-8")
    workpaper = workpaper.replace(
        "## Results",
        (
            "[Transaction records]"
            "(../04_evidence/02_raw_data/transactions.csv)\n\n"
            "## Results"
        ),
        1,
    )
    workpaper = workpaper.replace(
        '  title: ""',
        '  title: "Transactions released before approval"',
        1,
    )
    workpaper_path.write_text(workpaper, encoding="utf-8")

    invoke(runner, "create", "observations", "--project", project_arg)
    observation_path = project / "06_observations" / "OBS-001.yml"
    observation = yaml.safe_load(observation_path.read_text(encoding="utf-8"))
    observation.update(
        {
            "status": "validated",
            "severity": "Medium",
            "condition": "One transaction was released before recorded approval.",
            "criteria": "Transactions should be approved before release.",
            "cause": "The workflow did not block release before approval.",
            "risk_effect": "Unauthorized commitments may be created.",
            "recommendation": "Configure a preventive workflow block.",
            "executive_summary": "The approval control did not operate consistently.",
            "management_action_plan": [
                {
                    "action_id": "MAP-001",
                    "action": "Implement and test a workflow block.",
                    "responsible_name": "Alex Owner",
                    "due_date": "2026-06-30",
                }
            ],
        }
    )
    write_yaml(observation_path, observation)

    invoke(runner, "create", "report", "--project", project_arg)
    report_path = project / "07_reporting" / "report.qmd"
    report_path.write_text(
        report_path.read_text(encoding="utf-8")
        + "\n<!-- lifecycle-report-manual-note -->\n",
        encoding="utf-8",
    )
    invoke(runner, "create", "report", "--project", project_arg)
    assert "lifecycle-report-manual-note" in report_path.read_text(encoding="utf-8")
    assert "Transactions released before approval" in report_path.read_text(
        encoding="utf-8"
    )

    invoke(runner, "feedback", "request", "--project", project_arg)
    invoke(runner, "feedback", "summary", "--project", project_arg)

    invoke(runner, "create", "archive", "--project", project_arg)
    archive_path = project / "09_archive" / "audit_story.qmd"
    archive_path.write_text(
        archive_path.read_text(encoding="utf-8")
        + "\n<!-- lifecycle-archive-manual-note -->\n",
        encoding="utf-8",
    )
    invoke(runner, "create", "archive", "--project", project_arg)
    assert "lifecycle-archive-manual-note" in archive_path.read_text(encoding="utf-8")
    assert "OBS-001" in archive_path.read_text(encoding="utf-8")

    invoke(runner, "timeline", "refresh", "--project", project_arg)
    invoke(runner, "evidence", "refresh", "--project", project_arg)
    invoke(runner, "evidence", "status", "--project", project_arg)

    validation_output = invoke(
        runner,
        "validate",
        "--strict",
        "--project",
        project_arg,
    )
    assert "No validation issues found." in validation_output
