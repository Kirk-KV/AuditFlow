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
- why?” before “how?”: testing should focus on the areas identified as significant during planning
- work is easy to understand and trace, avoiding time wasted on clarification
- decisions and conclusions are data-based, and analysis is simple and fast: an error is fixed in a script in 5 minutes, not in Excel in 3 hours
- mechanical work is minimized

This is my specific view of what good internal audit work should look like.

---

## AuditFlow Approach

AuditFlow keeps the work in plain files:

- YAML for structured audit data and decisions;
- QMD / Markdown for audit narratives, workpapers, reports, and archive story;
- raw evidence kept unchanged;
- generated outputs kept separate from source evidence.

With Git, these source files also gain a reviewable history without manual copies such as `final_v2_revised`.

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
auditflow timeline refresh
auditflow validate
```

In practice, the auditor edits files between commands:

1. Complete `initial_data.yml` and `00_admin/*.yml`.
2. Run `auditflow create planning`.
3. Complete `01_planning/planning_document.qmd` and `01_planning/planning_decision.yml`.
4. Run `auditflow create audit-program`.
5. Complete `test_hypothesis` and `test_script` in `03_audit_program/audit_program.yml`.
   Optionally run `auditflow ai review-audit-program --dry-run`, then the same command without `--dry-run`.
6. Run `auditflow create workpapers`.
7. Complete workpapers in `05_workpapers/`.
8. Run `auditflow create observations`.
9. Complete observation YAML files in `06_observations/`.
   Optional AI commands are `auditflow ai draft-observation <workpaper_ref>` and `auditflow ai review-observation <observation_id>` (for instance `auditflow ai draft-observation WP-C-001` and `auditflow ai review-observation OBS-001`).
10. Run `auditflow create report`.
11. Run feedback and archive steps when the audit is complete.
12. Run `auditflow timeline refresh` if timeline facts were edited or events were added manually.
13. Run `auditflow validate` before rendering or sharing final materials.

QMD documents are previewed and rendered using the standard Quarto extension in VS Code or the `quarto preview` and `quarto render` commands. AuditFlow does not require a separate rendering workflow.

## Optional Git Collaboration

An AuditFlow project can be stored in a private GitLab, Azure DevOps, GitHub Enterprise, or equivalent repository. Protected branches and pull/merge requests let the audit manager comment on changes, request corrections, approve them, and safely revert earlier decisions.

Raw evidence and regulations stay outside Git. Their fingerprints are stored in a tracked manifest:

```bash
auditflow evidence refresh
auditflow evidence status
```

See `docs/git_collaboration.md` for the short setup and review workflow.

## Project Structure

```text
audit_project/
  initial_data.yml
  _quarto.yml

  00_admin/
    ai.yml
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
    evidence_manifest.yml       # optional; created by evidence refresh
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

  ai_outputs/                 # local AI review history; ignored by Git

  styles/
    auditflow.css
    brand.css
    report.css

  .vscode/
    settings.json
    tasks.json
    extensions.json
```

## Timeline Facts

`00_admin/timeline.yml` contains planned dates, fact dates, and recorded workflow events.

Planned dates are entered manually. Fact dates are updated by AuditFlow commands when workflow artifacts are created. For example, `auditflow create audit-program` records an `audit_program_created` event and can mark planning as completed.

Use:

```bash
auditflow timeline refresh
```

to rebuild empty fact dates from recorded events.

## Optional AI Assistance

AI is disabled by default. The implemented provider adapter is Ollama; Qwen3 8B is the default demonstration model, not a framework requirement.

```bash
ollama pull qwen3:8b
auditflow ai status
auditflow ai review-audit-program --dry-run
auditflow ai draft-observation <workpaper_ref> --dry-run
auditflow ai review-observation <observation_id> --dry-run
```

Set `enabled: true` in `00_admin/ai.yml` before a real model call. Always inspect the dry-run source manifest first.

AuditFlow uses a company-policy layer to control approved profiles, destinations, models, classifications, external-provider use, confirmation, and output retention. Set the policy path with `AUDITFLOW_AI_POLICY`; audit projects cannot override provider URLs or security rules.

AI tasks use selective context and do not overwrite audit artifacts. Raw evidence is excluded by default. Audit-program review also excludes every `test_script`: it checks only risk formulation, coverage, risk-control-test traceability, and internal consistency. Model comments are advisory; the auditor remains responsible for scope, test design, facts, and conclusions.

See `docs/llm_integration.md` for setup, policy format, context boundaries, and output structure.

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

## VSCode Support

`auditflow init` creates `.vscode/settings.json`, `.vscode/tasks.json`, and `.vscode/extensions.json`.

These files provide YAML/Quarto editor defaults, recommended extensions, and ready-to-run AuditFlow tasks such as `AuditFlow: status` and `AuditFlow: validate`. Use the standard Quarto extension in VS Code to preview and render QMD documents.

## Current Limitations

- `auditflow validate` currently performs basic project, schema, and link checks. Deeper methodology validation is still evolving.
- Long-term management action tracking is outside the current project scope.
- AI drafting and review are optional and currently use the Ollama runtime adapter. OpenAI-compatible and Hugging Face adapters are not implemented yet.
- Sensitive-data scanning is pattern-based and cannot prove that context is safe to disclose.
- Notification letter generation is not part of the current CLI workflow (however, you can see the notification template in 'auditflow/templates/').

## Documentation

- `docs/user_journey.md` — step-by-step user journey.
- `docs/project_structure.md` — project folders and source-of-truth files.
- `docs/workflow.md` — decision-oriented audit workflow.
- `docs/methodology.md` — methodology principles.
- `docs/customization.md` — customization approach.
- `docs/git_collaboration.md` — version history and manager review with Git.
- `examples/procurement_audit/` — synthetic example audit showing the generated structure, traceability chain, and reporting artifacts.

