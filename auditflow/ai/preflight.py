from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable

from auditflow.ai.config import ResolvedAIConfig
from auditflow.ai.context import (
    AuditProgramReviewContext,
    ObservationContext,
    ObservationReviewContext,
    SourceFragment,
)


TEMPLATE_GUIDANCE = {
    "Work performed": "Describe what was actually done.",
    "Evidence used": "List evidence actually used",
    "Evidence used and evaluated": "List evidence actually used",
    "Results": "Summarize the test results.",
    "Conclusion": "State the workpaper conclusion.",
}

SENSITIVE_PATTERNS = {
    "email_address": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b", re.IGNORECASE),
    "phone_number": re.compile(r"(?<!\w)\+?\d(?:[ ()-]*\d){9,14}(?!\w)"),
    "credential_like_value": re.compile(
        r"\b(?:api[_ -]?key|password|access[_ -]?token|secret)\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
}

PROMPT_INJECTION_PATTERN = re.compile(
    r"\b(?:ignore|disregard|override)\b.{0,40}\b(?:instructions?|system prompt|rules?)\b",
    re.IGNORECASE | re.DOTALL,
)


@dataclass(frozen=True)
class PreflightFinding:
    severity: str
    code: str
    message: str
    source: str | None = None


@dataclass(frozen=True)
class SourceManifestEntry:
    path: str
    selection: str
    sha256: str
    character_count: int


@dataclass(frozen=True)
class AIPreflight:
    decision: str
    sources: tuple[SourceManifestEntry, ...]
    findings: tuple[PreflightFinding, ...]
    raw_evidence_included: bool
    limitations: tuple[str, ...]

    @property
    def errors(self) -> tuple[PreflightFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "error")

    @property
    def warnings(self) -> tuple[PreflightFinding, ...]:
        return tuple(item for item in self.findings if item.severity == "warning")


def _fragment_text(fragment: SourceFragment) -> str:
    if isinstance(fragment.content, str):
        return fragment.content
    import yaml

    return yaml.safe_dump(
        fragment.content,
        allow_unicode=True,
        sort_keys=True,
        width=120,
    )


def _check_required_context(context: ObservationContext) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    if not context.test_id:
        findings.append(
            PreflightFinding("error", "missing_test_id", "Linked audit program row has no test_id.")
        )
    if not context.risk_id:
        findings.append(
            PreflightFinding("error", "missing_risk_id", "Linked audit program row has no risk_id.")
        )

    for section_name in ("Results", "Conclusion"):
        content = context.workpaper_sections.get(section_name, "").strip()
        source = f"05_workpapers/{context.workpaper_ref}.qmd"
        if not content:
            findings.append(
                PreflightFinding(
                    "error",
                    f"missing_{section_name.lower()}",
                    f"Workpaper section '{section_name}' is empty or missing.",
                    source,
                )
            )
        elif TEMPLATE_GUIDANCE[section_name].lower() in content.lower():
            findings.append(
                PreflightFinding(
                    "error",
                    f"template_{section_name.lower()}",
                    f"Workpaper section '{section_name}' still contains template guidance.",
                    source,
                )
            )

    for section_name in ("Work performed", "Evidence used", "Evidence used and evaluated"):
        if section_name not in context.workpaper_sections:
            continue
        content = context.workpaper_sections[section_name].strip()
        guidance = TEMPLATE_GUIDANCE[section_name]
        if not content or guidance.lower() in content.lower():
            findings.append(
                PreflightFinding(
                    "warning",
                    "incomplete_supporting_section",
                    f"Workpaper section '{section_name}' appears incomplete.",
                    f"05_workpapers/{context.workpaper_ref}.qmd",
                )
            )

    if not context.workpaper_sections.get("Observation proposal", "").strip():
        findings.append(
            PreflightFinding(
                "warning",
                "missing_observation_proposal",
                "Workpaper has no observation proposal section; the model must not "
                "assume that an observation is required.",
                f"05_workpapers/{context.workpaper_ref}.qmd",
            )
        )
    return findings


def _scan_fragments(fragments: Iterable[SourceFragment]) -> list[PreflightFinding]:
    findings: list[PreflightFinding] = []
    for fragment in fragments:
        text = _fragment_text(fragment)
        for category, pattern in SENSITIVE_PATTERNS.items():
            count = len(pattern.findall(text))
            if count:
                findings.append(
                    PreflightFinding(
                        "warning",
                        f"sensitive_{category}",
                        f"Detected {count} possible {category.replace('_', ' ')} value(s).",
                        fragment.path,
                    )
                )
        if PROMPT_INJECTION_PATTERN.search(text):
            findings.append(
                PreflightFinding(
                    "warning",
                    "possible_prompt_injection",
                    "Detected text that may attempt to instruct or override the model.",
                    fragment.path,
                )
            )
    return findings


def _build_preflight(
    fragments: tuple[SourceFragment, ...],
    findings: list[PreflightFinding],
    config: ResolvedAIConfig,
) -> AIPreflight:
    if config.rules.scan_sensitive_data:
        sensitive_findings = _scan_fragments(fragments)
        if config.rules.sensitive_data_action == "block":
            sensitive_findings = [
                PreflightFinding("error", item.code, item.message, item.source)
                if item.code.startswith("sensitive_")
                else item
                for item in sensitive_findings
            ]
        findings.extend(sensitive_findings)

    has_errors = any(item.severity == "error" for item in findings)
    requires_confirmation = (
        config.profile.is_external and config.rules.require_confirmation_for_external
    )
    if has_errors:
        decision = "blocked"
    elif requires_confirmation:
        decision = "confirmation_required"
    else:
        decision = "allowed"

    sources = tuple(
        SourceManifestEntry(
            path=fragment.path,
            selection=fragment.selection,
            sha256=fragment.sha256,
            character_count=fragment.character_count,
        )
        for fragment in fragments
    )
    return AIPreflight(
        decision=decision,
        sources=sources,
        findings=tuple(findings),
        raw_evidence_included=False,
        limitations=(
            "Pattern scanning cannot reliably detect personal names, company names, "
            "or every confidential identifier.",
            "A successful preflight is a guardrail, not proof that the context is "
            "safe to disclose.",
        ),
    )


def run_observation_preflight(
    context: ObservationContext,
    config: ResolvedAIConfig,
) -> AIPreflight:
    findings = _check_required_context(context)
    return _build_preflight(context.fragments, findings, config)


def run_observation_review_preflight(
    review_context: ObservationReviewContext,
    config: ResolvedAIConfig,
) -> AIPreflight:
    findings = _check_required_context(review_context.audit_context)
    observation = review_context.observation
    expected_links = {
        "source_workpaper": review_context.audit_context.workpaper_ref,
        "test_id": review_context.audit_context.test_id,
        "risk_id": review_context.audit_context.risk_id,
    }
    source = f"06_observations/{review_context.observation_id}.yml"
    for field, expected in expected_links.items():
        actual = str(observation.get(field) or "").strip()
        if actual != expected:
            findings.append(
                PreflightFinding(
                    "error",
                    f"observation_{field}_mismatch",
                    f"Observation {field} is '{actual or '<empty>'}', expected '{expected}'.",
                    source,
                )
            )

    for field in ("title", "condition", "criteria", "cause", "risk_effect", "recommendation"):
        if not str(observation.get(field) or "").strip():
            findings.append(
                PreflightFinding(
                    "warning",
                    "incomplete_observation_field",
                    f"Observation field '{field}' is empty and should be reviewed.",
                    source,
                )
            )

    report = _build_preflight(
        review_context.audit_context.fragments,
        findings,
        config,
    )
    return AIPreflight(
        decision=report.decision,
        sources=report.sources,
        findings=tuple(findings),
        raw_evidence_included=report.raw_evidence_included,
        limitations=report.limitations,
    )


def _record_value(record: dict[str, object], *keys: str) -> str:
    for key in keys:
        value = str(record.get(key) or "").strip()
        if value:
            return value
    return ""


def run_audit_program_review_preflight(
    context: AuditProgramReviewContext,
    config: ResolvedAIConfig,
) -> AIPreflight:
    findings: list[PreflightFinding] = []
    source = "03_audit_program/audit_program.yml"
    risk_ids = {
        _record_value(risk, "risk_id", "id")
        for risk in context.risks
        if _record_value(risk, "risk_id", "id")
    }
    if not risk_ids:
        findings.append(
            PreflightFinding(
                "warning",
                "no_included_risks",
                "No included risks are available for AI review.",
                "01_planning/planning_decision.yml",
            )
        )
    if not context.program_rows:
        findings.append(
            PreflightFinding(
                "warning",
                "empty_audit_program",
                "The audit program has no rows to review.",
                source,
            )
        )

    test_ids: list[str] = []
    covered_risks: set[str] = set()
    controls_by_id = {
        _record_value(control, "control_id", "id"): control
        for control in context.controls
        if _record_value(control, "control_id", "id")
    }
    recommended_tests_by_id = {
        _record_value(test, "test_id", "id"): test
        for test in context.recommended_tests
        if _record_value(test, "test_id", "id")
    }

    for index, row in enumerate(context.program_rows, start=1):
        test_id = _record_value(row, "test_id", "id")
        risk_id = _record_value(row, "risk_id", "risk")
        control_id = _record_value(row, "control_id")
        row_label = test_id or f"row {index}"
        if not test_id:
            findings.append(
                PreflightFinding(
                    "warning",
                    "missing_program_test_id",
                    f"Audit program row {index} has no test_id.",
                    source,
                )
            )
        else:
            test_ids.append(test_id)
        if not risk_id:
            findings.append(
                PreflightFinding(
                    "warning",
                    "missing_program_risk_id",
                    f"Audit program {row_label} has no risk_id.",
                    source,
                )
            )
        elif risk_id not in risk_ids:
            findings.append(
                PreflightFinding(
                    "warning",
                    "program_risk_not_in_scope",
                    f"Audit program {row_label} links to risk {risk_id}, which is not included.",
                    source,
                )
            )
        elif test_id:
            covered_risks.add(risk_id)

        if control_id:
            control = controls_by_id.get(control_id)
            if control is None:
                findings.append(
                    PreflightFinding(
                        "warning",
                        "unknown_program_control",
                        f"Audit program {row_label} links to unknown control {control_id}.",
                        source,
                    )
                )
            else:
                control_risk_id = _record_value(control, "risk_id", "risk")
                if risk_id and control_risk_id and control_risk_id != risk_id:
                    findings.append(
                        PreflightFinding(
                            "warning",
                            "control_risk_mismatch",
                            f"Control {control_id} links to {control_risk_id}, but "
                            f"{row_label} links to {risk_id}.",
                            source,
                        )
                    )

        recommended_test = recommended_tests_by_id.get(test_id)
        if recommended_test is not None:
            recommended_risk_id = _record_value(recommended_test, "risk_id", "risk")
            if risk_id and recommended_risk_id and recommended_risk_id != risk_id:
                findings.append(
                    PreflightFinding(
                        "warning",
                        "recommended_test_risk_mismatch",
                        f"Recommended test {test_id} links to {recommended_risk_id}, "
                        f"but the program row links to {risk_id}.",
                        source,
                    )
                )

    duplicate_test_ids = sorted(
        test_id for test_id in set(test_ids) if test_ids.count(test_id) > 1
    )
    for test_id in duplicate_test_ids:
        findings.append(
            PreflightFinding(
                "warning",
                "duplicate_program_test_id",
                f"Audit program contains duplicate test_id {test_id}.",
                source,
            )
        )

    for risk_id in sorted(risk_ids - covered_risks):
        findings.append(
            PreflightFinding(
                "warning",
                "included_risk_not_covered",
                f"Included risk {risk_id} has no linked audit program row.",
                source,
            )
        )

    return _build_preflight(context.fragments, findings, config)
