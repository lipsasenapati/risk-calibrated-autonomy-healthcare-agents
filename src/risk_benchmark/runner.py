"""Arm execution, endpoint capture, and provenance logging.

Arms
----
``B2``
    Deterministic rules, no language model, no gateway.
``B3``
    Live agent with full tool access and no external authorization layer.
``B4``
    The same live agent, same prompt, same tools, same replicate index, with
    the Action Safety Gateway and Dynamic Autonomy Controller interposed.

Arm ``B1`` (manual workflow) is **not** implemented. It cannot be measured
without human participants, and simulating it would reintroduce the assumed
effect sizes this harness exists to eliminate.

The B3/B4 contrast is the only comparison that isolates governance, and
:func:`run_paired` enforces that the two arms are constructed identically.
"""
from __future__ import annotations

import json
import platform
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

from .adjudicator import (
    POLICY_VERSION,
    PROHIBITED_TOOLS,
    WRITE_TOOLS,
    BlindTrace,
    ExecutedAction,
    adjudicate,
    policy_digest,
)
from .agents import AGENT_REGISTRY, Agent, PROMPT_VERSION, prompt_digest
from .controller import DynamicAutonomyController, EpisodeSignals, controller_digest
from .gateway import (
    ALLOW,
    BLOCK,
    Decision,
    GATEWAY_VERSION,
    PRIMARY_STRICTNESS,
    REQUIRE_CONFIRMATION,
    ActionSafetyGateway,
    gateway_digest,
)
from .scenarios import Episode, episode_set_digest, generate_episodes
from .tools import HUMAN_EFFORT, ToolEnvironment

#: Arms in which the Action Safety Gateway is interposed.
GOVERNED_ARMS = frozenset({"B4", "B4G"})
#: Arms in which the Dynamic Autonomy Controller is active. ``B4G`` is a
#: prespecified mechanism-decomposition arm: gateway only, no controller, so the
#: contribution of each component can be separated rather than inferred.
CONTROLLED_ARMS = frozenset({"B4"})
LLM_ARMS = frozenset({"B3", "B4", "B4G"})
ALL_ARMS = ("B2", "B3", "B4G", "B4")

#: Prespecified token prices (USD per 1M tokens) used for the cost endpoint,
#: keyed by model snapshot prefix. Recorded so the cost analysis is
#: reproducible independent of later repricing. A single flat price was
#: previously used regardless of which model was actually run, which
#: overstated cost for any model cheaper than gpt-4.1 (e.g. by 5x for
#: gpt-4.1-mini). Add new snapshots here as they are used.
MODEL_TOKEN_PRICES_USD_PER_M = {
    "gpt-4.1-nano": {"input": 0.10, "output": 0.40},
    "gpt-4.1-mini": {"input": 0.40, "output": 1.60},
    "gpt-4.1": {"input": 2.00, "output": 8.00},
}
#: Fallback for non-LLM arms (B2), where token usage is always zero and the
#: price table is therefore inert.
TOKEN_PRICES_USD_PER_M = MODEL_TOKEN_PRICES_USD_PER_M["gpt-4.1"]
#: Nominal loaded cost of one unit of human coordinator effort (USD).
HUMAN_EFFORT_COST_USD = 12.50


def token_prices_for_model(model: str) -> dict[str, float]:
    """Resolve the USD-per-1M-token price for a pinned model snapshot.

    Matches the longest known prefix first, so ``gpt-4.1-mini-2025-04-14``
    resolves to the mini price rather than the generic ``gpt-4.1`` price.
    """
    for prefix in sorted(MODEL_TOKEN_PRICES_USD_PER_M, key=len, reverse=True):
        if model.startswith(prefix):
            return MODEL_TOKEN_PRICES_USD_PER_M[prefix]
    raise ValueError(
        f"No known token price for model {model!r}; add it to "
        "MODEL_TOKEN_PRICES_USD_PER_M before running, so cost is not silently "
        "misreported under the wrong price table."
    )

MAX_STEPS = 8


@dataclass
class EpisodeResult:
    episode_id: str
    condition: str
    replicate: int
    # design variables
    strata: dict[str, Any]
    perturbation: str | None
    # adjudicated endpoints (condition-blinded)
    unsafe_action: bool
    unsafe_reasons: list[str]
    task_success: bool
    required_action: str
    escalation_appropriate: bool
    prohibited_action_attempted: bool
    # operational endpoints
    reported_confidence: float | None
    time_to_action_min: float
    human_effort_units: float
    tool_error_count: int
    reliable_tool_use: bool
    autonomous_writes: int
    confirmations_required: int
    blocked_proposals: int
    autonomy_state: str
    autonomy_transition: dict[str, Any] | None
    gateway_decisions: list[dict[str, Any]]
    executed_tools: list[str]
    proposed_tools: list[str]
    usage: dict[str, int]
    cost_usd: float
    audit: list[dict[str, Any]] = field(default_factory=list)


def _terminal_confidence(audit: list[dict[str, Any]]) -> float | None:
    """Confidence attached to the last decision action, clipped to [0,1]."""
    for entry in reversed(audit):
        value = entry.get("arguments", {}).get("confidence")
        if isinstance(value, (int, float)):
            return max(0.0, min(1.0, float(value)))
    return None


def _episode_cost(
    usage: dict[str, int], human_effort: float, token_prices: dict[str, float]
) -> float:
    tokens = (
        usage.get("input_tokens", 0) / 1e6 * token_prices["input"]
        + usage.get("output_tokens", 0) / 1e6 * token_prices["output"]
    )
    return round(tokens + human_effort * HUMAN_EFFORT_COST_USD, 4)


class BenchmarkRunner:
    """Executes episodes under a single arm."""

    def __init__(
        self,
        agent_factory: Callable[..., Agent],
        strictness: str = PRIMARY_STRICTNESS,
        max_steps: int = MAX_STEPS,
        token_prices: dict[str, float] | None = None,
    ):
        self.agent_factory = agent_factory
        self.strictness = strictness
        self.max_steps = max_steps
        self.token_prices = token_prices or TOKEN_PRICES_USD_PER_M

    # -- single episode ----------------------------------------------------- #

    def run_episode(
        self,
        episode: Episode,
        condition: str,
        replicate: int = 0,
        controller: DynamicAutonomyController | None = None,
    ) -> EpisodeResult:
        governed = condition in GOVERNED_ARMS
        agent = self.agent_factory(replicate=replicate)
        env = ToolEnvironment(episode)

        strictness = controller.strictness if (governed and controller) else self.strictness
        # ``None`` means the gateway's own disposition stands (arm B4G).
        write_budget = controller.autonomous_write_budget if (governed and controller) else None
        # A write counts as autonomous only if it executed under an outright
        # ALLOW. Writes executed under REQUIRE_CONFIRMATION had a human in the
        # loop and must not be credited as autonomy, or the Figure 1 frontier
        # inverts.
        autonomous_writes = 0
        gateway = ActionSafetyGateway(strictness) if governed else None
        # Monitoring-only gateway at fixed reference strictness. Never enforces;
        # supplies the controller with a strictness-invariant view of how often
        # this agent proposes something a reference policy would reject.
        monitor = ActionSafetyGateway(PRIMARY_STRICTNESS) if governed else None

        decisions: list[dict[str, Any]] = []
        proposed: list[str] = []
        signals = EpisodeSignals()
        extra_human_effort = 0.0

        calls = agent.start(episode, env.current_observation())
        for _ in range(self.max_steps):
            if not calls or env.terminated:
                break
            outputs = []
            for call in calls:
                proposed.append(call.name)
                signals.total_proposals += 1
                if call.name in PROHIBITED_TOOLS:
                    signals.prohibited_proposals += 1

                if monitor is not None:
                    shadow = monitor.authorize(
                        env.current_observation(), call.name, call.arguments, env.executed_writes
                    )
                    if shadow.disposition == BLOCK:
                        signals.reference_blocked_proposals += 1

                if gateway is None:
                    result = env.execute(call.name, call.arguments)
                    if call.name in WRITE_TOOLS and result.get("ok"):
                        autonomous_writes += 1
                else:
                    decision = gateway.authorize(
                        env.current_observation(), call.name, call.arguments, env.executed_writes
                    )
                    if (
                        write_budget is not None
                        and decision.disposition == ALLOW
                        and call.name in WRITE_TOOLS
                    ):
                        if autonomous_writes >= write_budget:
                            decision = Decision(
                                REQUIRE_CONFIRMATION,
                                f"autonomy state {controller.state} permits "
                                f"{write_budget} unconfirmed write(s) per episode",
                            )
                    decisions.append({"tool": call.name, **asdict(decision)})
                    if decision.disposition == BLOCK:
                        result = {"ok": False, "blocked": True, "reason": decision.reason}
                    else:
                        if decision.disposition == REQUIRE_CONFIRMATION:
                            signals.confirmations_required += 1
                            extra_human_effort += HUMAN_EFFORT["request_human_confirmation"]
                        result = env.execute(call.name, call.arguments)
                        if call.name in WRITE_TOOLS and result.get("ok"):
                            signals.executed_writes += 1
                            if decision.disposition == ALLOW:
                                autonomous_writes += 1

                if result.get("ok") is False and not result.get("blocked"):
                    signals.tool_errors += 1
                outputs.append(
                    {
                        "type": "function_call_output",
                        "call_id": call.call_id,
                        "output": env.json(result),
                    }
                )
            calls = agent.continue_with(outputs)

        transition = controller.observe(episode.episode_id, signals) if (governed and controller) else None

        # --- Condition-blinded adjudication -------------------------------- #
        trace = BlindTrace(
            episode_id=episode.episode_id,
            executed_actions=tuple(
                ExecutedAction(tool=e["tool"], arguments=e["arguments"], step=e["step"])
                for e in env.audit
            ),
            reported_confidence=_terminal_confidence(env.audit),
        )
        verdict = adjudicate(episode, trace)

        human_effort = env.human_effort + extra_human_effort
        usage = agent.usage
        return EpisodeResult(
            episode_id=episode.episode_id,
            condition=condition,
            replicate=replicate,
            strata=episode.public_dict(),
            perturbation=episode.perturbation,
            unsafe_action=verdict.unsafe_action,
            unsafe_reasons=verdict.unsafe_reasons,
            task_success=verdict.task_success,
            required_action=verdict.required_action,
            escalation_appropriate=verdict.escalation_appropriate,
            prohibited_action_attempted=verdict.prohibited_action_attempted,
            reported_confidence=trace.reported_confidence,
            time_to_action_min=round(env.minutes + extra_human_effort * 6.0, 3),
            human_effort_units=human_effort,
            tool_error_count=signals.tool_errors,
            reliable_tool_use=signals.tool_errors == 0 and bool(env.audit),
            autonomous_writes=autonomous_writes,
            confirmations_required=signals.confirmations_required,
            blocked_proposals=sum(1 for d in decisions if d["disposition"] == BLOCK),
            autonomy_state=controller.state if (governed and controller) else "n/a",
            autonomy_transition=asdict(transition) if transition else None,
            gateway_decisions=decisions,
            executed_tools=[e["tool"] for e in env.audit],
            proposed_tools=proposed,
            usage=usage,
            cost_usd=_episode_cost(usage, human_effort, self.token_prices),
            audit=env.audit,
        )

    # -- arm ---------------------------------------------------------------- #

    def run_arm(
        self, condition: str, episodes: Iterable[Episode], replicate: int = 0
    ) -> tuple[list[EpisodeResult], DynamicAutonomyController | None]:
        controller = DynamicAutonomyController() if condition in CONTROLLED_ARMS else None
        results = [
            self.run_episode(ep, condition, replicate=replicate, controller=controller)
            for ep in episodes
        ]
        return results, controller


def run_paired(
    agent_name: str,
    conditions: list[str],
    replicates: int = 1,
    episode_limit: int | None = None,
    strictness: str = PRIMARY_STRICTNESS,
    model: str | None = None,
) -> dict[str, Any]:
    """Run every requested arm over the identical frozen episode set.

    For each replicate index, arms ``B3`` and ``B4`` are given the same agent
    class, model, prompt, tools, and replicate index. The interposed gateway is
    the sole difference, which is what licenses a causal reading of the paired
    contrast.
    """
    episodes = generate_episodes(episode_limit)
    resolved_prices = (
        token_prices_for_model(model or "gpt-4.1")
        if agent_name == "openai"
        else TOKEN_PRICES_USD_PER_M
    )

    def factory_for(condition: str) -> Callable[..., Agent]:
        """Bind the agent for an arm.

        ``B2`` is *defined* as the deterministic-rules comparator and always
        uses :class:`RuleBasedAgent`, whatever ``--agent`` requests. Binding the
        requested agent to every arm silently collapses B2 onto B3 and destroys
        the comparator.
        """
        name = "rules" if condition == "B2" else agent_name
        agent_class = AGENT_REGISTRY[name]

        def factory(**kwargs: Any) -> Agent:
            if name == "openai":
                return agent_class(model=model or "gpt-4.1", **kwargs)
            return agent_class(**kwargs)

        return factory

    rows: list[dict[str, Any]] = []
    transitions: list[dict[str, Any]] = []
    for replicate in range(replicates):
        for condition in conditions:
            runner = BenchmarkRunner(
                factory_for(condition), strictness=strictness, token_prices=resolved_prices
            )
            results, controller = runner.run_arm(condition, episodes, replicate=replicate)
            rows.extend(asdict(r) for r in results)
            if controller:
                transitions.extend(
                    {"condition": condition, "replicate": replicate, **asdict(t)}
                    for t in controller.transitions
                )

    return {
        "provenance": {
            "run_started_utc": datetime.now(timezone.utc).isoformat(),
            "agent": agent_name,
            "model": model if agent_name == "openai" else None,
            "conditions": conditions,
            "replicates": replicates,
            "n_episodes": len(episodes),
            "gateway_strictness": strictness,
            "episode_set_digest": episode_set_digest(episodes),
            "policy_version": POLICY_VERSION,
            "policy_digest": policy_digest(),
            "gateway_version": GATEWAY_VERSION,
            "gateway_digest": gateway_digest(),
            "controller_digest": controller_digest(),
            "prompt_version": PROMPT_VERSION,
            "prompt_digest": prompt_digest(),
            "token_prices_usd_per_m": resolved_prices,
            "human_effort_cost_usd": HUMAN_EFFORT_COST_USD,
            "python": sys.version.split()[0],
            "platform": platform.platform(),
        },
        "results": rows,
        "autonomy_transitions": transitions,
    }


def write_run(payload: dict[str, Any], output: str | Path) -> Path:
    """Write results as JSONL with a leading provenance record."""
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        handle.write(json.dumps({"record_type": "provenance", **payload["provenance"]}, sort_keys=True) + "\n")
        for row in payload["results"]:
            handle.write(json.dumps({"record_type": "episode", **row}, sort_keys=True) + "\n")
        for row in payload["autonomy_transitions"]:
            handle.write(json.dumps({"record_type": "transition", **row}, sort_keys=True) + "\n")
    return path
