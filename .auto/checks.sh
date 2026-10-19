#!/usr/bin/env bash
# Backpressure for the soft-objective palette search.
#
# Two independent layers:
#   1. scripts/soft_gate.py -- hard-gates every palette the benchmark just
#      produced: WCAG 2.x floors against the canvas AND every co-occurring
#      surface, sRGB gamut, every taste fence, the distance-matrix
#      same_family.min_distance output gate, and palette completeness.
#      These are the constraints that must NEVER trade for a better number.
#   2. pytest -- the repo's own suite, scoped by what actually changed.
#      `src/grotto/` or `spec/` touched -> full suite; only scripts/ touched
#      -> the palette/metric subset that can see them.
set -uo pipefail
cd "$(dirname "$0")/.."

fail=0

echo "== palette gate =="
uv run python scripts/soft_gate.py .auto/work 2>&1 | tail -30 || fail=1

BASE=$(git merge-base HEAD origin/review/palette-first-design)
if [ -n "$(git diff --name-only "$BASE" -- src/grotto spec)" ]; then
  echo "== pytest (full: src/grotto or spec changed) =="
  TESTS=""
else
  echo "== pytest (palette/metric subset) =="
  TESTS="tests/test_numeric_palette.py tests/test_middle_palette.py tests/test_metrics.py tests/test_spec_palette.py tests/test_check.py"
fi
if ! uv run pytest -q --no-header $TESTS 2>&1 | tail -25; then
  fail=1
fi
if [ "$fail" -ne 0 ]; then
  echo "CHECKS FAILED"
fi
exit $fail