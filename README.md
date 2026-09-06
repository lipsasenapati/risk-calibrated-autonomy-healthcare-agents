# Risk Calibrated Autonomy Healthcare Agents

Reproducibility materials for the deterministic synthetic benchmark reported in
*From Prediction to Governed Action: A Synthetic Benchmark Evaluation of a
Risk-Calibrated Autonomy Gateway for Healthcare AI Agents*.

## Scope

This repository contains a parameterized synthetic simulation. It is not a
clinical dataset, a live LLM deployment, or evidence of clinical effectiveness.
The benchmark generates 384 fixed care-coordination episodes and evaluates each
under four workflow conditions:

- `B1`: manual workflow
- `B2`: predictive model plus deterministic rules
- `B3`: unconstrained agent proxy
- `B4`: governed agent proxy with an action-safety gateway and dynamic autonomy controller

The default seed is `20260905`. Running the script regenerates the same
episode-level outputs and condition summaries used in the manuscript.

## Run

The benchmark uses only the Python standard library.

```bash
python3 src/run_synthetic_benchmark.py
```

This writes a `benchmark_results/` directory containing episode-level results,
condition summaries, paired bootstrap comparisons, and a plain-text run report.

## Included derived outputs

The manuscript-ready outputs generated with the default seed are committed in
[`data/derived`](data/derived):

- `episode_level_results.csv` — all 1,536 condition-episode runs
- `condition_summary.csv` — condition-level outcome estimates
- `b4_vs_b3_bootstrap.csv` — paired bootstrap comparisons
- `run_report.txt` — transition and subgroup summary

## Interpretation

The simulation deliberately tests the hypothesis that independent authorization
controls can reduce unsafe actions at a cost in time and human intervention.
Its parameters are explicit in `src/run_synthetic_benchmark.py`; conclusions
should be replicated with implemented agents, independently adjudicated tasks,
and a preregistered analysis plan before making deployment or clinical claims.

## License

Code and derived synthetic outputs are released under the MIT License. Cite the
associated manuscript and this repository revision when using these materials.
