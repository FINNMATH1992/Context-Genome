import unittest

from context_genome.engine.models import GardenConfig
from context_genome.engine.world import ContextGenomeWorld


class TokenBudgetTests(unittest.TestCase):
    def test_budget_guard_stops_future_ticks(self):
        world = ContextGenomeWorld(GardenConfig(agent_mode="llm_json", llm_token_budget=10), seed=1)
        world.record_llm_usage({"total_tokens": 10})
        before_tick = world.tick

        snapshot = world.step(1)

        self.assertEqual(world.tick, before_tick)
        self.assertTrue(snapshot["stats"]["llm_token_budget_exhausted"])
        self.assertEqual(snapshot["stats"]["llm_token_budget_remaining"], 0)
        self.assertTrue(any("token budget" in event["message"] for event in snapshot["events"]))

    def test_increasing_budget_reenables_ticks(self):
        world = ContextGenomeWorld(GardenConfig(agent_mode="rule", llm_token_budget=10), seed=1)
        world.record_llm_usage({"total_tokens": 10})

        world.update_config({"llm_token_budget": 20})
        snapshot = world.step(1)

        self.assertFalse(snapshot["stats"]["llm_token_budget_exhausted"])
        self.assertEqual(world.tick, 1)


if __name__ == "__main__":
    unittest.main()
