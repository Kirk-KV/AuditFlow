from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml

from auditflow.commands.evidence import EvidenceManifestError, load_evidence_manifest


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


def load_qmd_front_matter(path: Path, result: ValidationResult) -> dict[str, Any]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        result.error(f"Could not read {path}: {exc}")
        return {}

    if not lines or lines[0].strip() != "---":
        return {}

    try:
        closing_index = next(
            index for index, line in enumerate(lines[1:], start=1) if line.strip() == "---"
        )
    except StopIteration:
        result.error(f"Invalid QMD front matter in {path}: closing delimiter is missing")
        return {}

    try:
        metadata = yaml.safe_load("\n".join(lines[1:closing_index])) or {}
    except yaml.YAMLError as exc:
        result.error(f"Invalid QMD front matter in {path}: {exc}")
        return {}

    return metadata if isinstance(metadata, dict) else {}


def schema_root() -> Path:
    return Path(__file__).resolve().parents[1] / "schemas"


def validate_with_schema(
    *,
    data_path: Path,
    schema_name: str,
    result: ValidationResult,
) -> None:
    if not data_path.exists():
        return

    try:
        from jsonschema import Draft202012Validator, FormatChecker
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
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda item: item.path)

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


def duplicate_values(values: list[str]) -> set[str]:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for value in values:
        if value in seen:
            duplicates.add(value)
        seen.add(value)
    return duplicates


def validate_reference(
    project_root: Path,
    reference: str,
    context: str,
    result: ValidationResult,
) -> None:
    reference_path = Path(reference)
    if reference_path.is_absolute():
        result.error(f"{context}: reference must be relative to the project: {reference}")
        return

    project_root = project_root.resolve()
    resolved = (project_root / reference_path).resolve()
    try:
        resolved.relative_to(project_root)
    except ValueError:
        result.error(f"{context}: reference escapes the project folder: {reference}")
        return

    if not resolved.is_file():
        result.error(f"{context}: referenced file does not exist: {reference}")


def validate_workpaper_evidence_links(
    project_root: Path,
    workpaper_path: Path,
    result: ValidationResult,
) -> list[str] | None:
    try:
        from markdown_it import MarkdownIt
    except ImportError:
        result.warning(
            f"{workpaper_path}: evidence link validation skipped because "
            "markdown-it-py is not installed"
        )
        return None

    try:
        source = workpaper_path.read_text(encoding="utf-8")
        tokens = MarkdownIt("commonmark").parse(source)
    except (OSError, RuntimeError, ValueError) as exc:
        result.error(f"Could not parse Markdown links in {workpaper_path}: {exc}")
        return None

    targets: list[str] = []
    for token in tokens:
        if token.type != "inline":
            continue
        for child in token.children or []:
            if child.type == "link_open":
                target = child.attrGet("href")
            elif child.type == "image":
                target = child.attrGet("src")
            else:
                continue
            if target:
                targets.append(target)

    evidence_root = (project_root / "04_evidence").resolve()
    evidence_targets: list[str] = []
    seen_paths: set[Path] = set()

    for target in targets:
        parsed = urlsplit(target)
        if parsed.scheme or parsed.netloc or not parsed.path:
            continue

        relative_path = Path(unquote(parsed.path))
        if relative_path.is_absolute():
            continue

        resolved = (workpaper_path.parent / relative_path).resolve()
        try:
            resolved.relative_to(evidence_root)
        except ValueError:
            continue

        if resolved in seen_paths:
            continue
        seen_paths.add(resolved)
        evidence_targets.append(target)

        if not resolved.is_file():
            result.error(
                f"{workpaper_path}: linked evidence file does not exist or is not a file: "
                f"{target}"
            )

    return evidence_targets


def validate_audit_program(
    project_root: Path,
    result: ValidationResult,
    *,
    strict: bool = False,
) -> list[dict[str, Any]]:
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

    if strict and isinstance(data, dict):
        program = data.get("program", {})
        if isinstance(program, dict) and str(program.get("status") or "").lower() == "draft":
            result.warning("03_audit_program/audit_program.yml: program status is draft")

    if not isinstance(rows, list):
        result.error("03_audit_program/audit_program.yml: program_rows must be a list")
        return []

    valid_rows = [row for row in rows if isinstance(row, dict)]
    test_ids = [str(row.get("test_id")) for row in valid_rows if row.get("test_id")]
    workpaper_refs = [
        str(row.get("workpaper_ref")) for row in valid_rows if row.get("workpaper_ref")
    ]
    for duplicate in sorted(duplicate_values(test_ids)):
        result.error(f"03_audit_program/audit_program.yml: duplicate test_id: {duplicate}")
    for duplicate in sorted(duplicate_values(workpaper_refs)):
        result.error(f"03_audit_program/audit_program.yml: duplicate workpaper_ref: {duplicate}")

    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            result.error(
                f"03_audit_program/audit_program.yml: "
                f"program_rows[{index}] must be a mapping"
            )
            continue

        workpaper_ref = str(row.get("workpaper_ref") or "")
        if workpaper_ref:
            workpaper_path = project_root / "05_workpapers" / f"{workpaper_ref}.qmd"
            if not workpaper_path.exists():
                result.warning(
                    f"Program row {row.get('test_id', index)} references missing workpaper: "
                    f"05_workpapers/{workpaper_ref}.qmd"
                )
            else:
                metadata = load_qmd_front_matter(workpaper_path, result)
                auditflow_metadata = metadata.get("auditflow", {})
                declared_ref = (
                    str(auditflow_metadata.get("workpaper_ref") or "")
                    if isinstance(auditflow_metadata, dict)
                    else ""
                )
                if declared_ref and declared_ref != workpaper_ref:
                    result.error(
                        f"{workpaper_path}: front matter workpaper_ref {declared_ref} "
                        f"does not match audit_program.yml reference {workpaper_ref}"
                    )
                elif strict and not declared_ref:
                    result.warning(
                        f"{workpaper_path}: front matter auditflow.workpaper_ref is missing"
                    )
                if not isinstance(auditflow_metadata, dict):
                    result.error(f"{workpaper_path}: front matter auditflow must be a mapping")

                evidence_links = validate_workpaper_evidence_links(
                    project_root,
                    workpaper_path,
                    result,
                )
                if evidence_links == []:
                    result.warning(
                        f"{workpaper_path}: no local Markdown links to files in 04_evidence"
                    )

        if strict:
            test_id = str(row.get("test_id") or index)
            if not str(row.get("test_hypothesis") or "").strip():
                result.warning(f"Program row {test_id}: test_hypothesis is empty")
            if not row.get("test_script"):
                result.warning(f"Program row {test_id}: test_script is empty")

    return valid_rows


def validate_observations(
    project_root: Path,
    program_rows: list[dict[str, Any]],
    result: ValidationResult,
    *,
    strict: bool = False,
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
    observation_ids: list[str] = []

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

        observation_id = str(observation.get("observation_id") or "")
        if observation_id:
            observation_ids.append(observation_id)

        source_workpaper = str(observation.get("source_workpaper") or "")
        if source_workpaper and source_workpaper not in rows_by_workpaper:
            result.error(
                f"{observation_path}: source_workpaper {source_workpaper} "
                "is not present in audit_program.yml"
            )

        linked_row = rows_by_workpaper.get(source_workpaper)

        test_id = str(observation.get("test_id") or "")
        if test_id and test_id not in test_ids:
            result.error(
                f"{observation_path}: test_id {test_id} is not present in audit_program.yml"
            )
        elif linked_row and test_id != str(linked_row.get("test_id") or ""):
            result.error(
                f"{observation_path}: test_id {test_id} does not match "
                f"source_workpaper {source_workpaper}"
            )

        risk_id = str(observation.get("risk_id") or "")
        if risk_id and risk_id not in risk_ids:
            result.error(
                f"{observation_path}: risk_id {risk_id} is not present in audit_program.yml"
            )
        elif linked_row and risk_id != str(linked_row.get("risk_id") or ""):
            result.error(
                f"{observation_path}: risk_id {risk_id} does not match "
                f"source_workpaper {source_workpaper}"
            )

        source_file = str(observation.get("source_file") or "")
        if source_file:
            validate_reference(project_root, source_file, str(observation_path), result)
            expected_source = f"05_workpapers/{source_workpaper}.qmd"
            if source_file.replace("\\", "/") != expected_source:
                result.error(
                    f"{observation_path}: source_file must match source_workpaper: "
                    f"expected {expected_source}"
                )

        actions = observation.get("management_action_plan", [])
        if isinstance(actions, list):
            action_ids = [
                str(action.get("action_id"))
                for action in actions
                if isinstance(action, dict) and action.get("action_id")
            ]
            for duplicate in sorted(duplicate_values(action_ids)):
                result.error(f"{observation_path}: duplicate action_id: {duplicate}")

            for action in actions:
                if not isinstance(action, dict):
                    continue
                due_date = str(action.get("due_date") or "").strip()
                if due_date:
                    try:
                        date.fromisoformat(due_date)
                    except ValueError:
                        result.error(
                            f"{observation_path}: invalid management action due_date: {due_date}"
                        )

        if strict:
            if str(observation.get("status") or "").lower() == "draft":
                result.warning(f"{observation_path}: observation status is draft")
            for field_name in (
                "condition",
                "criteria",
                "cause",
                "risk_effect",
                "recommendation",
            ):
                if not str(observation.get(field_name) or "").strip():
                    result.warning(f"{observation_path}: {field_name} is empty")
            if isinstance(actions, list):
                for action_index, action in enumerate(actions, start=1):
                    if not isinstance(action, dict):
                        continue
                    for field_name in ("action", "responsible_name", "due_date"):
                        if not str(action.get(field_name) or "").strip():
                            result.warning(
                                f"{observation_path}: management_action_plan[{action_index}]."
                                f"{field_name} is empty"
                            )

    for duplicate in sorted(duplicate_values(observation_ids)):
        result.error(f"06_observations: duplicate observation_id: {duplicate}")


def validate_evidence_manifest(project_root: Path, result: ValidationResult) -> None:
    manifest_path = project_root / "04_evidence" / "evidence_manifest.yml"
    if not manifest_path.exists():
        return
    try:
        load_evidence_manifest(project_root)
    except EvidenceManifestError as exc:
        result.error(f"Invalid evidence manifest: {exc}")


def validate_project(project_root: Path, *, strict: bool = False) -> ValidationResult:
    result = ValidationResult()
    validate_required_structure(project_root, result)
    load_yaml(project_root / "initial_data.yml", result)
    for file_name in REQUIRED_ADMIN_FILES:
        load_yaml(project_root / "00_admin" / file_name, result)

    program_rows = validate_audit_program(project_root, result, strict=strict)
    validate_observations(project_root, program_rows, result, strict=strict)
    validate_evidence_manifest(project_root, result)

    return result
