# Cover letter — npj Digital Medicine

> Replace every `PENDING` before sending. Do not soften the third and fourth
> paragraphs: they state the study's limits accurately, and an editor who
> discovers those limits during review rather than in the cover letter is
> entitled to conclude they were being minimised.

---

To the Editors, *npj Digital Medicine*

**Re: "A live agent benchmark of independent action authorization for healthcare AI agents"**

Dear Editors,

I am submitting the above manuscript for consideration as an Article.

Healthcare agent benchmarks measure capability. MedAgentBench asks what an agent
can accomplish in a FHIR-compliant record environment; AgentClinic asks how
capability survives sequential, multimodal encounters; and Liu et al. recently
showed in this journal that two deployed agent architectures deliver only modest
accuracy gains at more than ten times the token cost, with hallucinations
persisting despite in-agent safeguards filtering 89.9% of them. None of these
measures *authorization*: which actions an agent may execute, under what
preconditions, and for how long. That question is currently settled by
engineering defaults, and the observation that an agent's own safeguards leave a
substantial residue of failure is precisely the argument for enforcing
authorization outside the agent.

This study isolates that variable. Four arms run on an identical frozen set of
576 synthetic care-coordination episodes with the same model, prompt, tool
schemas and replicate index; the only difference is whether an Action Safety
Gateway, and separately a Dynamic Autonomy Controller, is interposed between a
proposed action and its execution. The design was registered before any agent
was run, and the episode set, adjudication policy, gateway, controller and prompt
were content-hashed at registration, so every reported figure can be verified
against the registered materials.

The methodological contribution I would most like to draw to your attention is
the property that makes the comparison falsifiable. Each episode carries hidden
ground truth and a deliberately lossy observable projection. The gateway sees
only the projection; adjudication uses only the truth. Under strata that degrade
observation, the gateway can therefore wrongly authorize an unsafe action *and*
wrongly block a correct one, so both the safety benefit and the efficiency price
are measured rather than assumed. A gateway given access to ground truth is an
oracle whose unsafe-action rate is zero by construction, and a primary endpoint
computed against it measures nothing. An earlier version of this work had exactly
that defect, and I report the correction explicitly rather than quietly: the
superseded analysis is described as superseded in the manuscript, in the
archived repository, and in the deposited code.

I want to be equally direct about what the study does not support, since these
limits are structural rather than incidental. The episodes are synthetic, so no
reported rate estimates a real-world rate. Adjudication is rule-based and
blinded to arm by construction, but no clinician reviewed these episodes, and I
make no claim of clinical adjudication. There is no human-workflow comparator,
because measuring one requires participants who were not recruited and
simulating one would reintroduce the assumed effect sizes this design exists to
remove; nothing here compares governed agents with current practice. One model
was prespecified, so the direction of an effect may generalise but its magnitude
should not be assumed to. Accordingly the manuscript makes no clinical
effectiveness claim, and the conclusions are framed as justifying shadow-mode
evaluation rather than deployment.

I believe the work is nonetheless a fit for *npj Digital Medicine*. The journal
has published the capability benchmarks this study complements, and the
authorization question is the immediate practical obstacle facing any
organisation deciding how much independence to grant a deployed clinical agent.
The mechanism decomposition — gateway alone versus gateway plus controller —
gives that decision an empirical basis rather than an architectural argument.

The manuscript is original, is not under consideration elsewhere, and has no
overlapping submissions. It involved no human participants, no animal subjects,
no patient data and no identifiable personal information, so institutional
review board approval was not applicable. Code and all episode-level outputs are
archived under an MIT licence in a DOI-minting deposit, and the preregistration
is included as supplementary material. I am the sole author and accept
responsibility for the integrity of the work. I declare no competing interests
beyond my employment at DaVita Inc., which had no role in the design, conduct,
analysis or reporting of this study and provided no data, systems or funding.

Suggested reviewers with relevant expertise in agent evaluation and human–AI
safety, none of whom I have collaborated with: PENDING — name, affiliation,
email × 3.

Thank you for considering this submission.

Yours sincerely,

Lipsa Senapati
AI Strategy and Execution, DaVita Inc., Denver, Colorado, USA
ORCID 0009-0009-4780-6953
lipsa.email@gmail.com
