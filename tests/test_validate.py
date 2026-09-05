from __future__ import annotations

from pathlib import Path

import yaml
import pytest

from auditflow.commands.validate import validate_project


def write_yaml(path: Path, content: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(content, sort_keys=False), encoding="utf-8")


def make_project(tmp_path: Path) -> Path:
    project = tmp_path / "audit"
    for folder in (
        "01_regulations",
        "02_raw_data",
        "03_correspondence",
        "04_reference_materials",
        "05_screenshots",
        "99_generated",
    ):
        (project / "04_evidence" / folder).mkdir(parents=True, exist_ok=True)
    (project / "05_workpapers").mkdir(parents=True)
    (project / "06_observations").mkdir(parents=True)

    write_yaml(
        project / "initial_data.yml",
        {
            "audit": {"id": "A-001", "title": "Test audit", "type": "assurance"},
            "objectives": [{"id": "OBJ-001", "statement": "Assess purchase approval."}],
            "scope": {"in_scope": ["Purchasing"]},
            "risks": [
                {
                    "id": "R-001",
                    "title": "Unauthorized purchase",
                    "rationale": "Approval may be bypassed.",
                }
            ],
        },
    )
    write_yaml(
        project / "01_planning" / "planning_decision.yml",
        {
            "included_risks": [
                {
                    "id": "R-001",
                    "title": "Unauthorized purchase",
                    "rationale": "Approval may be bypassed.",
                }
            ],
            "controls": [{"control_id": "C-001", "risk_id": "R-001", "description": "Approval"}],
        },
    )
    for file_name in ("stakeholders.yml", "team.yml", "decisions.yml", "timeline.yml"):
        write_yaml(project / "00_admin" / file_name, {})

    script = project / "04_evidence" / "02_raw_data" / "test.py"
    output = project / "04_evidence" / "99_generated" / "result.csv"
    evidence = project / "04_evidence" / "02_raw_data" / "source.csv"
    script.write_text("print('test')\n", encoding="utf-8")
    output.write_text("id\n1\n", encoding="utf-8")
    evidence.write_text("id\n1\n", encoding="utf-8")
    (project / "05_workpapers" / "WP-C-001.qmd").write_text(
        "---\n"
        "auditflow:\n"
        "  workpaper_ref: WP-C-001\n"
        "---\n\n"
        "# Workpaper\n\n"
        "- [Analysis](../04_evidence/02_raw_data/test.py)\n"
        "- [Output](../04_evidence/99_generated/result.csv)\n"
        "- [Evidence](../04_evidence/02_raw_data/source.csv)\n",
        encoding="utf-8",
    )

    write_yaml(
        project / "03_audit_program" / "audit_program.yml",
        {
            "program": {
                "status": "final",
                "source": {"planning_decision": "01_planning/planning_decision.yml"},
            },
            "program_rows": [
                {
                    "test_id": "T-001",
                    "risk_id": "R-001",
                    "risk_title": "Unauthorized purchase",
                    "test_hypothesis": "An unauthorized purchase may occur.",
                    "test_script": ["Inspect the population."],
                    "workpaper_ref": "WP-C-001",
                }
            ],
        },
    )
    write_yaml(
        project / "06_observations" / "OBS-001.yml",
        {
            "observation_id": "OBS-001",
            "status": "final",
            "source_workpaper": "WP-C-001",
            "source_file": "05_workpapers/WP-C-001.qmd",
            "test_id": "T-001",
            "risk_id": "R-001",
            "risk_title": "Unauthorized purchase",
            "title": "Approval was absent",
            "condition": "One purchase lacked approval.",
            "criteria": "Purchases require approval.",
            "cause": "The workflow allowed release.",
            "risk_effect": "Unauthorized purchases may occur.",
            "recommendation": "Block release before approval.",
            "management_action_plan": [],
        },
    )
    return project


def test_validate_project_checks_markdown_evidence_links_and_exact_links(tmp_path: Path) -> None:
    project = make_project(tmp_path)

    result = validate_project(project, strict=True)

    assert result.errors == []
    assert result.warnings == []


def test_validate_project_reports_missing_output_and_mismatched_test(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "04_evidence" / "99_generated" / "result.csv").unlink()
    observation_path = project / "06_observations" / "OBS-001.yml"
    observation = yaml.safe_load(observation_path.read_text(encoding="utf-8"))
    observation["test_id"] = "T-999"
    write_yaml(observation_path, observation)

    result = validate_project(project)

    assert any("linked evidence file does not exist" in message for message in result.errors)
    assert any("test_id T-999" in message for message in result.errors)


def test_validate_project_checks_workpaper_front_matter_reference(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "05_workpapers" / "WP-C-001.qmd").write_text(
        "---\nauditflow:\n  workpaper_ref: WP-C-999\n---\n",
        encoding="utf-8",
    )

    result = validate_project(project)

    assert any("front matter workpaper_ref WP-C-999" in message for message in result.errors)


def test_strict_validation_accepts_one_markdown_evidence_link(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "05_workpapers" / "WP-C-001.qmd").write_text(
        "---\n"
        "auditflow:\n"
        "  workpaper_ref: WP-C-001\n"
        "---\n\n"
        "[Evidence](../04_evidence/02_raw_data/source.csv)\n",
        encoding="utf-8",
    )

    result = validate_project(project, strict=True)

    assert result.errors == []
    assert result.warnings == []


def test_strict_validation_requires_workpaper_evidence_link(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "05_workpapers" / "WP-C-001.qmd").write_text(
        "---\nauditflow:\n  workpaper_ref: WP-C-001\n---\n",
        encoding="utf-8",
    )

    result = validate_project(project, strict=True)

    assert any("no local Markdown links" in message for message in result.warnings)


@pytest.mark.parametrize("strict", [False, True])
def test_empty_scope_rejects_existing_program(tmp_path: Path, strict: bool) -> None:
    project = make_project(tmp_path)
    write_yaml(project / "01_planning" / "planning_decision.yml", {
        "included_risks": [],
        "excluded_risks": [{"id": "R-001"}],
        "controls": [{"control_id": "C-001", "risk_id": "R-001"}],
    })
    result = validate_project(project, strict=strict)
    assert any("risk R-001 is not in" in error for error in result.errors)
    assert any("which is not in included_risks" in warning for warning in result.warnings)


@pytest.mark.parametrize("value", [None, "R-001", {"id": "R-001"}, ["R-001"]])
def test_invalid_planning_risk_list_is_reported(tmp_path: Path, value: object) -> None:
    project = make_project(tmp_path)
    write_yaml(project / "01_planning" / "planning_decision.yml", {"included_risks": value})
    assert any("included_risks must be a list" in error for error in validate_project(project).errors)


def test_company_ids_are_valid_through_observations(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    for relative in (
        "initial_data.yml", "01_planning/planning_decision.yml",
        "03_audit_program/audit_program.yml", "06_observations/OBS-001.yml",
    ):
        path = project / relative
        path.write_text(path.read_text(encoding="utf-8").replace("R-001", "Р РёСЃРє.1"), encoding="utf-8")
    path = project / "06_observations" / "OBS-001.yml"
    observation = yaml.safe_load(path.read_text(encoding="utf-8"))
    observation["control_id"] = "РљРѕРЅС‚СЂРѕР»СЊ/1"
    write_yaml(path, observation)
    result = validate_project(project, strict=True)
    assert result.errors == []
    assert result.warnings == []


def test_links_in_code_and_external_links_are_not_evidence(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "05_workpapers" / "WP-C-001.qmd").write_text(
        "---\nauditflow:\n  workpaper_ref: WP-C-001\n---\n\n"
        "`[Code example](../04_evidence/02_raw_data/missing.csv)`\n\n"
        "[External reference](https://example.com/evidence.csv)\n",
        encoding="utf-8",
    )

    result = validate_project(project)

    assert not any("missing.csv" in message for message in result.errors)
    assert any("no local Markdown links" in message for message in result.warnings)
