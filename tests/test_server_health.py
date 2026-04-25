from __future__ import annotations

import unittest
from unittest.mock import patch

from context_genome import __version__
from context_genome.engine.models import GardenConfig
from context_genome.engine.world import ContextGenomeWorld
from context_genome.server import _health_payload


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


if __name__ == "__main__":
    unittest.main()
