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
auditflow render <planning|report|feedback|archive|all>
auditflow validate
```

`validate` is currently a placeholder.

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

## `auditflow render`

Renders Quarto documents.

```bash
auditflow render planning
auditflow render report
auditflow render feedback
auditflow render archive
auditflow render all
```

Requires Quarto to be installed and available on PATH.

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
AuditFlow: Render All
```
