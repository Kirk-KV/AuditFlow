# Audit Methodology

This document describes the general methodology behind the framework. It is intentionally generic.
Adapt it to your own circumstances and context. 

---

## 1. Principles

### 1.1 Risk-Based

The audit engagement itself and its scope are based on risks. Approach to risk analysis is out of scope of this document.

For documentation quality, a risk should normally describe cause, event, and consequence; event plus consequence is acceptable. AuditFlow AI checks apply this as a non-blocking reminder.

Just remember: time is valuable, don't spend it on something useless.  
The audit team should focus on areas where:

* risks are material;
* we test key controls that cover/ mitigate those material risks;
* control failure may lead to meaningful impact;
* audit work can provide useful assurance or insight.

---

### 1.2 Data-Driven When Possible

Whenever reliable data is available, audit work should use data analysis (and full population instead of sampling).

---

### 1.3 Traceability & Reproducibility

AuditFlow uses the following traceability chain:

```text
Risk → Control → Test → Evidence → Result → Observation → Action → Report
```

Each conclusion in the report should be traceable to the underlying audit work.

Audit work should be reproducible where practical. Another qualified auditor should be able to understand:

* what data was received;
* what transformations were performed;
* what tests were executed;
* what exceptions were identified;
* how results were linked to observations and conclusions.

Reproducibility does not equal unnecessary documentation, it means that audit conclusions are supported by a clear and reviewable trail.

---

### 1.5 Objective and Constructive Communication

Audit communication should be objective, factual, neutral, and constructive. We are neither punishing process owners nor looking for guilty ones, we help the company understand risks, improve controls, and make better decisions.

Facts should be validated with management before final conclusions are issued. Management does not need to agree with the audit conclusion, but factual accuracy should be confirmed or clearly disputed.

---

## 2. Audit Lifecycle

See in workflow.md
There are several Gates where you need to think through and could cancel/ defer the audit or change its scope.

---

### Annual Planning

Annual planning defines the initial audit candidate.
I will not provide the approach to annual planning in this document. At the moment we just assume that there were some actions, risk assessment, BoD approval, and there are audits to be implemented for the upcoming period of time (Y, Q - does not matter).

Annual planning does not freeze the final audit scope. The scope, objectives, risks, timing, and resources are to be refined during planning.

---

### Planning

**First stage**: pre-planning - performed before the audit team fully engages process owners. Its objectives:
- get acquainted with available data, data structure, process descriptions, etc. So during the interview, auditor would not start from scratch;
- to understand whether the audit should proceed and where audit work is likely to create value.

The audit team should use this stage to form better questions for management and avoid spending interviews on basic information that can be obtained independently. Communication with management at this stage is as brief as possible (no communication preferred).

**After notification**: the audit team meets with responsible managers and process owners. These meetings focus on targeted questions, clarification of risk areas, process nuances, and control understanding.

Planning should cover:

* process objectives;
* process flow;
* responsible roles;
* key systems and data sources;
* known issues and incidents;
* current controls;
* control owners;
* performance indicators;
* second line input where relevant;
* data quality limitations;
* management's own view of risks and controls.

The output of this stage is a **Planning document** - it helps the audit team avoid missing important information before finalizing the audit program.

It should normally describe:

* process background;
* audit objectives;
* preliminary and revised scope;
* out-of-scope areas;
* stakeholders;
* process owners;
* key systems;
* available data;
* data limitations;
* process statistics;
* known issues;
* current controls;
* initial design assessment;
* significant risks;
* rationale for including or excluding risks from the audit program;
* proposed audit approach.

The planning document should not be a bureaucratic formality. It should explain why the audit team believes the selected scope and audit program are appropriate.

During this stage audit team does not perform controls testing, but could use test of one, walkthrough - to confirm a control design described by management or in the company's regulations. 
See below for the distinction between design and operating effectiveness. At the planning stage it is just the design that auditor looks at.

---

### Notification

If the audit proceeds, the audit team sends a notification letter to the audit sponsor or equivalent senior stakeholder.

The notification should give management enough context to prepare. The notification letter draft is provided in the project. 

---

### Audit Program

The audit program translates risk assessment into specific audit procedures.

The audit program should focus on the most significant risks and the key controls or process areas that address those risks.

See an audit program template in this project. In general, the audit program should not attempt to test everything in the process - just what matters most for the audit objectives.

---

### Sponsor Alignment

**Sponsor** is a VP/ EVP or member of some Board - he usually 'owns' several blocks of business processes. 
**Auditee** is a particular process owner.

Before fieldwork starts, the audit team should discuss the proposed audit scope/program with the audit sponsor or equivalent senior stakeholder. 

The objective is to validate whether the audit focus is reasonable.

The sponsor may challenge the proposed scope. The audit team should evaluate the sponsor's arguments and update the audit program when appropriate.

Sponsor input should be considered, but audit judgment should remain independent.

---

### Fieldwork

Fieldwork is the execution of the approved audit program and may include:

* control design assessment;
* operating effectiveness testing;
* transaction testing;
* data analysis;
* interviews;
* walkthroughs;
* document review;
* exception investigation;
* validation of process understanding.

For each audit procedure, the workpaper should document:

* objective of the procedure;
* risk or control tested;
* evidence used;
* steps performed;
* population and sampling approach where relevant;
* exceptions identified;
* conclusion;
* reviewer comments where relevant.

**Control Design and Operating Effectiveness**

Audit work should distinguish between control design and operating effectiveness.

Design effectiveness asks:

> If the control operates as described, would it adequately reduce the risk?

Operating effectiveness asks:

> Did the control actually operate as designed during the audit period?

If the control design is clearly ineffective, the audit team should consider whether operating effectiveness testing is still useful. The decision should be documented.

---

### Observations

Audit observations should be structured clearly using the following logic:

```text
Criterion → Condition → Cause → Risk / Effect → Action
```

This means:

* **Criterion:** what should happen (what the company/ standards, common sense wanted it to be);
* **Condition:** what actually happened (how it is really in practice in the company);
* **Cause:** why the issue occurred;
* **Risk / Effect:** what may happen if the issue continues;
* **Action:** what should be done to reduce the risk.

A weak observation often lacks one of these elements:

* a condition without a criterion is just a fact;
* a condition without a cause lead to weak remediation;
* a risk without evidence may sound speculative;
* an action that does not address the cause may not reduce the risk.

It is quite important to find an actual cause. It may look easy, but in practice it is often the most challenging part. Good actions address the cause (it's like with a decease - better to treat 'core' illness, not the symptoms).

An audior validate material facts with management at every stage of the process. The purpose of fact validation is to confirm factual accuracy, not to ask management to approve the audit conclusion.
The audit team should distinguish between factual corrections and disagreements with audit judgment.

A good practice is to ask management, immediately after validating the observation, "What do you think should be done to improve the situation?".
This approach encourages management to take ownership of the corrective actions, rather than perceiving them as recommendations imposed by the auditor. You can then discuss and refine the wording together, resulting in a preliminary action plan that later be reviewed and formally approved by the Sponsor.
Each agreed action should normally include:

* linked observation;
* action description;
* responsible owner;
* due date;
* risk acceptance decision where relevant.

If management accepts the risk and does not plan corrective action, the audit team should assess whether this is within the company's risk appetite and escalation rules.

---

### Draft Report

The draft report should communicate audit results clearly, objectively, and constructively.

A draft report usually includes:

* audit background;
* objectives;
* scope and limitations;
* overall conclusion;
* key statistics;
* observations;
* risk ratings where used;
* management responses if necessary;
* proposed actions;
* appendices where necessary.

The report should avoid:

* emotional language;
* unsupported claims;
* excessive jargon;
* unnecessary details;
* misleading extrapolation;
* ambiguous wording.

The report should contain enough detail to support the conclusion, but not so much detail that the main message becomes unclear.

---

### Sponsor Discussion

Before final report issuance, the audit team should discuss the draft report, key conclusions, and management action plan with the audit sponsor or equivalent senior stakeholder.

The purpose is to ensure that:

* the sponsor understands the main risks;
* material disagreements are addressed;
* proposed actions are realistic;
* deadlines and owners are clear;
* escalation is performed where necessary.

---

### Final Report

The final report should be distributed to the recipients, following the company's confidentiality, governance, and escalation requirements.

The final report should be consistent with:

* validated facts;
* final observations;
* agreed management actions;
* sponsor discussion outcomes;
* evidence retained in the audit file.

---

### Feedback

After report issuance, the audit team request feedback from the key auditees.
Feedback should be used to improve future audits, not to compromise audit independence.

---

### Archiving

After the final report is issued, the audit file should be archived.

The archive should include, where relevant:

* planning document;
* final audit program;
* workpapers;
* evidence register;
* data analysis scripts;
* generated outputs;
* observations;
* fact validation log;
* management action plan;
* final report;
* validation report;
* archive index.

The archive should allow a qualified reviewer to understand the audit work performed and the basis for the final report.

---

## 3. Action Tracking

Audit work does not end when the final report is issued. Agreed management actions should be tracked until:

* action is completed and risk is mitigated (merely complete an action is insufficient);
* risk is formally accepted;
* action is no longer relevant due to process change;
* another documented closure rationale applies.

The action tracking process should follow the company's governance and escalation rules.

---

## 4. Use of LLMs

LLMs may support audit quality checks, but they should not replace professional judgment.

Possible uses include:

* checking whether observations have a complete logic chain;
* challenging whether audit risks appear complete;
* checking whether the audit program is aligned with risks;
* reviewing report wording for clarity and neutrality;
* identifying inconsistencies between risks, tests, observations, and actions.

The implemented commands are `auditflow ai draft-observation`, `auditflow ai review-observation`, and `auditflow ai review-audit-program`. Audit-program review does not receive `test_script` and does not assess whether a script is executable; that judgment remains with the auditor.

LLM output should be treated as a suggestion.

The audit team remains responsible for all decisions and conclusions.

Confidential evidence, personal data, credentials, and internal documents should not be sent to external LLMs unless explicitly permitted by the company.

---
