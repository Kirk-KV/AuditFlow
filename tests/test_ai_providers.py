from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from auditflow.ai.providers import (
    AIProviderError,
    AnthropicProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    create_provider,
)


class OllamaProviderTests(unittest.TestCase):
    @patch("auditflow.ai.providers.httpx.request")
    def test_status_checks_installed_model(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = {"models": [{"name": "qwen3:8b"}]}
        response.raise_for_status.return_value = None
        request.return_value = response

        status = OllamaProvider("http://127.0.0.1:11434").status("qwen3:8b")

        self.assertTrue(status.reachable)
        self.assertTrue(status.model_available)
        self.assertEqual(request.call_args.kwargs["timeout"], 5)
        self.assertFalse(request.call_args.kwargs["follow_redirects"])

    @patch("auditflow.ai.providers.httpx.request")
    def test_structured_request_uses_schema_and_profile_options(self, request: Mock) -> None:
        structured_content = {
            "observation_needed": False,
            "assessment": "Insufficient support.",
            "draft": None,
            "missing_information": ["Confirmed exception details"],
        }
        response = Mock()
        response.json.return_value = {
            "model": "qwen3:8b",
            "created_at": "2026-07-20T12:00:00Z",
            "message": {"content": json.dumps(structured_content)},
            "prompt_eval_count": 100,
            "eval_count": 20,
        }
        response.raise_for_status.return_value = None
        request.return_value = response
        schema = {"type": "object"}

        result = OllamaProvider("http://127.0.0.1:11434").generate_structured(
            model="qwen3:8b",
            system_prompt="System",
            user_prompt="User",
            response_schema=schema,
            options={"temperature": 0, "context_length": 8192, "thinking": False},
        )

        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload["format"], schema)
        self.assertEqual(payload["options"]["temperature"], 0)
        self.assertEqual(payload["options"]["num_ctx"], 8192)
        self.assertFalse(payload["think"])
        self.assertEqual(result.content, structured_content)


class OpenAICompatibleProviderTests(unittest.TestCase):
    @patch("auditflow.ai.providers.httpx.request")
    def test_status_checks_model_with_bearer_auth(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = {"data": [{"id": "gpt-approved"}]}
        response.raise_for_status.return_value = None
        request.return_value = response

        status = OpenAICompatibleProvider(
            "https://api.openai.com/v1",
            api_key="test-key",
        ).status("gpt-approved")

        self.assertTrue(status.reachable)
        self.assertTrue(status.model_available)
        self.assertEqual(
            request.call_args.args,
            ("GET", "https://api.openai.com/v1/models"),
        )
        self.assertEqual(
            request.call_args.kwargs["headers"]["authorization"],
            "Bearer test-key",
        )

    @patch("auditflow.ai.providers.httpx.request")
    def test_structured_request_uses_json_schema_and_usage(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = {
            "model": "gpt-approved",
            "created": 1_700_000_000,
            "choices": [
                {"message": {"content": json.dumps({"result": "supported"})}}
            ],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20},
        }
        response.raise_for_status.return_value = None
        request.return_value = response
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["result"],
            "properties": {"result": {"type": "string", "const": "supported"}},
            "allOf": [{"if": {"properties": {"result": {"const": "supported"}}}}],
        }

        result = OpenAICompatibleProvider(
            "https://api.openai.com/v1",
            api_key="test-key",
        ).generate_structured(
            model="gpt-approved",
            system_prompt="System",
            user_prompt="Return JSON",
            response_schema=schema,
            options={"temperature": 0},
        )

        payload = request.call_args.kwargs["json"]
        transported = payload["response_format"]["json_schema"]["schema"]
        self.assertEqual(payload["response_format"]["type"], "json_schema")
        self.assertTrue(payload["response_format"]["json_schema"]["strict"])
        self.assertNotIn("allOf", transported)
        self.assertEqual(
            transported["properties"]["result"]["enum"],
            ["supported"],
        )
        self.assertEqual(result.content, {"result": "supported"})
        self.assertEqual(result.prompt_tokens, 100)
        self.assertEqual(result.completion_tokens, 20)

    @patch("auditflow.ai.providers.httpx.request")
    def test_json_object_mode_supports_other_compatible_endpoints(
        self,
        request: Mock,
    ) -> None:
        response = Mock()
        response.json.return_value = {
            "model": "approved-model",
            "choices": [{"message": {"content": '{"result": "ok"}'}}],
        }
        response.raise_for_status.return_value = None
        request.return_value = response

        OpenAICompatibleProvider(
            "https://llm.company.test/v1",
            api_key=None,
        ).generate_structured(
            model="approved-model",
            system_prompt="Return JSON",
            user_prompt="User",
            response_schema={"type": "object"},
            options={"response_format": "json_object"},
        )

        self.assertEqual(
            request.call_args.kwargs["json"]["response_format"],
            {"type": "json_object"},
        )


class AnthropicProviderTests(unittest.TestCase):
    @patch("auditflow.ai.providers.httpx.request")
    def test_status_checks_model_with_anthropic_headers(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = {"data": [{"id": "claude-approved"}]}
        response.raise_for_status.return_value = None
        request.return_value = response

        status = AnthropicProvider(
            "https://api.anthropic.com/v1",
            api_key="test-key",
        ).status("claude-approved")

        self.assertTrue(status.reachable)
        self.assertTrue(status.model_available)
        headers = request.call_args.kwargs["headers"]
        self.assertEqual(headers["x-api-key"], "test-key")
        self.assertEqual(headers["anthropic-version"], "2023-06-01")

    @patch("auditflow.ai.providers.httpx.request")
    def test_structured_request_uses_output_config_and_usage(self, request: Mock) -> None:
        response = Mock()
        response.json.return_value = {
            "model": "claude-approved",
            "content": [
                {"type": "text", "text": json.dumps({"result": "supported"})}
            ],
            "usage": {"input_tokens": 120, "output_tokens": 30},
        }
        response.raise_for_status.return_value = None
        request.return_value = response
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["result"],
            "properties": {"result": {"type": "string"}},
        }

        result = AnthropicProvider(
            "https://api.anthropic.com/v1",
            api_key="test-key",
        ).generate_structured(
            model="claude-approved",
            system_prompt="System",
            user_prompt="User",
            response_schema=schema,
            options={"max_tokens": 2048, "temperature": 0},
        )

        payload = request.call_args.kwargs["json"]
        self.assertEqual(payload["system"], "System")
        self.assertEqual(payload["max_tokens"], 2048)
        self.assertEqual(
            payload["output_config"]["format"]["type"],
            "json_schema",
        )
        self.assertEqual(result.content, {"result": "supported"})
        self.assertEqual(result.prompt_tokens, 120)
        self.assertEqual(result.completion_tokens, 30)


class ProviderFactoryTests(unittest.TestCase):
    @patch.dict("os.environ", {"OPENAI_API_KEY": "test-key"}, clear=True)
    def test_creates_openai_compatible_provider_from_profile(self) -> None:
        config = SimpleNamespace(
            profile=SimpleNamespace(
                provider="openai_compatible",
                base_url="https://api.openai.com/v1",
                api_key_env="OPENAI_API_KEY",
                options={},
            )
        )

        provider = create_provider(config)

        self.assertIsInstance(provider, OpenAICompatibleProvider)

    @patch.dict("os.environ", {}, clear=True)
    def test_anthropic_provider_requires_configured_key(self) -> None:
        config = SimpleNamespace(
            profile=SimpleNamespace(
                provider="anthropic",
                base_url="https://api.anthropic.com/v1",
                api_key_env="ANTHROPIC_API_KEY",
                options={},
            )
        )

        with self.assertRaisesRegex(AIProviderError, "ANTHROPIC_API_KEY"):
            create_provider(config)


if __name__ == "__main__":
    unittest.main()
