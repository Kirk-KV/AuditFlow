# VSCode And CLI

AuditFlow uses VSCode as a practical audit workspace and the CLI as the command layer.

The command set is intentionally small. Commands should create or refresh artifacts; they should not replace audit judgment.

## Current Commands

```bash
auditflow --help
auditflow init <project>
auditflow status
auditflow create planning
auditflow create audit-program
auditflow create workpapers
auditflow create observations
auditflow create report
auditflow feedback request
auditflow feedback summary
auditflow create archive
auditflow evidence status
auditflow evidence refresh
auditflow ai status
auditflow ai draft-observation <workpaper_ref>
auditflow ai review-observation <observation_id>
auditflow ai review-audit-program
auditflow validate
auditflow validate --strict
```

AI commands are optional and disabled by default in new projects.

Commands `auditflow evidence status` and `auditflow evidence refresh` are also optional; use
them when the team enables Git review of evidence fingerprints.

## `auditflow init`

Creates a new audit project.

```bash
auditflow init "C:/Audits/2026-001_procurement"
```

Russian document templates:

```bash
auditflow init "C:/Audits/2026-001_procurement" --language ru
```

The selection is stored in `00_admin/settings.yml`. Existing projects without this file continue to use English templates.

Optional styling arguments:

```bash
auditflow init "C:/Audits/2026-001_procurement" \
  --brand-css "C:/AuditFlowBrand/brand.css" \
  --report-css "C:/AuditFlowBrand/report.css"
```

Environment variable alternatives:

```powershell
[Environment]::SetEnvironmentVariable("AUDITFLOW_BRAND_CSS", "C:\AuditFlowBrand\brand.css", "User")
[Environment]::SetEnvironmentVariable("AUDITFLOW_REPORT_CSS", "C:\AuditFlowBrand\report.css", "User")
```

## `auditflow status`

Shows current stage completion and the next recommended command.

```bash
auditflow status
```

## `auditflow create planning`

Creates:

```text
01_planning/planning_document.qmd
01_planning/planning_decision.yml
```

Fill in `planning_decision.yml`, including `controls[].planning_approach`, then
rerun the command to refresh the risk, control, and test tables in the planning
document. In a customized legacy document, add an `AUTO:PLANNING_APPROACH`
START/END comment pair where the tables should appear.

## `auditflow create audit-program`

Creates or updates:

```text
03_audit_program/audit_program.yml
03_audit_program/audit_program.qmd
```

The command reads `01_planning/planning_decision.yml`. Edit hypotheses and test
procedures in the program YAML, then rerun without `--overwrite` to refresh
the QMD table and preserve those fields. For a custom QMD, add an
`AUTO:AUDIT_PROGRAM` START/END comment pair where the table should appear.

## `auditflow create workpapers`

Creates one workpaper per audit program row:

```text
05_workpapers/WP-*.qmd
```

Rerunning updates the existing QMD title from the audit program and preserves
the body. Use `--overwrite` only to recreate the whole workpaper.

## `auditflow create observations`

Creates observation YAML files from completed workpaper observation proposal blocks:

```text
06_observations/OBS-*.yml
```

The workpaper proposal supplies the title when an observation is first created.
Edit the title in the observation YAML as the finding develops. Rerunning
refreshes linked audit program fields and preserves the title, severity,
narrative, and management action plan. Use `--clean-stale` to remove observations
whose source no longer proposes one. `--overwrite` recreates the observation
from its sources and discards manual edits.

Useful options:

```bash
auditflow create observations --verbose
auditflow create observations --clean-stale
```

## `auditflow create report`

Creates or updates:

```text
07_reporting/report.qmd
```

The generated report references:

```text
../styles/report.css
```

The observation fields `criteria`, `condition`, `cause`, `risk_effect`, and
`recommendation` support Markdown. Use a YAML literal block (`|`) for
multi-line text and lists.

## `auditflow feedback request`

Creates feedback request text files and response YAML templates:

```bash
auditflow feedback request
auditflow feedback request --include-sponsor --response-due-date 2026-04-15
```

## `auditflow feedback summary`

Creates:

```text
08_feedback/feedback_summary.qmd
```

## `auditflow create archive`

Creates or updates:

```text
09_archive/audit_story.qmd
```

## `auditflow evidence`

`auditflow evidence refresh` creates or updates the optional `04_evidence/evidence_manifest.yml`; `auditflow evidence status` compares local evidence with it. Evidence contents remain outside Git; see `git_collaboration.md` for the review workflow.

## `auditflow ai`

Shows the effective company policy, destination, model, project classification, and provider availability:

```bash
auditflow ai status
```

Available review and drafting commands:

```bash
auditflow ai draft-observation <workpaper_ref> --dry-run
auditflow ai review-observation <observation_id> --dry-run
auditflow ai review-audit-program --dry-run
```

Remove `--dry-run` only after reviewing the source manifest and preflight findings. A dry run does not contact the provider or create output.

AI output is written separately under `ai_outputs/`; source workpapers, observations, and the audit program are not overwritten. Audit-program review excludes `test_script` and does not assess test executability. See `llm_integration.md` for setup and company-policy controls.

## `auditflow validate`

`auditflow validate` checks project structure, schemas, unique IDs, links between the program and observations, and local Markdown links from workpapers into `04_evidence`.

It also checks both ends of the traceability chain. At the start, risks in `01_planning/planning_decision.yml` must come from `initial_data.yml`, and every audit program row must test a risk the planning decision included. At the end, `07_reporting/report.qmd` and `09_archive/audit_story.qmd` must still contain their `AUTO` markers, and their recorded generation stamp must match the current `06_observations`. A report written before the observations last changed is reported as out of date.

Use `auditflow validate --strict` before final sharing. Strict mode requires at least one valid evidence link per workpaper, adds finalization-oriented checks, and treats warnings as failures. Other local and external links are ignored. Neither mode confirms audit quality, evidence sufficiency, or the correctness of conclusions.

## Rendering QMD Documents

QMD documents are previewed and rendered using the standard Quarto extension in VS Code. While editing a document, use the Quarto Preview button or run:

```bash
quarto preview 07_reporting/report.qmd
```

To create a standalone rendered output, run:

```bash
quarto render 07_reporting/report.qmd
```

Replace the path with the QMD document you are working on. Quarto must be installed and available on `PATH`; AuditFlow does not require a separate rendering workflow.

Generated QMD files load shared HTML settings from `styles/quarto-html.yml`.
AuditFlow does not create a Quarto project, so rendering temporary files stay
in the local system temp directory. This also avoids known project-cache
problems on some Windows network and DFS drives.

For an audit created by an older AuditFlow version:

1. Delete `_quarto.yml`.
2. Add `styles/quarto-html.yml` from the current project template.
3. Add this to the front matter of each QMD:

```yaml
metadata-files:
  - ../styles/quarto-html.yml
```

## VSCode Tasks

The project template includes `.vscode` files so common commands can be exposed as tasks.

Recommended tasks should mirror the current CLI:

```text
AuditFlow: Status
AuditFlow: Create Planning
AuditFlow: Create Audit Program
AuditFlow: Create Workpapers
AuditFlow: Create Observations
AuditFlow: Create Report
AuditFlow: Feedback Request
AuditFlow: Feedback Summary
AuditFlow: Create Archive
```
