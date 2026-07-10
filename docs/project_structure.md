# Project Structure

AuditFlow treats each audit engagement as a structured project: a working environment where planning, data, tests, evidence, observations, actions, and report are connected.

The structure is opinionated but adaptable. One of the goals is to make audit work structured and traceable. The ultimate goal regarding data: it should flow naturally and be reusable. The auditor should not have to update the same information in multiple places.

Rename folders, add steps, or simplify the structure based on your methodology and your own sense of what is practical and clean. The structure should serve audit purpose and reasoning and not foster bureaucracy.
Audit should remain practical.

---

# Typical Project Structure

```text
audit_project/
  initial_data.yml              # info from the annual audit plan
  _quarto.yml

  00_admin/
    stakeholders.yml            # those who will receive the report
    team.yml                    # audit team
    timeline.yml                # audit deadlines (planned and actual)
    decisions.yml               # if you need to fix core decisions (highly advisable to do so)

  01_planning/
    planning_document.qmd       # exploration file
    planning_decision.yml       # final decisions after the planning phase (what to take, what not to take in the audit and why)
    *process_description.io     # (optional) process schema

  02_notification/
    notification_letter.md      # letter to the Sponsor. At the moment not created automatically

  03_audit_program/
    audit_program.yml           # what and why will be tested
    *sponsor_comments.yml       # (optional) if you need to fix the reason to change the scope from planning based on the Sponsor's comments

  04_evidence/
    01_regulations/
    02_raw_data/                
    03_correspondence/
    04_reference_materials/
    05_screenshots/
    99_generated/

  05_workpapers/
    WP-*.qmd    

  06_observations/
    OBS-*.yml                   # observations are created automatically based on workpapers

  07_reporting/
    report.qmd                  # here you write a report
    sponsor_discussion.md       # the result of the final discussion

  08_feedback/
    request/                    # request for feedback sent to auditees
    response/                   # received response (manually entered into created template)
      original/                 # folder to store original responses (emails, for instance)
    feedback_summary.qmd        # summary of received responses

  09_archive/
    audit_story.qmd             # automated audit story with manual 'lessons learned' block

  .vscode/
    settings.json
    tasks.json
    extensions.json

```

This structure is a starting point. A small audit may use fewer files, a complex one may require additional folders, more detailed workpapers, or separate sub-projects.

Optional files could be:
- control_inventory.yml, if the team maintains a formal control matrix;
- data_assessment.yml, if data limitations need structured tracking;
- fieldwork.qmd, for small audits with a single combined workpaper;
- action export, generated after report issuance.
etc. This supports the idea of customization of the audit project (these files are absent in the project at the moment).

The folders are created gradually. `auditflow init` creates the initial project structure and style files. Later `auditflow create ...` commands add stage-specific artifacts.

Source files are manually maintained or received as evidence. Generated files are produced from source files and should be reproducible.

| Area | Source Of Truth |
| --- | --- |
| Initial audit context | `initial_data.yml` |
| Stakeholders and audit team | `00_admin/*.yml` |
| Planning reasoning | `01_planning/planning_document.qmd` |
| Final planning decision | `01_planning/planning_decision.yml` |
| Audit program | `03_audit_program/audit_program.yml` |
| Work performed | `05_workpapers/*.qmd` |
| Observations | `06_observations/OBS-*.yml` |
| Report narrative | manual blocks in `07_reporting/report.qmd` |
| Feedback | `08_feedback/response/*.yml` |
| Archive story | `09_archive/audit_story.qmd` |

---

## `initial_data.yml`

The file includes high-level information about the audit engagement, taken from the annual audit plan (or other source). Typical content:

```yaml
audit:
  id: "2026-001"
  title: "Procurement Process Audit"
  type: "assurance"
  source: "annual_audit_plan"

scope:
  in_scope:
    - "Purchase requisition"
    - "Purchase order approval"
    - "Goods receipt"
    - "Invoice matching"
    - "Payment approval"
  out_of_scope:
    - "Strategic sourcing"
    - "Supplier performance management"

objectives:
  - id: OBJ-001
    statement: "Assess whether key procurement controls are designed and operating effectively."
  - id: OBJ-002
    statement: "Identify transactions with elevated fraud, compliance, or financial loss risk."

period:
  from: "2025-01-01"
  to: "2025-12-31"
```

The philosophy is to record stage outputs and decisions and then let the system reconstruct the audit story.
Each file should provide (meta)data that other files and templates can reference.
Also you may add there any relevant information known at the initial audit stage. From my experience, it is a valuable thing to use notes and sum up different comments/ thoughts in one place. This file could be such a place. These notes will then move to the planning_document.qmd in the separate section so you would not lose important ideas. This section arise in the planning_document.qmd only if there were notes in the initial_data.yml (you will not see the "Notes" block otherwise).

Do not use `initial_data.yml` as the live current state of the audit. Later decisions should be documented in `planning_decision.yml` or `00_admin/decisions.yml`.

---

## `00_admin/`

The folder contains administrative and governance information about the audit: stakeholders, team, timeline and decisions.

### `stakeholders.yml`

Contains the sponsor, auditees, report recipients, and other stakeholders.

Example:

```yaml
sponsor:
  name: "Christian Wolff"
  role: "Chief Financial Officer"

auditees:
  - name: "Chinese Dan"
    role: "Head of Procurement"
  - name: "Antony Soprano"
    role: "Head of Accounts Payable"

report_recipients:
  - "Christian Wolff"
  - "Chinese Dan"
  - "Antony Soprano"
```

`feedback request` uses `auditees` by default. If `auditees` is empty, it falls back to `report_recipients`. Use `--include-sponsor` to include the sponsor.

### `team.yml`

Contains the audit team and review responsibilities.

```yaml
engagement_lead:
  name: ""
  role: ""
  email: ""

members:
  - name: ""
    role: ""
    email: ""

reviewer:
  name: ""
  role: ""
  email: ""
```

### `timeline.yml`

Use this file for planned and actual dates if the team wants to compare planning assumptions with actual execution.

Planned dates are maintained manually in `timeline.plan`.

Actual dates are updated by AuditFlow commands through an event log in the same file. For example, when `auditflow create audit-program` succeeds, AuditFlow records an `audit_program_created` event and can treat this date as both the completion of planning and the initiation of the audit program stage.

Manual fact dates are preserved by default. The event log remains visible so a reviewer can understand why a fact date was recorded.

### `decisions.yml`

Use this file only for meaningful decisions that should remain visible later: scope change, timing change, cancelled work, major sponsor challenge, significant limitation, etc.

```yaml
decisions:
  - id: D-001
    date: "2026-02-10"
    stage: "pre_planning"
    decision: "scope change"
    rationale: "Initial risks are not supported by available data, process key risks are different."
    approved_by: "Audit Manager"
    link: "link_to_the_taken_decision_and_supported_materials"

```

---
## `01_planning/`

The planning phase consists of two linked stages, separated by 'notification letter'.
The first stage is 'pre-planning': includes early analysis of available data and processes (before detailed engagement with management).
You may create separate folder with files like:

```text
pre_planning/
  pre_planning_notes.md
  data_inventory.yml
```

The purpose of this stage is to understand the data, the process, identify which parts of the process are material, weakly controlled, or higher risk. 
I prefer to use one file (notebook) both for pre-planning and planning stages. During pre-planning you understand the data, its structure, reliability, etc. (first part of the notebook - EDA). During planning you use the same initial data + some additional data to check every aspect you think important and to see main risks. These are connected tasks, it is better to use one script/ document. 
Also with a lot of data you may prefer to use .ipynb instead of .qmd for EDA.

The `01_planning/` folder contains planning_document.qmd, planning_decision.yml and (optionally) *process_description.io.
The planning stage should explain why the audit team believes the selected scope and audit approach are appropriate.

### `planning_document.qmd`

This is the main planning document. It may include:

* process background;
* audit objectives;
* scope and out-of-scope areas;
* key stakeholders;
* process description;
* key systems;
* available data & data limitations;
* data analysis;
* known issues;
* current controls;
* significant risks;
* rationale for audit program focus/ risk assessment;
* go-forward recommendation.

You may add separate risk assessment and controls files if you like and if you have good formalized risk universe and control matrix. 
You may add 'data assessment' block in the file (data availability and limitations), for instance,

```yaml
data_sources:
  - id: DS-001
    name: "Purchase order extract"
    system: "ERP"
    owner: "Procurement Operations"
    period: "2025-01-01 to 2025-12-31"
    limitations:
      - "Approval timestamps are missing for legacy purchase orders."
```

### `planning_decision.yml`

This file records the final planning decisions with a structured final scope, risks and its rationale. Will be used later in audit program and when archiving - to get the full audit picture.  

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

If no formal control exists for a risk, either leave the control absent or use a control row with `id: "NA"` and describe the situation.

### `process_description.io`

**Optional**. Describe the process in plain language in planning_document.qmd, using BPMN in .io file.

---

## `02_notification/`

The folder for the notification letter to the Sponsor. The letter could include:

* audit topic;
* preliminary objectives/ scope/ key risks;
* audit team;
* expected timing;
* request to appoint responsible contacts;
* expected date when the audit team will return with the proposed audit program.

---

## `03_audit_program/`

Include audit_program.yml: file takes data from the planning_decision.yml and the auditor need to add test scripts (audit procedures).
Audit program should focus on the risks and controls that matter most (if the planning was good, fieldwork will be shorter).

Example:

```yaml
tests:
  - id: T-001
    risk_id: R-001
    control_id: C-001
    title: "Test purchase order approval before release"
    objective: "Verify that purchase orders were approved before release to suppliers."
    procedure:
      - "Obtain purchase order population."
      - "Identify approval timestamp and release timestamp."
      - "Check whether approval occurred before release."
      - "Investigate exceptions."
```

Sponsor comments and changes to the audit program should be documented.

Example:

```yaml
comments:
  - id: SC-001
    date: "2026-02-28"
    source: "Audit Sponsor"
    comment: "Include supplier bank account changes because of recent incidents."
    audit_response: "Added test T-006."
```

Rows are created for every included risk. If no valid control ID exists, AuditFlow still creates a program row and adds a warning.

Manual fields preserved on regeneration:

```yaml
test_hypothesis: ""
test_script: []
```


---

## `04_evidence`

Evidence folders:

| Folder | Purpose |
| --- | --- |
| `01_regulations/` | Policies, procedures, standards, process descriptions |
| `02_raw_data/` | Raw system extracts and other unmodified data |
| `03_correspondence/` | Emails, confirmations, meeting notes |
| `04_reference_materials/` | Org charts, presentations, reports, background materials |
| `05_screenshots/` | Screenshots used as evidence |
| `99_generated/` | Generated analysis outputs, charts, profiling files |

General approach:
regulations → "how the process should work";
raw_data → "what actually happened";
correspondence → "what people told us";
reference_materials → "additional business context";
screenshots → "visual evidence";
generated → "outputs created by the auditor/ scripts".

Note that there are "scripts" in "raw_data". Include there general scripts that you used to get the information.

---

## `05_workpapers/`

The folder contains workpapers and testing results. You may create evidence register if you like. One workpaper is generated per audit program row. 

Workpapers should document:

- work performed;
- evidence used and evaluated;
- results;
- conclusion;
- observation proposal, if needed.

**Optionally** you may use the evidence register, like: 

```yaml
evidence:
  - id: E-001
    title: "Purchase order population"
    source_file: "05_data/raw/purchase_orders.xlsx"
    received_from: "Procurement Operations"
    related_tests:
      - T-001
```

---

## `06_observations/`

Observation YAML files are generated if there is a title for observation in the end of workpaper.

AuditFlow uses the following observation logic:

```text
Criteria -> Condition -> Cause -> Risk / Effect -> Recommendation -> Management Action Plan
```

Fact validation should normally be evidenced by linked files, not duplicated in a separate manual log.
Add one as an optional file if necessary.
---

## `07_reporting/`

The folder contains report and sponsor discussion notes.


### `report.qmd`

Contains the audit report. The report is generated from structured project data where possible. 
`report.qmd` uses protected AUTO blocks. Generated sections can be refreshed while manual narrative sections are preserved.
Note that when created there is a "draft" sign, that you need to remove after report validation.
If you need to save versions of the report, you may do so by saving versions of report.qmd. It should be automated, but at the moment this is the decision. 

The report uses project-level CSS:

```text
../styles/report.css
```

### `sponsor_discussion.md`

Documents discussion with the sponsor before final report issuance. This may include:

* key messages discussed;
* sponsor comments;
* agreed changes;
* unresolved disagreements;
* escalation decisions.

---

## `08_feedback/`

The folder is for feedback materials:

* usefulness of the audit;
* clarity of communication;
* professionalism of the audit team;
* quality of recommendations;
* opportunities to improve the audit process.

Feedback should help improve future audits and should not compromise audit independence.

A good practice is to assess the audit team after each audit - to help them improve future work. However, not every person agrees for others to see his/her feedback, so it's up to you.

Request files are email bodies. Response files are YAML templates completed by the auditor after receiving replies.

---

## `09_archive/`

The folder contains the final audit story. This is needed due to project philosophy: the auditor enters information once, and AuditFlow reconstructs the full audit story from existing artifacts.
The archive should allow a qualified reviewer to understand:

* what was planned;
* what was tested;
* what evidence was used;
* what conclusions were reached;
* how report observations were supported.

---

## Styling Files

`auditflow init` creates:

```text
styles/auditflow.css
styles/brand.css
styles/report.css
```

`brand.css` and `report.css` can be customized per project or supplied through:

```text
AUDITFLOW_BRAND_CSS
AUDITFLOW_REPORT_CSS
```

## File Naming

```text
R-001   Risk
C-001   Control
T-001   Test
E-001   Evidence
WP-001  Workpaper
O-001   Observation
D-001   Decision
```

Use simple and obvious names whenever possible, like 

```text
01_load_raw.py
02_clean_data.py
03_run_tests.py
04_generate_charts.py
```

For the generated output:

```text
YYYY-MM-DD_output_name.ext
```

The exact naming convention may be customized, the important point is consistency.

---
