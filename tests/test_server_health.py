from __future__ import annotations

import unittest
from unittest.mock import patch

from context_genome import __version__
from context_genome.engine.models import GardenConfig, VFile
from context_genome.engine.world import ContextGenomeWorld
from context_genome.server import _build_llm_inspector_payload, _health_payload


class ServerHealthTests(unittest.TestCase):
    def test_health_payload_is_safe_and_operational(self) -> None:
        world = ContextGenomeWorld(GardenConfig(agent_mode="rule", initial_orgs=2), seed=7)

        secret = "secret-health-value-that-should-not-appear"
        with patch.dict(
            "os.environ",
            {"OPENAI_API_KEY": secret, "OPENAI_MODEL": "health-model"},
            clear=True,
        ):
            payload = _health_payload(world)

        self.assertTrue(payload["ok"])
        self.assertEqual(payload["product"], "Context Genome")
        self.assertEqual(payload["version"], __version__)
        self.assertEqual(payload["agent_mode"], "rule")
        self.assertIn("llm_runtime", payload)
        self.assertTrue(payload["llm_runtime"]["has_api_key"])
        self.assertNotIn(secret, repr(payload))
        self.assertNotIn("Bearer", repr(payload))

    def test_llm_inspector_exposes_prompt_response_and_parsed_action(self) -> None:
        world = ContextGenomeWorld(GardenConfig(agent_mode="rule", initial_orgs=1), seed=7)
        org = next(iter(world.orgs.values()))
        org.files["last_prompt.txt"] = VFile("last_prompt.txt", '[{"role":"user","content":"observe"}]')
        org.files["last_llm_response.json"] = VFile(
            "last_llm_response.json",
            '{"content":"{\\"action\\":\\"harvest\\",\\"energy_bid\\":1}",'
            '"usage":{"total_tokens":12,"prompt_tokens":9,"completion_tokens":3}}',
        )

        payload = _build_llm_inspector_payload(world, org.org_id)

        self.assertIsNotNone(payload)
        self.assertEqual(payload["org_id"], org.org_id)
        self.assertEqual(payload["usage"]["total_tokens"], 12)
        self.assertEqual(payload["parsed_action"]["action"], "harvest")
        self.assertIn("observe", payload["prompt"])


if __name__ == "__main__":
    unittest.main()
