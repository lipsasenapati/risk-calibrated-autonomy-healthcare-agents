from __future__ import annotations

import argparse
from pathlib import Path

from .agents import OpenAIResponsesAgent, ScriptedAgent
from .runner import BenchmarkRunner


def main() -> None:
    p = argparse.ArgumentParser(description="Run the synthetic agent-and-tool benchmark.")
    p.add_argument("--agent", choices=("scripted", "openai"), default="scripted")
    p.add_argument("--model", default="gpt-5")
    p.add_argument("--episodes", type=int, default=None)
    p.add_argument("--conditions", default="B3,B4")
    p.add_argument("--output", default="live_benchmark_results.jsonl")
    a = p.parse_args()
    factory = ScriptedAgent if a.agent == "scripted" else lambda: OpenAIResponsesAgent(a.model)
    results = BenchmarkRunner(factory).run(a.conditions.split(","), a.episodes)
    BenchmarkRunner.write_jsonl(results, a.output)
    print(f"Wrote {len(results)} condition-episode results to {Path(a.output).resolve()}")


if __name__ == "__main__": main()
