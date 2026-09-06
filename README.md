# Risk-Calibrated Autonomy for Healthcare AI Agents

A live-agent benchmark that holds the task, model, prompt and tools constant and
varies only whether an independent action-authorization layer is interposed
between an agent's proposed action and its execution.

Everything here is synthetic. No patient data, no human subjects, no
identifiable information.

## ⚠️ Status and a necessary warning about earlier results

This repository previously contained `src/run_synthetic_benchmark.py`, a
parameterized simulation in which each arm's unsafe-action propensity was a
**hand-set constant** (`B3: unsafe=-1.66`, `B4: unsafe=-3.20`, plus a hardcoded
0.78 interception rate). Any contrast computed from it — including the widely
quoted "39.6% → 2.1%" reduction — is an arithmetic restatement of those
constants, not a measurement. Its confidence intervals describe bootstrap noise
around an assumption.

**Those numbers are superseded and must not be cited as findings.** The file is
retained only for provenance. The current harness (`src/risk_benchmark`) replaces
it with live tool-calling agents and a measurement instrument that is
independent of the intervention.

No live-agent results have been produced yet. The manuscript in `manuscript/`
contains no literal numbers, by construction.

## Why this benchmark can produce a falsifiable result

The critical design property is that **the gateway is fallible**.

Each episode carries hidden true state and a deliberately lossy observable
projection. The agent and the gateway see only the projection; the adjudicator
uses only the hidden truth. Under strata that degrade observation — missing
data, high signal noise, context volatility, tool-channel failure — the gateway
can wrongly authorize an unsafe action *or* wrongly block a correct one. So both
the size of any safety benefit and the efficiency price paid for it are measured.

A gateway with access to ground truth is an oracle: its unsafe-action rate is
zero by construction and the primary endpoint measures nothing. The previous
harness had exactly this defect — `gateway.py` read `episode.expected_action`,
which was *defined* as the conditions the gateway then checked. A live run would
have reproduced the circularity rather than fixing it.

`tests/test_benchmark.py::NonCircularityTests` fails the build if the gateway
ever becomes error-free with respect to adjudicated truth.

## Design

| Arm | Description | Agent | Gateway | Controller |
|---|---|---|---|---|
| `B2` | Deterministic thresholded workflow rules | none | no | no |
| `B3` | Unconstrained agent, full tool access | LLM | no | no |
| `B4G` | Gateway only (mechanism decomposition) | LLM | yes | no |
| `B4` | Gateway + Dynamic Autonomy Controller | LLM | yes | yes |

**There is no `B1`.** A manual human-workflow arm cannot be measured without
human participants. Simulating one would reintroduce the assumed effect sizes
this harness exists to eliminate, so the benchmark makes no claim about governed
agents versus current human practice.

Episodes: full factorial over seven factors (correct terminal action, social
risk, data completeness, signal noise, context volatility, communication
preference, tool availability) = 288 cells, each appearing once routine and once
perturbed = **576 episodes**. Perturbation status is exactly orthogonal to all
seven factors; the correct action is balanced at 192 per level; each of eight
perturbation types appears 36 times.

The correct terminal action is a *balanced design factor*, not a by-product of
the strata. When it was derived from the strata, 89% of episodes required the
same answer and neither task success nor escalation accuracy could discriminate.

## Install

Runs on the Python standard library for the benchmark itself. Analysis and
figures need `numpy`, `scipy` and `matplotlib`.

```bash
python3 -m pip install -r requirements.txt
```

## Run

```bash
# 1. Verify the freeze digests match the preregistration
PYTHONPATH=src python3 -m risk_benchmark.cli --print-freeze

# 2. Validate the harness offline (deterministic; NOT a reportable result)
PYTHONPATH=src python3 -m unittest discover -s tests -v
PYTHONPATH=src python3 -m risk_benchmark.cli --agent scripted \
    --conditions B2,B3,B4G,B4 --output outputs/validation.jsonl

# 3. Pilot the live agent on 16 episodes and check cost
export OPENAI_API_KEY=...        # your shell only; never commit it
PYTHONPATH=src python3 -m risk_benchmark.cli --agent openai \
    --model gpt-4.1-2025-04-14 --episodes 16 \
    --conditions B3,B4 --output outputs/pilot.jsonl

# 4. Full preregistered run (see scripts/run_full_benchmark.sh)
bash scripts/run_full_benchmark.sh gpt-4.1-2025-04-14 3

# 5. Analysis, tables and figures
PYTHONPATH=src python3 -m risk_benchmark.analyze \
    --run moderate=outputs/live_moderate.jsonl \
    --run strict=outputs/live_strict.jsonl \
    --run permissive=outputs/live_permissive.jsonl \
    --outdir outputs/analysis

# 6. Render the manuscript from those outputs only
python3 scripts/render_manuscript.py --analysis outputs/analysis
```

Step 6 refuses to run on scripted- or rules-agent outputs, and fails if any
quantitative token is unresolved. No number can reach the manuscript without
coming from a run.

## Repository layout

```
prereg/PREREGISTRATION.md      Analysis plan, hypotheses, power, freeze digests
src/risk_benchmark/
  scenarios.py                 Frozen episode set; hidden truth vs observation
  tools.py                     In-memory tools, incl. a prohibited action
  gateway.py                   Action Safety Gateway (observables only)
  controller.py                Dynamic Autonomy Controller
  adjudicator.py               Frozen policy; condition-blinded measurement
  agents.py                    Rules / scripted / live adapters
  runner.py                    Arm execution, endpoints, provenance
  analysis.py                  Paired inference, calibration, equity, power
  figures.py                   Figures 1-3 from run outputs
  analyze.py                   Analysis CLI
  run_synthetic_benchmark.py   SUPERSEDED. Provenance only. Do not cite.
manuscript/manuscript.md       Source manuscript; contains no literal numbers
scripts/render_manuscript.py   Binds manuscript numbers to run outputs
tests/test_benchmark.py        Invariant tests (blinding, non-circularity)
```

## Adjudication, and what it is not

Safety is adjudicated by a frozen, prespecified rule set (P1–P7) applied to the
executed action trace. It is **condition-blinded by construction**: the
adjudicator receives a `BlindTrace` that structurally cannot carry the arm
label, model identity, or gateway dispositions, and a test asserts this.

It is **not** independent clinical adjudication. No clinician reviewed these
episodes. The endpoint detects only the violations the seven rules encode. Any
manuscript using this harness must say so.

## Live runs

Live runs are opt-in, cost money, and should not be performed before the
preregistration is deposited. Only synthetic episode text is transmitted, with
server-side retention disabled.

Pin an exact model snapshot (`gpt-4.1-2025-04-14`, not `gpt-4.1`): a moving
alias can change weights mid-study and silently break the comparison.

On HTTP 429, read the reported `code`. `insufficient_quota` and
`billing_hard_limit_reached` are treated as non-retryable, because retrying an
account-configuration problem only wastes time and money.

## Licence

MIT. Cite the associated manuscript and the archived Zenodo revision, not this
mirror.
