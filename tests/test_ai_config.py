from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import yaml

from auditflow.ai.config import AIConfigError, resolve_ai_config


class AIConfigTests(unittest.TestCase):
    def make_project(self, ai_settings: dict | None = None) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        project_root = Path(temp_dir.name)
        admin_dir = project_root / "00_admin"
        admin_dir.mkdir()
        (project_root / "initial_data.yml").write_text("audit: {}\n", encoding="utf-8")
        if ai_settings is not None:
            (admin_dir / "ai.yml").write_text(
                yaml.safe_dump({"ai": ai_settings}, sort_keys=False),
                encoding="utf-8",
            )
        return project_root

    def write_policy(self, project_root: Path, policy: dict) -> Path:
        path = project_root / "company-ai-policy.yml"
        path.write_text(yaml.safe_dump(policy, sort_keys=False), encoding="utf-8")
        return path

    def test_secure_defaults_use_local_ollama(self) -> None:
        config = resolve_ai_config(self.make_project(), environ={})

        self.assertFalse(config.enabled)
        self.assertEqual(config.profile.name, "local_ollama")
        self.assertEqual(config.profile.data_boundary, "local_machine")
        self.assertEqual(config.model, "qwen3:8b")
        self.assertFalse(config.rules.allow_raw_evidence)
        self.assertTrue(config.rules.require_preflight)

    def test_company_policy_controls_destination_and_allowed_model(self) -> None:
        project_root = self.make_project(
            {
                "enabled": True,
                "profile": "corporate_llm",
                "model": "audit-reviewer",
                "project_classification": "confidential",
                "output_language": "auto",
            }
        )
        policy_path = self.write_policy(
            project_root,
            {
                "schema_version": 1,
                "policy_id": "company-policy-1",
                "default_profile": "corporate_llm",
                "profiles": {
                    "corporate_llm": {
                        "provider": "openai_compatible",
                        "base_url": "https://llm.company.test/v1",
                        "api_key_env": "COMPANY_LLM_API_KEY",
                        "default_model": "audit-reviewer",
                        "allowed_models": ["audit-reviewer"],
                        "data_boundary": "company_network",
                        "allowed_classifications": ["internal", "confidential"],
                    }
                },
                "rules": {"allow_external_providers": False},
            },
        )

        config = resolve_ai_config(
            project_root,
            environ={
                "AUDITFLOW_AI_POLICY": str(policy_path),
                "COMPANY_LLM_API_KEY": "secret-value",
            },
        )

        self.assertEqual(config.policy_id, "company-policy-1")
        self.assertEqual(config.profile.base_url, "https://llm.company.test/v1")
        self.assertTrue(config.api_key_configured)

    def test_project_cannot_select_disallowed_model(self) -> None:
        project_root = self.make_project(
            {
                "profile": "corporate_llm",
                "model": "unapproved-model",
                "project_classification": "internal",
            }
        )
        policy_path = self.write_policy(
            project_root,
            {
                "schema_version": 1,
                "policy_id": "company-policy-1",
                "default_profile": "corporate_llm",
                "profiles": {
                    "corporate_llm": {
                        "provider": "openai_compatible",
                        "base_url": "https://llm.company.test/v1",
                        "default_model": "approved-model",
                        "allowed_models": ["approved-model"],
                        "data_boundary": "company_network",
                        "allowed_classifications": ["internal"],
                    }
                },
            },
        )

        with self.assertRaisesRegex(AIConfigError, "not allowed"):
            resolve_ai_config(
                project_root,
                environ={"AUDITFLOW_AI_POLICY": str(policy_path)},
            )

    def test_project_cannot_override_provider_or_destination(self) -> None:
        project_root = self.make_project(
            {
                "profile": "local_ollama",
                "provider": "openai_compatible",
                "base_url": "https://example.test/v1",
            }
        )

        with self.assertRaisesRegex(AIConfigError, "Unknown project ai field"):
            resolve_ai_config(project_root, environ={})

    def test_external_profile_requires_explicit_policy_permission(self) -> None:
        project_root = self.make_project(
            {
                "profile": "external_llm",
                "project_classification": "public",
            }
        )
        policy_path = self.write_policy(
            project_root,
            {
                "schema_version": 1,
                "policy_id": "company-policy-1",
                "default_profile": "external_llm",
                "profiles": {
                    "external_llm": {
                        "provider": "openai_compatible",
                        "base_url": "https://api.example.test/v1",
                        "default_model": "approved-model",
                        "allowed_models": ["approved-model"],
                        "data_boundary": "external",
                        "allowed_classifications": ["public"],
                    }
                },
            },
        )

        with self.assertRaisesRegex(AIConfigError, "does not allow external providers"):
            resolve_ai_config(
                project_root,
                environ={"AUDITFLOW_AI_POLICY": str(policy_path)},
            )


if __name__ == "__main__":
    unittest.main()
