#!/usr/bin/env python3
"""Fill the manuscript's quantitative tokens from analysis outputs.

Every number in the manuscript is a ``{{TOKEN}}`` resolved here from
``outputs/analysis/``, and every table is a ``<!-- TABLE:x -->`` marker replaced
by a table rendered from the corresponding CSV. Rendering **fails** if any token
or table marker is left unresolved.

The point is traceability. A previous version of this work reported hand-set
simulation parameters as measured results; requiring that every figure in the
prose be derived mechanically from a run output makes that class of error
impossible to commit silently.

Manual tokens (email, ORCID, DOIs, registration id, prose selections) are read
from a small JSON file so that they are also explicit and reviewable rather than
typed into the manuscript body.

Usage::

    python3 scripts/render_manuscript.py \
        --analysis outputs/analysis \
        --manual manuscript/manual_fields.json \
        --out manuscript/manuscript_rendered.md
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

TOKEN_RE = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
TABLE_RE = re.compile(r"<!--\s*TABLE:([a-z0-9_]+)\s*-->")

ARMS = ("B2", "B3", "B4G", "B4")


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open() as handle:
        return list(csv.DictReader(handle))


def pct(value: Any, digits: int = 1) -> str:
    """Format a proportion as a percentage string."""
    try:
        return f"{float(value) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "not estimable"


def num(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}"
    except (TypeError, ValueError):
        return "not estimable"


def pp(value: Any, digits: int = 1) -> str:
    """Format a risk difference in percentage points, with explicit sign."""
    try:
        return f"{float(value) * 100:+.{digits}f}"
    except (TypeError, ValueError):
        return "not estimable"


def fmt_p(value: Any) -> str:
    try:
        p = float(value)
    except (TypeError, ValueError):
        return "p not estimable"
    if p < 1e-4:
        return "P < 0.0001"
    return f"P = {p:.4f}"


def fmt_ci(low: Any, high: Any) -> str:
    try:
        return f"95% CI {float(low) * 100:+.1f} to {float(high) * 100:+.1f}"
    except (TypeError, ValueError):
        return "95% CI not estimable"


def markdown_table(rows: List[Dict[str, str]], caption: str) -> str:
    if not rows:
        return (
            f"> _{caption}: no rows available. This table's source CSV is "
            "missing or empty; the corresponding analysis step did not run._"
        )
    headers = list(rows[0].keys())
    lines = [
        "| " + " | ".join(h.replace("_", " ") for h in headers) + " |",
        "|" + "|".join("---" for _ in headers) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(h, "")) for h in headers) + " |")
    return "\n".join(lines)


def build_tokens(analysis: Path, manual: Dict[str, str]) -> Dict[str, str]:
    summary_path = analysis / "summary.json"
    if not summary_path.exists():
        raise SystemExit(
            f"missing {summary_path}. Run the benchmark and "
            "`python3 -m risk_benchmark.analyze` before rendering."
        )
    summary = json.loads(summary_path.read_text())
    provenance = summary.get("provenance", {})
    primary = summary.get("primary_endpoint", {})

    outcomes = {r["condition"]: r for r in read_csv(analysis / "table2_outcomes_by_condition.csv")}
    paired = {r["family"]: r for r in read_csv(analysis / "table3_paired_comparisons.csv")}
    mechanism = read_csv(analysis / "table4_mechanism_decomposition.csv")
    equity = read_csv(analysis / "table5_equity.csv")
    calibration = summary.get("calibration", {})
    h6 = summary.get("autonomy_transitions_h6", {})

    tokens: Dict[str, str] = dict(manual)

    # --- design ---------------------------------------------------------- #
    n_episodes = provenance.get("n_episodes")
    tokens["N_EPISODES"] = str(n_episodes) if n_episodes else "not recorded"
    tokens["N_CELLS"] = str(int(n_episodes) // 2) if n_episodes else "not recorded"
    tokens["N_PER_TARGET"] = str(int(n_episodes) // 3) if n_episodes else "not recorded"
    tokens["N_REPLICATES"] = str(provenance.get("replicates", "not recorded"))
    tokens["MODEL"] = provenance.get("model") or provenance.get("agent") or "not recorded"
    total = sum(int(outcomes[a]["n"]) for a in outcomes)
    tokens["N_RUNS_TOTAL"] = f"{total:,}"
    tokens["CODE_COMMIT"] = manual.get("CODE_COMMIT", "not recorded")

    # --- primary --------------------------------------------------------- #
    tokens["PRIMARY_DIFF"] = pp(primary.get("difference"))
    tokens["PRIMARY_CI"] = fmt_ci(primary.get("ci_low"), primary.get("ci_high"))
    tokens["PRIMARY_P"] = fmt_p(primary.get("p_value"))
    tokens["PRIMARY_NPAIRS"] = f"{int(primary.get('n_pairs', 0)):,}"
    tokens["DISCORDANT_B4_ONLY"] = str(primary.get("discordant_pairs_arm_only", "n/a"))
    tokens["DISCORDANT_B3_ONLY"] = str(primary.get("discordant_pairs_reference_only", "n/a"))

    # --- per-arm --------------------------------------------------------- #
    for arm in ARMS:
        row = outcomes.get(arm, {})
        tokens[f"UNSAFE_{arm}"] = pct(row.get("unsafe_action_rate"))
        tokens[f"SUCCESS_ROUTINE_{arm}"] = pct(row.get("task_success_routine"))
        tokens[f"SUCCESS_PERTURBED_{arm}"] = pct(row.get("task_success_perturbed"))
        tokens[f"TIME_{arm}"] = num(row.get("time_to_action_min"))
        tokens[f"HUMAN_{arm}"] = num(row.get("human_effort_units"))
        tokens[f"ECE_{arm}"] = num((calibration.get(arm) or {}).get("ece"), 3)

    # --- mechanism ------------------------------------------------------- #
    def mech(fragment: str) -> str:
        for row in mechanism:
            if fragment in row.get("contrast", ""):
                return pp(row.get("difference"))
        return "not estimable"

    tokens["MECH_GATEWAY_DIFF"] = mech("B4G vs B3")
    tokens["MECH_CONTROLLER_DIFF"] = mech("B4 vs B4G")

    # --- equity ---------------------------------------------------------- #
    def gap(arm: str) -> str:
        for row in equity:
            if row.get("endpoint") == "unsafe_action" and row.get("social_risk", "").startswith("gap") and row.get("arm") == arm:
                return pp(row.get("difference"))
        return "not estimable"

    tokens["EQUITY_GAP_B4"] = gap("B4")
    tokens["EQUITY_GAP_B3"] = gap("B3")

    # --- H6 -------------------------------------------------------------- #
    tokens["N_TRANSITIONS"] = f"{h6.get('n_transitions', 0):,}"
    counts = h6.get("counts", {})
    tokens["TRANSITION_COUNTS"] = (
        ", ".join(f"{v} {k}" for k, v in sorted(counts.items(), key=lambda kv: -kv[1]))
        or "no transitions recorded"
    )
    stat = h6.get("statistic_block_rate_difference")
    tokens["H6_STATISTIC"] = (
        f"block-rate difference {num(stat, 3)}" if stat is not None else "statistic not estimable"
    )
    tokens["H6_P"] = fmt_p(h6.get("p_value")) if "p_value" in h6 else "P not estimable"

    # --- prose that must be selected, not invented ----------------------- #
    tokens.setdefault(
        "PRIMARY_INTERPRETATION",
        "[SELECT: state whether H1 was supported, using only the numbers above.]",
    )
    # Length-representative placeholder. A six-word stub would let the abstract
    # pass the 150-word check and then overrun once a real sentence replaced it.
    tokens.setdefault(
        "ABSTRACT_SECONDARY_SENTENCE",
        "[SELECT: one sentence of about twenty words reporting task success, "
        "human effort, and calibration with paired differences.]",
    )
    tokens.setdefault("MECH_INTERPRETATION", "[SELECT: which component carried the effect.]")
    tokens.setdefault("DISCUSSION_PRINCIPAL", "[SELECT: preregistered interpretation paragraph.]")
    tokens.setdefault("DISCUSSION_B2", "[SELECT: interpretation of the rules comparator.]")
    tokens.setdefault("DISCUSSION_CONCLUSION", "[SELECT: preregistered conclusion paragraph.]")
    return tokens


VALIDATION_BANNER = (
    "> **NOT FOR SUBMISSION — HARNESS VALIDATION DATA.** The numbers below were\n"
    "> produced by the deterministic `{agent}` agent, not by a live model. They\n"
    "> exercise the pipeline and must never be reported as findings.\n"
)


def render(
    manuscript: Path, analysis: Path, manual: Dict[str, str], allow_validation: bool = False
) -> str:
    text = manuscript.read_text()
    tokens = build_tokens(analysis, manual)

    # The single most damaging mistake available here is rendering a manuscript
    # from the scripted or rules agent and mistaking it for a live-agent result.
    agent = json.loads((analysis / "summary.json").read_text()).get("provenance", {}).get("agent")
    if agent in ("scripted", "rules"):
        if not allow_validation:
            raise SystemExit(
                f"refusing to render: these analysis outputs came from the '{agent}' "
                "agent, which is harness validation and not a reportable result.\n"
                "Run the preregistered live benchmark, or pass "
                "--allow-validation-data to render a clearly watermarked draft."
            )
        text = VALIDATION_BANNER.format(agent=agent) + "\n" + text

    captions = {
        "table1": "Table 1",
        "table2": "Table 2",
        "table3": "Table 3",
        "table4": "Table 4",
        "table5": "Table 5",
    }
    sources = {
        "table1": "table1_strata.csv",
        "table2": "table2_outcomes_by_condition.csv",
        "table3": "table3_paired_comparisons.csv",
        "table4": "table4_mechanism_decomposition.csv",
        "table5": "table5_equity.csv",
    }

    def table_sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in sources:
            raise SystemExit(f"unknown table marker: {name}")
        return markdown_table(read_csv(analysis / sources[name]), captions[name])

    text = TABLE_RE.sub(table_sub, text)

    missing: List[str] = []

    def token_sub(match: re.Match) -> str:
        name = match.group(1)
        if name not in tokens:
            missing.append(name)
            return match.group(0)
        return str(tokens[name])

    text = TOKEN_RE.sub(token_sub, text)

    if missing:
        raise SystemExit(
            "unresolved tokens; the manuscript is not renderable:\n  "
            + "\n  ".join(sorted(set(missing)))
            + "\n\nAdd them to the manual fields file or fix the analysis outputs."
        )

    remaining = TABLE_RE.search(text)
    if remaining:
        raise SystemExit(f"unresolved table marker: {remaining.group(0)}")
    return text


# --------------------------------------------------------------------------- #
# Journal compliance
# --------------------------------------------------------------------------- #

#: npj Digital Medicine "Article" limits, from the journal's content-types page.
#: Checked on the *rendered* text, because token expansion changes word counts:
#: an abstract that fits before rendering can overrun once a confidence interval
#: expands into six words.
TITLE_MAX_WORDS = 15
ABSTRACT_MAX_WORDS = 150
REQUIRED_SECTIONS = (
    "Abstract",
    "Introduction",
    "Results",
    "Discussion",
    "Methods",
    "Data availability",
    "Code availability",
    "Acknowledgements",
    "Author contributions",
    "Competing interests",
)


def _strip_markup(text: str) -> str:
    text = re.sub(r"\[\^[^\]]+\]", " ", text)          # footnote refs
    text = re.sub(r"<!--.*?-->", " ", text, flags=re.S)  # html comments
    text = re.sub(r"[*_`]", "", text)                    # emphasis
    return text


def _section(text: str, name: str) -> str | None:
    match = re.search(
        rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", text, flags=re.M | re.S
    )
    return match.group(1) if match else None


def check_compliance(text: str) -> List[str]:
    """Return a list of npj Digital Medicine Article violations."""
    problems: List[str] = []

    title_match = re.search(r"^#\s+(.+)$", text, flags=re.M)
    if not title_match:
        problems.append("no level-1 title found")
    else:
        title = title_match.group(1).strip()
        words = len(title.split())
        if words > TITLE_MAX_WORDS:
            problems.append(f"title is {words} words; limit is {TITLE_MAX_WORDS}")
        # The journal requires titles "free of punctuation, idioms, and puns".
        # Hyphens inside compound words are tolerated; terminal and clausal
        # punctuation is not.
        for char in ":;,.?!—":
            if char in title:
                problems.append(f"title contains punctuation {char!r}")

    abstract = _section(text, "Abstract")
    if abstract is None:
        problems.append("no Abstract section found")
    else:
        if re.search(r"^#{3,}", abstract, flags=re.M):
            problems.append("Abstract contains subheadings, which are not permitted")
        words = len(_strip_markup(abstract).split())
        if words > ABSTRACT_MAX_WORDS:
            problems.append(
                f"abstract is {words} words after token expansion; "
                f"limit is {ABSTRACT_MAX_WORDS}"
            )

    discussion = _section(text, "Discussion")
    if discussion is None:
        problems.append("no Discussion section found")
    else:
        if re.search(r"^#{3,}\s", discussion, flags=re.M):
            problems.append(
                "Discussion contains subheadings; npj permits none, and no "
                "limitations or conclusions sections"
            )
        for banned in ("Limitations", "Conclusion"):
            if re.search(rf"^#+\s*{banned}", discussion, flags=re.M | re.I):
                problems.append(f"Discussion contains a {banned} heading, which is not permitted")

    if _section(text, "Results") and not re.search(
        r"^###\s", _section(text, "Results"), flags=re.M
    ):
        problems.append("Results should use subheadings")

    for name in REQUIRED_SECTIONS:
        if _section(text, name) is None:
            problems.append(f"missing required section: {name}")

    if re.search(r"^##\s+Funding\s*$", text, flags=re.M):
        problems.append(
            "a separate Funding section is not permitted; declare funding in Acknowledgements"
        )

    refs = _section(text, "References") or ""
    defined = set(re.findall(r"^\[\^([^\]]+)\]:", refs, flags=re.M))
    if len(defined) > 60:
        problems.append(f"{len(defined)} references; the guideline limit is 60")

    # Uncited definitions and undefined citations are both defects, and both are
    # easy to introduce while restructuring sections.
    body = text[: text.find("## References")] if "## References" in text else text
    cited = set(re.findall(r"\[\^([^\]]+)\]", body))
    for key in sorted(defined - cited):
        problems.append(f"reference defined but never cited: {key}")
    for key in sorted(cited - defined):
        problems.append(f"reference cited but not defined: {key}")

    return problems


def main(argv: List[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manuscript", default="manuscript/manuscript.md")
    parser.add_argument("--analysis", default="outputs/analysis")
    parser.add_argument("--manual", default="manuscript/manual_fields.json")
    parser.add_argument("--out", default="manuscript/manuscript_rendered.md")
    parser.add_argument(
        "--allow-validation-data",
        action="store_true",
        help="Render from scripted/rules-agent outputs, watermarked NOT FOR SUBMISSION.",
    )
    args = parser.parse_args(argv)

    manual_path = Path(args.manual)
    manual = json.loads(manual_path.read_text()) if manual_path.exists() else {}
    text = render(
        Path(args.manuscript), Path(args.analysis), manual, args.allow_validation_data
    )

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)
    print(f"Rendered {out} ({len(text.splitlines())} lines)")

    problems = check_compliance(text)
    if problems:
        print("\nnpj Digital Medicine Article compliance FAILED:")
        for problem in problems:
            print(f"  - {problem}")
    else:
        print("npj Digital Medicine Article compliance: OK")

    placeholders = text.count("[SELECT:") + text.count("PENDING")
    if problems:
        sys.exit(3)
    if placeholders:
        print(
            f"WARNING: {placeholders} placeholder(s) remain that require a human "
            "decision ([SELECT:...] or PENDING). The manuscript is not submittable "
            "until each is resolved."
        )
        sys.exit(2)


if __name__ == "__main__":
    main()
