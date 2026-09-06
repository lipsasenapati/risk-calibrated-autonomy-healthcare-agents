"""Manuscript figures, generated only from run outputs.

Figures 1 and 2 are drawn from measured results and will refuse to render if
the required records are absent, so a figure can never silently depict data
that was not collected. Figure 3 is a schematic of the gateway control points
and is explicitly labelled as such.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from .analysis import Run, table_outcomes

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.6,
    }
)

ARM_LABELS = {
    "B2": "B2 Deterministic rules",
    "B3": "B3 Unconstrained agent",
    "B4G": "B4G Gateway only",
    "B4": "B4 Gateway + controller",
}
ARM_COLORS = {"B2": "#6E7B8B", "B3": "#C0392B", "B4G": "#E08A1E", "B4": "#1F6FB2"}


def _label(arm: str) -> str:
    return ARM_LABELS.get(arm, arm)


def figure1_frontier(
    runs_by_strictness: Dict[str, Run], output: str | Path
) -> Path:
    """Autonomy-performance frontier.

    x: proportion of episodes with at least one autonomously executed write.
    y: safe successful task completion (task success, which already requires
       that no unsafe action was executed).

    Governed arms trace a curve across gateway strictness levels; ungoverned
    arms appear as single points because strictness does not apply to them.
    """
    if not runs_by_strictness:
        raise ValueError("Figure 1 requires at least one run; none supplied.")

    series: Dict[str, List[Dict[str, Any]]] = {}
    for strictness, run in runs_by_strictness.items():
        for row in table_outcomes(run):
            series.setdefault(row["condition"], []).append({"strictness": strictness, **row})

    fig, ax = plt.subplots(figsize=(5.8, 4.2))
    for arm, points in series.items():
        points = sorted(points, key=lambda p: p["autonomous_action_rate"])
        xs = [p["autonomous_action_rate"] for p in points]
        ys = [(p["task_success_routine"] + p["task_success_perturbed"]) / 2.0 for p in points]
        color = ARM_COLORS.get(arm, "#444444")

        # Gateway strictness does not apply to ungoverned arms, so their points
        # coincide across runs. Collapse them to a single marker instead of
        # overplotting three identical points and three overlapping labels.
        varies = len(points) > 1 and (max(xs) - min(xs) > 0.01 or max(ys) - min(ys) > 0.01)
        if not varies:
            ax.plot(
                [sum(xs) / len(xs)], [sum(ys) / len(ys)],
                "D", color=color, label=_label(arm), markersize=7.5,
                markeredgecolor="white", markeredgewidth=0.8,
            )
            continue

        ax.plot(xs, ys, "-o", color=color, label=_label(arm), markersize=5.5, linewidth=1.6)
        for point, x, y in zip(points, xs, ys):
            ax.annotate(
                point["strictness"],
                (x, y),
                textcoords="offset points",
                xytext=(0, -13),
                fontsize=6.8,
                color=color,
                ha="center",
            )

    ax.set_xlabel("Autonomous action rate\n(episodes with $\\geq$1 unconfirmed write)")
    ax.set_ylabel("Safe successful task completion")
    ax.set_title("Figure 1. Autonomy-performance frontier", loc="left", fontsize=10)
    ax.set_xlim(-0.03, 1.03)
    ax.set_ylim(-0.03, 1.03)
    ax.legend(frameon=False, fontsize=7.5, loc="lower right")
    return _save(fig, output)


def figure2_autonomy_states(run: Run, output: str | Path, arm: str = "B4") -> Path:
    """Autonomy state over the episode sequence, with transitions marked."""
    transitions = [t for t in run.transitions if t["condition"] == arm and t["replicate"] == 0]
    if not transitions:
        raise ValueError(
            f"Figure 2 requires controller transitions for arm {arm}; none present. "
            "Run an arm with the Dynamic Autonomy Controller enabled."
        )
    states = ["A0", "A1", "A2", "A3"]
    order = {s: i for i, s in enumerate(states)}
    xs = [t["episode_index"] for t in transitions]
    ys = [order[t["to_state"]] for t in transitions]

    fig, (ax, ax2) = plt.subplots(
        2, 1, figsize=(7.0, 4.4), sharex=True, gridspec_kw={"height_ratios": [2, 1]}
    )
    ax.step(xs, ys, where="post", color="#1F6FB2", linewidth=1.4)
    marks = {
        "reduce": ("v", "#C0392B", "reduction"),
        "revoke": ("X", "#7B1113", "revocation"),
        "increase": ("^", "#1E8449", "increase"),
    }
    seen = set()
    for kind, (marker, color, legend) in marks.items():
        picked = [(t["episode_index"], order[t["to_state"]]) for t in transitions if t["kind"] == kind]
        if not picked:
            continue
        seen.add(legend)
        ax.plot(
            [p[0] for p in picked],
            [p[1] for p in picked],
            marker,
            color=color,
            markersize=7,
            linestyle="none",
            label=legend,
        )
    ax.set_yticks(range(len(states)))
    ax.set_yticklabels(states)
    ax.set_ylabel("Autonomy state")
    ax.set_title(
        f"Figure 2. Autonomy state over episodes, arm {arm}", loc="left", fontsize=10
    )
    if seen:
        ax.legend(frameon=False, fontsize=7.5, ncol=3, loc="upper left")

    ax2.plot(
        xs,
        [t["window_block_rate"] for t in transitions],
        color="#C0392B",
        linewidth=1.2,
        label="reference block rate",
    )
    ax2.plot(
        xs,
        [t["window_error_rate"] for t in transitions],
        color="#6E7B8B",
        linewidth=1.2,
        linestyle="--",
        label="tool error rate",
    )
    ax2.set_xlabel("Episode index")
    ax2.set_ylabel("Rolling rate")
    ax2.legend(frameon=False, fontsize=7.5, ncol=2)
    return _save(fig, output)


def figure3_gateway_schematic(output: str | Path) -> Path:
    """Schematic of the Action Safety Gateway control points.

    Labelled a schematic because it depicts architecture, not measurements.
    """
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.axis("off")
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 5)

    def box(x, y, w, h, text, face, edge, size=8):
        ax.add_patch(
            FancyBboxPatch(
                (x, y), w, h,
                boxstyle="round,pad=0.06,rounding_size=0.12",
                facecolor=face, edgecolor=edge, linewidth=1.1,
            )
        )
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=size, wrap=True)

    def arrow(x1, y1, x2, y2, color="#333333"):
        ax.add_patch(
            FancyArrowPatch((x1, y1), (x2, y2), arrowstyle="-|>", mutation_scale=11,
                            color=color, linewidth=1.0, shrinkA=1, shrinkB=1)
        )

    box(0.15, 2.05, 1.6, 0.9, "Agent-proposed\naction", "#EAF2FA", "#1F6FB2")
    box(2.05, 1.15, 2.45, 2.7,
        "Independent validation\n(observable signals only)\n\n"
        "action space\ndata freshness\nrecord consistency\n"
        "outreach authorization\nspecialist availability\n"
        "duplication\nequity safeguard",
        "#FFF6E5", "#E08A1E", size=7.2)

    # Three dispositions, matching ActionSafetyGateway exactly.
    box(5.1, 3.25, 2.25, 0.8, "allow\n(autonomous)", "#E8F6EC", "#1E8449", size=7.8)
    box(5.1, 2.15, 2.25, 0.8, "require\nconfirmation", "#FDF3E7", "#E08A1E", size=7.8)
    box(5.1, 1.05, 2.25, 0.8, "block\n(agent must escalate)", "#FBEAE9", "#C0392B", size=7.2)

    box(7.95, 1.6, 1.9, 2.05,
        "Immutable audit\nrecord\n\ninputs, evidence,\nmodel and policy\nversions, tools,\nchecks, outcome",
        "#F2F2F2", "#6E7B8B", size=6.9)

    arrow(1.75, 2.5, 2.05, 2.5)
    for y in (3.65, 2.55, 1.45):
        arrow(4.5, 2.5, 5.1, y)
        arrow(7.35, y, 7.95, 2.62)

    ax.text(0.15, 4.6, "Figure 3. Action Safety Gateway control points (schematic)",
            fontsize=10, va="center")
    ax.text(0.15, 0.3,
            "Schematic of architecture, not measured data. The gateway evaluates "
            "observable system signals only and never receives episode ground truth;\n"
            "adjudication of safety is performed separately and blinded to condition.",
            fontsize=7.0, va="center", color="#555555", style="italic")
    return _save(fig, output)


def _save(fig, output: str | Path) -> Path:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path)
    plt.close(fig)
    return path
