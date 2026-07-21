from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import yaml
from jsonschema import Draft202012Validator

from auditflow.ai.config import ResolvedAIConfig, resolve_ai_config
from auditflow.ai.context import (
    AIContextError,
    AuditProgramReviewContext,
    ObservationContext,
    build_audit_program_review_context,
    build_observation_context,
    build_observation_review_context,
)
from auditflow.ai.preflight import (
    AIPreflight,
    run_audit_program_review_preflight,
    run_observation_preflight,
    run_observation_review_preflight,
)
from auditflow.ai.prompts import (
    audit_program_review_schema,
    audit_program_review_system_prompt,
    build_audit_program_review_prompt,
    build_observation_draft_prompt,
    build_observation_review_prompt,
    observation_draft_system_prompt,
    observation_draft_schema,
    observation_review_system_prompt,
    observation_review_schema,
    render_saved_prompt,
)
from auditflow.ai.providers import (
    AIProvider,
    AIProviderError,
    StructuredAIResponse,
    create_provider,
)
from auditflow.ai.quality import (
    DraftQualityFinding,
    evaluate_observation_draft,
    evaluate_risk_formulation_reviews,
)


class AIServiceError(RuntimeError):
    """Raised when an AI task cannot proceed safely."""


@dataclass(frozen=True)
class PreparedObservationDraft:
    config: ResolvedAIConfig
    context: ObservationContext
    preflight: AIPreflight
    system_prompt: str
    user_prompt: str
    response_schema: dict[str, Any]


@dataclass(frozen=True)
class ObservationDraftResult:
    run_id: str
    run_directory: Path
    manifest_path: Path
    draft_path: Path
    prompt_path: Path | None
    response_path: Path | None
    content: dict[str, Any]
    quality_findings: tuple[DraftQualityFinding, ...]


@dataclass(frozen=True)
class PreparedObservationReview:
    observation_id: str
    config: ResolvedAIConfig
    context: ObservationContext
    preflight: AIPreflight
    system_prompt: str
    user_prompt: str
    response_schema: dict[str, Any]


@dataclass(frozen=True)
class ObservationReviewResult:
    run_id: str
    run_directory: Path
    manifest_path: Path
    review_path: Path
    prompt_path: Path | None
    response_path: Path | None
    content: dict[str, Any]
    quality_findings: tuple[DraftQualityFinding, ...]


@dataclass(frozen=True)
class PreparedAuditProgramReview:
    config: ResolvedAIConfig
    context: AuditProgramReviewContext
    preflight: AIPreflight
    system_prompt: str
    user_prompt: str
    response_schema: dict[str, Any]


@dataclass(frozen=True)
class AuditProgramReviewResult:
    run_id: str
    run_directory: Path
    manifest_path: Path
    review_path: Path
    prompt_path: Path | None
    response_path: Path | None
    content: dict[str, Any]
    quality_findings: tuple[DraftQualityFinding, ...]


def prepare_observation_draft(
    project_root: Path,
    workpaper_ref: str,
) -> PreparedObservationDraft:
    config = resolve_ai_config(project_root)
    try:
        context = build_observation_context(project_root, workpaper_ref)
    except AIContextError as exc:
        raise AIServiceError(str(exc)) from exc
    preflight = run_observation_preflight(context, config)
    return PreparedObservationDraft(
        config=config,
        context=context,
        preflight=preflight,
        system_prompt=observation_draft_system_prompt(),
        user_prompt=build_observation_draft_prompt(
            context,
            output_language=config.output_language,
        ),
        response_schema=observation_draft_schema(context.risk_text),
    )


def prepare_observation_review(
    project_root: Path,
    observation_id: str,
) -> PreparedObservationReview:
    config = resolve_ai_config(project_root)
    try:
        review_context = build_observation_review_context(project_root, observation_id)
    except AIContextError as exc:
        raise AIServiceError(str(exc)) from exc
    preflight = run_observation_review_preflight(review_context, config)
    return PreparedObservationReview(
        observation_id=review_context.observation_id,
        config=config,
        context=review_context.audit_context,
        preflight=preflight,
        system_prompt=observation_review_system_prompt(),
        user_prompt=build_observation_review_prompt(
            review_context.audit_context,
            observation_id=review_context.observation_id,
            output_language=config.output_language,
        ),
        response_schema=observation_review_schema(review_context.audit_context.risk_text),
    )


def prepare_audit_program_review(project_root: Path) -> PreparedAuditProgramReview:
    config = resolve_ai_config(project_root)
    try:
        context = build_audit_program_review_context(project_root)
    except AIContextError as exc:
        raise AIServiceError(str(exc)) from exc
    preflight = run_audit_program_review_preflight(context, config)
    return PreparedAuditProgramReview(
        config=config,
        context=context,
        preflight=preflight,
        system_prompt=audit_program_review_system_prompt(),
        user_prompt=build_audit_program_review_prompt(
            context,
            output_language=config.output_language,
        ),
        response_schema=audit_program_review_schema(context.risks),
    )


def _validate_response(content: dict[str, Any], schema: dict[str, Any]) -> None:
    errors = sorted(
        Draft202012Validator(schema).iter_errors(content),
        key=lambda error: tuple(str(part) for part in error.path),
    )
    if not errors:
        return

    details = []
    for error in errors[:5]:
        location = ".".join(str(part) for part in error.path) or "<root>"
        details.append(f"{location}: {error.message}")
    raise AIServiceError("AI response failed schema validation: " + "; ".join(details))


def _validate_audit_program_review_response(
    content: dict[str, Any],
    context: AuditProgramReviewContext,
) -> None:
    expected_risks = {
        str(risk.get("risk_id") or ""): str(risk.get("risk_text") or "")
        for risk in context.risks
        if risk.get("risk_id")
    }
    for field in ("risk_reviews", "coverage_reviews"):
        items = content.get(field, [])
        risk_ids = [str(item.get("risk_id") or "") for item in items]
        if len(risk_ids) != len(set(risk_ids)):
            raise AIServiceError(
                f"AI response contains duplicate risk_id values in {field}."
            )
        if set(risk_ids) != set(expected_risks):
            raise AIServiceError(
                f"AI response {field} must contain each included risk exactly once."
            )

    for item in content.get("risk_reviews", []):
        risk_id = str(item.get("risk_id") or "")
        if str(item.get("risk_text") or "") != expected_risks.get(risk_id):
            raise AIServiceError(
                f"AI response changed the source risk text for {risk_id}."
            )


def _safe_output_root(project_root: Path, relative_folder: str) -> Path:
    root = project_root.resolve()
    output_root = (root / relative_folder).resolve()
    try:
        output_root.relative_to(root)
    except ValueError as exc:
        raise AIServiceError("AI output folder resolves outside the audit project.") from exc
    return output_root


def _write_yaml(path: Path, data: Any) -> None:
    path.write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=120),
        encoding="utf-8",
    )


def _manifest(
    *,
    config: ResolvedAIConfig,
    preflight: AIPreflight,
    response: StructuredAIResponse,
    run_id: str,
    task: str,
    subject: dict[str, Any],
    quality_findings: tuple[DraftQualityFinding, ...],
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "task": task,
        "created_at": datetime.now(timezone.utc).isoformat(),
        **subject,
        "policy": {
            "id": config.policy_id,
            "hash": config.policy_hash,
            "source": config.policy_source,
        },
        "profile": {
            "name": config.profile.name,
            "provider": config.profile.provider,
            "destination": config.profile.base_url,
            "data_boundary": config.profile.data_boundary,
            "model_requested": config.model,
            "model_returned": response.model,
        },
        "project_classification": config.project_classification,
        "preflight": {
            "decision": preflight.decision,
            "raw_evidence_included": preflight.raw_evidence_included,
            "findings": [
                {
                    "severity": item.severity,
                    "code": item.code,
                    "message": item.message,
                    "source": item.source,
                }
                for item in preflight.findings
            ],
            "limitations": list(preflight.limitations),
        },
        "sources": [
            {
                "path": item.path,
                "selection": item.selection,
                "sha256": item.sha256,
                "character_count": item.character_count,
            }
            for item in preflight.sources
        ],
        "quality_review": [
            {
                "code": item.code,
                "field": item.field,
                "message": item.message,
            }
            for item in quality_findings
        ],
        "usage": {
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_duration_ns": response.total_duration_ns,
        },
    }


def _assert_generation_allowed(
    config: ResolvedAIConfig,
    preflight: AIPreflight,
    confirmation_granted: bool,
) -> None:
    if preflight.decision == "blocked":
        raise AIServiceError("Preflight blocked the AI request. Resolve all errors first.")
    if preflight.decision == "confirmation_required" and not confirmation_granted:
        raise AIServiceError("External provider confirmation is required.")
    if not config.enabled:
        raise AIServiceError("AI is disabled in 00_admin/ai.yml.")
    if config.profile.api_key_env and not config.api_key_configured:
        raise AIServiceError(
            f"Required API key environment variable is missing: "
            f"{config.profile.api_key_env}"
        )


def _write_prompt_and_response(
    run_directory: Path,
    config: ResolvedAIConfig,
    system_prompt: str,
    user_prompt: str,
    response: StructuredAIResponse,
) -> tuple[Path | None, Path | None]:
    prompt_path = None
    if config.rules.save_prompt:
        prompt_path = run_directory / "prompt.md"
        prompt_path.write_text(
            render_saved_prompt(system_prompt, user_prompt),
            encoding="utf-8",
        )

    response_path = None
    if config.rules.save_response:
        response_path = run_directory / "response.json"
        response_path.write_text(
            json.dumps(response.raw_response, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    return prompt_path, response_path


def generate_observation_draft(
    project_root: Path,
    prepared: PreparedObservationDraft,
    *,
    confirmation_granted: bool = False,
    provider: AIProvider | None = None,
) -> ObservationDraftResult:
    _assert_generation_allowed(
        prepared.config,
        prepared.preflight,
        confirmation_granted,
    )

    active_provider = provider or create_provider(prepared.config)
    try:
        response = active_provider.generate_structured(
            model=prepared.config.model,
            system_prompt=prepared.system_prompt,
            user_prompt=prepared.user_prompt,
            response_schema=prepared.response_schema,
            options=dict(prepared.config.profile.options),
        )
    except AIProviderError as exc:
        raise AIServiceError(str(exc)) from exc
    _validate_response(response.content, prepared.response_schema)
    quality_findings = (
        *evaluate_observation_draft(prepared.context, response.content),
        *evaluate_risk_formulation_reviews(response.content),
    )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output_root = _safe_output_root(
        project_root,
        prepared.config.rules.output_folder,
    )
    run_directory = (
        output_root
        / "observation_drafts"
        / prepared.context.workpaper_ref
        / run_id
    )
    run_directory.mkdir(parents=True, exist_ok=False)

    manifest_path = run_directory / "manifest.yml"
    draft_path = run_directory / "draft.yml"
    _write_yaml(
        manifest_path,
        _manifest(
            config=prepared.config,
            preflight=prepared.preflight,
            response=response,
            run_id=run_id,
            task="observation_draft",
            subject={"workpaper_ref": prepared.context.workpaper_ref},
            quality_findings=quality_findings,
        ),
    )
    _write_yaml(
        draft_path,
        {
            "metadata": {
                "status": "ai_generated_not_auditor_approved",
                "run_id": run_id,
                "source_workpaper": prepared.context.workpaper_ref,
                "model": response.model,
            },
            **response.content,
            "quality_warnings": [
                {
                    "code": item.code,
                    "field": item.field,
                    "message": item.message,
                }
                for item in quality_findings
            ],
        },
    )

    prompt_path, response_path = _write_prompt_and_response(
        run_directory,
        prepared.config,
        prepared.system_prompt,
        prepared.user_prompt,
        response,
    )

    return ObservationDraftResult(
        run_id=run_id,
        run_directory=run_directory,
        manifest_path=manifest_path,
        draft_path=draft_path,
        prompt_path=prompt_path,
        response_path=response_path,
        content=response.content,
        quality_findings=quality_findings,
    )


def generate_observation_review(
    project_root: Path,
    prepared: PreparedObservationReview,
    *,
    confirmation_granted: bool = False,
    provider: AIProvider | None = None,
) -> ObservationReviewResult:
    _assert_generation_allowed(
        prepared.config,
        prepared.preflight,
        confirmation_granted,
    )
    active_provider = provider or create_provider(prepared.config)
    try:
        response = active_provider.generate_structured(
            model=prepared.config.model,
            system_prompt=prepared.system_prompt,
            user_prompt=prepared.user_prompt,
            response_schema=prepared.response_schema,
            options=dict(prepared.config.profile.options),
        )
    except AIProviderError as exc:
        raise AIServiceError(str(exc)) from exc
    _validate_response(response.content, prepared.response_schema)
    quality_findings = evaluate_risk_formulation_reviews(response.content)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output_root = _safe_output_root(project_root, prepared.config.rules.output_folder)
    run_directory = (
        output_root
        / "observation_reviews"
        / prepared.observation_id
        / run_id
    )
    run_directory.mkdir(parents=True, exist_ok=False)

    manifest_path = run_directory / "manifest.yml"
    review_path = run_directory / "review.yml"
    _write_yaml(
        manifest_path,
        _manifest(
            config=prepared.config,
            preflight=prepared.preflight,
            response=response,
            run_id=run_id,
            task="observation_review",
            subject={
                "observation_id": prepared.observation_id,
                "workpaper_ref": prepared.context.workpaper_ref,
            },
            quality_findings=quality_findings,
        ),
    )
    _write_yaml(
        review_path,
        {
            "metadata": {
                "status": "ai_review_not_auditor_decision",
                "run_id": run_id,
                "observation_id": prepared.observation_id,
                "model": response.model,
            },
            **response.content,
            "quality_warnings": [
                {
                    "code": item.code,
                    "field": item.field,
                    "message": item.message,
                }
                for item in quality_findings
            ],
        },
    )
    prompt_path, response_path = _write_prompt_and_response(
        run_directory,
        prepared.config,
        prepared.system_prompt,
        prepared.user_prompt,
        response,
    )
    return ObservationReviewResult(
        run_id=run_id,
        run_directory=run_directory,
        manifest_path=manifest_path,
        review_path=review_path,
        prompt_path=prompt_path,
        response_path=response_path,
        content=response.content,
        quality_findings=quality_findings,
    )


def generate_audit_program_review(
    project_root: Path,
    prepared: PreparedAuditProgramReview,
    *,
    confirmation_granted: bool = False,
    provider: AIProvider | None = None,
) -> AuditProgramReviewResult:
    _assert_generation_allowed(
        prepared.config,
        prepared.preflight,
        confirmation_granted,
    )
    active_provider = provider or create_provider(prepared.config)
    try:
        response = active_provider.generate_structured(
            model=prepared.config.model,
            system_prompt=prepared.system_prompt,
            user_prompt=prepared.user_prompt,
            response_schema=prepared.response_schema,
            options=dict(prepared.config.profile.options),
        )
    except AIProviderError as exc:
        raise AIServiceError(str(exc)) from exc
    _validate_response(response.content, prepared.response_schema)
    _validate_audit_program_review_response(response.content, prepared.context)
    quality_findings = evaluate_risk_formulation_reviews(response.content)

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output_root = _safe_output_root(project_root, prepared.config.rules.output_folder)
    run_directory = output_root / "audit_program_reviews" / run_id
    run_directory.mkdir(parents=True, exist_ok=False)

    manifest_path = run_directory / "manifest.yml"
    review_path = run_directory / "review.yml"
    _write_yaml(
        manifest_path,
        _manifest(
            config=prepared.config,
            preflight=prepared.preflight,
            response=response,
            run_id=run_id,
            task="audit_program_review",
            subject={"audit_program": "03_audit_program/audit_program.yml"},
            quality_findings=quality_findings,
        ),
    )
    _write_yaml(
        review_path,
        {
            "metadata": {
                "status": "ai_review_not_auditor_decision",
                "run_id": run_id,
                "audit_program": "03_audit_program/audit_program.yml",
                "model": response.model,
            },
            **response.content,
            "quality_warnings": [
                {
                    "code": item.code,
                    "field": item.field,
                    "message": item.message,
                }
                for item in quality_findings
            ],
        },
    )
    prompt_path, response_path = _write_prompt_and_response(
        run_directory,
        prepared.config,
        prepared.system_prompt,
        prepared.user_prompt,
        response,
    )
    return AuditProgramReviewResult(
        run_id=run_id,
        run_directory=run_directory,
        manifest_path=manifest_path,
        review_path=review_path,
        prompt_path=prompt_path,
        response_path=response_path,
        content=response.content,
        quality_findings=quality_findings,
    )
