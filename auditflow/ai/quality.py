from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from auditflow.ai.context import ObservationContext


# Russian alternatives match inflected forms; \w* consumes the remaining suffix.
CAUSE_RESTATEMENT_PATTERN = re.compile(
    r"(?:\bcontrol\b.{0,80}\b(?:did not operate|not effective|ineffective|failed|failure)\b|"
    r"\bконтрол(?:ь|я|ю|ем|е|и|ей|ям|ями|ях)\b.{0,80}"
    r"\b(?:не\s+(?:сработал\w*|работал\w*)|неэффектив\w*|сбо(?:й|я|ем|и))\b)",
    re.IGNORECASE | re.DOTALL,
)

UNRESOLVED_QUALIFIER_PATTERN = re.compile(
    r"\b(?:unresolved|неразреш[её]н\w*|неурегулирован\w*)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class DraftQualityFinding:
    code: str
    field: str
    message: str


def evaluate_observation_draft(
    context: ObservationContext,
    content: dict[str, Any],
) -> tuple[DraftQualityFinding, ...]:
    if not content.get("observation_needed"):
        return ()

    draft = content.get("draft")
    if not isinstance(draft, dict):
        return ()

    findings: list[DraftQualityFinding] = []
    condition = str(draft.get("condition") or "").strip()
    cause = str(draft.get("cause") or "").strip()
    missing_information = [
        str(item).lower()
        for item in content.get("missing_information", [])
        if str(item).strip()
    ]

    results_source = context.workpaper_sections.get("Results", "")
    if UNRESOLVED_QUALIFIER_PATTERN.search(
        results_source
    ) and not UNRESOLVED_QUALIFIER_PATTERN.search(condition):
        findings.append(
            DraftQualityFinding(
                code="qualifier_not_preserved",
                field="condition",
                message=(
                    "Source results contain unresolved items, but the drafted condition "
                    "does not preserve that qualifier."
                ),
            )
        )

    if cause and CAUSE_RESTATEMENT_PATTERN.search(cause):
        findings.append(
            DraftQualityFinding(
                code="cause_restates_control_failure",
                field="cause",
                message=(
                    "Drafted cause appears to restate control failure or ineffectiveness "
                    "instead of explaining why the condition occurred."
                ),
            )
        )

    required_fields = (
        "title",
        "condition",
        "criteria",
        "cause",
        "risk_effect",
        "recommendation",
    )
    for field in required_fields:
        if str(draft.get(field) or "").strip():
            continue
        if not any(field.replace("_", " ") in item for item in missing_information):
            findings.append(
                DraftQualityFinding(
                    code="empty_field_not_explained",
                    field=field,
                    message=(
                        f"Draft field '{field}' is empty, but missing_information does not "
                        "explain the gap."
                    ),
                )
            )

    return tuple(findings)


def evaluate_risk_formulation_reviews(
    content: dict[str, Any],
) -> tuple[DraftQualityFinding, ...]:
    reviews: list[dict[str, Any]] = []
    single_review = content.get("risk_formulation_review")
    if isinstance(single_review, dict):
        reviews.append(single_review)
    program_reviews = content.get("risk_reviews", [])
    if isinstance(program_reviews, list):
        reviews.extend(item for item in program_reviews if isinstance(item, dict))

    findings: list[DraftQualityFinding] = []
    for review in reviews:
        risk_id = str(review.get("risk_id") or "linked risk").strip()
        structure = str(review.get("structure") or "").strip()
        event = bool(str(review.get("event") or "").strip())
        cause = bool(str(review.get("cause") or "").strip())
        consequence = bool(str(review.get("consequence") or "").strip())
        field = f"risk_formulation_review[{risk_id}]"

        if structure == "event_cause_consequence" and not all(
            (event, cause, consequence)
        ):
            findings.append(
                DraftQualityFinding(
                    code="risk_structure_elements_mismatch",
                    field=field,
                    message=(
                        "Risk is classified as event-cause-consequence, but at least "
                        "one of those elements is empty."
                    ),
                )
            )
        elif structure == "event_consequence":
            if not event or not consequence:
                findings.append(
                    DraftQualityFinding(
                        code="risk_structure_elements_mismatch",
                        field=field,
                        message=(
                            "Risk is classified as event-consequence, but event or "
                            "consequence is empty."
                        ),
                    )
                )
            if cause:
                findings.append(
                    DraftQualityFinding(
                        code="risk_structure_omits_identified_cause",
                        field=field,
                        message=(
                            "The review identifies a cause but classifies the risk as "
                            "event-consequence rather than event-cause-consequence."
                        ),
                    )
                )

    return tuple(findings)
