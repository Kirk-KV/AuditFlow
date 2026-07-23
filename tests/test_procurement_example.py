from __future__ import annotations

import importlib.util
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from auditflow.commands.validate import ValidationResult, validate_workpaper_evidence_links


REPO_ROOT = Path(__file__).resolve().parents[1]
EXAMPLE_ROOT = REPO_ROOT / "examples" / "procurement_audit"
ANALYSIS_SCRIPT = (
    EXAMPLE_ROOT
    / "04_evidence"
    / "02_raw_data"
    / "scripts"
    / "procurement_analysis.py"
)


def load_analysis_module():
    spec = importlib.util.spec_from_file_location("procurement_analysis", ANALYSIS_SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_procurement_analysis_reproduces_expected_results(tmp_path: Path) -> None:
    project_root = tmp_path / "procurement_audit"
    shutil.copytree(EXAMPLE_ROOT, project_root)
    module = load_analysis_module()

    outputs = module.run_test_analysis(project_root)

    assert len(outputs["t001_candidates"]) == 38
    assert (outputs["t001_review"]["review_status"] == "unresolved").sum() == 31
    assert len(outputs["t002_exceptions"]) == 0
    assert len(outputs["t003_invoice_groups"]) == 8
    assert len(outputs["t003_payment_groups"]) == 12
    assert (outputs["t003_review"]["review_status"] == "unresolved").sum() == 3
    assert len(outputs["t004_candidates"]) == 12
    assert (outputs["t004_review"]["review_status"] == "unresolved").sum() == 6

    generated_dir = project_root / "04_evidence" / "99_generated"
    for output_name in module.OUTPUT_FILES.values():
        assert (generated_dir / output_name).is_file()


def test_procurement_workpapers_reference_existing_files() -> None:
    program_path = EXAMPLE_ROOT / "03_audit_program" / "audit_program.yml"
    program = yaml.safe_load(program_path.read_text(encoding="utf-8"))

    for row in program["program_rows"]:
        workpaper_path = EXAMPLE_ROOT / "05_workpapers" / f"{row['workpaper_ref']}.qmd"
        front_matter = workpaper_path.read_text(encoding="utf-8").split("---", 2)[1]
        metadata = yaml.safe_load(front_matter)["auditflow"]
        assert metadata["workpaper_ref"] == row["workpaper_ref"]
        assert set(metadata) == {"workpaper_ref"}

        validation = ValidationResult()
        references = validate_workpaper_evidence_links(
            EXAMPLE_ROOT,
            workpaper_path,
            validation,
        )
        assert references
        assert validation.errors == []


def test_procurement_example_has_no_legacy_workpaper_or_output_references() -> None:
    legacy_values = {
        "WP-G-004",
        "approval_authority_check.csv",
        "99_generated/release_before_approval_candidates.csv",
        "duplicate_payment_candidates.csv",
        "99_generated/split_purchase_candidates.csv",
    }
    source_files = [
        *EXAMPLE_ROOT.rglob("*.qmd"),
        *EXAMPLE_ROOT.rglob("*.yml"),
    ]
    combined_text = "\n".join(path.read_text(encoding="utf-8") for path in source_files)

    for legacy_value in legacy_values:
        assert legacy_value not in combined_text


@pytest.mark.integration
def test_procurement_qmd_renders_when_quarto_is_available(tmp_path: Path) -> None:
    quarto = shutil.which("quarto")
    if quarto is None:
        pytest.skip("Quarto is not available on PATH")

    project_root = tmp_path / "procurement_audit"
    shutil.copytree(EXAMPLE_ROOT, project_root)
    documents = [
        "01_planning/planning_document.qmd",
        "05_workpapers/WP-C-001.qmd",
        "05_workpapers/WP-C-002.qmd",
        "05_workpapers/WP-C-003.qmd",
        "05_workpapers/WP-R-003-NO-CONTROL.qmd",
        "07_reporting/report.qmd",
        "09_archive/audit_story.qmd",
    ]

    for document in documents:
        subprocess.run(
            [quarto, "render", document],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
