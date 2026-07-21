from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Mapping
from urllib.parse import urlparse

import yaml


POLICY_ENV_VAR = "AUDITFLOW_AI_POLICY"
SUPPORTED_PROVIDERS = {"ollama", "openai_compatible", "huggingface"}
CLASSIFICATION_LEVELS = ("public", "internal", "confidential", "restricted")
DATA_BOUNDARIES = {"local_machine", "company_network", "external"}

BUILT_IN_POLICY: dict[str, Any] = {
    "schema_version": 1,
    "policy_id": "auditflow-secure-defaults-v1",
    "default_profile": "local_ollama",
    "profiles": {
        "local_ollama": {
            "provider": "ollama",
            "base_url": "http://127.0.0.1:11434",
            "default_model": "qwen3:8b",
            "allowed_models": ["*"],
            "data_boundary": "local_machine",
            "allowed_classifications": list(CLASSIFICATION_LEVELS),
            "options": {
                "temperature": 0,
                "context_length": 8192,
                "thinking": False,
            },
        }
    },
    "rules": {
        "allow_raw_evidence": False,
        "allow_external_providers": False,
        "require_preflight": True,
        "require_confirmation_for_external": True,
        "save_prompt": True,
        "save_response": True,
        "scan_sensitive_data": True,
        "sensitive_data_action": "warn",
        "output_folder": "ai_outputs",
    },
}


class AIConfigError(ValueError):
    """Raised when AI policy or project settings are invalid or conflict."""


@dataclass(frozen=True)
class ProviderProfile:
    name: str
    provider: str
    base_url: str
    api_key_env: str | None
    default_model: str
    allowed_models: tuple[str, ...]
    data_boundary: str
    allowed_classifications: tuple[str, ...]
    options: Mapping[str, Any]

    @property
    def is_external(self) -> bool:
        return self.data_boundary == "external"


@dataclass(frozen=True)
class AIRules:
    allow_raw_evidence: bool
    allow_external_providers: bool
    require_preflight: bool
    require_confirmation_for_external: bool
    save_prompt: bool
    save_response: bool
    scan_sensitive_data: bool
    sensitive_data_action: str
    output_folder: str


@dataclass(frozen=True)
class ResolvedAIConfig:
    enabled: bool
    profile: ProviderProfile
    model: str
    project_classification: str
    output_language: str
    rules: AIRules
    policy_id: str
    policy_source: str
    policy_hash: str
    project_settings_source: str
    api_key_configured: bool | None


def _load_yaml_mapping(path: Path, label: str) -> dict[str, Any]:
    if not path.exists():
        raise AIConfigError(f"{label} not found: {path}")
    if not path.is_file():
        raise AIConfigError(f"{label} is not a file: {path}")

    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, UnicodeError, yaml.YAMLError) as exc:
        raise AIConfigError(f"Cannot read {label} {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise AIConfigError(f"{label} must contain a YAML mapping: {path}")
    return data


def _ensure_known_keys(data: Mapping[str, Any], allowed: set[str], label: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise AIConfigError(f"Unknown {label} field(s): {', '.join(unknown)}")


def _require_string(data: Mapping[str, Any], key: str, label: str) -> str:
    value = str(data.get(key) or "").strip()
    if not value:
        raise AIConfigError(f"{label}.{key} must be a non-empty string")
    return value


def _string_list(value: Any, label: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise AIConfigError(f"{label} must be a non-empty list")
    result = tuple(str(item).strip() for item in value if str(item).strip())
    if not result:
        raise AIConfigError(f"{label} must contain at least one non-empty value")
    return result


def _is_loopback_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _parse_profile(name: str, data: Any) -> ProviderProfile:
    if not isinstance(data, dict):
        raise AIConfigError(f"Policy profile {name} must be a mapping")

    _ensure_known_keys(
        data,
        {
            "provider",
            "base_url",
            "api_key_env",
            "default_model",
            "allowed_models",
            "data_boundary",
            "allowed_classifications",
            "options",
        },
        f"policy profile {name}",
    )

    provider = _require_string(data, "provider", f"profiles.{name}")
    if provider not in SUPPORTED_PROVIDERS:
        raise AIConfigError(
            f"profiles.{name}.provider must be one of: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
        )

    base_url = _require_string(data, "base_url", f"profiles.{name}").rstrip("/")
    parsed_url = urlparse(base_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        raise AIConfigError(f"profiles.{name}.base_url must be an absolute HTTP(S) URL")

    data_boundary = _require_string(data, "data_boundary", f"profiles.{name}")
    if data_boundary not in DATA_BOUNDARIES:
        raise AIConfigError(
            f"profiles.{name}.data_boundary must be one of: {', '.join(sorted(DATA_BOUNDARIES))}"
        )
    if data_boundary == "local_machine" and not _is_loopback_url(base_url):
        raise AIConfigError(
            f"profiles.{name}.base_url must use a loopback HTTP address for local_machine"
        )
    if data_boundary != "local_machine" and parsed_url.scheme != "https":
        raise AIConfigError(f"profiles.{name}.base_url must use HTTPS outside the local machine")

    default_model = _require_string(data, "default_model", f"profiles.{name}")
    allowed_models = _string_list(
        data.get("allowed_models", [default_model]),
        f"profiles.{name}.allowed_models",
    )
    if "*" not in allowed_models and default_model not in allowed_models:
        raise AIConfigError(
            f"profiles.{name}.default_model is not included in allowed_models"
        )

    allowed_classifications = _string_list(
        data.get("allowed_classifications", ["public"]),
        f"profiles.{name}.allowed_classifications",
    )
    invalid_classifications = sorted(set(allowed_classifications) - set(CLASSIFICATION_LEVELS))
    if invalid_classifications:
        raise AIConfigError(
            f"profiles.{name}.allowed_classifications contains unsupported value(s): "
            f"{', '.join(invalid_classifications)}"
        )

    options = data.get("options", {})
    if not isinstance(options, dict):
        raise AIConfigError(f"profiles.{name}.options must be a mapping")

    api_key_env = str(data.get("api_key_env") or "").strip() or None
    return ProviderProfile(
        name=name,
        provider=provider,
        base_url=base_url,
        api_key_env=api_key_env,
        default_model=default_model,
        allowed_models=allowed_models,
        data_boundary=data_boundary,
        allowed_classifications=allowed_classifications,
        options=dict(options),
    )


def _parse_rules(data: Any) -> AIRules:
    if not isinstance(data, dict):
        raise AIConfigError("Policy rules must be a mapping")

    defaults = BUILT_IN_POLICY["rules"]
    _ensure_known_keys(data, set(defaults), "policy rules")
    merged = {**defaults, **data}

    boolean_fields = set(defaults) - {"sensitive_data_action", "output_folder"}
    for key in boolean_fields:
        value = merged[key]
        if not isinstance(value, bool):
            raise AIConfigError(f"rules.{key} must be true or false")
    if not merged["require_preflight"]:
        raise AIConfigError("rules.require_preflight cannot be disabled")

    sensitive_data_action = merged["sensitive_data_action"]
    if sensitive_data_action not in {"warn", "block"}:
        raise AIConfigError("rules.sensitive_data_action must be 'warn' or 'block'")

    output_folder = str(merged["output_folder"] or "").strip().replace("\\", "/")
    output_path = PurePosixPath(output_folder)
    if (
        not output_folder
        or output_path.is_absolute()
        or ".." in output_path.parts
        or ":" in output_folder
    ):
        raise AIConfigError("rules.output_folder must be a safe relative project path")
    merged["output_folder"] = output_folder

    return AIRules(**merged)


def _policy_hash(data: Mapping[str, Any]) -> str:
    canonical = json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load_policy(environ: Mapping[str, str]) -> tuple[dict[str, Any], str, str]:
    configured_path = str(environ.get(POLICY_ENV_VAR) or "").strip()
    if not configured_path:
        policy = BUILT_IN_POLICY
        return policy, "built-in", _policy_hash(policy)

    policy_path = Path(configured_path).expanduser().resolve()
    policy = _load_yaml_mapping(policy_path, "AI policy")
    return policy, str(policy_path), _policy_hash(policy)


def _parse_policy(
    policy: Mapping[str, Any],
) -> tuple[str, str, dict[str, ProviderProfile], AIRules]:
    _ensure_known_keys(
        policy,
        {"schema_version", "policy_id", "default_profile", "profiles", "rules"},
        "policy",
    )
    if policy.get("schema_version") != 1:
        raise AIConfigError("AI policy schema_version must be 1")

    policy_id = _require_string(policy, "policy_id", "policy")
    default_profile = _require_string(policy, "default_profile", "policy")
    raw_profiles = policy.get("profiles")
    if not isinstance(raw_profiles, dict) or not raw_profiles:
        raise AIConfigError("Policy profiles must be a non-empty mapping")

    profiles = {
        str(name): _parse_profile(str(name), profile)
        for name, profile in raw_profiles.items()
    }
    if default_profile not in profiles:
        raise AIConfigError(f"Policy default_profile does not exist: {default_profile}")

    rules = _parse_rules(policy.get("rules", {}))
    return policy_id, default_profile, profiles, rules


def _load_project_settings(project_root: Path) -> tuple[dict[str, Any], str]:
    settings_path = project_root / "00_admin" / "ai.yml"
    if not settings_path.exists():
        return {}, "built-in defaults (00_admin/ai.yml not found)"

    raw = _load_yaml_mapping(settings_path, "Project AI settings")
    _ensure_known_keys(raw, {"ai"}, "project AI settings")
    settings = raw.get("ai", {})
    if not isinstance(settings, dict):
        raise AIConfigError("Project AI settings field 'ai' must be a mapping")
    _ensure_known_keys(
        settings,
        {"enabled", "profile", "model", "project_classification", "output_language"},
        "project ai",
    )
    return settings, str(settings_path)


def resolve_ai_config(
    project_root: Path,
    *,
    environ: Mapping[str, str] | None = None,
) -> ResolvedAIConfig:
    environ = os.environ if environ is None else environ
    policy, policy_source, policy_hash = _load_policy(environ)
    policy_id, default_profile, profiles, rules = _parse_policy(policy)
    settings, project_settings_source = _load_project_settings(project_root)

    enabled = settings.get("enabled", False)
    if not isinstance(enabled, bool):
        raise AIConfigError("ai.enabled must be true or false")

    profile_name = str(settings.get("profile") or default_profile).strip()
    if profile_name not in profiles:
        raise AIConfigError(
            f"AI profile '{profile_name}' is not allowed by policy '{policy_id}'"
        )
    profile = profiles[profile_name]

    model = str(settings.get("model") or profile.default_model).strip()
    if not model:
        raise AIConfigError("AI model must not be empty")
    if "*" not in profile.allowed_models and model not in profile.allowed_models:
        raise AIConfigError(
            f"Model '{model}' is not allowed by AI profile '{profile.name}'"
        )

    classification = str(
        settings.get("project_classification") or "confidential"
    ).strip().lower()
    if classification not in CLASSIFICATION_LEVELS:
        raise AIConfigError(
            "ai.project_classification must be one of: "
            + ", ".join(CLASSIFICATION_LEVELS)
        )
    if classification not in profile.allowed_classifications:
        raise AIConfigError(
            f"Project classification '{classification}' is not allowed by profile "
            f"'{profile.name}'"
        )

    if profile.is_external and not rules.allow_external_providers:
        raise AIConfigError(
            f"Profile '{profile.name}' uses an external provider, but company policy "
            "does not allow external providers"
        )

    output_language = str(settings.get("output_language") or "auto").strip()
    if not output_language:
        raise AIConfigError("ai.output_language must not be empty")

    api_key_configured = None
    if profile.api_key_env:
        api_key_configured = bool(str(environ.get(profile.api_key_env) or "").strip())

    return ResolvedAIConfig(
        enabled=enabled,
        profile=profile,
        model=model,
        project_classification=classification,
        output_language=output_language,
        rules=rules,
        policy_id=policy_id,
        policy_source=policy_source,
        policy_hash=policy_hash,
        project_settings_source=project_settings_source,
        api_key_configured=api_key_configured,
    )
