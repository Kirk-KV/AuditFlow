# Feedback workflow

Generated: $generated_date

Audit: $audit_name

Folders:

- `request/` - plain-text email bodies to send to recipients.
- `response/` - YAML templates completed by the auditor after replies are received.
- `response/original/` - original replies from management, such as `.eml`, `.msg`, `.pdf`, or screenshots.

Workflow:

1. Open the relevant `*_request.txt` and send it to the recipient.
2. Save the original reply in `response/original/`.
3. Complete the corresponding `*_response.yml`.
4. Run `auditflow feedback summary`.
5. Review `08_feedback/feedback_summary.qmd`.

Request files can be regenerated with `--overwrite`. Response templates are reset only
when `--reset-response-templates` is explicitly used.

