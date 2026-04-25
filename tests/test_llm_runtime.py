import os
import unittest
from unittest.mock import patch

from context_genome.agents.drivers import llm_runtime_status


class LlmRuntimeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
