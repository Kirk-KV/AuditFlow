from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from auditflow.ai.config import ResolvedAIConfig


class AIProviderError(RuntimeError):
    """Raised when an AI provider cannot complete a request."""


@dataclass(frozen=True)
class ProviderStatus:
    reachable: bool
    model_available: bool
    detail: str


@dataclass(frozen=True)
class StructuredAIResponse:
    content: dict[str, Any]
    raw_response: dict[str, Any]
    model: str
    created_at: str
    prompt_tokens: int | None
    completion_tokens: int | None
    total_duration_ns: int | None


class AIProvider(Protocol):
    def status(self, model: str) -> ProviderStatus: ...

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any],
        options: dict[str, Any],
    ) -> StructuredAIResponse: ...


class OllamaProvider:
    def __init__(self, base_url: str, timeout_seconds: float = 300) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                timeout=self.timeout_seconds if timeout_seconds is None else timeout_seconds,
                follow_redirects=False,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except httpx.ConnectError as exc:
            raise AIProviderError(
                f"Cannot connect to Ollama at {self.base_url}. Start Ollama and try again."
            ) from exc
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                f"Ollama request timed out after {self.timeout_seconds:g} seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            if len(detail) > 500:
                detail = detail[:500] + "..."
            raise AIProviderError(
                f"Ollama returned HTTP {exc.response.status_code}: {detail or 'no details'}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"Ollama request failed: {exc}") from exc

    def status(self, model: str) -> ProviderStatus:
        try:
            response = self._request(
                "GET",
                "/api/tags",
                timeout_seconds=min(self.timeout_seconds, 5),
            )
            payload = response.json()
        except AIProviderError as exc:
            return ProviderStatus(False, False, str(exc))
        except (json.JSONDecodeError, ValueError) as exc:
            return ProviderStatus(False, False, f"Ollama returned invalid JSON: {exc}")

        models = payload.get("models", []) if isinstance(payload, dict) else []
        names = {
            str(item.get("name") or item.get("model") or "")
            for item in models
            if isinstance(item, dict)
        }
        aliases = {model}
        if ":" not in model:
            aliases.add(f"{model}:latest")
        available = bool(names & aliases)
        if available:
            detail = f"Model '{model}' is available."
        else:
            detail = f"Model '{model}' is not installed. Run: ollama pull {model}"
        return ProviderStatus(True, available, detail)

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any],
        options: dict[str, Any],
    ) -> StructuredAIResponse:
        ollama_options: dict[str, Any] = {}
        if "temperature" in options:
            ollama_options["temperature"] = options["temperature"]
        if "context_length" in options:
            ollama_options["num_ctx"] = options["context_length"]

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "format": response_schema,
            "options": ollama_options,
        }
        if "thinking" in options:
            payload["think"] = bool(options["thinking"])

        response = self._request("POST", "/api/chat", json=payload)
        try:
            raw = response.json()
            message = raw.get("message", {})
            content_text = message.get("content", "")
            content = json.loads(content_text)
        except (AttributeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AIProviderError("Ollama returned an invalid structured response.") from exc

        if not isinstance(raw, dict) or not isinstance(content, dict):
            raise AIProviderError("Ollama structured response must be a JSON object.")

        return StructuredAIResponse(
            content=content,
            raw_response=raw,
            model=str(raw.get("model") or model),
            created_at=str(raw.get("created_at") or ""),
            prompt_tokens=_optional_int(raw.get("prompt_eval_count")),
            completion_tokens=_optional_int(raw.get("eval_count")),
            total_duration_ns=_optional_int(raw.get("total_duration")),
        )


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def create_provider(config: ResolvedAIConfig) -> AIProvider:
    if config.profile.provider == "ollama":
        timeout = config.profile.options.get("timeout_seconds", 300)
        try:
            timeout_seconds = float(timeout)
        except (TypeError, ValueError) as exc:
            raise AIProviderError("AI profile option timeout_seconds must be numeric.") from exc
        return OllamaProvider(config.profile.base_url, timeout_seconds=timeout_seconds)

    raise AIProviderError(
        f"Provider adapter '{config.profile.provider}' is not implemented yet."
    )
