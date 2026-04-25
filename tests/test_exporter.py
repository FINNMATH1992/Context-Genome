import tempfile
import unittest
from pathlib import Path

from context_genome.engine.exporter import list_runs, load_run_summary, save_run
from context_genome.engine.models import GardenConfig
from context_genome.engine.world import ContextGenomeWorld


class ExporterTests(unittest.TestCase):
    def test_summary_uses_relative_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "runs"
            world = ContextGenomeWorld(GardenConfig(agent_mode="rule", initial_orgs=1), seed=7)

            summary = save_run(world, output_root)

            for path_text in summary["files"].values():
                self.assertFalse(Path(path_text).is_absolute(), path_text)
                self.assertTrue(path_text.startswith("runs/"), path_text)

    def test_list_runs_exposes_comparison_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_root = Path(tmp) / "runs"
            world = ContextGenomeWorld(GardenConfig(agent_mode="rule", initial_orgs=1), seed=7)

            summary = save_run(world, output_root)
            rows = list_runs(output_root)
            loaded = load_run_summary(output_root, summary["run_id"])

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["run_id"], summary["run_id"])
            self.assertIn("lineages", rows[0])
            self.assertIn("stats", rows[0])
            self.assertEqual(loaded["run_id"], summary["run_id"])


if __name__ == "__main__":
    unittest.main()
