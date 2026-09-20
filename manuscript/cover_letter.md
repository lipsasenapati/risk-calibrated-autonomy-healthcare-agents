# Cover letter — BMC Medical Informatics and Decision Making

> Replace every `PENDING` before sending. Do not soften the discussion of
> limits or the null result: an editor who discovers them during review rather
> than in the cover letter is entitled to conclude they were being minimised.

---

To the Editors, *BMC Medical Informatics and Decision Making*

**Re: "A live agent benchmark of independent action authorization for healthcare AI agents"**

Dear Editors,

I am submitting the above manuscript for consideration as an Article.

Healthcare agent benchmarks measure capability. MedAgentBench asks what an agent
can accomplish in a FHIR-compliant record environment; AgentClinic asks how
capability survives sequential, multimodal encounters; and Liu et al. showed
that two deployed agent architectures deliver only modest accuracy gains at
more than ten times the token cost, with hallucinations persisting despite
in-agent safeguards filtering 89.9% of them. None of these measures
*authorization*: which actions an agent may execute, under what preconditions,
and for how long. That question is currently settled by engineering defaults,
and the observation that an agent's own safeguards leave a substantial residue
of failure is precisely the argument for enforcing authorization outside the
agent.

This study isolates that variable. Four arms run on an identical frozen set of
576 synthetic care-coordination episodes with the same model, prompt, tool
schemas and replicate index; the only difference is whether an Action Safety
Gateway, and separately a Dynamic Autonomy Controller, is interposed between a
proposed action and its execution. The design was registered on OSF before any
agent was run (https://osf.io/3wc9s), and the episode set, adjudication policy,
gateway, controller and prompt were content-hashed at registration, so every
reported figure can be verified against the registered materials.

**The result is a null finding, and I want that stated plainly rather than
discovered in review.** The primary hypothesis — that governance reduces the
unsafe-action rate — was not supported: the governed arm's rate (0.69%) was
numerically higher, not lower, than the unconstrained arm's (0.35%), and the
paired difference was not statistically significant (P = 0.6875, 95% CI −0.52
to +1.22 points). Neither the gateway alone nor adding the controller produced
a significant change. The most parsimonious explanation is a floor effect: the
prespecified model (gpt-4.1-mini) never once attempted the explicitly
prohibited action across 576 episodes even without a gateway, leaving little
room for an external layer to demonstrate a benefit. Governance was not free —
task success, escalation accuracy, and calibration were each significantly
worse under full governance, and time-to-action, human effort, and cost were
each significantly higher — so the manuscript reports a real, measured cost
without a measured safety benefit for this model.

I believe this is still a genuine contribution, for two reasons. First, the
property that makes the comparison falsifiable is orthogonal to which way the
result came out: each episode carries hidden ground truth and a deliberately
lossy observable projection, so the gateway could have wrongly authorized an
unsafe action or wrongly blocked a correct one, and a continuous-integration
test fails the build if the gateway ever becomes error-free with respect to
adjudicated truth. A gateway given access to ground truth would be an oracle,
and a primary endpoint computed against it would measure nothing; this design
avoids that failure mode regardless of outcome. Second, the null result is
itself informative: it identifies a boundary condition under which an
authorization layer's value is not guaranteed — a sufficiently well-aligned
model can leave the layer nothing to correct while it still imposes cost — which
is directly relevant to any organisation deciding whether such a layer is worth
its overhead for a given model.

I want to be equally direct about what the study does not support, since these
limits are structural rather than incidental. The episodes are synthetic, so no
reported rate estimates a real-world rate. Adjudication is rule-based and
blinded to arm by construction, but no clinician reviewed these episodes, and I
make no claim of clinical adjudication. There is no human-workflow comparator,
because measuring one requires participants who were not recruited and
simulating one would reintroduce assumed effect sizes. One model was
prespecified, so this null result should not be read as evidence that
authorization layers are never useful — only that their value depends on the
underlying agent's propensity to propose unsafe actions, which this design did
not vary. Accordingly the manuscript makes no clinical effectiveness claim.

I believe the work is nonetheless a fit for *BMC Medical Informatics and
Decision Making*. The authorization question is a practical one facing any
organisation deciding how much independence to grant a deployed clinical
agent, and a rigorously falsifiable null result — reported as such rather than
reframed — is a useful and underrepresented complement to the positive-result
literature on agent safeguards.

The manuscript is original, is not under consideration elsewhere, and has no
overlapping submissions. It involved no human participants, no animal
subjects, no patient data and no identifiable personal information, so
institutional review board approval was not applicable. Code and all
episode-level outputs are archived under an MIT licence at
https://doi.org/10.5281/zenodo.22851264, and the preregistration is included as
supplementary material. I am the sole author and accept responsibility for the
integrity of the work. I declare no competing interests beyond my employment
at DaVita Inc., which had no role in the design, conduct, analysis or
reporting of this study, provided no data, systems, or funding, and whose
publication clearance process was determined not to apply to this independent,
non-company work.

Suggested reviewers with relevant expertise in agent evaluation and human–AI
safety, none of whom I have collaborated with: PENDING — name, affiliation,
email × 3.

Thank you for considering this submission.

Yours sincerely,

Lipsa Senapati
AI Strategy and Execution, DaVita Inc., Denver, Colorado, USA
ORCID 0009-0009-4780-6953
lipsa.email@gmail.com
