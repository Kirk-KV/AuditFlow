# Procurement candidate follow-up summary

This synthetic example records the outcome of the audit team's review of data-analysis
candidates. Candidate-level decisions are stored in `candidate_review_dispositions.csv`.

- T-001: 31 release-before-approval candidates remained unresolved; 7 were confirmed as
  technical re-releases and treated as false positives.
- T-003: 3 duplicate invoice or repeated-payment candidates remained unresolved; 17 were
  resolved using the synthetic supporting explanations.
- T-004: 6 split-purchase groups remained unresolved; 6 were supported as separate business
  needs.

In a real audit, the `evidence_ref` column should point to the actual correspondence or source
document supporting each disposition. The summary does not replace those source documents.
