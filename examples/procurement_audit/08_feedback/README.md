# Feedback workflow

Generated: 2026-07-05

Audit: Procurement Process Audit

Folders:
- `request/` — plain-text email bodies to send to recipients. The email uses a simple 1-to-5 score instruction and no question sections.
- `response/` — YAML templates to be completed by the auditor after replies are received. A template is treated as received if scores/comments/open answers are entered, even if `response.received` is still false.
- `response/original/` — original replies from management, such as .eml, .msg, .pdf, or screenshots.

Workflow:
1. Open the relevant `*_request.txt`.
2. Copy the text into an email and send it to the recipient.
3. Save the recipient's original reply in `response/original/`.
4. Complete the corresponding `*_response.yml`. You may either set `response.received: true` or just enter scores/comments; the summary will infer that a response was received.
5. Run `python scripts/feedback_workflow.py --summary`.
6. Review `08_feedback/feedback_summary.qmd`.

Important:
- Request files are safe to regenerate with `--overwrite`.
- Response templates are not reset unless you explicitly use `--reset-response-templates`.
