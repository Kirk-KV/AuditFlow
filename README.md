# AuditFlow

> **A lightweight framework for structured, traceable, reproducible internal audit work**

---
**Why:**
Internal audit work is often scattered across manually edited Excel files, Word files, emails, screenshots, and slide decks. 
Some calculations are copied, some formulas are replaced, several filters are applied, a few pivot tables appear, "irrelevant" rows are manually removed, etc.
The conclusion may be correct, but the reasoning behind it has largely disappeared.
Moreover, calculations 'update' become quite time-consuming.

---

## AuditFlow Philosophy

Time is the most valuable thing. So:
- no work for the sake of work
- auditor must think before going into tests
- work should be easily understood and traceable, so there will be no time wasting for clarification
- decisions and conclusions should be data-based, and data analysis should be as easy and quick as possible: any error is corrected in script in 5 minutes and not in Excel in 3 hours
- 'mechanical' work should be minimized

This is my specific view of what good internal audit work should look like.

---

## AuditFlow Approach

AuditFlow keeps the work in plain files:

- YAML for structured audit data and decisions;
- QMD / Markdown for audit narratives, workpapers, reports, and archive story;
- raw evidence kept unchanged;
- generated outputs kept separate from source evidence.

The current traceability chain is:

```text
Initial input -> Planning decision -> Audit program -> Workpapers -> Observations -> Report -> Feedback -> Archive
```

Internal audit is not only about evidence, it is also about reasoning: why was this risk included, or this control considered key, or this sample selected? Which evidence supports this conclusion?
If the source data changes tomorrow or we find a minor mistake in the file, can we rebuild everything quickly?

The goal of this approach is to address these issues with an open-source free tool.

I tried to link every stage of the audit:

Risk → Control → Test → Evidence → Result → Observation → Action → Report

---

AuditFlow is an opinionated framework. It assumes that:

- planning creates most of the audit value;
- data analysis should be reproducible;
- documentation should explain reasoning;
- professional judgment should remain human;
- automation should remove mechanical work;
- AI should challenge thinking, not replace it.


> Disclaimer:
- this is not a complete methodology needed for sound IA process in a company;
- you need a little bit of Python practice to get most of this tool;
- by default, AuditFlow should not send raw evidence or confidential data to any external LLM. Use either local LLM in a company (mind the risks) or thoroughly analyze what you give to an external model. 


## Install

```bash
git clone https://github.com/Kirk-KV/auditflow.git
cd auditflow
pip install -e .
auditflow --help
```

## Basic Workflow

```bash
auditflow init "C:/Audits/2026-001_procurement"
cd "C:/Audits/2026-001_procurement"

auditflow status
auditflow create planning
auditflow create audit-program
auditflow create workpapers
auditflow create observations
auditflow create report
auditflow feedback request
auditflow feedback summary
auditflow create archive
auditflow render all
```

In practice, the auditor edits files between commands:

1. Complete `initial_data.yml` and `00_admin/*.yml`.
2. Run `auditflow create planning`.
3. Complete `01_planning/planning_document.qmd` and `01_planning/planning_decision.yml`.
4. Run `auditflow create audit-program`.
5. Complete `test_hypothesis` and `test_script` in `03_audit_program/audit_program.yml`.
6. Run `auditflow create workpapers`.
7. Complete workpapers in `05_workpapers/`.
8. Run `auditflow create observations`.
9. Complete observation YAML files in `06_observations/`.
10. Run `auditflow create report`.
11. Run feedback and archive steps when the audit is complete.

## Project Structure

```text
audit_project/
  initial_data.yml
  _quarto.yml

  00_admin/
    stakeholders.yml
    team.yml
    decisions.yml
    timeline.yml

  01_planning/
    planning_document.qmd
    planning_decision.yml

  03_audit_program/
    audit_program.yml

  04_evidence/
    01_regulations/
    02_raw_data/
    03_correspondence/
    04_reference_materials/
    05_screenshots/
    99_generated/

  05_workpapers/
  06_observations/
  07_reporting/
  08_feedback/
  09_archive/

  styles/
    auditflow.css
    brand.css
    report.css
```

## Styling

`auditflow init` creates project-level style files:

```text
styles/auditflow.css
styles/brand.css
styles/report.css
```

Default templates are stored in:

```text
auditflow/templates/styles/
```

Customization priority:

1. explicit CLI argument;
2. environment variable;
3. bundled default template.

For `brand.css`:

```bash
auditflow init "C:/Audits/2026-001_procurement" --brand-css "C:/AuditFlowBrand/brand.css"
```

or set once:

```powershell
[Environment]::SetEnvironmentVariable("AUDITFLOW_BRAND_CSS", "C:\AuditFlowBrand\brand.css", "User")
```

For `report.css`:

```bash
auditflow init "C:/Audits/2026-001_procurement" --report-css "C:/AuditFlowBrand/report.css"
```

or set once:

```powershell
[Environment]::SetEnvironmentVariable("AUDITFLOW_REPORT_CSS", "C:\AuditFlowBrand\report.css", "User")
```

Generated `07_reporting/report.qmd` references:

```yaml
format:
  html:
    css: ../styles/report.css
```

## Current Limitations

- `auditflow validate` is a placeholder.
- Long-term management action tracking is outside the current project scope.
- LLM integration is not automated and not finished yet; any LLM use should follow company data protection rules.
- Notification letter generation is not part of the current CLI workflow (however, you can see the notification template in 'auditflow/templates/').

## Documentation

- `docs/user_journey.md` — step-by-step user journey.
- `docs/project_structure.md` — project folders and source-of-truth files.
- `docs/workflow.md` — decision-oriented audit workflow.
- `docs/methodology.md` — methodology principles.
- `docs/customization.md` — customization approach.
- `examples/procurement_audit/` — synthetic example audit (at the moment it differs from the current structure a little bit. I will update it shortly, but it is useful to understand what should appear where).

