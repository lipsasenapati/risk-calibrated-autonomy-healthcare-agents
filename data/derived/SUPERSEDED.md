# SUPERSEDED OUTPUTS — DO NOT CITE

The CSV and text files in this directory were produced by
`src/run_synthetic_benchmark.py`, a parameterized simulation in which each arm's
unsafe-action propensity was a **hand-set constant**:

```python
"B3": dict(success=0.88, unsafe=-1.66, ...)
"B4": dict(success=0.78, unsafe=-3.20, ...)
# plus a hardcoded 0.78 pre-execution interception rate
```

Consequences:

- The frequently quoted contrast (unsafe actions "39.6% → 2.1%", a difference of
  −37.5 percentage points) is an arithmetic restatement of the constants
  `-1.66` and `-3.20`. It is not a measurement.
- The reported confidence interval describes bootstrap resampling noise around
  an assumed parameter, not sampling uncertainty about an estimated effect.
- The corresponding hypothesis could not have failed, because its answer was
  supplied as an input.

These files are retained solely so the record of what was previously computed
remains inspectable. They must not be cited as findings, used to populate any
manuscript table or figure, or described as evidence about governed agents.

The replacement is `src/risk_benchmark`, which runs live tool-calling agents and
measures safety with an adjudicator that is independent of the intervention. See
the repository README and `prereg/PREREGISTRATION.md`.

Files in this directory: `episode_level_results.csv`, `condition_summary.csv`,
`b4_vs_b3_bootstrap.csv`, `run_report.txt`.
