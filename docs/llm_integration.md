# Using LLMs in AuditFlow

> LLMs review and draft; auditors decide.

AuditFlow provides optional AI assistance for observation drafting, observation review, and audit-program review. AI is disabled in new projects by default. AI output is always stored as a separate review artifact and never overwrites an audit program, workpaper, or observation.

## Implemented Commands

```bash
auditflow ai status
auditflow ai draft-observation WP-C-001 --dry-run
auditflow ai draft-observation WP-C-001
auditflow ai review-observation OBS-001 --dry-run
auditflow ai review-observation OBS-001
auditflow ai review-audit-program --dry-run
auditflow ai review-audit-program
```

Use `--dry-run` first. It resolves the effective policy, assembles the exact source selection, scans it, and prints the source manifest without contacting the model or creating AI output.

`--confirm-send` can provide explicit confirmation non-interactively when a company policy requires confirmation for an external destination.

## Current Provider Support

The implemented runtime adapter is Ollama. The policy schema reserves `openai_compatible` and `huggingface` provider names for future adapters, but those adapters are not implemented yet.

Qwen3 8B is the default demonstration model, not a framework requirement. A company can approve another model through its policy. Hardware sizing and model selection belong to the deployment environment, not to an audit project.

## Local Ollama Setup on Windows

1. Install Ollama from `https://ollama.com/download/windows`.
2. Pull the demonstration model:

```powershell
ollama pull qwen3:8b
```

3. Confirm that Ollama is running. The Windows application normally starts the local service automatically. If needed, run:

```powershell
ollama serve
```

4. Enable AI in the audit project's `00_admin/ai.yml`:

```yaml
ai:
  enabled: true
  profile: local_ollama
  model: qwen3:8b
  project_classification: confidential
  output_language: auto
```

5. Check the effective configuration and model availability:

```powershell
auditflow ai status
```

The built-in local profile uses `http://127.0.0.1:11434`. Local-machine profiles may use only a loopback HTTP address.

## Company Policy and Project Settings

`00_admin/ai.yml` contains project choices only:

- whether AI is enabled;
- which company-approved profile and model to use;
- project classification;
- output language.

It cannot set a provider URL, API key, or relax security rules.

Company-wide settings belong in a separate policy file referenced by `AUDITFLOW_AI_POLICY`:

```powershell
[Environment]::SetEnvironmentVariable(
  "AUDITFLOW_AI_POLICY",
  "C:\AuditFlowPolicy\company-ai-policy.yml",
  "User"
)
```

Example policy structure:

```yaml
schema_version: 1
policy_id: company-ai-policy-v1
default_profile: local_ollama

profiles:
  local_ollama:
    provider: ollama
    base_url: http://127.0.0.1:11434
    default_model: qwen3:8b
    allowed_models: [qwen3:8b]
    data_boundary: local_machine
    allowed_classifications: [public, internal, confidential, restricted]
    options:
      temperature: 0
      context_length: 8192
      thinking: false

rules:
  allow_raw_evidence: false
  allow_external_providers: false
  require_preflight: true
  require_confirmation_for_external: true
  save_prompt: true
  save_response: true
  scan_sensitive_data: true
  sensitive_data_action: warn
  output_folder: ai_outputs
```

The policy controls destinations, model allowlists, permitted classifications, external-provider use, confirmation, sensitive-data handling, and retention of prompts/responses. API keys belong in the environment variable named by `api_key_env`; they must not be stored in YAML.

`require_preflight` cannot be disabled. Non-local endpoints must use HTTPS. An external profile is rejected unless the policy explicitly allows external providers.

## Data-Minimization Rules

AuditFlow builds task-specific context instead of sending the entire project.

For an observation draft, it selects:

- audit objectives and scope;
- the linked risk, control, test, and audit-program row;
- selected workpaper sections: work performed, evidence used, results, conclusion, and observation proposal.

For an observation review, it adds the selected `OBS-*.yml` file.

For an audit-program review, it selects:

- objectives, scope, and risk register;
- included/excluded risks, controls, and recommended tests;
- audit-program metadata and rows.

Raw evidence, workpapers, observations, and all `test_script` content are excluded from audit-program review. The model therefore does not assess script executability, technical feasibility, or procedural sufficiency; those decisions remain with the auditor.

The sensitive-data scan checks common email, phone, IBAN, credential-like, and prompt-injection patterns without echoing matched values. It cannot reliably find every personal name, company name, or confidential identifier. A successful preflight is a guardrail, not proof that disclosure is safe.

## Methodology Checks

Observation drafting and review include a non-blocking risk-formulation reminder. A useful risk normally identifies cause, event, and consequence; event plus consequence is acceptable. A topic, control name, vague concern, or consequence alone is reported as weak without blocking the command.

Audit-program review is limited to:

- formulation of each included risk;
- coverage of included risks by program rows;
- traceability of risk, control, and test links;
- internal consistency and questions for the auditor.

It does not approve scope, tests, observations, or conclusions.

## Outputs and Audit Trail

AI artifacts are stored under the policy-controlled output folder, `ai_outputs` by default:

```text
ai_outputs/
  observation_drafts/WP-C-001/<run-id>/
    manifest.yml
    prompt.md
    response.json
    draft.yml
  observation_reviews/OBS-001/<run-id>/
    manifest.yml
    prompt.md
    response.json
    review.yml
  audit_program_reviews/<run-id>/
    manifest.yml
    prompt.md
    response.json
    review.yml
```

The manifest records the policy ID/hash, destination, requested and returned model, project classification, preflight findings, selected source hashes, and provider usage metadata. Prompt and raw response retention follow company policy.

`ai_outputs/`, `.env*`, key files, and `secrets.yml` are ignored by the generated project `.gitignore`. If company policy changes `output_folder`, add that folder to the project's ignore rules. AI files can still contain confidential audit context and must follow the company's retention and access rules.

## Responsibility and Limitations

- Review every AI result against source records.
- Do not treat model output as evidence.
- Do not accept invented criteria, causes, quantities, or management commitments.
- Preserve uncertainty such as candidate, possible, unresolved, or preliminary.
- Investigate sensitive-data warnings before sending context outside an approved boundary.
- Keep final wording, ratings, scope, test design, and conclusions auditor-owned.

The local Qwen3 8B profile is suitable for demonstrating the integration but may still lose qualifiers, infer unsupported causes, or classify a risk inconsistently with the elements it extracted. AuditFlow adds deterministic warnings for some known drafting and risk-structure errors, but these checks do not make model output authoritative.
