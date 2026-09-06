"""Prespecified analysis: tables, paired inference, and figures.

The analysis is deliberately simple. The primary endpoint is a paired binary
outcome on the same episodes, so an exact McNemar test plus a cluster bootstrap
confidence interval is both sufficient and more transparent than the
mixed-effects logistic model asserted in earlier drafts, which would have
imposed distributional assumptions this design does not need.

Only ``numpy``, ``scipy`` and ``matplotlib`` are required.

Statistical plan
----------------
Primary
    Unsafe-action rate, arm B4 versus B3, paired on ``(episode_id, replicate)``.
    Exact McNemar test on discordant pairs; risk difference with a 95 percent
    percentile confidence interval from a bootstrap that resamples *episodes*
    (clusters), not condition-episode rows.
Secondary
    Task success (routine and perturbed reported separately), escalation
    accuracy, reliable tool use, time-to-action, human effort, cost, and
    expected calibration error. Family-wise error controlled by Holm.
Mechanism
    Arm B4G (gateway, no controller) separates the gateway's contribution from
    the controller's rather than inferring it.
Equity
    Paired differences within each ``social_risk`` stratum and the largest
    between-stratum gap, each with bootstrap intervals.
H6
    Permutation test of whether autonomy reductions co-occur with concurrent
    operating signals more than expected under a shuffled episode order.
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.stats import binomtest, wilcoxon

BOOTSTRAP_DRAWS = 10000
BOOTSTRAP_SEED = 20260906
ECE_BINS = 10
ALPHA = 0.05

PRIMARY_ARM = "B4"
REFERENCE_ARM = "B3"

BINARY_ENDPOINTS = (
    "unsafe_action",
    "task_success",
    "escalation_appropriate",
    "reliable_tool_use",
    "prohibited_action_attempted",
)
CONTINUOUS_ENDPOINTS = ("time_to_action_min", "human_effort_units", "cost_usd")


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


@dataclass
class Run:
    provenance: Dict[str, Any]
    episodes: List[Dict[str, Any]]
    transitions: List[Dict[str, Any]]

    @property
    def arms(self) -> List[str]:
        seen = []
        for row in self.episodes:
            if row["condition"] not in seen:
                seen.append(row["condition"])
        return seen

    def arm(self, condition: str) -> List[Dict[str, Any]]:
        return [r for r in self.episodes if r["condition"] == condition]


def load_run(path: str | Path) -> Run:
    provenance: Dict[str, Any] = {}
    episodes: List[Dict[str, Any]] = []
    transitions: List[Dict[str, Any]] = []
    with Path(path).open() as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            kind = row.pop("record_type")
            if kind == "provenance":
                provenance = row
            elif kind == "episode":
                # Flatten design factors for stratified analysis.
                row.update(row.get("strata", {}))
                episodes.append(row)
            elif kind == "transition":
                transitions.append(row)
    if not episodes:
        raise ValueError(f"no episode records found in {path}")
    return Run(provenance, episodes, transitions)


# --------------------------------------------------------------------------- #
# Pairing
# --------------------------------------------------------------------------- #


def pair_key(row: Dict[str, Any]) -> Tuple[str, int]:
    return (row["episode_id"], row["replicate"])


def paired_values(
    run: Run, endpoint: str, arm_a: str, arm_b: str, predicate: Optional[Callable[[Dict[str, Any]], bool]] = None
) -> Tuple[np.ndarray, np.ndarray, List[str]]:
    """Aligned endpoint vectors for two arms plus the episode id of each pair.

    Pairs are formed on ``(episode_id, replicate)`` so that a governed and an
    ungoverned run of the *same* episode under the *same* replicate index are
    compared. Episode ids are returned so the bootstrap can resample clusters.
    """
    index_a = {pair_key(r): r for r in run.arm(arm_a)}
    index_b = {pair_key(r): r for r in run.arm(arm_b)}
    keys = sorted(set(index_a) & set(index_b))
    if predicate is not None:
        keys = [k for k in keys if predicate(index_a[k])]
    values_a = np.array([float(index_a[k][endpoint]) for k in keys], dtype=float)
    values_b = np.array([float(index_b[k][endpoint]) for k in keys], dtype=float)
    return values_a, values_b, [k[0] for k in keys]


# --------------------------------------------------------------------------- #
# Inference
# --------------------------------------------------------------------------- #


@dataclass
class PairedResult:
    endpoint: str
    arm: str
    reference: str
    n_pairs: int
    rate_arm: float
    rate_reference: float
    difference: float
    ci_low: float
    ci_high: float
    p_value: float
    test: str
    discordant_arm_only: int = 0
    discordant_reference_only: int = 0

    def as_row(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "arm": self.arm,
            "reference": self.reference,
            "n_pairs": self.n_pairs,
            f"estimate_{self.arm}": round(self.rate_arm, 4),
            f"estimate_{self.reference}": round(self.rate_reference, 4),
            "difference": round(self.difference, 4),
            "ci_low": round(self.ci_low, 4),
            "ci_high": round(self.ci_high, 4),
            "p_value": self.p_value,
            "test": self.test,
        }


def _cluster_bootstrap_ci(
    values_a: np.ndarray,
    values_b: np.ndarray,
    clusters: Sequence[str],
    draws: int = BOOTSTRAP_DRAWS,
    seed: int = BOOTSTRAP_SEED,
) -> Tuple[float, float]:
    """Percentile CI for ``mean(a) - mean(b)`` resampling whole episodes.

    Resampling condition-episode rows independently would understate
    uncertainty, because the two arms share the episode.
    """
    if len(values_a) == 0:
        return (float("nan"), float("nan"))
    clusters = np.asarray(clusters)
    unique = np.unique(clusters)
    members = {c: np.flatnonzero(clusters == c) for c in unique}
    rng = np.random.default_rng(seed)
    diffs = np.empty(draws, dtype=float)
    for draw in range(draws):
        picked = rng.choice(unique, size=len(unique), replace=True)
        index = np.concatenate([members[c] for c in picked])
        diffs[draw] = values_a[index].mean() - values_b[index].mean()
    return (
        float(np.percentile(diffs, 100 * ALPHA / 2)),
        float(np.percentile(diffs, 100 * (1 - ALPHA / 2))),
    )


def paired_binary(
    run: Run,
    endpoint: str,
    arm: str = PRIMARY_ARM,
    reference: str = REFERENCE_ARM,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> PairedResult:
    """Exact McNemar test and bootstrap risk difference for a binary endpoint."""
    a, b, clusters = paired_values(run, endpoint, arm, reference, predicate)
    arm_only = int(np.sum((a == 1) & (b == 0)))
    ref_only = int(np.sum((a == 0) & (b == 1)))
    discordant = arm_only + ref_only
    p_value = (
        float(binomtest(arm_only, discordant, 0.5).pvalue) if discordant else 1.0
    )
    low, high = _cluster_bootstrap_ci(a, b, clusters)
    return PairedResult(
        endpoint=endpoint,
        arm=arm,
        reference=reference,
        n_pairs=len(a),
        rate_arm=float(a.mean()) if len(a) else float("nan"),
        rate_reference=float(b.mean()) if len(b) else float("nan"),
        difference=float(a.mean() - b.mean()) if len(a) else float("nan"),
        ci_low=low,
        ci_high=high,
        p_value=p_value,
        test="exact McNemar",
        discordant_arm_only=arm_only,
        discordant_reference_only=ref_only,
    )


def paired_continuous(
    run: Run,
    endpoint: str,
    arm: str = PRIMARY_ARM,
    reference: str = REFERENCE_ARM,
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None,
) -> PairedResult:
    """Wilcoxon signed-rank test and bootstrap mean difference."""
    a, b, clusters = paired_values(run, endpoint, arm, reference, predicate)
    if len(a) and np.any(a != b):
        p_value = float(wilcoxon(a, b, zero_method="wilcox").pvalue)
    else:
        p_value = 1.0
    low, high = _cluster_bootstrap_ci(a, b, clusters)
    return PairedResult(
        endpoint=endpoint,
        arm=arm,
        reference=reference,
        n_pairs=len(a),
        rate_arm=float(a.mean()) if len(a) else float("nan"),
        rate_reference=float(b.mean()) if len(b) else float("nan"),
        difference=float(a.mean() - b.mean()) if len(a) else float("nan"),
        ci_low=low,
        ci_high=high,
        p_value=p_value,
        test="Wilcoxon signed-rank",
    )


def holm(p_values: Sequence[float]) -> List[float]:
    """Holm-adjusted p-values, preserving input order."""
    order = np.argsort(p_values)
    n = len(p_values)
    adjusted = np.empty(n, dtype=float)
    running = 0.0
    for rank, index in enumerate(order):
        value = (n - rank) * p_values[index]
        running = max(running, value)
        adjusted[index] = min(1.0, running)
    return [float(x) for x in adjusted]


# --------------------------------------------------------------------------- #
# Calibration
# --------------------------------------------------------------------------- #


def expected_calibration_error(
    confidences: Sequence[float], correct: Sequence[float], bins: int = ECE_BINS
) -> float:
    """Equal-width binned ECE. Episodes without a reported confidence are dropped."""
    conf = np.asarray(confidences, dtype=float)
    hit = np.asarray(correct, dtype=float)
    keep = ~np.isnan(conf)
    conf, hit = conf[keep], hit[keep]
    if conf.size == 0:
        return float("nan")
    edges = np.linspace(0.0, 1.0, bins + 1)
    total = 0.0
    for low, high in zip(edges[:-1], edges[1:]):
        mask = (conf > low) & (conf <= high) if low > 0 else (conf >= low) & (conf <= high)
        if not mask.any():
            continue
        total += mask.mean() * abs(hit[mask].mean() - conf[mask].mean())
    return float(total)


def calibration_by_arm(run: Run, bins: int = ECE_BINS) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    rng = np.random.default_rng(BOOTSTRAP_SEED)
    for condition in run.arms:
        rows = run.arm(condition)
        conf = np.array(
            [r["reported_confidence"] if r["reported_confidence"] is not None else np.nan for r in rows],
            dtype=float,
        )
        hit = np.array([float(r["task_success"]) for r in rows], dtype=float)
        keep = ~np.isnan(conf)
        point = expected_calibration_error(conf, hit, bins)
        draws = []
        if keep.sum() > 1:
            index = np.flatnonzero(keep)
            for _ in range(1000):
                picked = rng.choice(index, size=index.size, replace=True)
                draws.append(expected_calibration_error(conf[picked], hit[picked], bins))
        out[condition] = {
            "ece": round(point, 4) if point == point else None,
            "ci_low": round(float(np.percentile(draws, 2.5)), 4) if draws else None,
            "ci_high": round(float(np.percentile(draws, 97.5)), 4) if draws else None,
            "n_with_confidence": int(keep.sum()),
        }
    return out


# --------------------------------------------------------------------------- #
# Descriptive tables
# --------------------------------------------------------------------------- #


def _rate(rows: List[Dict[str, Any]], key: str) -> float:
    return float(np.mean([float(r[key]) for r in rows])) if rows else float("nan")


def table1_strata(run: Run) -> List[Dict[str, Any]]:
    """Realised episode counts for every design factor (manuscript Table 1)."""
    factors = (
        "target_action",
        "social_risk",
        "data_completeness",
        "signal_noise",
        "context_volatility",
        "communication_preference",
        "tool_availability",
    )
    reference = run.arm(run.arms[0])
    rows = []
    for factor in factors:
        counts: Dict[str, int] = defaultdict(int)
        for row in reference:
            counts[row[factor]] += 1
        rows.append(
            {
                "stratum": factor,
                "levels": " / ".join(sorted(counts)),
                "episodes_per_condition": " / ".join(str(counts[k]) for k in sorted(counts)),
            }
        )
    perturbed = sum(1 for r in reference if r["perturbation"])
    rows.append(
        {
            "stratum": "perturbation status",
            "levels": "routine / perturbed",
            "episodes_per_condition": f"{len(reference) - perturbed} / {perturbed}",
        }
    )
    return rows


def table_outcomes(run: Run) -> List[Dict[str, Any]]:
    """Per-arm point estimates for every endpoint (manuscript Tables 2 and 3)."""
    calib = calibration_by_arm(run)
    rows = []
    for condition in run.arms:
        arm_rows = run.arm(condition)
        routine = [r for r in arm_rows if not r["perturbation"]]
        perturbed = [r for r in arm_rows if r["perturbation"]]
        successes = sum(float(r["task_success"]) for r in arm_rows)
        rows.append(
            {
                "condition": condition,
                "n": len(arm_rows),
                "unsafe_action_rate": round(_rate(arm_rows, "unsafe_action"), 4),
                "prohibited_action_rate": round(_rate(arm_rows, "prohibited_action_attempted"), 4),
                "task_success_routine": round(_rate(routine, "task_success"), 4),
                "task_success_perturbed": round(_rate(perturbed, "task_success"), 4),
                "escalation_accuracy": round(_rate(arm_rows, "escalation_appropriate"), 4),
                "reliable_tool_use": round(_rate(arm_rows, "reliable_tool_use"), 4),
                "time_to_action_min": round(_rate(arm_rows, "time_to_action_min"), 3),
                "human_effort_units": round(_rate(arm_rows, "human_effort_units"), 3),
                "autonomous_action_rate": round(
                    float(np.mean([1.0 if r["autonomous_writes"] > 0 else 0.0 for r in arm_rows])), 4
                ),
                "ece": calib[condition]["ece"],
                "cost_per_success_usd": (
                    round(sum(r["cost_usd"] for r in arm_rows) / successes, 2) if successes else None
                ),
            }
        )
    return rows


def equity_table(run: Run, arm: str = PRIMARY_ARM, reference: str = REFERENCE_ARM) -> List[Dict[str, Any]]:
    """Paired differences within social-risk strata and the largest gap."""
    rows = []
    for endpoint in ("unsafe_action", "task_success"):
        by_level = {}
        for level in ("low", "high"):
            result = paired_binary(
                run, endpoint, arm, reference, predicate=lambda r, lv=level: r["social_risk"] == lv
            )
            by_level[level] = result
            rows.append({"endpoint": endpoint, "social_risk": level, **result.as_row()})
        for condition in (arm, reference):
            levels = [
                _rate([r for r in run.arm(condition) if r["social_risk"] == lv], endpoint)
                for lv in ("low", "high")
            ]
            rows.append(
                {
                    "endpoint": endpoint,
                    "social_risk": "gap (high - low)",
                    "arm": condition,
                    "difference": round(levels[1] - levels[0], 4),
                }
            )
    return rows


# --------------------------------------------------------------------------- #
# H6: are autonomy reductions signal-driven?
# --------------------------------------------------------------------------- #


def autonomy_transition_test(run: Run, draws: int = BOOTSTRAP_DRAWS, seed: int = BOOTSTRAP_SEED) -> Dict[str, Any]:
    """Permutation test that reductions co-occur with concurrent risk signals.

    Statistic: mean reference-strictness block rate in episodes where autonomy
    was reduced or revoked, minus the mean in episodes where it was not. Under
    the null, transition labels are exchangeable with respect to the signal, so
    labels are permuted while the signal series is held fixed.
    """
    transitions = run.transitions
    if not transitions:
        return {"n_transitions": 0, "note": "no governed arm with a controller in this run"}
    reduced = np.array(
        [1.0 if t["kind"] in ("reduce", "revoke") else 0.0 for t in transitions]
    )
    signal = np.array([t["window_block_rate"] for t in transitions], dtype=float)
    counts: Dict[str, int] = defaultdict(int)
    for t in transitions:
        counts[t["kind"]] += 1
    if reduced.sum() == 0 or reduced.sum() == reduced.size:
        return {
            "n_transitions": len(transitions),
            "counts": dict(counts),
            "note": "no variation in reduction status; test not estimable",
        }
    observed = signal[reduced == 1].mean() - signal[reduced == 0].mean()
    rng = np.random.default_rng(seed)
    null = np.empty(draws)
    for i in range(draws):
        shuffled = rng.permutation(reduced)
        null[i] = signal[shuffled == 1].mean() - signal[shuffled == 0].mean()
    p_value = float((np.abs(null) >= abs(observed)).mean())
    return {
        "n_transitions": len(transitions),
        "counts": dict(counts),
        "statistic_block_rate_difference": round(float(observed), 4),
        "p_value": p_value,
        "test": "permutation (labels permuted, signal fixed)",
        "trigger_counts": dict(
            sorted(((k, v) for k, v in _trigger_counts(transitions).items()), key=lambda kv: -kv[1])
        ),
    }


def _trigger_counts(transitions: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = defaultdict(int)
    for t in transitions:
        counts[t["trigger"]] += 1
    return dict(counts)


# --------------------------------------------------------------------------- #
# Power
# --------------------------------------------------------------------------- #


def mcnemar_power(
    n_pairs: int,
    p_reference_unsafe: float,
    p_arm_unsafe: float,
    correlation: float = 0.5,
    draws: int = 4000,
    seed: int = BOOTSTRAP_SEED,
) -> float:
    """Simulation-based power for the exact McNemar test.

    ``correlation`` is the assumed within-episode association between the arms'
    unsafe-action indicators; higher values mean fewer discordant pairs and so
    less power for a given marginal difference. Reported across a range because
    it cannot be known before the run.
    """
    rng = np.random.default_rng(seed)
    hits = 0
    for _ in range(draws):
        shared = rng.random(n_pairs) < correlation
        ref = rng.random(n_pairs) < p_reference_unsafe
        arm = np.where(shared, ref & (rng.random(n_pairs) < p_arm_unsafe / max(p_reference_unsafe, 1e-9)), rng.random(n_pairs) < p_arm_unsafe)
        b = int(np.sum(arm & ~ref))
        c = int(np.sum(~arm & ref))
        if b + c == 0:
            continue
        if binomtest(b, b + c, 0.5).pvalue < ALPHA:
            hits += 1
    return hits / draws


def power_table(
    n_grid: Sequence[int] = (72, 144, 288, 576),
    scenarios: Sequence[Tuple[float, float]] = ((0.30, 0.15), (0.20, 0.10), (0.15, 0.10)),
    correlations: Sequence[float] = (0.3, 0.5, 0.7),
) -> List[Dict[str, Any]]:
    rows = []
    for p_ref, p_arm in scenarios:
        for rho in correlations:
            for n in n_grid:
                rows.append(
                    {
                        "n_pairs": n,
                        "p_unsafe_reference": p_ref,
                        "p_unsafe_arm": p_arm,
                        "assumed_correlation": rho,
                        "power": round(mcnemar_power(n, p_ref, p_arm, rho), 3),
                    }
                )
    return rows
