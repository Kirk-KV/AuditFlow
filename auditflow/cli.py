from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Optional

import typer

from auditflow.commands.archive import update_archive
from auditflow.commands.audit_program import create_audit_program
from auditflow.commands.feedback import create_requests, create_summary
from auditflow.commands.init_project import create_initial_project
from auditflow.commands.observations import generate_observations
from auditflow.commands.planning import create_planning_files
from auditflow.commands.report import update_report_qmd
from auditflow.commands.status import get_status
from auditflow.commands.workpapers import generate_workpapers
from auditflow.project import AuditFlowProjectNotFound, relative_to_cwd, resolve_project

app = typer.Typer(
    name="auditflow",
    help="A lightweight framework for structured, traceable internal audit work.",
    no_args_is_help=True,
)

create_app = typer.Typer(help="Create staged audit artifacts.", no_args_is_help=True)
feedback_app = typer.Typer(help="Create feedback requests and summaries.", no_args_is_help=True)
app.add_typer(create_app, name="create")
app.add_typer(feedback_app, name="feedback")


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


@create_app.command("report")
def create_report_command(
    project: Optional[Path] = project_option(),
    reset_report: bool = typer.Option(False, help="Recreate report.qmd from template. Deletes manual edits."),
) -> None:
    """Create or update 07_reporting/report.qmd using protected AUTO blocks."""
    project_root = require_project(project)
    report_path = update_report_qmd(project_root, reset_report=reset_report)
    typer.echo(f"Report updated: {report_path}")


@create_app.command("archive")
def create_archive_command(
    project: Optional[Path] = project_option(),
    reset_archive: bool = typer.Option(False, help="Recreate audit_story.qmd from template. Deletes manual edits."),
) -> None:
    """Create or update 09_archive/audit_story.qmd."""
    project_root = require_project(project)
    archive_path = update_archive(project_root, reset=reset_archive)
    typer.echo(f"Audit story updated: {archive_path}")


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


@feedback_app.command("summary")
def feedback_summary_command(
    project: Optional[Path] = project_option(),
) -> None:
    """Create one 08_feedback/feedback_summary.qmd from response templates."""
    project_root = require_project(project)
    create_summary(project_root)


@app.command()
def validate(
    project: Optional[Path] = project_option(),
    strict: bool = typer.Option(False, help="Run strict validation."),
) -> None:
    """Validate audit project structure and links."""
    project_root = require_project(project)
    mode = "strict" if strict else "soft"
    typer.echo(f"Validating audit project: {project_root}")
    typer.echo(f"Validation mode: {mode}")
    typer.echo("Not implemented yet. Planned for the validation iteration.")
    raise typer.Exit(code=1)


@app.command()
def render(
    target: str = typer.Argument(..., help="Target to render: planning, report, feedback, archive, all."),
    project: Optional[Path] = project_option(),
) -> None:
    """Render Quarto documents for a project."""
    project_root = require_project(project)
    targets = {
        "planning": [project_root / "01_planning" / "planning_document.qmd"],
        "report": [project_root / "07_reporting" / "report.qmd"],
        "feedback": [project_root / "08_feedback" / "feedback_summary.qmd"],
        "archive": [project_root / "09_archive" / "audit_story.qmd"],
    }

    if target == "all":
        paths = [path for group in targets.values() for path in group]
    elif target in targets:
        paths = targets[target]
    else:
        typer.echo("Unknown target. Use: planning, report, feedback, archive, all.", err=True)
        raise typer.Exit(code=1)

    rendered = 0
    for path in paths:
        if not path.exists():
            typer.echo(f"Skipped missing file: {path}")
            continue
        subprocess.run(["quarto", "render", str(path)], cwd=project_root, check=True)
        rendered += 1

    typer.echo(f"Rendered documents: {rendered}")
