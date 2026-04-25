from __future__ import annotations

import unittest

from scripts.doctor import (
    ServerProbe,
    check_port,
    check_server_health,
    default_port,
    health_probe_host,
    parse_dotenv_text,
    runtime_env_summary,
)


class DoctorTests(unittest.TestCase):
    def test_runtime_env_summary_prefers_project_variables(self) -> None:
        summary = runtime_env_summary(
            {
                "CONTEXT_GENOME_LLM_API_KEY": "context-key",
                "SKILL_GARDEN_LLM_API_KEY": "legacy-key",
                "OPENAI_API_KEY": "openai-key",
                "CONTEXT_GENOME_LLM_MODEL": "context-model",
                "OPENAI_MODEL": "openai-model",
                "CONTEXT_GENOME_LLM_BASE_URL": "https://context.example/v1",
                "OPENAI_BASE_URL": "https://openai.example/v1",
            }
        )
        self.assertTrue(summary["has_api_key"])
        self.assertEqual(summary["api_key_source"], "CONTEXT_GENOME_LLM_API_KEY")
        self.assertEqual(summary["model"], "context-model")
        self.assertEqual(summary["base_url"], "https://context.example/v1")

    def test_runtime_env_summary_does_not_expose_secret_value(self) -> None:
        secret = "secret-value-that-should-not-appear"
        summary = runtime_env_summary({"OPENAI_API_KEY": secret})
        self.assertTrue(summary["has_api_key"])
        self.assertNotIn(secret, {str(value) for value in summary.values()})

    def test_parse_dotenv_text_handles_quotes_and_comments(self) -> None:
        values = parse_dotenv_text(
            """
            # local settings
            CONTEXT_GENOME_PORT=8777
            CONTEXT_GENOME_LLM_MODEL="deepseek-v4-flash"
            BAD-NAME=ignored
            """
        )
        self.assertEqual(values["CONTEXT_GENOME_PORT"], "8777")
        self.assertEqual(values["CONTEXT_GENOME_LLM_MODEL"], "deepseek-v4-flash")
        self.assertNotIn("BAD-NAME", values)

    def test_default_port_falls_back_on_invalid_env(self) -> None:
        self.assertEqual(default_port({"CONTEXT_GENOME_PORT": "8777"}), 8777)
        self.assertEqual(default_port({"CONTEXT_GENOME_PORT": "not-a-port"}), 8765)

    def test_health_probe_host_uses_loopback_for_wildcard_bind(self) -> None:
        self.assertEqual(health_probe_host("0.0.0.0"), "127.0.0.1")
        self.assertEqual(health_probe_host("127.0.0.1"), "127.0.0.1")

    def test_port_check_accepts_running_context_genome_server(self) -> None:
        health = {"ok": True, "product": "Context Genome", "version": "0.1.0", "tick": 3}
        server_check = check_server_health(ServerProbe(health), 8765)
        port_check = check_port("127.0.0.1", 8765, health)
        self.assertEqual(server_check.status, "ok")
        self.assertEqual(port_check.status, "ok")
        self.assertIn("Context Genome", port_check.detail)

    def test_server_probe_reports_sandbox_permission_limits(self) -> None:
        check = check_server_health(ServerProbe(None, "[Errno 1] Operation not permitted"), 8765)
        self.assertEqual(check.status, "warn")
        self.assertIn("probe unavailable", check.detail)


if __name__ == "__main__":
    unittest.main()
