from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from auditflow.commands.audit_program import create_audit_program
from auditflow.commands.init_project import create_initial_project
from auditflow.commands.validate import validate_project
from auditflow.commands.workpapers import generate_workpapers
from auditflow.errors import AuditFlowDataError
from auditflow.ids import build_workpaper_ref, is_safe_workpaper_ref


def write_planning(project: Path, controls: list[dict[str, str]]) -> None:
    (project / "01_planning").mkdir(parents=True, exist_ok=True)
    (project / "01_planning" / "planning_decision.yml").write_text(
        yaml.safe_dump(
            {
                "included_risks": [
                    {"id": "R-001", "title": "Risk one", "rationale": "Because."}
                ],
                "controls": controls,
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def program_rows(project: Path) -> list[dict]:
    data = yaml.safe_load(
        (project / "03_audit_program" / "audit_program.yml").read_text(encoding="utf-8")
    )
    return data["program_rows"]


def test_non_latin_control_ids_produce_distinct_workpapers(tmp_path: Path) -> None:
    """Two controls must never collapse into one workpaper file.

    Control identifiers come from the company's own framework. When they were
    sanitized at the point the file was written rather than when the reference
    was created, 'К-001' and 'Ц-001' both became 'WP-_-001' and the second
    workpaper silently overwrote the first, losing a test procedure.
    """

    project = tmp_path / "audit"
    create_initial_project(project, language="ru")
    write_planning(
        project,
        [
            {"control_id": "К-001", "risk_id": "R-001", "description": "Контроль К"},
            {"control_id": "Ц-001", "risk_id": "R-001", "description": "Контроль Ц"},
            {"control_id": "C.1", "risk_id": "R-001", "description": "Dotted"},
        ],
    )

    create_audit_program(project)
    refs = [row["workpaper_ref"] for row in program_rows(project)]

    assert len(set(refs)) == 3
    assert all(is_safe_workpaper_ref(ref) for ref in refs)

    result = generate_workpapers(project)

    assert result["created"] == 3
    assert result["skipped"] == 0
    assert sorted(path.stem for path in (project / "05_workpapers").glob("*.qmd")) == sorted(refs)


def test_workpaper_refs_survive_program_regeneration(tmp_path: Path) -> None:
    """A reference is a file name, so adding a control must not rename existing ones."""

    project = tmp_path / "audit"
    create_initial_project(project)
    write_planning(
        project,
        [
            {"control_id": "К-001", "risk_id": "R-001", "description": "First"},
            {"control_id": "К-002", "risk_id": "R-001", "description": "Second"},
        ],
    )
    create_audit_program(project)
    before = {row["control_id"]: row["workpaper_ref"] for row in program_rows(project)}

    write_planning(
        project,
        [
            {"control_id": "НОВЫЙ", "risk_id": "R-001", "description": "Inserted first"},
            {"control_id": "К-001", "risk_id": "R-001", "description": "First"},
            {"control_id": "К-002", "risk_id": "R-001", "description": "Second"},
        ],
    )
    create_audit_program(project)
    after = {row["control_id"]: row["workpaper_ref"] for row in program_rows(project)}

    assert after["К-001"] == before["К-001"]
    assert after["К-002"] == before["К-002"]
    assert len(set(after.values())) == 3


def test_generated_workpapers_satisfy_validation(tmp_path: Path) -> None:
    project = tmp_path / "audit"
    create_initial_project(project)
    write_planning(
        project,
        [{"control_id": "К-001", "risk_id": "R-001", "description": "Контроль"}],
    )
    create_audit_program(project)
    generate_workpapers(project)

    result = validate_project(project)

    assert result.errors == []
    assert not any("missing workpaper" in warning for warning in result.warnings)


def test_duplicate_workpaper_ref_is_refused(tmp_path: Path) -> None:
    """A hand-edited program that reuses a reference must fail, not overwrite."""

    project = tmp_path / "audit"
    create_initial_project(project)
    write_planning(
        project,
        [
            {"control_id": "C-001", "risk_id": "R-001", "description": "First"},
            {"control_id": "C-002", "risk_id": "R-001", "description": "Second"},
        ],
    )
    create_audit_program(project)

    program_path = project / "03_audit_program" / "audit_program.yml"
    data = yaml.safe_load(program_path.read_text(encoding="utf-8"))
    data["program_rows"][1]["workpaper_ref"] = data["program_rows"][0]["workpaper_ref"]
    program_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(AuditFlowDataError, match="share workpaper_ref"):
        generate_workpapers(project)


def test_unsafe_workpaper_ref_is_refused(tmp_path: Path) -> None:
    project = tmp_path / "audit"
    create_initial_project(project)
    write_planning(
        project,
        [{"control_id": "C-001", "risk_id": "R-001", "description": "First"}],
    )
    create_audit_program(project)

    program_path = project / "03_audit_program" / "audit_program.yml"
    data = yaml.safe_load(program_path.read_text(encoding="utf-8"))
    data["program_rows"][0]["workpaper_ref"] = "WP-К 001"
    program_path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")

    with pytest.raises(AuditFlowDataError, match="cannot be used as a file name"):
        generate_workpapers(project)

    assert any(
        "cannot be used as a file name" in error
        for error in validate_project(project).errors
    )


def test_build_workpaper_ref_falls_back_to_test_id() -> None:
    taken: set[str] = set()

    assert build_workpaper_ref(control_id="C-001", test_id="T-001", taken=taken) == "WP-C-001"
    # A control identifier with nothing reusable falls back to the test identifier.
    assert build_workpaper_ref(control_id="///", test_id="T-002", taken=taken) == "WP-T-002"
    # A collision is resolved rather than allowed.
    assert build_workpaper_ref(control_id="C-001", test_id="T-003", taken=taken) == "WP-T-003"
    assert len(taken) == 3


def test_case_only_control_ids_create_separate_workpapers(tmp_path: Path) -> None:
    project = tmp_path / "audit"
    create_initial_project(project)
    write_planning(project, [
        {"control_id": control, "risk_id": "R-001", "description": control}
        for control in ("C-ABC", "c-abc")
    ])
    create_audit_program(project)
    refs = [row["workpaper_ref"] for row in program_rows(project)]
    assert len({ref.casefold() for ref in refs}) == 2
    assert generate_workpapers(project)["created"] == 2


@pytest.mark.parametrize("new_control", ["C-1", "c-1"])
def test_inserted_collision_cannot_steal_existing_workpaper(
    tmp_path: Path, new_control: str,
) -> None:
    project = tmp_path / "audit"
    create_initial_project(project)
    original = {"control_id": "C.1", "risk_id": "R-001", "description": "Original"}
    write_planning(project, [original])
    create_audit_program(project)
    generate_workpapers(project)
    ref = program_rows(project)[0]["workpaper_ref"]
    workpaper = project / "05_workpapers" / f"{ref}.qmd"
    before = workpaper.read_bytes()
    write_planning(project, [
        {"control_id": new_control, "risk_id": "R-001", "description": "New"}, original,
    ])
    create_audit_program(project)
    rows = {row["control_id"]: row for row in program_rows(project)}
    assert rows["C.1"]["workpaper_ref"] == ref
    assert rows[new_control]["workpaper_ref"].casefold() != ref.casefold()
    assert generate_workpapers(project)["created"] == 1
    assert workpaper.read_bytes() == before


@pytest.mark.parametrize("duplicate", ["WP-C-001", "WP-c-001"])
def test_invalid_program_does_not_overwrite_any_workpaper(tmp_path: Path, duplicate: str) -> None:
    project = tmp_path / "audit"
    create_initial_project(project)
    write_planning(project, [
        {"control_id": "C-001", "risk_id": "R-001", "description": "First"},
        {"control_id": "C-002", "risk_id": "R-001", "description": "Second"},
    ])
    create_audit_program(project)
    generate_workpapers(project)
    workpaper = project / "05_workpapers" / "WP-C-001.qmd"
    workpaper.write_text("Auditor's completed work", encoding="utf-8")
    program_path = project / "03_audit_program" / "audit_program.yml"
    data = yaml.safe_load(program_path.read_text(encoding="utf-8"))
    data["program_rows"][1]["workpaper_ref"] = duplicate
    program_path.write_text(yaml.safe_dump(data), encoding="utf-8")
    with pytest.raises(AuditFlowDataError, match="share workpaper_ref"):
        generate_workpapers(project, overwrite=True)
    assert workpaper.read_text(encoding="utf-8") == "Auditor's completed work"
    assert any("duplicate workpaper_ref" in error for error in validate_project(project).errors)
