from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer

from auditflow.ai.config import AIConfigError, resolve_ai_config
from auditflow.ai.providers import AIProviderError, create_provider
from auditflow.ai.service import (
    AIServiceError,
    PreparedAuditProgramReview,
    PreparedObservationDraft,
    PreparedObservationReview,
    generate_audit_program_review,
    generate_observation_draft,
    generate_observation_review,
    prepare_audit_program_review,
    prepare_observation_draft,
    prepare_observation_review,
)
from auditflow.commands.archive import update_archive
from auditflow.commands.audit_program import create_audit_program
from auditflow.commands.evidence import (
    EvidenceChange,
    EvidenceManifestError,
    compare_evidence,
    refresh_evidence_manifest,
)
from auditflow.commands.feedback import create_requests, create_summary
from auditflow.commands.init_project import create_initial_project
from auditflow.commands.observations import generate_observations
from auditflow.commands.planning import create_planning_files
from auditflow.commands.report import update_report_qmd
from auditflow.commands.status import get_status
from auditflow.commands.validate import validate_project
from auditflow.commands.workpapers import generate_workpapers
from auditflow.project import AuditFlowProjectNotFound, relative_to_cwd, resolve_project
from auditflow.timeline import record_event, refresh_timeline

app = typer.Typer(
    name="auditflow",
    help="A lightweight framework for structured, traceable internal audit work.",
    no_args_is_help=True,
)

create_app = typer.Typer(help="Create staged audit artifacts.", no_args_is_help=True)
feedback_app = typer.Typer(help="Create feedback requests and summaries.", no_args_is_help=True)
timeline_app = typer.Typer(help="Work with audit timeline facts.", no_args_is_help=True)
ai_app = typer.Typer(help="Use approved AI profiles for audit assistance.", no_args_is_help=True)
evidence_app = typer.Typer(
    help="Track hashes of evidence files kept outside Git.",
    no_args_is_help=True,
)
app.add_typer(create_app, name="create")
app.add_typer(feedback_app, name="feedback")
app.add_typer(timeline_app, name="timeline")
app.add_typer(ai_app, name="ai")
app.add_typer(evidence_app, name="evidence")


def project_option() -> Optional[Path]:
    return typer.Option(
        None,
        "--project",
        "-p",
        help="Audit project path. Omit when running inside an AuditFlow project.",
    )


def require_project(project: Optional[Path]) -> Path:
    try:
        return resolve_project(project)
    except AuditFlowProjectNotFound as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(code=1) from exc


@app.command()
def init(
    path: Path = typer.Argument(..., help="Path where the audit project should be created. Use . for the current folder."),
    overwrite: bool = typer.Option(False, help="Overwrite existing starter files if they already exist."),
    brand_css: Optional[Path] = typer.Option(
        None,
        "--brand-css",
        help=(
            "Optional path to company/project brand.css. "
            "If omitted, AUDITFLOW_BRAND_CSS is used when set; otherwise the default template is used."
        ),
    ),
    report_css: Optional[Path] = typer.Option(
        None,
        "--report-css",
        help=(
            "Optional path to company/project report.css. "
            "If omitted, AUDITFLOW_REPORT_CSS is used when set; otherwise the default template is used."
        ),
    ),
) -> None:
    """Create a new staged AuditFlow project."""
    result = create_initial_project(
        path,
        overwrite=overwrite,
        brand_css=brand_css,
        report_css=report_css,
    )
    typer.echo(f"AuditFlow project created: {result['project_root']}")
    typer.echo(f"Created folders: {len(result['created_dirs'])}")
    typer.echo(f"Created files: {len(result['created_files'])}")
    record_event(
        result["project_root"],
        event="project_initialized",
        command="auditflow init",
        artifact="initial_data.yml",
    )
    typer.echo("Next: cd into the project and complete initial_data.yml and 00_admin/*.yml")


@app.command()
def status(
    project: Optional[Path] = project_option(),
) -> None:
    """Show current workflow status and the next recommended command."""
    project_root = require_project(project)
    status_data = get_status(project_root)

    typer.echo(f"Audit project: {status_data['audit_title']}")
    typer.echo(f"Path: {relative_to_cwd(project_root)}")
    typer.echo("")
    typer.echo("Stage")

    for row in status_data["rows"]:
        mark = "✓" if row["done"] else "○"
        typer.echo(f"{mark} {row['name']} — {row['details']}")

    typer.echo("")
    typer.echo("Next recommended command:")
    typer.echo(status_data["next_command"])


@create_app.command("planning")
def create_planning_command(
    project: Optional[Path] = project_option(),
    overwrite: bool = typer.Option(False, help="Overwrite existing planning files. Use carefully."),
) -> None:
    """Create planning_document.qmd and planning_decision.yml."""
    project_root = require_project(project)
    result = create_planning_files(project_root, overwrite=overwrite)
    typer.echo(f"Planning directory: {result['planning_dir']}")
    typer.echo(f"Created: {len(result['created'])}")
    typer.echo(f"Kept existing: {len(result['kept'])}")
    record_event(
        project_root,
        event="planning_created",
        command="auditflow create planning",
        artifact="01_planning/planning_decision.yml",
    )


@create_app.command("audit-program")
def create_audit_program_command(
    project: Optional[Path] = project_option(),
    overwrite: bool = typer.Option(False, help="Overwrite existing manual fields in audit_program.yml."),
) -> None:
    """Create or update 03_audit_program/audit_program.yml."""
    project_root = require_project(project)
    result = create_audit_program(project_root, overwrite=overwrite)
    typer.echo(f"Audit program generated: {result['path']}")
    typer.echo(f"Rows: {result['rows']}")
    if result["manual_fields_preserved"]:
        typer.echo("Manual fields preserved.")
    record_event(
        project_root,
        event="audit_program_created",
        command="auditflow create audit-program",
        artifact="03_audit_program/audit_program.yml",
    )


@create_app.command("workpapers")
def create_workpapers_command(
    project: Optional[Path] = project_option(),
    overwrite: bool = typer.Option(False, help="Overwrite existing workpaper files. Use carefully."),
) -> None:
    """Create workpaper QMD templates from audit_program.yml."""
    project_root = require_project(project)
    result = generate_workpapers(project_root, overwrite=overwrite)
    typer.echo(f"Workpapers created: {result['created']}")
    typer.echo(f"Workpapers skipped: {result['skipped']}")
    typer.echo(f"Rows without workpaper_ref: {result.get('missing_workpaper_ref', 0)}")
    typer.echo(f"Output directory: {result['workpapers_dir']}")
    record_event(
        project_root,
        event="workpapers_created",
        command="auditflow create workpapers",
        artifact="05_workpapers",
    )


@create_app.command("observations")
def create_observations_command(
    project: Optional[Path] = project_option(),
    overwrite: bool = typer.Option(False, help="Overwrite existing OBS-XXX.yml files."),
    clean_stale: bool = typer.Option(False, help="Delete stale observations whose source workpaper no longer proposes an observation."),
    verbose: bool = typer.Option(False, help="Show workpapers without parseable Observation proposal YAML blocks."),
) -> None:
    """Create individual OBS-XXX.yml files from workpaper Observation proposal blocks."""
    project_root = require_project(project)
    result = generate_observations(
        audit_project_root=project_root,
        overwrite=overwrite,
        clean_stale=clean_stale,
    )
    typer.echo(f"Output directory: {result['observations_dir']}")
    typer.echo(f"Created: {result['created']}")
    typer.echo(f"Updated: {result['updated']}")
    typer.echo(f"Skipped existing: {result['skipped_existing']}")
    typer.echo(f"Skipped not required: {result['skipped_not_required']}")
    typer.echo(f"Workpapers without Observation proposal YAML block: {len(result['missing_block'])}")

    if verbose and result["missing_block"]:
        typer.echo("Missing or unparsable blocks:")
        for name in result["missing_block"]:
            typer.echo(f"  - {name}")

    if result["stale_candidates"]:
        typer.echo(f"Stale observation files: {len(result['stale_candidates'])}")
        if not clean_stale:
            typer.echo("Use --clean-stale to delete stale observation files.")
    record_event(
        project_root,
        event="observations_created",
        command="auditflow create observations",
        artifact="06_observations",
    )


@create_app.command("report")
def create_report_command(
    project: Optional[Path] = project_option(),
    reset_report: bool = typer.Option(False, help="Recreate report.qmd from template. Deletes manual edits."),
) -> None:
    """Create or update 07_reporting/report.qmd using protected AUTO blocks."""
    project_root = require_project(project)
    report_path = update_report_qmd(project_root, reset_report=reset_report)
    typer.echo(f"Report updated: {report_path}")
    record_event(
        project_root,
        event="report_created",
        command="auditflow create report",
        artifact="07_reporting/report.qmd",
    )


@create_app.command("archive")
def create_archive_command(
    project: Optional[Path] = project_option(),
    reset_archive: bool = typer.Option(False, help="Recreate audit_story.qmd from template. Deletes manual edits."),
) -> None:
    """Create or update 09_archive/audit_story.qmd."""
    project_root = require_project(project)
    archive_path = update_archive(project_root, reset=reset_archive)
    typer.echo(f"Audit story updated: {archive_path}")
    record_event(
        project_root,
        event="archive_created",
        command="auditflow create archive",
        artifact="09_archive/audit_story.qmd",
    )


@feedback_app.command("request")
def feedback_request_command(
    project: Optional[Path] = project_option(),
    include_sponsor: bool = typer.Option(False, help="Also generate a request for sponsor."),
    response_due_date: str = typer.Option("", help="Optional response due date, e.g. 2026-04-15."),
    overwrite: bool = typer.Option(False, help="Overwrite generated request text files."),
    reset_response_templates: bool = typer.Option(False, help="Reset response YAML templates. This can delete entered feedback."),
) -> None:
    """Create plain-text feedback requests and response templates."""
    project_root = require_project(project)
    create_requests(
        project_root=project_root,
        include_sponsor=include_sponsor,
        response_due_date=response_due_date,
        overwrite_requests=overwrite,
        reset_response_templates=reset_response_templates,
    )
    record_event(
        project_root,
        event="feedback_requested",
        command="auditflow feedback request",
        artifact="08_feedback/request",
    )


@feedback_app.command("summary")
def feedback_summary_command(
    project: Optional[Path] = project_option(),
) -> None:
    """Create one 08_feedback/feedback_summary.qmd from response templates."""
    project_root = require_project(project)
    create_summary(project_root)


@timeline_app.command("refresh")
def timeline_refresh_command(
    project: Optional[Path] = project_option(),
    overwrite_facts: bool = typer.Option(
        False,
        help="Overwrite existing fact dates from recorded events.",
    ),
) -> None:
    """Refresh timeline fact dates from recorded workflow events."""
    project_root = require_project(project)
    result = refresh_timeline(project_root, overwrite_facts=overwrite_facts)
    events = result.get("events", [])
    event_count = len(events) if isinstance(events, list) else 0
    typer.echo("Timeline refreshed.")
    typer.echo(f"Events: {event_count}")


def _echo_evidence_changes(changes: tuple[EvidenceChange, ...]) -> None:
    for change in changes:
        if change.kind == "modified":
            typer.echo(
                f"- MODIFIED {change.path}: "
                f"{str(change.expected_sha256)[:12]} -> "
                f"{str(change.actual_sha256)[:12]}"
            )
        elif change.kind == "added":
            typer.echo(
                f"- ADDED {change.path}: sha256 "
                f"{str(change.actual_sha256)[:12]}"
            )
        else:
            typer.echo(
                f"- MISSING {change.path}: expected sha256 "
                f"{str(change.expected_sha256)[:12]}"
            )


@evidence_app.command("status")
def evidence_status_command(
    project: Optional[Path] = project_option(),
) -> None:
    """Compare local evidence files with the tracked SHA-256 manifest."""
    project_root = require_project(project)
    try:
        comparison = compare_evidence(project_root)
    except EvidenceManifestError as exc:
        typer.echo(f"Evidence status error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Evidence files found: {len(comparison.current_files)}")
    if not comparison.manifest_exists:
        typer.echo(
            "Evidence manifest is missing. Run 'auditflow evidence refresh' to create it."
        )
        raise typer.Exit(code=1)
    if comparison.changes:
        typer.echo("Evidence differs from 04_evidence/evidence_manifest.yml:")
        _echo_evidence_changes(comparison.changes)
        typer.echo(
            "Review the changes, then run 'auditflow evidence refresh' only when the "
            "new evidence state is accepted for review."
        )
        raise typer.Exit(code=1)
    typer.echo("Evidence matches 04_evidence/evidence_manifest.yml.")


@evidence_app.command("refresh")
def evidence_refresh_command(
    project: Optional[Path] = project_option(),
) -> None:
    """Record the current local evidence hashes in the tracked manifest."""
    project_root = require_project(project)
    try:
        result = refresh_evidence_manifest(project_root)
    except EvidenceManifestError as exc:
        typer.echo(f"Evidence refresh error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if result.previous_changes:
        typer.echo("Evidence snapshot changes recorded:")
        _echo_evidence_changes(result.previous_changes)
    typer.echo(f"Evidence files recorded: {len(result.files)}")
    typer.echo(
        f"Evidence manifest {'updated' if result.changed else 'unchanged'}: "
        f"{result.manifest_path}"
    )
    typer.echo(
        "Commit the manifest change for manager review; do not add evidence file "
        "contents to Git."
    )


@ai_app.command("status")
def ai_status_command(
    project: Optional[Path] = project_option(),
    check_provider: bool = typer.Option(
        True,
        "--check-provider/--no-check-provider",
        help="Check provider availability and whether the selected model is installed.",
    ),
) -> None:
    """Show resolved AI policy, profile, and project permissions."""
    project_root = require_project(project)
    try:
        config = resolve_ai_config(project_root)
    except AIConfigError as exc:
        typer.echo(f"AI configuration error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    profile = config.profile
    rules = config.rules
    typer.echo(f"AI enabled: {'yes' if config.enabled else 'no'}")
    typer.echo(f"Policy: {config.policy_id}")
    typer.echo(f"Policy source: {config.policy_source}")
    typer.echo(f"Policy hash: {config.policy_hash[:12]}")
    typer.echo(f"Project settings: {config.project_settings_source}")
    typer.echo(f"Profile: {profile.name}")
    typer.echo(f"Provider: {profile.provider}")
    typer.echo(f"Destination: {profile.base_url}")
    typer.echo(f"Data boundary: {profile.data_boundary}")
    typer.echo(f"Model: {config.model}")
    typer.echo(f"Project classification: {config.project_classification}")
    typer.echo(f"Raw evidence: {'allowed' if rules.allow_raw_evidence else 'denied'}")
    typer.echo(f"Preflight: {'required' if rules.require_preflight else 'optional'}")
    typer.echo(f"Sensitive-data findings: {rules.sensitive_data_action}")
    typer.echo(f"AI output folder: {rules.output_folder}")
    typer.echo(
        "External confirmation: "
        + ("required" if rules.require_confirmation_for_external else "not required")
    )
    if profile.api_key_env:
        key_status = "configured" if config.api_key_configured else "missing"
        typer.echo(f"API key environment: {profile.api_key_env} ({key_status})")

    if check_provider:
        try:
            provider = create_provider(config)
            provider_status = provider.status(config.model)
            typer.echo(
                f"Provider connection: {'available' if provider_status.reachable else 'unavailable'}"
            )
            typer.echo(f"Provider detail: {provider_status.detail}")
            if config.enabled and (
                not provider_status.reachable or not provider_status.model_available
            ):
                raise typer.Exit(code=1)
        except AIProviderError as exc:
            typer.echo(f"Provider connection: unavailable ({exc})")
            if config.enabled:
                raise typer.Exit(code=1) from exc


def _echo_ai_preflight(
    prepared: (
        PreparedObservationDraft
        | PreparedObservationReview
        | PreparedAuditProgramReview
    ),
    subject: str,
) -> None:
    preflight = prepared.preflight
    config = prepared.config
    typer.echo(f"AI preflight: {subject}")
    typer.echo(f"Destination: {config.profile.name} ({config.profile.base_url})")
    typer.echo(f"Data boundary: {config.profile.data_boundary}")
    typer.echo(f"Project classification: {config.project_classification}")
    typer.echo(f"Raw evidence included: {'yes' if preflight.raw_evidence_included else 'no'}")
    typer.echo(f"Context characters: {prepared.context.character_count}")
    typer.echo("Sources:")
    for source in preflight.sources:
        typer.echo(
            f"- {source.path}: {source.selection} "
            f"({source.character_count} characters, sha256 {source.sha256[:12]})"
        )
    if preflight.findings:
        typer.echo("Findings:")
        for finding in preflight.findings:
            source_suffix = f" [{finding.source}]" if finding.source else ""
            typer.echo(
                f"- {finding.severity.upper()} {finding.code}: "
                f"{finding.message}{source_suffix}"
            )
    else:
        typer.echo("Findings: none")
    typer.echo(f"Decision: {preflight.decision}")


@ai_app.command("draft-observation")
def ai_draft_observation_command(
    workpaper_ref: str = typer.Argument(..., help="Workpaper reference, e.g. WP-C-001."),
    project: Optional[Path] = project_option(),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run preflight and show the source manifest without contacting the provider.",
    ),
    confirm_send: bool = typer.Option(
        False,
        "--confirm-send",
        help="Explicitly confirm sending context when company policy requires confirmation.",
    ),
) -> None:
    """Prepare an AI observation draft without changing OBS-*.yml files."""
    project_root = require_project(project)
    try:
        prepared = prepare_observation_draft(project_root, workpaper_ref)
    except (AIConfigError, AIServiceError) as exc:
        typer.echo(f"AI preparation error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _echo_ai_preflight(prepared, prepared.context.workpaper_ref)
    if prepared.preflight.decision == "blocked":
        raise typer.Exit(code=1)
    if dry_run:
        typer.echo("Dry run complete. No data was sent and no AI output was created.")
        return

    confirmation_granted = confirm_send
    if prepared.preflight.decision == "confirmation_required" and not confirmation_granted:
        confirmation_granted = typer.confirm(
            "Company policy requires confirmation before sending this context. Continue?",
            default=False,
        )
        if not confirmation_granted:
            typer.echo("AI request cancelled. No data was sent.")
            raise typer.Exit(code=1)

    try:
        result = generate_observation_draft(
            project_root,
            prepared,
            confirmation_granted=confirmation_granted,
        )
    except AIServiceError as exc:
        typer.echo(f"AI generation error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"AI draft created: {result.draft_path}")
    typer.echo(f"Run manifest: {result.manifest_path}")
    typer.echo(
        "Observation needed: "
        + ("yes" if result.content.get("observation_needed") else "no")
    )
    if result.quality_findings:
        typer.echo("Draft quality warnings:")
        for finding in result.quality_findings:
            typer.echo(f"- {finding.field}: {finding.message}")
    else:
        typer.echo("Draft quality warnings: none")
    risk_review = result.content.get("risk_formulation_review", {})
    if isinstance(risk_review, dict):
        typer.echo(f"Risk formulation: {risk_review.get('structure', 'not reviewed')}")
        reminder = str(risk_review.get("reminder") or "").strip()
        if reminder:
            typer.echo(f"Risk reminder: {reminder}")
    typer.echo("Review the draft manually. No OBS-*.yml file was changed.")


@ai_app.command("review-observation")
def ai_review_observation_command(
    observation_id: str = typer.Argument(..., help="Observation ID, e.g. OBS-001."),
    project: Optional[Path] = project_option(),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run preflight and show the source manifest without contacting the provider.",
    ),
    confirm_send: bool = typer.Option(
        False,
        "--confirm-send",
        help="Explicitly confirm sending context when company policy requires confirmation.",
    ),
) -> None:
    """Review an observation without changing its OBS-*.yml file."""
    project_root = require_project(project)
    try:
        prepared = prepare_observation_review(project_root, observation_id)
    except (AIConfigError, AIServiceError) as exc:
        typer.echo(f"AI preparation error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _echo_ai_preflight(prepared, prepared.context.workpaper_ref)
    if prepared.preflight.decision == "blocked":
        raise typer.Exit(code=1)
    if dry_run:
        typer.echo("Dry run complete. No data was sent and no AI output was created.")
        return

    confirmation_granted = confirm_send
    if prepared.preflight.decision == "confirmation_required" and not confirmation_granted:
        confirmation_granted = typer.confirm(
            "Company policy requires confirmation before sending this context. Continue?",
            default=False,
        )
        if not confirmation_granted:
            typer.echo("AI request cancelled. No data was sent.")
            raise typer.Exit(code=1)

    try:
        result = generate_observation_review(
            project_root,
            prepared,
            confirmation_granted=confirmation_granted,
        )
    except AIServiceError as exc:
        typer.echo(f"AI review error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"AI review created: {result.review_path}")
    typer.echo(f"Run manifest: {result.manifest_path}")
    risk_review = result.content.get("risk_formulation_review", {})
    if isinstance(risk_review, dict):
        typer.echo(f"Risk formulation: {risk_review.get('structure', 'not reviewed')}")
        reminder = str(risk_review.get("reminder") or "").strip()
        if reminder:
            typer.echo(f"Risk reminder: {reminder}")
    if result.quality_findings:
        typer.echo("AI response quality warnings:")
        for finding in result.quality_findings:
            typer.echo(f"- {finding.field}: {finding.message}")
    typer.echo("Review comments are advisory. No OBS-*.yml file was changed.")


@ai_app.command("review-audit-program")
def ai_review_audit_program_command(
    project: Optional[Path] = project_option(),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run preflight and show the source manifest without contacting the provider.",
    ),
    confirm_send: bool = typer.Option(
        False,
        "--confirm-send",
        help="Explicitly confirm sending context when company policy requires confirmation.",
    ),
) -> None:
    """Review audit-program risks, coverage, traceability, and consistency."""
    project_root = require_project(project)
    try:
        prepared = prepare_audit_program_review(project_root)
    except (AIConfigError, AIServiceError) as exc:
        typer.echo(f"AI preparation error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    _echo_ai_preflight(prepared, "audit program")
    typer.echo("Test scripts included: no")
    if prepared.preflight.decision == "blocked":
        raise typer.Exit(code=1)
    if dry_run:
        typer.echo("Dry run complete. No data was sent and no AI output was created.")
        return

    confirmation_granted = confirm_send
    if prepared.preflight.decision == "confirmation_required" and not confirmation_granted:
        confirmation_granted = typer.confirm(
            "Company policy requires confirmation before sending this context. Continue?",
            default=False,
        )
        if not confirmation_granted:
            typer.echo("AI request cancelled. No data was sent.")
            raise typer.Exit(code=1)

    try:
        result = generate_audit_program_review(
            project_root,
            prepared,
            confirmation_granted=confirmation_granted,
        )
    except AIServiceError as exc:
        typer.echo(f"AI review error: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"AI review created: {result.review_path}")
    typer.echo(f"Run manifest: {result.manifest_path}")
    typer.echo(f"Risk formulation reviews: {len(result.content['risk_reviews'])}")
    typer.echo(f"Coverage reviews: {len(result.content['coverage_reviews'])}")
    typer.echo(f"Traceability issues: {len(result.content['traceability_issues'])}")
    if result.quality_findings:
        typer.echo("AI response quality warnings:")
        for finding in result.quality_findings:
            typer.echo(f"- {finding.field}: {finding.message}")
    else:
        typer.echo("AI response quality warnings: none")
    typer.echo(
        "Review comments are advisory. The audit program was not changed, and "
        "test scripts were not assessed."
    )


@app.command()
def validate(
    project: Optional[Path] = project_option(),
    strict: bool = typer.Option(False, help="Run strict validation."),
) -> None:
    """Validate audit project structure and links."""
    project_root = require_project(project)
    mode = "strict" if strict else "soft"
    result = validate_project(project_root)

    typer.echo(f"Validating audit project: {project_root}")
    typer.echo(f"Validation mode: {mode}")

    if result.errors:
        typer.echo("")
        typer.echo("Errors:")
        for message in result.errors:
            typer.echo(f"- {message}")

    if result.warnings:
        typer.echo("")
        typer.echo("Warnings:")
        for message in result.warnings:
            typer.echo(f"- {message}")

    if not result.errors and not result.warnings:
        typer.echo("")
        typer.echo("No validation issues found.")

    if result.has_failures(strict=strict):
        raise typer.Exit(code=1)
