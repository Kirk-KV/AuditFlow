# User Journey

AuditFlow is designed as a staged audit workspace. The project should grow as the audit progresses.

The basic idea is to create only what is needed now and to generate the next artifact from what has already been documented.

---

## 1. Install and Open the Tool

A user downloads or installs AuditFlow.

```bash
git clone https://github.com/Kirk-KV/auditflow.git
cd auditflow
pip install -e .
auditflow --help
```

---

## 2. Create an Audit Project

```bash
auditflow init "C:/Audits/2026-001_procurement"
```

Optional style overrides:

```bash
auditflow init "C:/Audits/2026-001_procurement" \
  --brand-css "C:/AuditFlowBrand/brand.css" \
  --report-css "C:/AuditFlowBrand/report.css"
```

`init` creates:

```text
initial_data.yml
_quarto.yml

00_admin/
04_evidence/
styles/
.vscode/
```

Open the audit project folder in VSCode:

```bash
code "C:/Audits/2026-001_procurement"
```

From this point, run commands inside the audit project folder or pass `--project`.

---

## 3. Complete Initial Data

Complete:

```text
initial_data.yml
00_admin/stakeholders.yml
00_admin/team.yml
00_admin/timeline.yml
00_admin/decisions.yml
```

`initial_data.yml` is the starting point. It should contain what is known before planning: audit title, company, type, source, preliminary objectives, preliminary scope, initial risks, and notes.

It should not be repeatedly rewritten to reflect every later decision. Later decisions belong in `planning_decision.yml` or `00_admin/decisions.yml`.

Check status:

```bash
auditflow status
```

---

## 4. Create Notification Letter

I will automate it later. Use the template from auditflow/templates/

Note that notification letter includes scope and risks from the annual plan (preliminary ones). Final risks would be included in the audit program after the meeting with the Sponsor. 

---

## 4. Create Planning Files

```bash
auditflow create planning
```

Creates:

```text
01_planning/
  planning_document.qmd
  planning_decision.yml
```

`planning_document.qmd` is the working planning analysis. It may include process understanding, EDA, management input, second line input, IT context, fraud red flags, data limitations, and planning conclusions.

For HTML:
- use Plotly for charts;
- avoid matplotlib unless static image export is explicitly required;
- do not use plt.show() in QMD templates.

`planning_decision.yml` is the structured final planning decision. It drives the audit program.

The auditor completes `planning_decision.yml` manually after planning analysis.

Current core structure:

```yaml
overall_conclusion: ""

scope:
  in_scope: []
  out_of_scope: []
  rationale: []

included_risks:
  - id: "R-001"
    title: ""
    rationale: ""

excluded_risks:
  - id: "R-002"
    title: ""
    rationale: ""

controls:
  - id: "C-001"
    risk_id: "R-001"
    description: ""
    owner: ""
    design_assessment: ""

recommended_tests:
  - id: "RT-001"
    risk_id: "R-001"
    control_id: "C-001"
    test_objective: ""
```

If no formal control exists for an included risk, either:

- leave the control absent; AuditFlow will create a program row and warning; or
- add a control row with `id: "NA"` and describe the situation.

Example:

```yaml
controls:
  - id: "NA"
    risk_id: "R-002"
    description: "No formal monitoring control exists."
    owner: "GR"
    design_assessment: "Control gap"
```

---

## 5. Create Audit Program

```bash
auditflow create audit-program
```

Creates or updates:

```text
03_audit_program/audit_program.yml
```

The audit program is generated from `01_planning/planning_decision.yml`.

Rows are created for every included risk. If an included risk has no valid control ID, AuditFlow still creates a program row and adds a warning:

```yaml
planning_warnings:
  included_risks_without_valid_controls:
    - risk_id: R-002
      risk_title: ""
      message: No valid control id is identified for this included risk in planning_decision.yml.
```

The auditor completes manual fields:

```yaml
test_hypothesis: ""
test_script: []
```

When regenerated without `--overwrite`, existing manual fields are preserved.

### Optional: Review the Audit Program with AI

Check exactly what would be sent before contacting a model:

```bash
auditflow ai review-audit-program --dry-run
```

If the preflight result and destination are acceptable, run:

```bash
auditflow ai review-audit-program
```

The review covers risk formulation, included-risk coverage, risk-control-test traceability, and internal consistency. It does not include or assess `test_script`. Comments are saved separately under `ai_outputs/audit_program_reviews/` and do not change `audit_program.yml`.

## 6. Create Workpapers

```bash
auditflow create workpapers
```

Creates:

```text
05_workpapers/
  WP-*.qmd
```

Each workpaper is generated from one row in `03_audit_program/audit_program.yml`.

The auditor completes:

- work performed;
- evidence used and evaluated;
- results;
- conclusion;
- observation proposal block, if an issue should become an observation.

Observation proposal block:

```yaml
proposed_observation:
  title: ""
```

If the title is empty, no observation is generated from that workpaper.

## 7. Create Observations

```bash
auditflow create observations
```

Creates:

```text
06_observations/
  OBS-001.yml
```

Observation files are created only from workpapers with a non-empty observation title.

The auditor then completes:

- severity;
- condition;
- criteria;
- cause;
- risk / effect;
- recommendation;
- management action plan.

### Optional: Draft or Review an Observation with AI

An AI draft can be requested from a completed workpaper before or after generating an observation:

```bash
auditflow ai draft-observation <workpaper_ref> --dry-run
auditflow ai draft-observation <workpaper_ref>
```

Review an existing observation with its linked workpaper and program context:

```bash
auditflow ai review-observation <observation_id> --dry-run
auditflow ai review-observation <observation_id>
```

Both commands check the linked risk formulation as a non-blocking reminder. AI results are sidecar files under `ai_outputs/`; no `OBS-*.yml` file is changed automatically.

## 8. Create Report

```bash
auditflow create report
```

Creates or updates:

```text
07_reporting/report.qmd
```

The report uses protected AUTO blocks. The script updates generated blocks while preserving manual sections.

Generated content includes:

- cover;
- audit facts;
- summary of observations;
- detailed observation cards;
- report recipients and audit team.

The report references:

```text
../styles/report.css
```

So `styles/report.css` is created during `auditflow init`, not during report generation.

Preview the report while editing it with the Quarto extension in VS Code, or run:

```bash
quarto preview 07_reporting/report.qmd
```

Use `quarto render 07_reporting/report.qmd` when a standalone rendered output is needed.

## 9. Feedback

Create feedback requests and response templates:

```bash
auditflow feedback request
```

Optional:

```bash
auditflow feedback request --include-sponsor --response-due-date 2026-04-15
```

Creates:

```text
08_feedback/
  request/
  response/
    original/
```

The request text is intended to be copied into email. The YAML response template is completed by the auditor after receiving replies.

Create feedback summary:

```bash
auditflow feedback summary
```

Creates:

```text
08_feedback/feedback_summary.qmd
```

Preview the feedback summary with the Quarto extension in VS Code, or run:

```bash
quarto preview 08_feedback/feedback_summary.qmd
```

Use `quarto render 08_feedback/feedback_summary.qmd` when a standalone rendered output is needed.

## 10. Archive Story

```bash
auditflow create archive
```

Creates:

```text
09_archive/audit_story.qmd
```

The archive story reconstructs the audit from existing artifacts:

- initial assumptions;
- planning decisions;
- scope and risk evolution;
- testing traceability;
- observations;
- evidence map;
- lessons learned.

Preview the archive story with the Quarto extension in VS Code, or run:

```bash
quarto preview 09_archive/audit_story.qmd
```

Use `quarto render 09_archive/audit_story.qmd` when a standalone rendered output is needed.

## 11. Full Current Command Sequence

```bash
auditflow init "C:/Audits/2026-001_procurement"
cd "C:/Audits/2026-001_procurement"

auditflow status

# Fill initial_data.yml and 00_admin/*.yml
auditflow create planning

# Complete planning_document.qmd and planning_decision.yml
auditflow create audit-program

# Complete test_hypothesis and test_script
# Optional: auditflow ai review-audit-program --dry-run
auditflow create workpapers

# Complete workpapers
auditflow create observations

# Complete observation YAML files
# Optional: auditflow ai review-observation <observation_id> --dry-run
auditflow create report

# Complete report manual sections
auditflow feedback request
auditflow feedback summary
auditflow create archive
```

QMD documents are previewed and rendered using the standard Quarto extension in VS Code or the `quarto preview` and `quarto render` commands. AuditFlow does not require a separate rendering workflow.

## 12. Current Non-Goals

The current CLI does not yet implement:

- notification letter generation;
- strict validation;
- automated management action export;
- OpenAI-compatible and Hugging Face provider adapters;
- long-term action tracking.

Those may be added later, but the current workflow should stay small until it is sufficiently tested several times on real audits.
