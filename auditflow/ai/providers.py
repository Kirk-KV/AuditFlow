from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from auditflow.ai.config import ResolvedAIConfig
from auditflow.errors import AuditFlowError


class AIProviderError(AuditFlowError, RuntimeError):
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


class _RemoteHTTPProvider:
    provider_name = "AI provider"

    def __init__(
        self,
        base_url: str,
        *,
        api_key: str | None,
        timeout_seconds: float = 300,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {"content-type": "application/json"}

    def _request(
        self,
        method: str,
        path: str,
        *,
        timeout_seconds: float | None = None,
        **kwargs: Any,
    ) -> httpx.Response:
        headers = {**self._headers(), **kwargs.pop("headers", {})}
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        try:
            response = httpx.request(
                method,
                f"{self.base_url}{path}",
                headers=headers,
                timeout=timeout,
                follow_redirects=False,
                **kwargs,
            )
            response.raise_for_status()
            return response
        except httpx.ConnectError as exc:
            raise AIProviderError(
                f"Cannot connect to {self.provider_name} at {self.base_url}."
            ) from exc
        except httpx.TimeoutException as exc:
            raise AIProviderError(
                f"{self.provider_name} request timed out after {timeout:g} seconds."
            ) from exc
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text.strip()
            if len(detail) > 500:
                detail = detail[:500] + "..."
            raise AIProviderError(
                f"{self.provider_name} returned HTTP {exc.response.status_code}: "
                f"{detail or 'no details'}"
            ) from exc
        except httpx.HTTPError as exc:
            raise AIProviderError(f"{self.provider_name} request failed: {exc}") from exc

    def _model_status(self, model: str) -> ProviderStatus:
        try:
            response = self._request(
                "GET",
                "/models",
                timeout_seconds=min(self.timeout_seconds, 5),
            )
            payload = response.json()
        except AIProviderError as exc:
            return ProviderStatus(False, False, str(exc))
        except (json.JSONDecodeError, ValueError) as exc:
            return ProviderStatus(
                False,
                False,
                f"{self.provider_name} returned invalid JSON: {exc}",
            )

        models = payload.get("data", []) if isinstance(payload, dict) else []
        names = {
            str(item.get("id") or item.get("name") or "")
            for item in models
            if isinstance(item, dict)
        }
        available = model in names
        detail = (
            f"Model '{model}' is available."
            if available
            else f"Model '{model}' is not available to the configured API key."
        )
        return ProviderStatus(True, available, detail)


class OpenAICompatibleProvider(_RemoteHTTPProvider):
    provider_name = "OpenAI-compatible provider"

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.api_key:
            headers["authorization"] = f"Bearer {self.api_key}"
        return headers

    def status(self, model: str) -> ProviderStatus:
        return self._model_status(model)

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any],
        options: dict[str, Any],
    ) -> StructuredAIResponse:
        response_format = str(options.get("response_format") or "json_schema")
        if response_format == "json_schema":
            format_payload: dict[str, Any] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "auditflow_response",
                    "strict": True,
                    "schema": _portable_response_schema(response_schema),
                },
            }
        elif response_format == "json_object":
            format_payload = {"type": "json_object"}
        else:
            raise AIProviderError(
                "OpenAI-compatible option response_format must be "
                "'json_schema' or 'json_object'."
            )

        payload: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "response_format": format_payload,
        }
        for option in ("temperature", "max_tokens", "max_completion_tokens"):
            if option in options:
                payload[option] = options[option]
        if "reasoning_effort" in options:
            payload["reasoning_effort"] = options["reasoning_effort"]
        if "enable_thinking" in options:
            payload["enable_thinking"] = bool(options["enable_thinking"])

        response = self._request("POST", "/chat/completions", json=payload)
        try:
            raw = response.json()
            choices = raw.get("choices", [])
            message = choices[0].get("message", {})
            content = json.loads(_message_text(message.get("content")))
            usage = raw.get("usage", {})
        except (AttributeError, IndexError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AIProviderError(
                "OpenAI-compatible provider returned an invalid structured response."
            ) from exc

        if not isinstance(raw, dict) or not isinstance(content, dict):
            raise AIProviderError(
                "OpenAI-compatible structured response must be a JSON object."
            )

        return StructuredAIResponse(
            content=content,
            raw_response=raw,
            model=str(raw.get("model") or model),
            created_at=_created_at(raw.get("created")),
            prompt_tokens=_optional_int(usage.get("prompt_tokens")),
            completion_tokens=_optional_int(usage.get("completion_tokens")),
            total_duration_ns=None,
        )


class AnthropicProvider(_RemoteHTTPProvider):
    provider_name = "Anthropic"

    def _headers(self) -> dict[str, str]:
        headers = super()._headers()
        if self.api_key:
            headers["x-api-key"] = self.api_key
        headers["anthropic-version"] = "2023-06-01"
        return headers

    def status(self, model: str) -> ProviderStatus:
        return self._model_status(model)

    def generate_structured(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
        response_schema: dict[str, Any],
        options: dict[str, Any],
    ) -> StructuredAIResponse:
        max_tokens = options.get("max_tokens", 4096)
        try:
            max_tokens = int(max_tokens)
        except (TypeError, ValueError) as exc:
            raise AIProviderError(
                "Anthropic profile option max_tokens must be an integer."
            ) from exc
        if max_tokens <= 0:
            raise AIProviderError(
                "Anthropic profile option max_tokens must be greater than zero."
            )

        payload: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_prompt}],
            "output_config": {
                "format": {
                    "type": "json_schema",
                    "schema": _portable_response_schema(response_schema),
                }
            },
        }
        if "temperature" in options:
            payload["temperature"] = options["temperature"]

        response = self._request("POST", "/messages", json=payload)
        try:
            raw = response.json()
            blocks = raw.get("content", [])
            content_text = "".join(
                str(block.get("text") or "")
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
            content = json.loads(content_text)
            usage = raw.get("usage", {})
        except (AttributeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise AIProviderError(
                "Anthropic returned an invalid structured response."
            ) from exc

        if not isinstance(raw, dict) or not isinstance(content, dict):
            raise AIProviderError("Anthropic structured response must be a JSON object.")

        return StructuredAIResponse(
            content=content,
            raw_response=raw,
            model=str(raw.get("model") or model),
            created_at=str(raw.get("created_at") or ""),
            prompt_tokens=_optional_int(usage.get("input_tokens")),
            completion_tokens=_optional_int(usage.get("output_tokens")),
            total_duration_ns=None,
        )


def _portable_response_schema(value: Any) -> Any:
    if isinstance(value, list):
        return [_portable_response_schema(item) for item in value]
    if not isinstance(value, dict):
        return value

    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in {"allOf", "if", "then", "else"}:
            continue
        if key == "const":
            result["enum"] = [_portable_response_schema(item)]
            continue
        result[key] = _portable_response_schema(item)
    return result


def _message_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(
            str(item.get("text") or "")
            for item in value
            if isinstance(item, dict)
        )
    raise ValueError("message content is not text")


def _created_at(value: Any) -> str:
    timestamp = _optional_int(value)
    if timestamp is None:
        return ""
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _optional_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def create_provider(config: ResolvedAIConfig) -> AIProvider:
    timeout = config.profile.options.get("timeout_seconds", 300)
    try:
        timeout_seconds = float(timeout)
    except (TypeError, ValueError) as exc:
        raise AIProviderError("AI profile option timeout_seconds must be numeric.") from exc
    if timeout_seconds <= 0:
        raise AIProviderError(
            "AI profile option timeout_seconds must be greater than zero."
        )

    if config.profile.provider == "ollama":
        return OllamaProvider(config.profile.base_url, timeout_seconds=timeout_seconds)

    api_key = None
    if config.profile.api_key_env:
        api_key = str(os.environ.get(config.profile.api_key_env) or "").strip() or None
        if api_key is None:
            raise AIProviderError(
                "Required API key environment variable is missing: "
                f"{config.profile.api_key_env}"
            )

    if config.profile.provider == "openai_compatible":
        return OpenAICompatibleProvider(
            config.profile.base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

    if config.profile.provider == "anthropic":
        if not config.profile.api_key_env:
            raise AIProviderError(
                "Anthropic profiles must define api_key_env in company policy."
            )
        return AnthropicProvider(
            config.profile.base_url,
            api_key=api_key,
            timeout_seconds=timeout_seconds,
        )

    raise AIProviderError(
        f"Provider adapter '{config.profile.provider}' is not implemented yet."
    )
