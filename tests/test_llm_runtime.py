import os
import unittest
from unittest.mock import patch

from context_genome.agents.drivers import llm_runtime_status, update_llm_runtime_overrides


class LlmRuntimeTests(unittest.TestCase):
    def setUp(self):
        update_llm_runtime_overrides(clear_api_key=True, base_url="")

    def tearDown(self):
        update_llm_runtime_overrides(clear_api_key=True, base_url="")

    def test_context_genome_variables_work_without_skill_garden_aliases(self):
        env = {
            "CONTEXT_GENOME_LLM_API_KEY": "test-key",
            "CONTEXT_GENOME_LLM_MODEL": "deepseek-v4-flash",
            "CONTEXT_GENOME_LLM_BASE_URL": "https://api.deepseek.com",
            "CONTEXT_GENOME_LLM_DISABLE_THINKING": "1",
            "SKILL_GARDEN_LLM_API_KEY": "",
            "SKILL_GARDEN_LLM_MODEL": "",
            "SKILL_GARDEN_LLM_BASE_URL": "",
            "OPENAI_API_KEY": "",
            "OPENAI_MODEL": "",
            "OPENAI_BASE_URL": "",
        }

        with patch.dict(os.environ, env, clear=True):
            status = llm_runtime_status()

        self.assertTrue(status["configured"])
        self.assertEqual(status["missing"], [])
        self.assertEqual(status["model"], "deepseek-v4-flash")
        self.assertEqual(status["base_url"], "https://api.deepseek.com")
        self.assertTrue(status["has_api_key"])
        self.assertTrue(status["disable_thinking"])

    def test_runtime_override_key_is_hidden_from_status(self):
        with patch.dict(os.environ, {}, clear=True):
            status = update_llm_runtime_overrides(
                api_key="runtime-key",
                base_url="https://runtime.example/v1",
                config_model="runtime-model",
            )

        self.assertTrue(status["configured"])
        self.assertTrue(status["has_api_key"])
        self.assertEqual(status["base_url"], "https://runtime.example/v1")
        self.assertEqual(status["model"], "runtime-model")
        self.assertNotIn("api_key", status)
        self.assertNotIn("runtime-key", repr(status))


if __name__ == "__main__":
    unittest.main()
