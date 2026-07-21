from __future__ import annotations

import unittest

from auditflow.ai.context import ObservationContext
from auditflow.ai.quality import (
    evaluate_observation_draft,
    evaluate_risk_formulation_reviews,
)


class AIQualityTests(unittest.TestCase):
    def context(self) -> ObservationContext:
        return ObservationContext(
            workpaper_ref="WP-C-001",
            test_id="T-001",
            risk_id="R-001",
            risk_text="Approval risk",
            control_id="C-001",
            fragments=(),
            workpaper_sections={
                "Results": "31 cases remained confirmed or unresolved.",
                "Conclusion": "An observation should be raised.",
            },
        )

    def test_flags_lost_qualifier_and_control_failure_as_cause(self) -> None:
        content = {
            "observation_needed": True,
            "draft": {
                "title": "Approval exceptions",
                "condition": "31 confirmed exceptions were identified.",
                "criteria": "Approval is required.",
                "cause": "The control did not operate effectively.",
                "risk_effect": "Unauthorized transactions may occur.",
                "recommendation": "Strengthen approval controls.",
            },
            "missing_information": [],
        }

        findings = evaluate_observation_draft(self.context(), content)

        self.assertEqual(
            {item.code for item in findings},
            {"qualifier_not_preserved", "cause_restates_control_failure"},
        )

    def test_no_observation_has_no_draft_quality_findings(self) -> None:
        content = {
            "observation_needed": False,
            "draft": None,
            "missing_information": ["No supported condition"],
        }

        self.assertFalse(evaluate_observation_draft(self.context(), content))

    def test_flags_risk_structure_that_omits_a_populated_cause(self) -> None:
        content = {
            "risk_reviews": [
                {
                    "risk_id": "R-002",
                    "structure": "event_consequence",
                    "event": "An invoice is paid twice.",
                    "cause": "Duplicate records are not detected.",
                    "consequence": "The company incurs a duplicate payment.",
                }
            ]
        }

        findings = evaluate_risk_formulation_reviews(content)

        self.assertEqual(
            {item.code for item in findings},
            {"risk_structure_omits_identified_cause"},
        )


if __name__ == "__main__":
    unittest.main()
