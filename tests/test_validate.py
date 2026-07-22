from __future__ import annotations

from pathlib import Path

import yaml

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

    write_yaml(project / "initial_data.yml", {"audit": {"id": "A-001"}})
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
        "  analysis_refs:\n"
        "    - 04_evidence/02_raw_data/test.py\n"
        "  output_refs:\n"
        "    - 04_evidence/99_generated/result.csv\n"
        "  evidence_refs:\n"
        "    - 04_evidence/02_raw_data/source.csv\n"
        "---\n\n# Workpaper\n",
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


def test_validate_project_checks_declared_references_and_exact_links(tmp_path: Path) -> None:
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

    assert any("referenced file does not exist" in message for message in result.errors)
    assert any("test_id T-999" in message for message in result.errors)


def test_validate_project_checks_workpaper_front_matter_reference(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "05_workpapers" / "WP-C-001.qmd").write_text(
        "---\nauditflow:\n  workpaper_ref: WP-C-999\n---\n",
        encoding="utf-8",
    )

    result = validate_project(project)

    assert any("front matter workpaper_ref WP-C-999" in message for message in result.errors)


def test_strict_validation_does_not_require_analysis_or_output_refs(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "05_workpapers" / "WP-C-001.qmd").write_text(
        "---\n"
        "auditflow:\n"
        "  workpaper_ref: WP-C-001\n"
        "  evidence_refs:\n"
        "    - 04_evidence/02_raw_data/source.csv\n"
        "---\n",
        encoding="utf-8",
    )

    result = validate_project(project, strict=True)

    assert result.errors == []
    assert result.warnings == []


def test_strict_validation_requires_workpaper_evidence_refs(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "05_workpapers" / "WP-C-001.qmd").write_text(
        "---\nauditflow:\n  workpaper_ref: WP-C-001\n---\n",
        encoding="utf-8",
    )

    result = validate_project(project, strict=True)

    assert any("auditflow.evidence_refs is empty" in message for message in result.warnings)
