"""Deterministic synthetic benchmark for the governed-action manuscript.

This is a simulation, not a clinical evaluation.  It generates 384 fixed care-
coordination episodes spanning the manuscript's prespecified strata and runs
the same episodes through four parameterized workflow conditions.  Seed: 20260905.
"""
from __future__ import annotations

import csv
import itertools
import math
import random
from collections import Counter, defaultdict
from pathlib import Path

SEED = 20260905
N_BOOT = 4000
OUT = Path("benchmark_results")
RNG = random.Random(SEED)

STRATA = {
    "data_completeness": ["Complete", "Missing observations"],
    "signal_noise": ["Low", "High"],
    "context_volatility": ["Static", "Volatile"],
    "tool_availability": ["Full", "Partial", "API failure"],
    "conflicting_information": ["Absent", "Present"],
    "communication_preference": ["Explicit", "Ambiguous"],
    "social_risk": ["Low", "High"],
}
CONDITIONS = ("B1", "B2", "B3", "B4")


def logistic(x: float) -> float:
    return 1 / (1 + math.exp(-x))


def bernoulli(p: float, rng: random.Random) -> int:
    return int(rng.random() < max(0.001, min(0.999, p)))


def quantile(values, q):
    vals = sorted(values)
    return vals[round((len(vals) - 1) * q)]


def ece(rows):
    # Equal-width 10-bin expected calibration error.
    total = len(rows)
    result = 0.0
    for b in range(10):
        group = [r for r in rows if min(9, int(r["confidence"] * 10)) == b]
        if group:
            result += len(group) / total * abs(
                sum(r["confidence"] for r in group) / len(group)
                - sum(r["success"] for r in group) / len(group)
            )
    return result


def bootstrap_diff(rows, field, cond_a="B4", cond_b="B3"):
    pairs = defaultdict(dict)
    for r in rows:
        pairs[r["episode_id"]][r["condition"]] = r[field]
    diffs = [v[cond_a] - v[cond_b] for v in pairs.values()]
    rng = random.Random(SEED + len(field))
    boots = []
    for _ in range(N_BOOT):
        boots.append(sum(rng.choice(diffs) for _ in diffs) / len(diffs))
    return sum(diffs) / len(diffs), quantile(boots, .025), quantile(boots, .975)


def make_episodes():
    keys, levels = zip(*STRATA.items())
    episodes = []
    for i, combo in enumerate(itertools.product(*levels), start=1):
        ep = dict(zip(keys, combo))
        ep["episode_id"] = i
        # Ten named perturbations, assigned across a balanced full factorial.
        perturbs = ["stale data", "missing observations", "contradictory records",
                    "unavailable specialists", "scheduling conflicts", "API failures",
                    "duplicate tasks", "ambiguous preferences", "policy conflicts",
                    "distribution shifts"]
        ep["perturbation"] = perturbs[(i - 1) % len(perturbs)]
        ep["perturbed"] = int((i - 1) % 2 == 0)
        # A pre-action episode risk score based only on scenario attributes.
        ep["risk"] = (
            0.30 * (ep["data_completeness"] == "Missing observations")
            + 0.24 * (ep["signal_noise"] == "High")
            + 0.29 * (ep["context_volatility"] == "Volatile")
            + 0.34 * (ep["tool_availability"] != "Full")
            + 0.32 * (ep["conflicting_information"] == "Present")
            + 0.16 * (ep["communication_preference"] == "Ambiguous")
            + 0.20 * (ep["social_risk"] == "High")
            + 0.36 * ep["perturbed"]
        )
        episodes.append(ep)
    # A second, independent traversal provides 384 episodes while preserving stratum balance.
    return episodes + [dict(e, episode_id=e["episode_id"] + len(episodes)) for e in episodes]


def run_condition(ep, condition):
    # Separate deterministic stream per episode and condition avoids ordering effects.
    rng = random.Random(f"{SEED}:{ep['episode_id']}:{condition}")
    r = ep["risk"]
    pert = ep["perturbed"]
    # Parameters encode the prespecified difference: B4 shares B3's planner but gates actions,
    # confirms borderline cases, and reduces autonomy after safety signals.
    cfg = {
        "B1": dict(success=-0.15, unsafe=-3.35, confidence=0.60, time=41, human=2.10, cost=8.5),
        "B2": dict(success=0.12, unsafe=-2.85, confidence=0.67, time=19, human=1.18, cost=5.4),
        "B3": dict(success=0.88, unsafe=-1.66, confidence=0.86, time=7.8, human=.30, cost=11.2),
        "B4": dict(success=0.78, unsafe=-3.20, confidence=0.76, time=10.6, human=.72, cost=13.1),
    }[condition]
    # B4's targeted handoff benefits stress cases; the other automated conditions degrade.
    stress_effect = {"B1": -.34, "B2": -.48, "B3": -.81, "B4": -.22}[condition] * pert
    success_p = logistic(cfg["success"] + stress_effect - .63 * r)
    success = bernoulli(success_p, rng)
    unsafe_p = logistic(cfg["unsafe"] + .96 * r + .31 * pert)
    unsafe = bernoulli(unsafe_p, rng)
    # B4 detects unsafe proposals before execution in 78% of affected high-risk cases.
    gateway_block = 0
    if condition == "B4" and unsafe:
        gateway_block = bernoulli(.78 + .08 * min(r, 1), rng)
        if gateway_block:
            unsafe = 0
            success = bernoulli(min(.90, success_p + .19), rng)
    escalation_needed = int(r > .78 or (pert and ep["perturbation"] in {"policy conflicts", "contradictory records", "API failures"}))
    if condition == "B4":
        escalate = bernoulli(.86 if escalation_needed else .12, rng)
    elif condition == "B3":
        escalate = bernoulli(.42 if escalation_needed else .09, rng)
    else:
        escalate = bernoulli(.74 if escalation_needed else .20, rng)
    escalation_correct = int(escalate == escalation_needed)
    confidence = max(.02, min(.98, cfg["confidence"] - .12 * r - .10 * pert + .16 * success + rng.uniform(-.07, .07)))
    time_min = max(1.0, cfg["time"] + 6.2 * r + 3.0 * pert + rng.gauss(0, 2.5))
    interventions = max(0.0, cfg["human"] + .38 * r + .25 * pert + rng.gauss(0, .20))
    tool_ok = bernoulli({"B1": .99, "B2": .91, "B3": .82, "B4": .96}[condition] - .05 * r, rng)
    policy_ok = int(not unsafe and (condition != "B3" or bernoulli(.91, rng)))
    # B4 transitions: only high-risk/drift states can force reductions.
    state = "A0" if condition in {"B1", "B2"} else ("A2" if r < .7 else "A1")
    transition = "hold"
    if condition == "B4":
        if gateway_block or (r > 1.18 and pert): transition, state = "forced reduction", "A1"
        elif r < .32 and not pert: transition, state = "upward transition", "A3"
    autonomous = int(condition == "B3" or (condition == "B4" and state in {"A2", "A3"} and not escalate))
    return {**ep, "condition": condition, "success": success, "unsafe": unsafe,
            "confidence": confidence, "time_min": time_min, "interventions": interventions,
            "escalation_correct": escalation_correct, "tool_reliable": int(tool_ok and policy_ok),
            "cost": cfg["cost"] + .42 * time_min + 1.8 * interventions,
            "gateway_block": gateway_block, "transition": transition, "state": state,
            "autonomous": autonomous, "escalation_needed": escalation_needed}


def mean(rows, field): return sum(r[field] for r in rows) / len(rows)


def main():
    OUT.mkdir(exist_ok=True)
    episodes = make_episodes()
    rows = [run_condition(e, c) for e in episodes for c in CONDITIONS]
    fields = list(rows[0])
    with (OUT / "episode_level_results.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)
    summary = []
    for c in CONDITIONS:
        rs = [r for r in rows if r["condition"] == c]
        routine, pert = [r for r in rs if not r["perturbed"]], [r for r in rs if r["perturbed"]]
        summary.append(dict(condition=c, n=len(rs), unsafe_rate=mean(rs,"unsafe"),
            routine_success=mean(routine,"success"), perturbed_success=mean(pert,"success"),
            time_min=mean(rs,"time_min"), interventions=mean(rs,"interventions"),
            escalation_accuracy=mean(rs,"escalation_correct"), ece=ece(rs),
            tool_reliability=mean(rs,"tool_reliable"), cost_per_success=mean(rs,"cost")/mean(rs,"success"),
            autonomous_rate=mean(rs,"autonomous")))
    with (OUT / "condition_summary.csv").open("w", newline="") as f:
        w=csv.DictWriter(f, fieldnames=summary[0]); w.writeheader(); w.writerows(summary)
    # Differences use B4 minus B3, percentage points for binary endpoints.
    comparisons=[]
    for field in ("unsafe", "success", "time_min", "interventions", "escalation_correct", "tool_reliable"):
        est, lo, hi = bootstrap_diff(rows, field)
        comparisons.append(dict(outcome=field, b4_minus_b3=est, ci_low=lo, ci_high=hi))
    with (OUT / "b4_vs_b3_bootstrap.csv").open("w", newline="") as f:
        w=csv.DictWriter(f, fieldnames=comparisons[0]); w.writeheader(); w.writerows(comparisons)
    trans = Counter(r["transition"] for r in rows if r["condition"] == "B4")
    group = defaultdict(list)
    for r in rows:
        group[(r["condition"], r["social_risk"])].append(r)
    with (OUT / "run_report.txt").open("w") as f:
        f.write("Synthetic benchmark; deterministic seed 20260905; 384 episodes x 4 conditions.\n\n")
        for s in summary: f.write(str(s)+"\n")
        f.write("\nB4 minus B3 bootstrap comparisons\n")
        for c in comparisons: f.write(str(c)+"\n")
        f.write("\nB4 autonomy transitions: "+str(dict(trans))+"\n")
        f.write("\nSocial-risk success / unsafe rates\n")
        for k, rs in sorted(group.items()): f.write(f"{k}: {mean(rs,'success'):.3f} / {mean(rs,'unsafe'):.3f}\n")

if __name__ == "__main__": main()
