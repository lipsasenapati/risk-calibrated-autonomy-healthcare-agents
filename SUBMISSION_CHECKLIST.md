# Submission checklist

Ordered. Items in **Phase 1** must be complete before any live API call, because
results from an unregistered run cannot be presented as preregistered.

Nothing in this repository can complete Phase 1 items 1–5 or Phase 4 item 3 on
your behalf; they require your accounts, your credentials, or your judgement.

---

## Phase 1 — Before spending anything

| # | Task | Why it blocks |
|---|---|---|
| 1 | Register an ORCID iD | Required by most journals; currently `PENDING` |
| 2 | Replace the correspondence address | The earlier draft used a placeholder gmail address, which signals an unfinished submission |
| 3 | Confirm DaVita publication clearance | Employer affiliation on a healthcare-AI governance paper; resolve before submission, not after review |
| 4 | Pin the exact model snapshot in `prereg/PREREGISTRATION.md` §4 | A moving alias can change weights mid-study and silently break the paired comparison |
| 5 | Commit, then record the commit SHA in prereg §0 | Ties the plan to code |
| 6 | Run `--print-freeze`; confirm all five digests match prereg §0 | Detects any drift since the plan was written |
| 7 | Deposit the preregistration (OSF Registries or AsPredicted) | **Must precede the run.** Record the ID and UTC timestamp in §0 |

## Phase 2 — Pilot

| # | Task |
|---|---|
| 8 | Run the 16-episode pilot with the pinned model |
| 9 | Read actual token usage from the run's provenance record and compare with the ~$110 estimate in prereg §9 |
| 10 | If measured cost exceeds the estimate by >100%, reduce replicates to 2 and record the deviation in prereg §12 |
| 11 | Confirm the live agent actually calls tools and returns parseable confidences; a model that ignores the tool schema invalidates the endpoints |

## Phase 3 — Full run and analysis

| # | Task |
|---|---|
| 12 | `bash scripts/run_full_benchmark.sh <pinned-snapshot> 3` |
| 13 | Confirm `outputs/analysis/summary.json` provenance digests match prereg §0 |
| 14 | Check the exclusion count; report it by arm and reason |
| 15 | Record every deviation in prereg §12 |
| 16 | Confirm the non-circularity result: if B4/B4G unsafe rate is exactly 0.000, stop and investigate — it implies the gateway became an oracle |

## Phase 4 — Manuscript

| # | Task |
|---|---|
| 17 | `python3 scripts/render_manuscript.py --analysis outputs/analysis` (must exit 0) |
| 18 | Resolve every `[SELECT:]` placeholder using the preregistered interpretation paragraphs; do not strengthen a claim |
| 19 | Complete the truncated author lists in the reference list from publisher records — **not from memory** |
| 20 | Re-read Discussion against prereg §10 "What this study cannot establish" |
| 21 | Confirm no sentence claims clinical effectiveness, superiority to human practice, or clinical adjudication |

## Phase 5 — Archive and submit

| # | Task |
|---|---|
| 22 | Create the Zenodo deposit (link GitHub → Zenodo, then cut a release); complete `.zenodo.json` `PENDING` fields |
| 23 | Insert the Zenodo DOI into the Data availability and Code availability sections |
| 24 | Confirm Data availability and Code availability are **separate** sections |
| 25 | Attach the preregistration as a supplementary file |
| 26 | Write the cover letter: state plainly that this is a synthetic benchmark with rule-based adjudication and no human comparator |

---

## Honest assessment of venue fit

npj Digital Medicine does publish agent benchmarking work — both AgentClinic
(`10.1038/s41746-026-02674-7`) and the Manus/OpenManus agent evaluation
(`10.1038/s41746-026-02443-6`) appeared there. So the topic is in scope, and my
earlier assessment that it was categorically out of scope was wrong.

Three things still distinguish this study from those, and reviewers will raise
each:

1. **No clinically derived content.** AgentClinic uses MIMIC-IV; MedAgentBench
   uses STARR-derived patient profiles. This benchmark's episodes are stylised
   and generated from a factorial design. That is a real limitation of external
   validity, and it is the single most likely basis for rejection.
2. **Rule-based rather than clinical adjudication.** Defensible and blinded, but
   not equivalent to physician review.
3. **Single author, single model.** Reviewers commonly ask for a second model
   and an independent adjudicator.

Two things are genuinely strong and worth foregrounding in the cover letter:

- The question — *authorization* rather than capability — is not addressed by
  any published benchmark, and the paired design isolates it cleanly.
- The mechanism decomposition (B4G vs B4) separates the gateway's contribution
  from the controller's rather than inferring it.

Realistically: plausible but not likely at npj Digital Medicine. If it is
desk-rejected, the natural next targets are *JAMIA*, *Journal of Biomedical
Informatics*, or *NEJM AI* (which published MedAgentBench). Strengthening it
before submission — a second model, and one independent adjudicator rating a
random subsample against the rule set — would materially improve the odds and
addresses reviewer objections 2 and 3 directly.

## What this package does not contain

- Live-agent results. None have been produced.
- Independent human adjudication. Not obtainable without adjudicators.
- A human-workflow comparator. Not obtainable without participants.
- A preregistration ID, ORCID, or DOI. All require your accounts.
