from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

import yaml

from auditflow.ai.config import resolve_ai_config
from auditflow.ai.context import (
    build_audit_program_review_context,
    build_observation_context,
    extract_workpaper_sections,
)
from auditflow.ai.preflight import (
    run_audit_program_review_preflight,
    run_observation_preflight,
)


class AIContextTests(unittest.TestCase):
    def make_project(self, *, results: str, conclusion: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        for directory in ["00_admin", "01_planning", "03_audit_program", "05_workpapers"]:
            (root / directory).mkdir(parents=True, exist_ok=True)

        (root / "initial_data.yml").write_text(
            yaml.safe_dump(
                {
                    "audit": {"id": "A-1", "title": "Test audit"},
                    "objectives": [{"id": "OBJ-001", "statement": "Test objective"}],
                    "risks": [
                        {"id": "R-001", "title": "Included risk"},
                        {"id": "R-002", "title": "Uncovered risk"},
                        {"id": "R-999", "title": "Unrelated risk"},
                    ],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (root / "01_planning" / "planning_decision.yml").write_text(
            yaml.safe_dump(
                {
                    "included_risks": [
                        {"id": "R-001", "title": "Included risk"},
                        {"id": "R-002", "title": "Uncovered risk"},
                    ],
                    "controls": [{"id": "C-001", "risk_id": "R-001"}],
                    "recommended_tests": [{"id": "T-001", "risk_id": "R-001"}],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (root / "03_audit_program" / "audit_program.yml").write_text(
            yaml.safe_dump(
                {
                    "program_rows": [
                        {
                            "test_id": "T-001",
                            "risk_id": "R-001",
                            "risk_title": "Included risk",
                            "control_id": "C-001",
                            "test_hypothesis": "Exceptions may exist.",
                            "test_script": ["SECRET_SCRIPT_MARKER"],
                            "workpaper_ref": "WP-C-001",
                        },
                        {
                            "test_id": "T-999",
                            "risk_id": "R-999",
                            "workpaper_ref": "WP-C-999",
                        },
                        {
                            "risk_id": "R-002",
                            "workpaper_ref": "WP-C-002",
                        },
                    ]
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (root / "05_workpapers" / "WP-C-001.qmd").write_text(
            f"""# Workpaper

## Work performed

Compared approved transactions with system records.

## Evidence used and evaluated

Referenced generated exception listing; raw evidence was not copied.

## Results

{results}

## Conclusion

{conclusion}

## Observation proposal

```yaml
proposed_observation:
  title: Test observation
```
""",
            encoding="utf-8",
        )
        return root

    def test_context_includes_only_linked_program_row_and_selected_sections(self) -> None:
        root = self.make_project(
            results="Three supported exceptions were identified.",
            conclusion="The control did not operate consistently.",
        )

        context = build_observation_context(root, "WP-C-001")
        serialized = "\n".join(str(fragment.content) for fragment in context.fragments)

        self.assertEqual(context.test_id, "T-001")
        self.assertEqual(context.risk_id, "R-001")
        self.assertIn("Three supported exceptions", context.workpaper_sections["Results"])
        self.assertNotIn("R-999", serialized)
        self.assertFalse(
            any(fragment.path.startswith("04_evidence/") for fragment in context.fragments)
        )

    def test_section_extractor_supports_legacy_potential_observation_heading(self) -> None:
        sections = extract_workpaper_sections(
            "## Results\nResult text\n\n## Potential observation\nProposal text\n"
        )
        self.assertEqual(sections["Observation proposal"], "Proposal text")

    def test_preflight_allows_complete_local_context(self) -> None:
        root = self.make_project(
            results="Three supported exceptions were identified.",
            conclusion="The control did not operate consistently.",
        )
        context = build_observation_context(root, "WP-C-001")
        report = run_observation_preflight(context, resolve_ai_config(root, environ={}))

        self.assertEqual(report.decision, "allowed")
        self.assertFalse(report.raw_evidence_included)
        self.assertFalse(report.errors)
        self.assertEqual(len(report.sources), 4)

    def test_preflight_blocks_template_results_and_conclusion(self) -> None:
        root = self.make_project(
            results="Summarize the test results.",
            conclusion="State the workpaper conclusion.",
        )
        context = build_observation_context(root, "WP-C-001")
        report = run_observation_preflight(context, resolve_ai_config(root, environ={}))

        self.assertEqual(report.decision, "blocked")
        self.assertEqual(
            {item.code for item in report.errors},
            {"template_results", "template_conclusion"},
        )

    def test_preflight_reports_sensitive_values_without_echoing_them(self) -> None:
        sensitive_email = "person@example.test"
        root = self.make_project(
            results=f"Follow-up was received from {sensitive_email}.",
            conclusion="The issue requires an observation.",
        )
        context = build_observation_context(root, "WP-C-001")
        report = run_observation_preflight(context, resolve_ai_config(root, environ={}))

        findings_text = "\n".join(item.message for item in report.findings)
        self.assertIn("sensitive_email_address", {item.code for item in report.warnings})
        self.assertNotIn(sensitive_email, findings_text)

    def test_policy_can_block_sensitive_data_findings(self) -> None:
        root = self.make_project(
            results="Follow-up was received from person@example.test.",
            conclusion="The issue requires an observation.",
        )
        context = build_observation_context(root, "WP-C-001")
        config = resolve_ai_config(root, environ={})
        config = replace(
            config,
            rules=replace(config.rules, sensitive_data_action="block"),
        )

        report = run_observation_preflight(context, config)

        self.assertEqual(report.decision, "blocked")
        self.assertIn("sensitive_email_address", {item.code for item in report.errors})

    def test_external_profile_requires_confirmation_after_successful_preflight(self) -> None:
        root = self.make_project(
            results="Three supported exceptions were identified.",
            conclusion="The control did not operate consistently.",
        )
        context = build_observation_context(root, "WP-C-001")
        config = resolve_ai_config(root, environ={})
        external_profile = replace(
            config.profile,
            base_url="https://api.example.test/v1",
            data_boundary="external",
        )
        config = replace(config, profile=external_profile)

        report = run_observation_preflight(context, config)

        self.assertEqual(report.decision, "confirmation_required")

    def test_audit_program_review_excludes_scripts_and_warns_on_coverage(self) -> None:
        root = self.make_project(
            results="Three supported exceptions were identified.",
            conclusion="The control did not operate consistently.",
        )

        context = build_audit_program_review_context(root)
        serialized = "\n".join(str(fragment.content) for fragment in context.fragments)
        report = run_audit_program_review_preflight(
            context,
            resolve_ai_config(root, environ={}),
        )

        self.assertNotIn("SECRET_SCRIPT_MARKER", serialized)
        self.assertNotIn("test_script", serialized)
        self.assertEqual(report.decision, "allowed")
        self.assertIn("missing_program_test_id", {item.code for item in report.warnings})
        self.assertIn("included_risk_not_covered", {item.code for item in report.warnings})


if __name__ == "__main__":
    unittest.main()
