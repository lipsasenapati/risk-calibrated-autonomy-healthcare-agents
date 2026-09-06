"""Run the prespecified analysis over one or more run files and emit outputs.

Usage::

    python3 -m risk_benchmark.analyze \
        --run moderate=outputs/run_moderate.jsonl \
        --run strict=outputs/run_strict.jsonl \
        --run permissive=outputs/run_permissive.jsonl \
        --outdir outputs/analysis

The run labelled with the primary gateway strictness supplies the primary and
secondary inference; the remaining runs contribute points to the Figure 1
frontier.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict, List

from .analysis import (
    BINARY_ENDPOINTS,
    CONTINUOUS_ENDPOINTS,
    PRIMARY_ARM,
    REFERENCE_ARM,
    autonomy_transition_test,
    calibration_by_arm,
    equity_table,
    holm,
    load_run,
    paired_binary,
    paired_continuous,
    power_table,
    table1_strata,
    table_outcomes,
)
from .figures import figure1_frontier, figure2_autonomy_states, figure3_gateway_schematic
from .gateway import PRIMARY_STRICTNESS


def _write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    if not rows:
        return
    fieldnames: List[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="append",
        required=True,
        metavar="LABEL=PATH",
        help="Run file labelled by gateway strictness, e.g. moderate=outputs/run.jsonl",
    )
    parser.add_argument("--primary", default=PRIMARY_STRICTNESS)
    parser.add_argument("--arm", default=PRIMARY_ARM)
    parser.add_argument("--reference", default=REFERENCE_ARM)
    parser.add_argument("--outdir", default="outputs/analysis")
    parser.add_argument("--skip-power", action="store_true")
    args = parser.parse_args(argv)

    runs = {}
    for item in args.run:
        if "=" not in item:
            parser.error(f"--run expects LABEL=PATH, got {item!r}")
        label, path = item.split("=", 1)
        runs[label] = load_run(path)

    if args.primary not in runs:
        parser.error(
            f"primary strictness {args.primary!r} not among supplied runs {sorted(runs)}"
        )
    primary = runs[args.primary]
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)

    arms = primary.arms
    if args.arm not in arms or args.reference not in arms:
        parser.error(
            f"run contains arms {arms}; need both {args.arm!r} and {args.reference!r} "
            "for the paired comparison"
        )

    # --- Tables --------------------------------------------------------- #
    _write_csv(table1_strata(primary), outdir / "table1_strata.csv")
    _write_csv(table_outcomes(primary), outdir / "table2_outcomes_by_condition.csv")

    # --- Primary and secondary paired inference -------------------------- #
    comparisons = []
    primary_result = paired_binary(primary, "unsafe_action", args.arm, args.reference)
    comparisons.append(("PRIMARY", primary_result))

    secondary = []
    secondary.append(
        (
            "task_success_routine",
            paired_binary(
                primary, "task_success", args.arm, args.reference,
                predicate=lambda r: not r["perturbation"],
            ),
        )
    )
    secondary.append(
        (
            "task_success_perturbed",
            paired_binary(
                primary, "task_success", args.arm, args.reference,
                predicate=lambda r: bool(r["perturbation"]),
            ),
        )
    )
    for endpoint in BINARY_ENDPOINTS:
        if endpoint in ("unsafe_action", "task_success"):
            continue
        secondary.append((endpoint, paired_binary(primary, endpoint, args.arm, args.reference)))
    for endpoint in CONTINUOUS_ENDPOINTS:
        secondary.append((endpoint, paired_continuous(primary, endpoint, args.arm, args.reference)))

    adjusted = holm([result.p_value for _, result in secondary])
    rows = [{"family": "primary", "adjusted_p_value": primary_result.p_value, **primary_result.as_row()}]
    for (name, result), adj in zip(secondary, adjusted):
        rows.append({"family": f"secondary:{name}", "adjusted_p_value": round(adj, 6), **result.as_row()})
    _write_csv(rows, outdir / "table3_paired_comparisons.csv")

    # --- Mechanism decomposition ---------------------------------------- #
    if "B4G" in arms:
        mechanism = [
            {"contrast": "B4G vs B3 (gateway only)", **paired_binary(primary, "unsafe_action", "B4G", args.reference).as_row()},
            {"contrast": "B4 vs B4G (controller added)", **paired_binary(primary, "unsafe_action", args.arm, "B4G").as_row()},
        ]
        _write_csv(mechanism, outdir / "table4_mechanism_decomposition.csv")

    _write_csv(equity_table(primary, args.arm, args.reference), outdir / "table5_equity.csv")

    summary: Dict[str, Any] = {
        "provenance": primary.provenance,
        "arms": arms,
        "primary_endpoint": {
            **primary_result.as_row(),
            "discordant_pairs_arm_only": primary_result.discordant_arm_only,
            "discordant_pairs_reference_only": primary_result.discordant_reference_only,
        },
        "calibration": calibration_by_arm(primary),
        "autonomy_transitions_h6": autonomy_transition_test(primary),
    }
    if not args.skip_power:
        _write_csv(power_table(), outdir / "table6_power.csv")

    (outdir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True))

    # --- Figures --------------------------------------------------------- #
    figures = {}
    try:
        figures["figure1"] = str(figure1_frontier(runs, outdir / "figure1_frontier.png"))
    except ValueError as error:
        figures["figure1"] = f"not generated: {error}"
    try:
        figures["figure2"] = str(
            figure2_autonomy_states(primary, outdir / "figure2_autonomy_states.png", args.arm)
        )
    except ValueError as error:
        figures["figure2"] = f"not generated: {error}"
    figures["figure3"] = str(figure3_gateway_schematic(outdir / "figure3_gateway_schematic.png"))

    print(json.dumps({"outdir": str(outdir.resolve()), "figures": figures}, indent=2))
    print("\nPrimary endpoint (unsafe-action rate):")
    print(json.dumps(summary["primary_endpoint"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
