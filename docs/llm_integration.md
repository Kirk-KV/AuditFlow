**NOTE: this is a general understanding. Not been tested yet.**

# Using LLMs in AuditFlow

AuditFlow may use LLMs to support audit quality.

Core rule:

> LLMs review, humans decide.

LLMs can help challenge reasoning, improve clarity, identify inconsistencies, and check whether audit documentation is complete enough to support conclusions.

Not replace professional judgment. 

Not decide audit conclusions.

Not approve audit observations.

Not be treated as evidence.

---

## Purpose of LLM Support

LLM support in AuditFlow is designed for review and challenge.

The goal is to help the audit team ask better questions and to maintain certain level of quality.

Useful LLM-assisted checks may include:

- checking whether an observation has a complete logic chain;
- identifying missing parts in audit documentation;
- challenging whether an audit program covers key risks;
- reviewing whether report wording is clear and neutral;
- identifying inconsistencies between risks, tests, observations, and actions;
- suggesting additional questions for planning interviews;
- checking whether conclusions appear unsupported by the provided documentation.

The LLM should be treated as a reviewer, not as an auditor.

LLMs can be useful for tasks that involve language, structure, consistency, and challenge.

> For instance, LLMs can: 
* check whether an observation contains:

```text
Criterion → Condition → Cause → Risk / Effect → Action
```

* review whether an audit program appears aligned with documented risks

* help improve report language
* compare structured audit artifacts and identify inconsistencies


By default, AuditFlow should not send confidential information to any external LLM. It is up to you to decide. 


## Recommended LLM Modes

AuditFlow should support several LLM modes.

**Mode 1: Disabled**

LLM functionality is turned off. Default mode.

llm:
  enabled: false

**Mode 2: Manual Prompt Export**

AuditFlow generates prompt files, but does not send anything automatically. Auditor review the prompt, remove sensitive information, and decide whether to use it.

llm:
  enabled: true
  mode: "manual_export"
  output_folder: "llm_reviews/prompts/"

This is the safest starting mode.

**Mode 3: Internal LLM**

AuditFlow sends review requests to an approved internal corporate LLM.

llm:
  enabled: true
  mode: "internal"
  provider: "openai_compatible"
  base_url_env: "AUDITFLOW_LLM_BASE_URL"
  api_key_env: "AUDITFLOW_LLM_API_KEY"
  model: "internal-audit-reviewer"

Credentials should be stored in environment variables, not in the repository.

**Mode 4: External LLM**

External LLM use should be explicitly approved by someone in authority who understands risks.

llm:
  enabled: true
  mode: "external"
  provider: "openai_compatible"
  base_url_env: "AUDITFLOW_LLM_BASE_URL"
  api_key_env: "AUDITFLOW_LLM_API_KEY"
  model: "approved-model-name"
  send_raw_evidence: false

Even in this mode, raw evidence should not be sent by default.

## Configuration Principles

LLM configuration should be explicit. Recommended configuration file:

llm.yml

Example:

llm:
  enabled: true
  mode: "manual_export"

  provider:
    type: "openai_compatible"
    base_url_env: "AUDITFLOW_LLM_BASE_URL"
    api_key_env: "AUDITFLOW_LLM_API_KEY"
    model: "internal-audit-reviewer"

  data_rules:
    send_raw_evidence: false
    send_personal_data: false
    send_confidential_data: false
    redact_before_sending: true

  outputs:
    save_prompts: true
    save_responses: true
    output_folder: "llm_reviews/"

Do not store API keys in llm.yml.

Use:

.env locally, and exclude it from Git.

Provide only:

.env.example in the repository.

You may save LLM Review Outputs any folder you like. For instance, llm_reviews/

Example:

llm_reviews/
  observation_O001_review.md
  audit_program_review.md
  report_clarity_review.md
  missing_risks_review.md

## Example Checks
**Observation Chain Check**

Purpose:
Check whether an observation contains a clear and logical chain.

Input:

observation text;
linked risk;
linked test;
relevant evidence summary, if safe to provide.

Prompt:

You are reviewing an internal audit observation.

Check whether the observation contains a clear logical chain:

1. Criterion — what should happen.
2. Condition — what actually happened.
3. Cause — why the issue occurred.
4. Risk / Effect — what may happen if the issue continues.
5. Action — what should be done to reduce the risk.

Do not invent facts.

Identify missing or weak elements. Suggest improvements. Return only review comments.

**Audit Program Review**

Purpose:

Check whether the audit program is aligned with documented risks.

Input:

audit objectives;
scope;
risk assessment;
control inventory;
audit program.

Prompt:

You are reviewing an internal audit program.

Check whether the audit program is aligned with the documented audit risks and objectives.

Review the following:

1. Are high risks covered by audit procedures?
2. Are there audit procedures not linked to risks?
3. Are risks included in scope but not addressed by tests?
4. Are any procedures too vague to be executed?
5. Does the audit program appear too broad or too narrow?
6. Are there obvious risk areas that may require consideration?

Do not invent facts. Do not decide the audit scope. Provide review comments and questions for the audit team.

**Scope Challenge**

Purpose:

Challenge whether the proposed audit scope is reasonable.

Input:

audit objectives;
in-scope areas;
out-of-scope areas;
key risks;
planning memo.

Prompt:

You are challenging the proposed scope of an internal audit.

Review whether the scope appears reasonable based on the objectives and risks.

Consider:

1. Is the scope clearly defined?
2. Are out-of-scope areas explained?
3. Are there inconsistencies between objectives, risks, and scope?
4. Does the scope appear too broad for effective audit work?
5. Does the scope appear too narrow to address the stated risks?
6. Are there areas where rationale should be documented more clearly?

Do not invent facts. Return questions and challenge points for the audit team.

**Report Clarity Review**

Purpose:

Check whether report wording is clear, neutral, and supported.

Input:

draft report;
observations;
management actions.

Prompt:

You are reviewing an internal audit draft report for clarity and neutrality.

Check whether the report is:

1. Clear.
2. Neutral.
3. Constructive.
4. Free of emotional language.
5. Free of unsupported claims.
6. Consistent with observations and management actions.
7. Understandable to non-auditors.

Do not rewrite the whole report unless asked. Identify specific issues and suggest improvements. 

**Missing Risks Review**

Purpose:

Help the audit team identify risks that may have been missed during planning.

Input:

process description;
audit objectives;
current risk list;
control inventory;
data assessment.

Prompt:

You are helping an internal audit team challenge its risk assessment.

Based on the process description, audit objectives, current risks, controls, and data limitations, identify risk areas that may require consideration.

Do not state that risks exist unless supported by the provided information.

Classify your output as:

1. Potential missing risk.
2. Why it may be relevant.
3. What additional question the auditor should ask.
4. Whether it appears in scope or only requires consideration.

Do not invent facts. Do not make audit conclusions.


## Keep in mind 

Redacting:

names;
emails;
employee IDs;
supplier names;
customer names;
account numbers;
contract numbers;
bank details;
transaction IDs;
confidential amounts, where not necessary.

Sometimes redaction makes the review useless. This is life.

When possible, provide evidence summaries instead of raw evidence.

## Example Workflow

A simple LLM-assisted review workflow may look like this:

1. Auditor prepares observation.
2. Auditor links observation to risk, test, and evidence.
3. AuditFlow generates LLM review prompt.
4. Auditor reviews prompt and removes sensitive information.
5. LLM reviews observation logic.
6. Auditor reviews LLM output.
7. Auditor accepts or rejects suggestions.
8. Final observation remains auditor-owned.

In manual export mode:

auditflow llm-export observation O-001

Potential output:

llm_reviews/prompts/O-001_observation_review_prompt.md

In internal LLM mode:

auditflow llm-review observation O-001

Potential output:

llm_reviews/O-001_observation_review.md

## Risks of LLM Use

confidential data leakage;
hallucinated facts;
overreliance on AI output;
unsupported conclusions;
inconsistent responses;
false sense of review quality;
unclear accountability;
violation of company policy.

Before using an LLM in audit work, ask: would I be comfortable explaining to the audit sponsor, management, legal, or the audit committee what information was sent and why?
If the answer is no, do not send it.