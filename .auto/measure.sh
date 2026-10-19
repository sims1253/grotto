#!/usr/bin/env bash
# Benchmark for the Grotto soft-objective Night palette search.
#
# Runs the search at a FIXED, deliberately small budget and re-scores the
# palette it produced with scripts/soft_metric.py -- the independent
# instrument, which never sees the search's own report.
#
# Three seeds are run and their utilities averaged, so a lucky seed cannot
# masquerade as a better search.  The per-seed spread is reported as
# `seed_spread` and is the honest stand-in for measurement noise: the search
# itself is byte-deterministic for a fixed seed.
set -euo pipefail
cd "$(dirname "$0")/.."

RESTARTS=${AR_RESTARTS:-4}
SAMPLES=${AR_SAMPLES:-8}
PASSES=${AR_PASSES:-10}
SEEDS=${AR_SEEDS:-"20260817 20260818 20260819"}
# CPU-time cap per seed.  The budget above is fixed in ITERATIONS so the
# search stays byte-deterministic; this cap stops the benchmark being won by
# brute force (more restarts, bigger move set) instead of by a better search.
# Baseline was 12.6 s/seed, so this allows a real improvement to cost
# something.  Exceeding it fails the measurement.
# It is PROCESS CPU time, not wall clock: this runs on a shared 2-core VM,
# and under another job's load the unchanged run-7 search measured 17.5 s
# wall -- a cap on wall time measured the neighbours, not the search.
SEED_CAP=${AR_SEED_CAP:-16.0}
WORK=${AR_WORK:-.auto/work}

rm -rf "$WORK"
mkdir -p "$WORK"

for seed in $SEEDS; do
  uv run python scripts/soft_palette.py \
      --seed "$seed" --restarts "$RESTARTS" --samples "$SAMPLES" \
      --refine-passes "$PASSES" --out "$WORK/seed-$seed" --no-install \
      >"$WORK/seed-$seed.log" 2>&1
  secs=$(sed -n 's/^\[done\] [0-9.]*s total, \([0-9.]*\)s cpu.*/\1/p' "$WORK/seed-$seed.log" | head -1)
  if [ -z "$secs" ]; then
    echo "MEASURE FAILED: seed $seed produced no [done] line"
    tail -20 "$WORK/seed-$seed.log"; exit 1
  fi
  echo "seed $seed: ${secs}s cpu (cap ${SEED_CAP}s)"
  awk -v s="$secs" -v c="$SEED_CAP" 'BEGIN { exit !(s <= c) }' || {
    echo "MEASURE FAILED: seed $seed took ${secs}s, over the ${SEED_CAP}s cap"
    exit 1
  }
done

# Independent scoring: one process, one palette each, no search code imported.
uv run python scripts/soft_metric.py --json \
    $(for s in $SEEDS; do printf '%s/soft-s01.night.yaml ' "$WORK/seed-$s"; done) \
    >"$WORK/scores.json"

uv run python - "$WORK/scores.json" "$WORK" <<'PY'
import json, sys, pathlib

rows = json.loads(pathlib.Path(sys.argv[1]).read_text())
work = pathlib.Path(sys.argv[2])
utils = [r["utility"] for r in rows]
mean = sum(utils) / len(utils)
spread = max(utils) - min(utils)
best = max(rows, key=lambda r: r["utility"])
mean_of = lambda k: sum(r[k] for r in rows) / len(rows)

print(f"seeds={len(rows)} restarts={rows[0].get('restarts','?')}")
for r, u in zip(rows, utils):
    print(f"  seed utility={u:.4f} sep={r['sep']:.4f} emph={r['emph']:.4f} "
          f"worst={r['worst_margin']:.4f} atTarget={r['at_target']}/{r['terms']} "
          f"wcag={r['wcag_violations']}")
print(f"mean utility {mean:.4f}")

m = {
    "utility": mean,
    "sep": mean_of("sep"),
    "emph": mean_of("emph"),
    "worst_margin": mean_of("worst_margin"),
    "at_target": mean_of("at_target"),
    "terms": rows[0]["terms"],
    "mean_cat_chroma": mean_of("mean_cat_chroma"),
    "max_cat_chroma": mean_of("max_cat_chroma"),
    "wcag_violations": mean_of("wcag_violations"),
    "min_must_cvd": mean_of("min_must_cvd"),
    "min_should": mean_of("min_should"),
    "min_anticollapse": mean_of("min_anticollapse"),
    "seed_spread": spread,
    "worst_seed_utility": min(utils),
}
for k, v in m.items():
    print(f"METRIC {k}={v}")
pathlib.Path(work / "summary.json").write_text(json.dumps(m, indent=2) + "\n")
PY