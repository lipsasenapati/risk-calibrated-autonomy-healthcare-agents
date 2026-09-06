#!/usr/bin/env bash
# Full preregistered live benchmark.
#
# Usage: bash scripts/run_full_benchmark.sh <model-snapshot> [replicates]
#
# Do not run this before the preregistration is deposited. It costs real money
# and its results are only interpretable against a timestamped plan.
set -euo pipefail

MODEL="${1:?pin an exact model snapshot, e.g. gpt-4.1-2025-04-14}"
REPLICATES="${2:-3}"
OUTDIR="${OUTDIR:-outputs}"

if [[ "$MODEL" != *-20* ]]; then
  echo "ERROR: '$MODEL' looks like a moving alias rather than a pinned snapshot." >&2
  echo "A moving alias can change weights mid-study and invalidate the comparison." >&2
  exit 1
fi

if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "ERROR: OPENAI_API_KEY is not set. Export it in your shell only." >&2
  exit 1
fi

export PYTHONPATH=src
mkdir -p "$OUTDIR"

echo "== Freeze digests (must match prereg/PREREGISTRATION.md section 0) =="
python3 -m risk_benchmark.cli --print-freeze | tee "$OUTDIR/freeze.json"

echo
read -r -p "Do these digests match the deposited preregistration? [yes/no] " CONFIRM
[[ "$CONFIRM" == "yes" ]] || { echo "Aborted."; exit 1; }

echo
echo "== Test suite =="
python3 -m unittest discover -s tests

# Primary run: all four arms at the prespecified moderate strictness.
echo
echo "== Primary run (moderate strictness, ${REPLICATES} replicates) =="
python3 -m risk_benchmark.cli \
  --agent openai --model "$MODEL" \
  --conditions B2,B3,B4G,B4 \
  --replicates "$REPLICATES" \
  --strictness moderate \
  --output "$OUTDIR/live_moderate.jsonl"

# Frontier runs: gateway-only arm at the other two strictness levels. B3 is
# included so each run file carries its own ungoverned reference.
for STRICTNESS in strict permissive; do
  echo
  echo "== Frontier run (${STRICTNESS}) =="
  python3 -m risk_benchmark.cli \
    --agent openai --model "$MODEL" \
    --conditions B3,B4G \
    --replicates "$REPLICATES" \
    --strictness "$STRICTNESS" \
    --output "$OUTDIR/live_${STRICTNESS}.jsonl"
done

echo
echo "== Analysis =="
python3 -m risk_benchmark.analyze \
  --run moderate="$OUTDIR/live_moderate.jsonl" \
  --run strict="$OUTDIR/live_strict.jsonl" \
  --run permissive="$OUTDIR/live_permissive.jsonl" \
  --outdir "$OUTDIR/analysis"

echo
echo "== Manuscript =="
python3 scripts/render_manuscript.py --analysis "$OUTDIR/analysis" || true

cat <<'NOTE'

Done. Before treating anything above as a result:
  1. Confirm outputs/analysis/summary.json provenance digests match the prereg.
  2. Record any deviation in prereg/PREREGISTRATION.md section 12.
  3. Resolve every [SELECT:] and PENDING placeholder in the manuscript.
  4. Archive to Zenodo and insert the DOI.
NOTE
