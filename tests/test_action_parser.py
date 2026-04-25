import unittest

from context_genome.agents.action_parser import parse_action_text


class ActionParserTests(unittest.TestCase):
    def test_parses_fenced_json_action(self):
        result = parse_action_text(
            "org_1",
            """```json
{"action":"move","target_cell":[3,4],"energy_bid":2.5,"note":"seek energy"}
```""",
        )

        self.assertTrue(result.ok)
        self.assertEqual(result.action.action, "move")
        self.assertEqual(result.action.actor_id, "org_1")
        self.assertEqual(result.action.target_cell, (3, 4))
        self.assertEqual(result.action.energy_bid, 2.5)

    def test_invalid_json_falls_back_to_wait(self):
        result = parse_action_text("org_2", "{not json")

        self.assertFalse(result.ok)
        self.assertEqual(result.action.action, "wait")
        self.assertIn("parse failure", result.action.note)

    def test_unknown_action_falls_back_to_wait(self):
        result = parse_action_text("org_3", '{"action":"teleport"}')

        self.assertFalse(result.ok)
        self.assertEqual(result.action.action, "wait")
        self.assertIn("unknown action", result.error)


if __name__ == "__main__":
    unittest.main()
