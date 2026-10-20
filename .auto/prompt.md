# Autoresearch: soft-objective Night palette search (Grotto)

## v2 (branch feat/palette-autoresearch-2) — read docs/review/soft-objective-v2.md

Runs 7–12 below the v1 record. v1's "converged" verdict was right about the
search and wrong about the cause: the surface cluster was boxed into a 0.035 L
band by the 3:1 muted inks, not by the fence. v2 lifts them, widens fences only
where the spec declares `lightness_offset`, adds convention windows, a surface
prominence rank and diagnostic chroma floors (all hard, all in the gate), and
fixes the salience repair's order. Benchmark 0.9369 → 0.9783 (stricter gate);
shipped `out/soft-night-v2/soft2-s01` 0.9797 vs v1 0.9392. The seed cap is
now CPU time. The default output is now `out/soft-night-v2`; v1's
`out/soft-night` is frozen.

**Run 13 changed the instrument** (`soft_metric.INSTRUMENT_VERSION = 2`, 127
terms): surface visibility bands read from `model.SURFACE_STEPS`, surface
anti-collapse, and CVD terms credited where `grotto.channels.judge` finds a
delivered channel. Numbers before and after run 13 are NOT comparable; re-score
references with `soft_metric.py`. The search optimises `sm.instrument_terms`, the
same table.

**Profiles (run 15 on).** `soft_palette.PROFILES`: `default` is Grotto Night
(now with 0.10 extra downward ink room and a 0.05 syntax chroma floor; shipped
0.9853). `cvd` is the experimental variant, benchmarked with
`AR_PROFILE=cvd uv run python .auto/ar.py measure` and scored colour-only.
Its log entries carry `profile=cvd` and are flagged as instrument changes.
It ships to `out/soft-night-v2-cvd` (68/78 CVD checks on colour alone).
docs/review/soft-objective-v2.md §7.

## Status: converged inside the declared design. Read this first.

The optimisation target has hit its ceiling, measured three independent ways
(§ "Saturation" below). **Do not re-run kicks or re-probe the gamut
fraction** — both are recorded negative results. The remaining work is not an
optimisation: see "If you resume this session".

Shipped: `out/soft-night/soft-s01.night.yaml`, seed 20260817, full budget —
**utility 0.9392**, emphasis 0.0426, worst margin 0.215, 0 WCAG violations,
0 salience reversals, 0 fence violations.

## Objective

Make the **Grotto Night theme palette** as good as it can be, and make the
**search that produces it** as good as it can be, by running the experiment
`docs/review/optimizer-constraints.md` asks for and then iterating on the
search until it is as strong as the fences allow.

## Metrics

`.auto/measure.sh` runs three fixed seeds of `scripts/soft_palette.py` at a
fixed budget and re-scores each result with `scripts/soft_metric.py` (an
instrument that never imports the search).

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
  generalises across seeds. A gain smaller than `seed_spread` is luck.

### Reference points on this instrument (measured, not estimated)

| palette | utility | sep | emph | worst | wcag |
|---|---|---|---|---|---|
| candidate-a restrained night | 0.7900 | 0.2735 | 0.0085 | 0.000 | 12 |
| candidate-b balanced night | 0.7896 | 0.2104 | 0.0199 | 0.000 | 12 |
| candidate-c expressive night | 0.8022 | 0.1978 | 0.0271 | 0.000 | 12 |
| fig-vivid night (PR #2 draft) | ~0.79 | 0.190 | 0.059 | 0.000 | 1 |
| middle-m01 night | 0.9361 | 0.0592 | 0.0456 | 0.282 | 0 |
| numeric-n01 night (**rejected**) | 0.6605 | 0.0228 | 0.0857 | 0.507 | 0 |
| **soft-s01 night (shipped)** | **0.9392** | 0.0608 | 0.0426 | 0.215 | 0 |

The instrument deliberately ranks the owner's *rejected* numeric frontier
**below** the middle frontier: the shortfall pays nothing for margin a term
already has, so loudness has to be paid out of the emphasis budget. If a change
makes numeric-n01 top the table again, the instrument has regressed to the
max-min objective it replaced.

## How to Run

```bash
uv run python .auto/ar.py measure     # ~38 s, prints the metric JSON
uv run python .auto/ar.py checks      # hard gates + scoped pytest
uv run python .auto/ar.py log keep "what I changed" --asi key=value
```

Loop: **change something → `measure` → `checks` → `log`**.
`keep` commits; `discard` / `crash` / `checks_failed` reverts the code and keeps
only the record. **Never** hand-edit `utility` into the log.

Budget is fixed by `.auto/measure.sh`: `--restarts 4 --samples 8
--refine-passes 10 --select 3`, seeds `20260817 20260818 20260819`, ~13 s per
seed, capped at 16 s per seed. The cap matters: without it the benchmark would
be won by brute force rather than by a better search. Raise the budget and you
have measured a different experiment.

**Bookmark:** `ar.py status` marks runs whose `asi` carries
`instrument_change` with `*` and excludes them from `best` and from `gain`.
A benchmark that averages across an instrument change starts lying.

## Files in Scope

- **`scripts/soft_palette.py`** — the search: `SoftProblem`, `soft_refine`,
  `run_search`, `finalize`, `shipped_hexes`, `repair_wcag`,
  `enforce_salience_rank`, `boost_normc`.
- **`scripts/soft_metric.py`** — the instrument. `EMPHASIS_BUDGET`,
  `EMPHASIS_WEIGHT`, `AREA_CLASS_SHARE`, `SURFACE_AREA_WEIGHT`,
  `SHORTFALL_EXP`, `CHROMA_FLOOR`, `ink_shares()`, `area_weights()`. Changing
  it changes the *goal*, not the search.
- **`scripts/soft_gate.py`** — hard gates. Treat as untouchable.
- **`.auto/measure.sh`** — the benchmark definition. Do not change the budget.

## Off Limits

Never touch, and never weaken to win a number:

- `scripts/numeric_palette.py`, `scripts/middle_palette.py` — the prior
  frontiers and the fences this search inherits.
- `spec/distance-matrix.yaml`, `spec/roles.yaml`, `spec/environments.yaml` —
  thresholds are READ, never edited.
- `src/grotto/**` — colour maths, contrast, CVD, spectral, pinned to primary
  sources by `tests/test_metrics.py`; editing it invalidates every number.
- `scripts/soft_gate.py`, `.auto/checks.sh`.
- `themes/**`, `out/**` — committed artifacts and the comparison points.

**Hard constraints, never negotiable for any utility:** WCAG 2.x floors against
the canvas and every co-occurring surface; sRGB gamut; the hue convention
windows; `same_family.min_distance`; the chroma floor; the DESIGN.md §6
salience budget; and within-family salience rank.

**Declared trial settings**, changeable but must stay declared in the source
and in the commit message: hue window edges, `INK_L_DELTA` / `SURFACE_L_DELTA`,
`SYNTAX_CAP` / `DIAGNOSTIC_CAP` / `SURFACE_CAP` / `GAMUT_FRACTION_CAP`, the
emphasis budget and weight, the area-class shares, the shortfall exponent.

## Constraints

- No new dependencies (`coloraide`, `numpy`, `pillow`, `pyyaml` only).
- Byte-deterministic for a fixed seed. No time- or hash-ordered behaviour.
- Every palette must pass `scripts/soft_gate.py`.
- Do not read the score out of the search's own report; `measure.sh` scores
  through `soft_metric.py` for exactly this reason.
- Simpler is better: removing code for equal utility is a `keep`.

## Autoresearch bookkeeping

```bash
uv run python .auto/ar.py status
uv run python .auto/ar.py show bound      # every logged value for an asi key
```

Branch `feat/pr-theme-autoresearch`, based on `origin/review/palette-first-design`
(PR #2 — the superset containing PR #1's toolkit and all three numeric
frontiers). One commit per experiment.

---

# What was learned

## Context from the open PRs

- **PR #1 `dev/review-and-respread`** — the toolkit. Its own summary reports the
  finding this loop exists to act on: A/B/C were **perceptually identical at
  night** (pairwise dE 0.011–0.020, below JND) because every candidate shares
  contrast-band lightness centres and shrinks chroma through a multiplicative
  chain.
- **PR #2 `review/palette-first-design`** — the design exploration on top of
  `dev/numeric-palettes`: the Vivid studies, `NUMERIC.md`, and
  `docs/review/optimizer-constraints.md`. That file is this loop's brief.
- **Pullfrog's review of PR #1** — two rounds, all findings fixed. Nothing here
  contradicts the plan.

## Where the loss actually is

The shortfall decomposes into **6 independent connected components** over the
23 optimised roles. A move inside one cannot change another's terms.

| component | roles | terms | share of loss |
|---|---|---|---|
| **surface cluster** | selection, search_match, search_match_current, diff_added, diff_removed, diff_changed | 44 | **99.2%** |
| syntax + diagnostics | keyword…error, warning, success, tag, type (13) | 96 | 0.8% |
| unconstrained | info, focus, debug_current, breakpoint | 0 | 0% |

Those four roles appear in **no** matrix pair at all. Inside the cluster the
argmin is always a **must-CVD** term against `active_line`, which is
*scaffold*: copied verbatim from candidate-b, never optimised. NUMERIC.md §5.2
reached the same conclusion for the numeric frontier.

## Saturation

| lever | result |
|---|---|
| 8x budget (24 x 16 x 30, 86 s vs 12.5 s) | 0.9474 → 0.9479, **below the seed spread** |
| loss-targeted iterated local search (component kicks) | +0.0001 for +50% wall clock |
| every single-fence relaxation | within seed noise |

The ascent converges in 6–8 passes from any sample. **The bottleneck is the
fences and the pinned scaffold, not the search.**

### Fence sensitivity (2–3 seeds each, post-repair)

| change | utility | verdict |
|---|---|---|
| baseline (middle fences) | 0.9448 | — |
| `SURFACE_L_DELTA` 0.06 → 0.10 | 0.9448 | no effect at all |
| `SURFACE_L_DELTA` → 0.14 | 0.9459 | within noise |
| `SURFACE_CAP` 0.10 → 0.14 | 0.9458 | within noise |
| diff/search hue windows +90° | 0.9457 | within noise; breaks conventions |
| `INK_L_DELTA` 0.04 → 0.08 | 0.9468 | within noise; **forbidden** |
| `GAMUT_FRACTION_CAP` 0.70 → 0.85 | 0.9383 | within noise, non-monotonic; **inert** |
| surface L 0.10 **and** ink L 0.08 | 0.9572 | **forbidden** |

Two traps, both rejected:

* **Lightness fences are forbidden by the DESIGN.** O4-vs-O2: *"Making pairs
  CVD-robust means lightness-separating them, which consumes the lightness axis
  that salience also needs… achieved through redundant non-colour channels
  rather than by distorting the palette."* The shortfall objective cannot see
  the cost. Run 2's salience gate is what makes it visible — **do not go back
  to this lever.**
* **`GAMUT_FRACTION_CAP` looked like the one reproducible lever** (+0.0015 with
  zero seed spread, measured pre-repair) and is **inert**. The class chroma
  caps bind first: 0/23 roles reach the gamut edge from 0.70 through 0.90.
  *Lesson: a probe that skips post-processing measures the wrong thing.*

### The emphasis budget is not the lever either

| budget | utility | EMPH |
|---|---|---|
| 0.050 / **0.045** | 0.9365 | 0.0405 |
| 0.042 | 0.9335 | 0.0408 |
| 0.038 | 0.9256 | 0.0389 |
| 0.035 | 0.9157 | 0.0366 |
| 0.032 | 0.9071 | 0.0333 |

Tightening costs ~**7 units of utility per 0.001 of quietness**. The palette
already lands at 0.0405, below the budget, so the term is inactive; it is
already quieter than every palette the owner has accepted. The proposal's third
experiment ("a lower surface-emphasis budget") is answered: **not at this
operating point.**

---

# Run log

## Run 0 — baseline shortfall search — **checks_failed**

Utility 0.9482 (beats middle-m01's 0.9361 at a 12 s budget against middle's
45 s) — but the gate rejected all three seeds: **`error` came out achromatic
(C = 0.0011–0.0022)**.

The exact pathology NUMERIC.md §10 documented for the middle frontier. Under a
shortfall objective it is not a corner case: a term that has cleared its
threshold contributes exactly zero, so achromatic is the cheapest way to stay
cleared.

## Run 1 — chroma floor — kept, 0.9455

`CHROMA_FLOOR = 0.02`, read from `middle_palette.HUE_AUDIT_MIN_CHROMA` — the
repository's own "hue is perceptually present" threshold, not a new number.
Cost 0.0027; `min_anticollapse` improved 1.030 → 1.077. **Still inadmissible,
for a reason the gate did not yet check.**

## Run 2 — salience rank promoted to a hard gate — kept, 0.9365

**The instrument was wrong and this run paid for it.** The shortfall objective
is structurally blind to the salience hierarchy. Measured on the run-1 palette:
**5 within-family salience reversals**, against **0** for committed candidate-b
and **1** for middle-m01.

`model.py` calls its proxy "a soft signal" and leaves it out of `ok`. Right for
a checker on hand-authored palettes, wrong for an optimiser, so the gate
promotes it — using **model.py's own definition** (chroma channel, within a hue
family, tied salience skipped, 2e-3, normalised `C / max_chroma(L, h)`). An
earlier attempt checked *lightness* rank across all roles and flagged the
committed palettes; that was a checker artefact and was discarded.

Utility fell 0.9455 → 0.9365. **That fall is the point** — the previous number
was measured on palettes that broke a design constraint. Seed spread tightened
0.0063 → 0.0013: the constraint removes a degree of freedom and the seed luck
with it.

Four findings from getting the search to satisfy it, all in the commits; the
interactions are the reusable part:

1. **Evaluate repairs against `shipped_hexes`** — the hexes the *written YAML*
   will carry, which differ by one 8-bit step from `problem.hexes()`. Snapping
   authored coordinates onto the hex instead breaks `fence_audit_state`, which
   allows no quantisation slack.
2. **Measure repair progress in normalised chroma, never coordinates**: the
   chroma ceiling clamps a coordinate move to "no change" while the hexes
   around it still shift.
3. **Run repairs to a fixed point.** Nudging a surface to restore a WCAG floor
   changes its lightness, which changes `max_chroma(L, h)`, which changes its
   normalised chroma and re-opens a salience pair the previous repair fixed.
4. **Accept a repair move only if it does not increase the reversals the moved
   role participates in.** Otherwise the operators fight: boosting
   `breakpoint` past `diff_removed` fixes one pair and breaks
   `breakpoint`/`error`, whose fallback then undoes the boost.

`boost_normc` also shows the salience channel can be raised **without adding
colour**: `C / max_chroma(L, h)` rises if the role moves where the gamut holds
less chroma. That matters because the chroma floor and the salience order are
in direct tension, and gamut capacity is the only way out.

## Run 3 — loss-targeted ILS kicks — discarded

Displaced the 99.2% component and re-refined only it. **+0.0001** for +50%
wall clock (19.7 s/seed, over the cap). Saturation confirmed a third way.
`SoftProblem.components` / `loss_component` / `_component_losses` are correct
and cheap — keep them if a future search needs component addressing.

## Run 4 — free `active_line` as a coloured surface — discarded, **owner decision**

**+0.0132** (0.9365 → 0.9497), worst margin 0.132 → 0.174, emphasis under
budget. Not taken: `spec/roles.yaml` declares the role `chroma_class: trace`,
`family: neutral`, `salience: 0`, with the note *"most themes overdo this and
create a permanent bright band"*; the current line is the largest non-canvas
area in an editor; and the repairs still leave 0.3 reversals/seed.

## Run 5 — emit the deliverable — kept, 0.9365

`variants.html` + an installable `vscode-preview/`. A palette nobody can look at
is not finished.

## Run 6 — select on the FINAL palette — kept, 0.9369 benchmark / 0.9392 full

The hard output constraints are **repairs, not filters**: they move colours, so
they reorder candidates. At full budget the best pre-repair candidate (0.9479)
finished post-repair at **0.9360**, while candidates starting 0.0008 lower
finished at **0.9392**. Ranking on the pre-repair score shipped the worse
palette. Selection now runs the whole pipeline over the strongest few
candidates and keeps the best final result.

Honest wart: the `free` restart kind is dropped on some seeds — the repairs do
not converge on the `rose` family (`breakpoint` sal 5, `error` 6,
`diff_removed` 3: three levels in one hue family, all needing monotone
normalised chroma, inside fences authored for a different purpose). Reported
per candidate with its reason, never silently swallowed.

---

# If you resume this session

The target has converged inside the declared design. Do not re-run kicks or
re-probe the gamut fraction. The remaining work is not an optimisation:

1. **The run-4 decision** — is +0.0132 worth colouring the current-line band?
   A `spec/roles.yaml` change and an owner call.
2. **The redundant non-colour channel.** The binding constraint is CVD survival
   of five co-occurring surfaces against a pinned `active_line`, inside sRGB.
   No palette reaches it. DESIGN.md D-3 and the matrix itself say the fix is a
   mapping-layer channel — selection/diff borders, gutter signs, distinct icons
   — and WCAG 2.2's use-of-colour criterion requires it independently of any
   simulation. **That verification is the next piece of work, and nothing in
   this session substitutes for it.**
3. **The `rose`-family repair convergence**, if the fences ever move.