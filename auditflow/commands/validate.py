from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


REQUIRED_ADMIN_FILES = [
    "stakeholders.yml",
    "team.yml",
    "decisions.yml",
    "timeline.yml",
]

REQUIRED_EVIDENCE_FOLDERS = [
    "01_regulations",
    "02_raw_data",
    "03_correspondence",
    "04_reference_materials",
    "05_screenshots",
    "99_generated",
]


@dataclass
class ValidationResult:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def error(self, message: str) -> None:
        self.errors.append(message)

    def warning(self, message: str) -> None:
        self.warnings.append(message)

    def has_failures(self, *, strict: bool = False) -> bool:
        return bool(self.errors or (strict and self.warnings))


def load_yaml(path: Path, result: ValidationResult) -> Any:
    if not path.exists():
        result.error(f"Missing file: {path}")
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    except yaml.YAMLError as exc:
        result.error(f"Invalid YAML in {path}: {exc}")
        return {}


def load_yaml_if_exists(path: Path, result: ValidationResult) -> Any:
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            return yaml.safe_load(file) or {}
    except yaml.YAMLError as exc:
        result.error(f"Invalid YAML in {path}: {exc}")
        return {}


def schema_root() -> Path:
    return Path(__file__).resolve().parents[2] / "schemas"


def validate_with_schema(
    *,
    data_path: Path,
    schema_name: str,
    result: ValidationResult,
) -> None:
    if not data_path.exists():
        return

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        result.warning("Schema validation skipped because jsonschema is not installed.")
        return

    schema_path = schema_root() / schema_name
    if not schema_path.exists():
        result.warning(f"Schema validation skipped because schema is missing: {schema_path}")
        return

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        result.error(f"Invalid JSON schema {schema_path}: {exc}")
        return

    data = load_yaml_if_exists(data_path, result)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda item: item.path)

    for error in errors:
        path = ".".join(str(part) for part in error.path) or "<root>"
        result.error(f"{data_path}: schema error at {path}: {error.message}")


def validate_required_structure(project_root: Path, result: ValidationResult) -> None:
    for relative_path in ["initial_data.yml", "00_admin", "04_evidence"]:
        path = project_root / relative_path
        if not path.exists():
            result.error(f"Missing required path: {relative_path}")

    for file_name in REQUIRED_ADMIN_FILES:
        path = project_root / "00_admin" / file_name
        if not path.exists():
            result.error(f"Missing required admin file: 00_admin/{file_name}")

    for folder_name in REQUIRED_EVIDENCE_FOLDERS:
        path = project_root / "04_evidence" / folder_name
        if not path.exists():
            result.error(f"Missing required evidence folder: 04_evidence/{folder_name}")


def validate_audit_program(project_root: Path, result: ValidationResult) -> list[dict[str, Any]]:
    audit_program_path = project_root / "03_audit_program" / "audit_program.yml"
    if not audit_program_path.exists():
        result.warning("Audit program not created yet: 03_audit_program/audit_program.yml")
        return []

    validate_with_schema(
        data_path=audit_program_path,
        schema_name="audit_program.schema.json",
        result=result,
    )

    data = load_yaml_if_exists(audit_program_path, result)
    rows = data.get("program_rows", []) if isinstance(data, dict) else []

    if not isinstance(rows, list):
        result.error("03_audit_program/audit_program.yml: program_rows must be a list")
        return []

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            result.error(f"03_audit_program/audit_program.yml: program_rows[{index}] must be a mapping")
            continue

        workpaper_ref = str(row.get("workpaper_ref") or "")
        if workpaper_ref:
            workpaper_path = project_root / "05_workpapers" / f"{workpaper_ref}.qmd"
            if not workpaper_path.exists():
                result.warning(
                    f"Program row {row.get('test_id', index)} references missing workpaper: "
                    f"05_workpapers/{workpaper_ref}.qmd"
                )

    return [row for row in rows if isinstance(row, dict)]


def validate_observations(
    project_root: Path,
    program_rows: list[dict[str, Any]],
    result: ValidationResult,
) -> None:
    observations_dir = project_root / "06_observations"
    if not observations_dir.exists():
        return

    rows_by_workpaper = {
        str(row.get("workpaper_ref")): row
        for row in program_rows
        if row.get("workpaper_ref")
    }
    test_ids = {str(row.get("test_id")) for row in program_rows if row.get("test_id")}
    risk_ids = {str(row.get("risk_id")) for row in program_rows if row.get("risk_id")}

    for observation_path in sorted(observations_dir.glob("OBS-*.yml")):
        validate_with_schema(
            data_path=observation_path,
            schema_name="observations.schema.json",
            result=result,
        )
        observation = load_yaml_if_exists(observation_path, result)
        if not isinstance(observation, dict):
            result.error(f"{observation_path}: observation file must contain a YAML mapping")
            continue

        source_workpaper = str(observation.get("source_workpaper") or "")
        if source_workpaper and source_workpaper not in rows_by_workpaper:
            result.error(
                f"{observation_path}: source_workpaper {source_workpaper} "
                "is not present in audit_program.yml"
            )

        test_id = str(observation.get("test_id") or "")
        if test_id and test_id not in test_ids:
            result.error(f"{observation_path}: test_id {test_id} is not present in audit_program.yml")

        risk_id = str(observation.get("risk_id") or "")
        if risk_id and risk_id not in risk_ids:
            result.error(f"{observation_path}: risk_id {risk_id} is not present in audit_program.yml")


def validate_project(project_root: Path) -> ValidationResult:
    result = ValidationResult()
    validate_required_structure(project_root, result)
    load_yaml(project_root / "initial_data.yml", result)
    for file_name in REQUIRED_ADMIN_FILES:
        load_yaml(project_root / "00_admin" / file_name, result)

    program_rows = validate_audit_program(project_root, result)
    validate_observations(project_root, program_rows, result)

    return result
