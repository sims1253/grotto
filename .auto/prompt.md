# Autoresearch: soft-objective Night palette search (Grotto)

## Objective

Make the **Grotto Night theme palette** as good as it can be, and make the
**search that produces it** as good as it can be, by running the experiment
`docs/review/optimizer-constraints.md` asks for and then iterating on the
search until it is as strong as the fences and the hardware allow.

This loop optimises **two** things at once, in one number:

1. the **palette** the search produces, and
2. the **search** that produces it, at a *fixed* budget (below). Budget-fixed
   means every point of improvement in `utility` is a better search, not a
   longer run.

## Metrics

`.auto/measure.sh` runs three fixed seeds of `scripts/soft_palette.py` at a
fixed small budget and re-scores each result with `scripts/soft_metric.py`
(an instrument that never imports the search). Reported as `METRIC` lines.

- **Primary**: `utility` (unitless, higher is better)

  ```
  utility(P) = 1 - SEP(P) - EMPHASIS_WEIGHT * EMPHASIS_EXCESS(P)
  SEP(P)     = mean over all 162 objective terms of max(0, 1 - margin_i)^2
  EMPH(P)    = area-weighted mean chroma (canvas excluded)
  EMPHASIS_EXCESS(P) = max(0, (EMPH(P) - 0.045) / 0.045)
  EMPHASIS_WEIGHT    = 0.35
  ```

- **Secondary** (monitors, not targets): `sep`, `emph`, `worst_margin` (the old
  max-min `J`), `at_target` (terms clearing their threshold, of 162),
  `mean_cat_chroma`, `max_cat_chroma`, `min_must_cvd`, `min_should`,
  `min_anticollapse`, `wcag_violations`, `seed_spread`.

- `seed_spread` is the honest stand-in for noise: the search is
  byte-deterministic per seed, so the only uncertainty is whether a change
  generalises across seeds. Treat a gain smaller than `seed_spread` as luck.

### Reference points on this instrument (measured, not estimated)

| palette | utility | sep | emph | worst | wcag |
|---|---|---|---|---|---|
| candidate-a restrained night | 0.7900 | 0.2735 | 0.0085 | 0.000 | 12 |
| candidate-b balanced night | 0.7896 | 0.2104 | 0.0199 | 0.000 | 12 |
| candidate-c expressive night | 0.8022 | 0.1978 | 0.0271 | 0.000 | 12 |
| middle-m01 night (45 s run) | 0.9361 | 0.0592 | 0.0456 | 0.282 | 0 |
| numeric-n01 night (**rejected**) | 0.6605 | 0.0228 | 0.0857 | 0.507 | 0 |
| fig-vivid night (PR #2 draft) | ~0.79 | 0.190 | 0.059 | 0.000 | 1 |

The instrument deliberately ranks the owner's *rejected* numeric frontier
**below** the middle frontier: the shortfall pays nothing for margin a term
already has, so loudness has to be paid for out of the emphasis budget. If a
change to the instrument makes numeric-n01 top the table again, the
instrument has regressed to the max-min objective it replaced.

## How to Run

```bash
uv run python .auto/ar.py measure     # ~38 s, prints the metric JSON
uv run python .auto/ar.py checks      # hard gates + scoped pytest
uv run python .auto/ar.py log keep "what I changed" --asi key=value
```

Loop: **change something → `measure` → `checks` → `log`**.
`keep` commits; `discard` / `crash` / `checks_failed` reverts the code and
keeps only the record. **Never** hand-edit `utility` into the log.

Budget is fixed by `.auto/measure.sh`: `--restarts 4 --samples 8
--refine-passes 10`, seeds `20260817 20260818 20260819`, ~12 s per seed.
Raise the budget and you have measured a different experiment.

## Files in Scope

- **`scripts/soft_palette.py`** — the search. `SoftProblem` (objective
  plumbing), `soft_refine` (coordinate ascent), `run_search` (multi-start),
  `main`. This is the primary lever: initialization, move set, acceptance,
  restarts, incremental evaluation, better use of the budget.
- **`scripts/soft_metric.py`** — the instrument. `EMPHASIS_BUDGET`,
  `EMPHASIS_WEIGHT`, `AREA_CLASS_SHARE`, `SURFACE_AREA_WEIGHT`,
  `SHORTFALL_EXP`, `ink_shares()`, `area_weights()`. Changing it changes the
  *goal*, not the search — see the warning below.
- **`scripts/soft_gate.py`** — hard gates. Treat as untouchable.
- **`.auto/measure.sh`** — the benchmark definition. Do not change the budget.

## Off Limits

Never touch, and never weaken to win a number:

- `scripts/numeric_palette.py`, `scripts/middle_palette.py` — the prior
  frontiers and the fences this search inherits.
- `spec/distance-matrix.yaml`, `spec/roles.yaml`, `spec/environments.yaml` —
  thresholds are READ, never edited.
- `src/grotto/**` — colour maths, contrast, CVD, spectral. Pinned to
  primary sources by `tests/test_metrics.py`; editing it invalidates every
  number in the repo.
- `scripts/soft_gate.py` — the gate.
- `themes/**`, `out/**` — committed artifacts and the comparison points.
- `.auto/checks.sh`.

**Hard constraints, never negotiable for any utility:** WCAG 2.x floors
against the canvas and every co-occurring surface; sRGB gamut; the hue
convention windows; the `same_family.min_distance` output gate; and the
chroma floor below. If a search change only helps by breaking one of these,
it is not an improvement.

**Declared trial settings, changeable but must stay declared** (each change
is an experiment, not a tuning knob, and belongs in the commit message):
hue window edges, `INK_L_DELTA` / `SURFACE_L_DELTA`, `SYNTAX_CAP` /
`DIAGNOSTIC_CAP` / `SURFACE_CAP` / `GAMUT_FRACTION_CAP`, the emphasis
budget and weight, the area-class shares, the shortfall exponent.

## Constraints

- No new dependencies. `coloraide`, `numpy`, `pillow`, `pyyaml` only.
- The search must stay **deterministic for a fixed seed** — byte-identical
  output across runs. No `time`-dependent or hash-ordered behaviour.
- Every palette must pass `scripts/soft_gate.py`. `ar.py log` will not `keep`
  a run whose checks failed.
- Do not read the score out of the search's own report. `measure.sh` scores
  through `soft_metric.py` for exactly this reason.
- Simpler is better: removing code for equal utility is a `keep`.

## Autoresearch bookkeeping

```bash
uv run python .auto/ar.py status           # best, gain, confidence, recent runs
uv run python .auto/ar.py show bound       # every logged value for an asi key
```

Working branch: `feat/pr-theme-autoresearch`, based on
`origin/review/palette-first-design` (PR #2, the superset that contains PR
#1's toolkit and all three numeric frontiers). Commits are one experiment
each.

## What's Been Tried

### Reading the open PRs first (context, not experiments)

- **PR #1 `dev/review-and-respread`** — the toolkit: contrast/CVD/spectral
  maths pinned to primary sources, the Layer-2 transform, candidates A/B/C,
  474→546 tests. Its own summary reports the finding this loop exists to act
  on: A/B/C were **perceptually identical at night** (pairwise dE 0.011–0.020,
  below JND), because every candidate shares contrast-band lightness centres
  and shrinks chroma through a multiplicative chain.
- **PR #2 `review/palette-first-design`** — the design exploration on top of
  `dev/numeric-palettes`: the Vivid studies, `NUMERIC.md`, and
  `docs/review/optimizer-constraints.md`. That last file is this loop's
  brief: it rejects Numeric N01 ("too intense and not visually pleasing"),
  notes Middle M01 is unselected, and specifies the small experiment.
- **Pullfrog's review of PR #1** — two rounds, all findings fixed; the only
  open nit is the nonstandard `module` semantic selector. Nothing here
  contradicts the plan.

### Run 0 — baseline search, soft objective — **checks_failed**

First honest run of the shortfall objective inside the middle fences.
Utility **0.9482** (vs middle-m01's 0.9361) at a 12 s budget against
middle's 45 s — the objective change itself is already a large win.

But `scripts/soft_gate.py` rejected it: **`error` came out achromatic
(C = 0.0011–0.0022) in all three seeds.** This is the exact pathology
`NUMERIC.md` §10 already documented for the middle frontier — "it zeroes one
diagnostic's chroma to buy lightness separation" — and the shortfall
objective inherits it, because a term that has already cleared its threshold
contributes zero and achromatic is the cheapest way to stay cleared.

Consequence for the loop: the objective has no floor, so it will always
prefer grey to a colour nobody asked for. Fixed next by a chroma **floor**
at `HUE_AUDIT_MIN_CHROMA` = 0.02 — the repo's own declared "hue is
perceptually present" threshold, not a new number.