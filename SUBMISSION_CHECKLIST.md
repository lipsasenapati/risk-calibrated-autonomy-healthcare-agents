# Submission checklist

Ordered. Items in **Phase 1** must be complete before any live API call, because
results from an unregistered run cannot be presented as preregistered.

Nothing in this repository can complete Phase 1 items 1–5 or Phase 4 item 3 on
your behalf; they require your accounts, your credentials, or your judgement.

---

## Phase 0 — Money and permission

| # | Task | Note |
|---|---|---|
| A | **Budget the APC: $4,290 USD** (£3,090 / €3,390) plus tax, for Original Research | npj Digital Medicine is fully open access and the APC is mandatory on acceptance. It is set by the *acceptance* date, not the submission date |
| B | Check Springer Nature institutional agreements and DaVita eligibility | Some institutions cover the APC in full; worth checking before you pay it personally |
| C | If requesting an APC waiver or discount, do it **at submission** | Requests made during review or after acceptance "are unable to be considered". This is irreversible if missed |
| D | Confirm DaVita publication clearance | Employer affiliation on a healthcare-AI governance paper; resolve before submission, not after review |
| E | Choose the licence: CC BY or CC BY-NC-ND | CC BY is required by some funders; you have no funder, so either is available |

## Phase 1 — Before spending anything on API calls

| # | Task | Why it blocks |
|---|---|---|
| 1 | ~~Register an ORCID iD~~ | **Done.** `0009-0009-4780-6953`, verified against the ORCID public API as registered to Lipsa Senapati |
| 2 | ~~Set the correspondence address~~ | **Done.** `lipsa.email@gmail.com`. See the note below — worth reconsidering, but not blocking |
| 3 | Pin the exact model snapshot in `prereg/PREREGISTRATION.md` §4 | A moving alias can change weights mid-study and silently break the paired comparison |
| 4 | Commit, then record the commit SHA in prereg §0 | Ties the plan to code |
| 5 | Run `--print-freeze`; confirm all five digests match prereg §0 | Detects any drift since the plan was written |
| 6 | Deposit the preregistration (OSF Registries or AsPredicted) | **Must precede the run.** Record the ID and UTC timestamp in §0 |

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
| 17 | `python3 scripts/render_manuscript.py --analysis outputs/analysis` — must exit 0. It enforces npj Article limits on the *rendered* text and fails on unresolved tokens, uncited references, and Discussion subheadings |
| 18 | Resolve every `[SELECT:]` placeholder using the preregistered interpretation paragraphs; do not strengthen a claim |
| 19 | Confirm MedAgentBench's NEJM AI volume and article number on the publisher page | 
| 20 | Re-read Discussion against prereg §10 "What this study cannot establish" |
| 21 | Confirm no sentence claims clinical effectiveness, superiority to human practice, or clinical adjudication |
| 22 | Delete the three HTML drafting-note comments from the manuscript |
| 23 | Fill the three suggested reviewers in `manuscript/cover_letter.md` |
| 24 | Convert to .docx or PDF — npj accepts unformatted initial submissions in Word or PDF, but the file must be editable at acceptance |

### npj Article requirements now enforced by the renderer

| Requirement | Status |
|---|---|
| Title ≤ 15 words, free of punctuation | Fixed: was 18 words with a colon, now 13 words, no punctuation |
| Abstract ≤ 150 words, no subheadings | Fixed: was ~230 words, now compliant *after token expansion* |
| Discussion: no subheadings, no Limitations section, no Conclusions section | Fixed: all three were present; Discussion is now continuous prose with limitations woven in |
| Results: subheadings used | Compliant |
| Methods: subheadings used, all methods in main file | Compliant |
| Data availability: mandatory | Present, separate section |
| Code availability | Present, separate section |
| Author contributions with initials | Present (`L.S.`) |
| Competing interests: mandatory, state even if none | Present |
| Funding declared in Acknowledgements, no separate Funding section | Enforced; fill `ACKNOWLEDGEMENTS` |
| References ≤ 60 | 9 |
| Figure legends ≤ 350 words | Compliant |

Note that npj does **not** impose a total word limit and does not require
formatting at initial submission — only the title, abstract, and section
structure above are hard constraints.

## Phase 5 — Archive and submit

| # | Task |
|---|---|
| 25 | Create the Zenodo deposit (link GitHub → Zenodo, then cut a release); complete `.zenodo.json` `PENDING` fields |
| 26 | Insert the Zenodo DOI into the Data availability and Code availability sections |
| 27 | Confirm Data availability and Code availability are **separate** sections |
| 28 | Attach the preregistration as a supplementary file |
| 29 | Finalise `manuscript/cover_letter.md` (drafted; needs reviewers + PENDING fields) |
| 30 | Submit at https://submission.springernature.com/new-submission/41746/3 |

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

## A note on the correspondence address

`lipsa.email@gmail.com` is now recorded as you specified, and npj Digital
Medicine accepts personal addresses, so this does not block submission.

One observation, offered once and then dropped: the local part `lipsa.email`
reads like a template placeholder rather than a real address, which is the same
signal that flagged it in the earlier draft. An editor skimming the title page
may read it as an unfinished submission. A durable address that does not look
generated — or an institutional one if DaVita permits external correspondence —
would remove that impression at no cost. Your call.

## What this package does not contain

- Live-agent results. None have been produced.
- Independent human adjudication. Not obtainable without adjudicators.
- A human-workflow comparator. Not obtainable without participants.
- A preregistration ID, ORCID, or DOI. All require your accounts.
