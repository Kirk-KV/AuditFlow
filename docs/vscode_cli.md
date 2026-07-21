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
auditflow ai status
auditflow ai draft-observation <workpaper_ref>
auditflow ai review-observation <observation_id>
auditflow ai review-audit-program
auditflow validate
```

AI commands are optional and disabled by default in new projects.

## `auditflow init`

Creates a new audit project.

```bash
auditflow init "C:/Audits/2026-001_procurement"
```

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

## `auditflow create audit-program`

Creates or updates:

```text
03_audit_program/audit_program.yml
```

The command reads `01_planning/planning_decision.yml`.

## `auditflow create workpapers`

Creates one workpaper per audit program row:

```text
05_workpapers/WP-*.qmd
```

## `auditflow create observations`

Creates observation YAML files from completed workpaper observation proposal blocks:

```text
06_observations/OBS-*.yml
```

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
