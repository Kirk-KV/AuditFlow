from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

import yaml

from auditflow.ai.providers import ProviderStatus, StructuredAIResponse
from auditflow.ai.service import (
    AIServiceError,
    generate_audit_program_review,
    generate_observation_draft,
    generate_observation_review,
    prepare_audit_program_review,
    prepare_observation_draft,
    prepare_observation_review,
)


VALID_RISK_REVIEW = {
    "risk_text": "Approval risk",
    "structure": "weak_or_not_a_risk",
    "event": "Transactions are processed without approval",
    "cause": "",
    "consequence": "Unauthorized transactions may occur",
    "reminder": "State the event and consequence explicitly in the risk description.",
}


VALID_DRAFT = {
    "observation_needed": True,
    "assessment": "The documented exception supports a draft observation.",
    "draft": {
        "title": "Transactions processed without required approval",
        "condition": "Three supported exceptions were identified.",
        "criteria": "Transactions should be approved before processing.",
        "cause": "The documented workflow did not consistently enforce approval.",
        "risk_effect": "Unauthorized transactions may be processed.",
        "recommendation": "Configure preventive approval controls and monitor exceptions.",
    },
    "missing_information": [],
    "risk_formulation_review": VALID_RISK_REVIEW,
}


VALID_OBSERVATION_REVIEW = {
    "overall_assessment": "The observation is generally supported but its cause is weak.",
    "logic_review": {
        "criterion": {"assessment": "adequate", "comment": "Linked to approval control."},
        "condition": {"assessment": "adequate", "comment": "Supported by test results."},
        "cause": {"assessment": "weak", "comment": "Restates control failure."},
        "risk_effect": {"assessment": "adequate", "comment": "Aligned with R-001."},
        "recommendation": {"assessment": "adequate", "comment": "Direction is proportionate."},
    },
    "consistency_issues": [],
    "unsupported_claims": [],
    "suggested_improvements": ["Determine and document the root cause."],
    "risk_formulation_review": VALID_RISK_REVIEW,
}


VALID_AUDIT_PROGRAM_REVIEW = {
    "overall_assessment": "The included risk is linked to one program test.",
    "risk_reviews": [{"risk_id": "R-001", **VALID_RISK_REVIEW}],
    "coverage_reviews": [
        {
            "risk_id": "R-001",
            "linked_test_ids": ["T-001"],
            "assessment": "covered",
            "comment": "T-001 is linked to the included risk.",
        }
    ],
    "traceability_issues": [],
    "consistency_questions": [],
}


class FakeProvider:
    def __init__(self, content: dict[str, Any]) -> None:
        self.content = content
        self.calls = 0

    def status(self, model: str) -> ProviderStatus:
        return ProviderStatus(True, True, f"{model} available")

    def generate_structured(self, **kwargs: Any) -> StructuredAIResponse:
        self.calls += 1
        return StructuredAIResponse(
            content=self.content,
            raw_response={
                "model": kwargs["model"],
                "message": {"role": "assistant", "content": "structured response"},
            },
            model=kwargs["model"],
            created_at="2026-07-20T12:00:00Z",
            prompt_tokens=1200,
            completion_tokens=240,
            total_duration_ns=1_000_000,
        )


class AIServiceTests(unittest.TestCase):
    def make_project(
        self,
        *,
        enabled: bool = True,
        results: str = "Three supported exceptions were identified.",
        conclusion: str = "The control did not operate consistently.",
    ) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        root = Path(temp_dir.name)
        for directory in [
            "00_admin",
            "01_planning",
            "03_audit_program",
            "05_workpapers",
            "06_observations",
        ]:
            (root / directory).mkdir(parents=True, exist_ok=True)

        (root / "00_admin" / "ai.yml").write_text(
            yaml.safe_dump(
                {
                    "ai": {
                        "enabled": enabled,
                        "profile": "local_ollama",
                        "model": "qwen3:8b",
                        "project_classification": "confidential",
                        "output_language": "auto",
                    }
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (root / "initial_data.yml").write_text(
            yaml.safe_dump(
                {
                    "audit": {"id": "A-1", "title": "Test audit"},
                    "objectives": [{"id": "OBJ-001", "statement": "Test objective"}],
                    "risks": [{"id": "R-001", "title": "Approval risk"}],
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (root / "01_planning" / "planning_decision.yml").write_text(
            yaml.safe_dump(
                {
                    "included_risks": [{"id": "R-001", "title": "Approval risk"}],
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
                            "risk_title": "Approval risk",
                            "control_id": "C-001",
                            "control_description": "Approval before processing",
                            "test_hypothesis": "Exceptions may exist.",
                            "test_script": ["SECRET_SCRIPT_MARKER"],
                            "workpaper_ref": "WP-C-001",
                        }
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
  title: Approval exceptions
```
""",
            encoding="utf-8",
        )
        (root / "06_observations" / "OBS-001.yml").write_text(
            yaml.safe_dump(
                {
                    "observation_id": "OBS-001",
                    "status": "draft",
                    "source_workpaper": "WP-C-001",
                    "test_id": "T-001",
                    "risk_id": "R-001",
                    "title": "Approval exceptions",
                    "condition": results,
                    "criteria": "Approval is required before processing.",
                    "cause": "The control did not operate consistently.",
                    "risk_effect": "Unauthorized transactions may be processed.",
                    "recommendation": "Strengthen approval controls.",
                },
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        return root

    def test_prepare_is_a_dry_run_without_provider_or_output_files(self) -> None:
        root = self.make_project(enabled=False)

        prepared = prepare_observation_draft(root, "WP-C-001")

        self.assertEqual(prepared.preflight.decision, "allowed")
        self.assertFalse((root / "ai_outputs").exists())

    def test_generate_saves_auditable_sidecar_without_changing_observation(self) -> None:
        root = self.make_project()
        observation_path = root / "06_observations" / "OBS-001.yml"
        original = observation_path.read_bytes()
        provider = FakeProvider(VALID_DRAFT)
        prepared = prepare_observation_draft(root, "WP-C-001")

        result = generate_observation_draft(root, prepared, provider=provider)

        self.assertEqual(provider.calls, 1)
        self.assertTrue(result.manifest_path.exists())
        self.assertTrue(result.draft_path.exists())
        self.assertTrue(result.prompt_path and result.prompt_path.exists())
        self.assertTrue(result.response_path and result.response_path.exists())
        self.assertEqual(observation_path.read_bytes(), original)

        draft = yaml.safe_load(result.draft_path.read_text(encoding="utf-8"))
        manifest = yaml.safe_load(result.manifest_path.read_text(encoding="utf-8"))
        self.assertEqual(draft["metadata"]["status"], "ai_generated_not_auditor_approved")
        self.assertEqual(manifest["policy"]["id"], "auditflow-secure-defaults-v1")
        self.assertFalse(manifest["preflight"]["raw_evidence_included"])
        self.assertEqual(len(manifest["sources"]), 4)

    def test_blocked_preflight_does_not_call_provider(self) -> None:
        root = self.make_project(
            results="Summarize the test results.",
            conclusion="State the workpaper conclusion.",
        )
        provider = FakeProvider(VALID_DRAFT)
        prepared = prepare_observation_draft(root, "WP-C-001")

        with self.assertRaisesRegex(AIServiceError, "Preflight blocked"):
            generate_observation_draft(root, prepared, provider=provider)

        self.assertEqual(provider.calls, 0)
        self.assertFalse((root / "ai_outputs").exists())

    def test_invalid_model_response_is_rejected_before_writing_files(self) -> None:
        root = self.make_project()
        provider = FakeProvider({"observation_needed": True})
        prepared = prepare_observation_draft(root, "WP-C-001")

        with self.assertRaisesRegex(AIServiceError, "schema validation"):
            generate_observation_draft(root, prepared, provider=provider)

        self.assertEqual(provider.calls, 1)
        self.assertFalse((root / "ai_outputs").exists())

    def test_response_cannot_claim_observation_without_a_draft_object(self) -> None:
        root = self.make_project()
        provider = FakeProvider(
            {
                "observation_needed": True,
                "assessment": "An observation appears necessary.",
                "draft": None,
                "missing_information": [],
                "risk_formulation_review": VALID_RISK_REVIEW,
            }
        )
        prepared = prepare_observation_draft(root, "WP-C-001")

        with self.assertRaisesRegex(AIServiceError, "schema validation"):
            generate_observation_draft(root, prepared, provider=provider)

        self.assertFalse((root / "ai_outputs").exists())

    def test_observation_review_saves_sidecar_without_changing_observation(self) -> None:
        root = self.make_project()
        observation_path = root / "06_observations" / "OBS-001.yml"
        original = observation_path.read_bytes()
        provider = FakeProvider(VALID_OBSERVATION_REVIEW)
        prepared = prepare_observation_review(root, "OBS-001")

        result = generate_observation_review(root, prepared, provider=provider)

        self.assertEqual(provider.calls, 1)
        self.assertTrue(result.review_path.exists())
        self.assertTrue(result.manifest_path.exists())
        self.assertEqual(observation_path.read_bytes(), original)
        review = yaml.safe_load(result.review_path.read_text(encoding="utf-8"))
        self.assertEqual(review["metadata"]["status"], "ai_review_not_auditor_decision")
        self.assertEqual(
            review["risk_formulation_review"]["structure"],
            "weak_or_not_a_risk",
        )

    def test_audit_program_review_saves_sidecar_without_scripts_or_source_changes(self) -> None:
        root = self.make_project()
        program_path = root / "03_audit_program" / "audit_program.yml"
        original = program_path.read_bytes()
        provider = FakeProvider(VALID_AUDIT_PROGRAM_REVIEW)
        prepared = prepare_audit_program_review(root)

        self.assertNotIn("SECRET_SCRIPT_MARKER", prepared.user_prompt)
        result = generate_audit_program_review(root, prepared, provider=provider)

        self.assertEqual(provider.calls, 1)
        self.assertTrue(result.review_path.exists())
        self.assertTrue(result.manifest_path.exists())
        self.assertEqual(program_path.read_bytes(), original)
        review = yaml.safe_load(result.review_path.read_text(encoding="utf-8"))
        self.assertEqual(review["metadata"]["status"], "ai_review_not_auditor_decision")
        self.assertEqual(review["coverage_reviews"][0]["assessment"], "covered")

    def test_audit_program_review_requires_each_included_risk_once(self) -> None:
        root = self.make_project()
        invalid = {**VALID_AUDIT_PROGRAM_REVIEW, "risk_reviews": []}
        provider = FakeProvider(invalid)
        prepared = prepare_audit_program_review(root)

        with self.assertRaisesRegex(AIServiceError, "each included risk exactly once"):
            generate_audit_program_review(root, prepared, provider=provider)

        self.assertFalse((root / "ai_outputs").exists())


if __name__ == "__main__":
    unittest.main()
