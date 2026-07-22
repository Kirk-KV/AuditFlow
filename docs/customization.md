# Customization

AuditFlow is intentionally opinionated. It provides a recommended way to structure audit work, but it is not intended to force everyone into the same process.

Rename folders and files to match your internal terminology and/or convenience. You may customize almost everything, just mind the connections between directories/ files and steps.
This is my vision and things that I worked through. If you have a vision how to simplify all of this - please, let me know.

---

## Several notes

Some parts of AuditFlow are more important than they may look. You can change them, but doing so may reduce the value of the framework.

* **Raw Data Principle**: raw data should remain unchanged. This principle should usually be preserved.
* **Risk-to-Report Traceability**: AuditFlow is built around this chain:

```text
Risk → Control → Test → Evidence → Result → Observation → Action → Report
```

You may simplify the structure, but the reasoning chain should remain visible.

Controls are important when they exist, but they are not mandatory as a separate entity. If no formal control exists for a risk, the audit program should still include a row for that risk and make the absence of control visible.


* **Minimal Manual Metadata**: manual metadata should be used only when it adds value. Do not add fields just because they make the structure look complete.
* **Evidence-First Design**: if something is already documented in evidence, try to use it "as is" without retyping it into another file.


**If you use an LLM**, define company rules in the policy file referenced by `AUDITFLOW_AI_POLICY`:
* whether LLM use is allowed;
* which profiles, destinations, models, and project classifications are allowed;
* whether external providers are allowed and require confirmation;
* whether sensitive-data findings warn or block;
* whether prompts and responses must be saved;
* where AI sidecar output is retained.

Keep `00_admin/ai.yml` limited to project choices. It must not contain endpoint URLs, credentials, or weaker security rules. See `llm_integration.md` for the implemented policy schema and context boundaries.


**Core validator rules**:

* required project structure and YAML schemas are valid;
* test, workpaper, and observation links are internally consistent;
* declared analysis, output, and evidence files exist;
* IDs that must be unique are not duplicated;
* strict mode identifies incomplete finalization fields and fails on warnings.

These are structural checks, not assurance that procedures, evidence, or conclusions are professionally sufficient. Add company-specific rules only where they support a real process.

---

## Recommended Customization Approach

1. Start with the default template.
2. Run one synthetic or pilot audit.
3. Identify what feels excessive or unclear.
4. Simplify fields and files.
5. Add company-specific templates.
6. Add validator rules only after the process is stable.
7. Automate repeated tasks.

Avoid designing a perfect methodology before testing the workflow.

---

## Styling Customization

`auditflow init` creates project-level style files:

```text
styles/auditflow.css
styles/brand.css
styles/report.css
```

Default CSS files live in:

```text
auditflow/templates/styles/
```

Use `brand.css` for general project/company branding and `report.css` for report-specific layout.

You can pass CSS files explicitly:

```bash
auditflow init "C:/Audits/2026-001_procurement" \
  --brand-css "C:/AuditFlowBrand/brand.css" \
  --report-css "C:/AuditFlowBrand/report.css"
```

Or set environment variables once:

```text
AUDITFLOW_BRAND_CSS
AUDITFLOW_REPORT_CSS
```

Do not edit bundled package templates for one audit project. Edit the project-level files in `styles/`.

---

## Some More Notes

In regulated environments, companies may need more formal documentation (formal approval records, independence confirmations, evidence retention rules, etc.): it is up to you to create.
You also could adapt this project for advisory work (for instance, you may reduce or remove control testing, operating effectiveness procedures, formal observations, etc.). However, advisory work should still preserve reasoning.
For investigations use it with caution (stricter confidentiality, restricted evidence access, etc. - this has not been worked through at the moment) 
Action tracking is currently not the part of this project. AuditFlow captures management actions at the point of report issuance, it does not require every audit project to maintain long-term action status manually.
Long-term action tracking is a separate process, maybe later I will do a separate action tracking.

---

## Signs of Over-Customization

* auditors spend more time updating metadata than doing audit work;
* files exist only because the template requires them;
* the structure hides reasoning instead of clarifying it;
* the same information is manually duplicated in several places;
* statuses are maintained manually but do not affect workflow;
* reports cannot be traced back to audit work;
* scripts produce outputs no one can understand;
* LLMs are used as a substitute for review.

AuditFlow should reduce friction. If customization increases bureaucracy without improving audit quality, simplify it.
