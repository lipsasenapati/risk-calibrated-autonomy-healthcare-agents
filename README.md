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

## Executable agent-and-tool benchmark

`src/risk_benchmark` is the new evaluation harness for actual tool-calling
agents. It provides synthetic, non-identifying episode ground truth; in-memory
EHR/scheduling/messaging tools; an independently invoked Action Safety Gateway;
JSONL provenance logs; and tests. The original `run_synthetic_benchmark.py`
remains available only to reproduce the manuscript's earlier parameterized
simulation and must not be represented as a live-agent result.

Run the fully offline integration harness:

```bash
PYTHONPATH=src python3 -m risk_benchmark.cli --agent scripted --episodes 16 --output results.jsonl
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

To run a real function-calling agent, configure `OPENAI_API_KEY` only in your
local environment and use an account-approved model. This sends synthetic
episode text—not clinical or patient data—to the API:

```bash
PYTHONPATH=src python3 -m risk_benchmark.cli --agent openai --model gpt-5 --episodes 16 --output openai_results.jsonl
```

The live run is opt-in, creates API usage, and should be preregistered before
its results replace any manuscript table or figure.

If a live run reports HTTP 429, read the reported `code` before retrying. It
may be a temporary rate limit, an exhausted credit balance, or a project or
organization spending limit; billing/quota errors require correcting the
account setting rather than repeated retries.

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
