from __future__ import annotations

import json
import unittest
from unittest.mock import Mock, patch

from auditflow.ai.providers import OllamaProvider


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


if __name__ == "__main__":
    unittest.main()
