"""Command-line entry point for the agent-and-tool benchmark."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .adjudicator import policy_digest
from .agents import prompt_digest
from .controller import controller_digest
from .gateway import PRIMARY_STRICTNESS, STRICTNESS_LEVELS, gateway_digest
from .runner import run_paired, write_run
from .scenarios import episode_set_digest, generate_episodes


def _freeze() -> dict[str, str]:
    return {
        "episode_set_digest": episode_set_digest(generate_episodes()),
        "policy_digest": policy_digest(),
        "gateway_digest": gateway_digest(),
        "controller_digest": controller_digest(),
        "prompt_digest": prompt_digest(),
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent",
        choices=("scripted", "rules", "openai"),
        default="scripted",
        help="scripted is for CI only and must not be reported.",
    )
    parser.add_argument("--model", default="gpt-4.1", help="Model id for --agent openai.")
    parser.add_argument(
        "--conditions",
        default="B2,B3,B4G,B4",
        help="Comma-separated arms. B1 is not implementable without human participants.",
    )
    parser.add_argument("--replicates", type=int, default=1)
    parser.add_argument(
        "--episodes",
        type=int,
        default=None,
        help="Truncate the frozen set. Smoke tests only; omit for reported runs.",
    )
    parser.add_argument("--strictness", choices=STRICTNESS_LEVELS, default=PRIMARY_STRICTNESS)
    parser.add_argument("--output", default="outputs/run.jsonl")
    parser.add_argument(
        "--print-freeze",
        action="store_true",
        help="Print the preregistration digests and exit without running.",
    )
    args = parser.parse_args(argv)

    if args.print_freeze:
        print(json.dumps(_freeze(), indent=2, sort_keys=True))
        return

    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    if "B1" in conditions:
        parser.error("B1 requires human participants and is not implemented; remove it.")
    if args.agent != "openai" and {"B3", "B4"} & set(conditions):
        print(
            "WARNING: arms B3/B4 are being run with a non-LLM agent. "
            "These results validate the harness only and must not be reported."
        )

    payload = run_paired(
        agent_name=args.agent,
        conditions=conditions,
        replicates=args.replicates,
        episode_limit=args.episodes,
        strictness=args.strictness,
        model=args.model,
    )
    path = write_run(payload, args.output)
    n_ep = len(payload["results"])
    print(f"Wrote {n_ep} condition-episode records to {path.resolve()}")
    print(json.dumps(payload["provenance"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
