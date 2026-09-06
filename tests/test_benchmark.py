import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from risk_benchmark.runner import BenchmarkRunner
from risk_benchmark.scenarios import generate_episodes


class BenchmarkTests(unittest.TestCase):
    def test_governed_agent_blocks_stale_outreach(self):
        episode = next(x for x in generate_episodes() if not x.data_fresh)
        result = BenchmarkRunner().run_episode(episode, "B4")
        self.assertTrue(any(x["disposition"] == "block" for x in result["gateway_decisions"]))
        self.assertFalse(result["unsafe_action"])

    def test_ungoverned_agent_executes_the_same_unsafe_write(self):
        episode = next(x for x in generate_episodes() if not x.data_fresh)
        result = BenchmarkRunner().run_episode(episode, "B3")
        self.assertTrue(result["unsafe_action"])

    def test_jsonl_provenance_is_written(self):
        results = BenchmarkRunner().run(episodes=3)
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / "results.jsonl"
            BenchmarkRunner.write_jsonl(results, out)
            self.assertEqual(len(out.read_text().splitlines()), 6)
