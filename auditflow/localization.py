from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

import yaml

from auditflow.errors import AuditFlowError
from auditflow.template_utils import load_yaml_template, read_template


DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "ru")
SETTINGS_PATH = Path("00_admin") / "settings.yml"


class UnsupportedLanguageError(AuditFlowError, ValueError):
    """Raised when a project requests an unsupported document language."""


def normalize_language(value: Any) -> str:
    language = str(value or DEFAULT_LANGUAGE).strip().lower().replace("_", "-")
    aliases = {
        "en-us": "en",
        "en-gb": "en",
        "english": "en",
        "ru-ru": "ru",
        "russian": "ru",
        "русский": "ru",
    }
    language = aliases.get(language, language)
    if language not in SUPPORTED_LANGUAGES:
        supported = ", ".join(SUPPORTED_LANGUAGES)
        raise UnsupportedLanguageError(
            f"Unsupported project language: {value!r}. Supported values: {supported}."
        )
    return language


def project_settings_path(project_root: Path) -> Path:
    return project_root / SETTINGS_PATH


def read_project_language(project_root: Path) -> str:
    settings_path = project_settings_path(project_root)
    if not settings_path.exists():
        return DEFAULT_LANGUAGE

    data = yaml.safe_load(settings_path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {settings_path}")

    value = data.get("language", DEFAULT_LANGUAGE)
    return normalize_language(value)


def language_settings(language: str) -> dict[str, str]:
    return {"language": normalize_language(language)}


def localized_template_path(relative_path: str, language: str) -> str:
    return f"{normalize_language(language)}/{relative_path}"


def read_localized_template(relative_path: str, language: str) -> str:
    return read_template(localized_template_path(relative_path, language))


def render_localized_template(
    relative_path: str,
    context: dict[str, Any],
    language: str,
) -> str:
    normalized_context = {
        key: "" if value is None else str(value)
        for key, value in context.items()
    }
    return Template(read_localized_template(relative_path, language)).safe_substitute(
        normalized_context
    )


def load_localized_yaml_template(
    relative_path: str,
    language: str,
    default: Any | None = None,
) -> Any:
    return load_yaml_template(
        localized_template_path(relative_path, language),
        default=default,
    )


@lru_cache(maxsize=len(SUPPORTED_LANGUAGES))
def load_messages(language: str) -> dict[str, Any]:
    data = load_localized_yaml_template("messages.yml", language)
    if not isinstance(data, dict):
        raise ValueError(f"Localized messages for {language!r} must be a YAML mapping")
    return data


def project_messages(project_root: Path) -> dict[str, Any]:
    return load_messages(read_project_language(project_root))


def message(messages: dict[str, Any], path: str) -> Any:
    current: Any = messages
    for key in path.split("."):
        if not isinstance(current, dict) or key not in current:
            raise KeyError(f"Missing localized message: {path}")
        current = current[key]
    return current


def translated_term(
    messages: dict[str, Any],
    category: str,
    value: Any,
) -> str:
    text = "" if value is None else str(value).strip()
    if not text:
        return text

    terms = message(messages, f"terms.{category}")
    if not isinstance(terms, dict):
        return text
    return str(terms.get(text.lower(), text))
