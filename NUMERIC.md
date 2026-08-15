# NUMERIC.md — the numeric-first palette frontier (NON-CANDIDATE)

Branch `dev/numeric-palettes`. Everything on this branch is **NON-CANDIDATE
exploration material**. Nothing here modifies the committed candidates, specs,
DESIGN.md, or any other artifact; every addition is a new file. Whether the
numeric frontier described below is *desirable* is a **human decision** — this
branch exists to show where the numbers alone actually land, so that decision
can be made against evidence instead of against a local minimum.

## 1. The question

The owner's complaint: **the Night palettes of all three candidates look almost
identical.** Verified root cause, in the Layer-2 transform:

1. every role's lightness is solved to an **APCA contrast-band centre shared by
   all candidates** (`spec/environments.yaml: contrast_bands`, plus
   `salience_apca_step`), so all candidates put (nearly) the same lightness on
   every role;
2. chroma passes through a **multiplicative chain** (night
   `chroma_attenuation: 0.35` × per-role `night_adaptation` × chroma-class
   fractions × absolute caps ~0.14–0.20), so categorical roles land at
   C ≈ 0.02–0.10;
3. hue anchors are shared across candidates.

Net effect: at night, categorical roles sit at almost the same lightness with
a trace of chroma — one theme, three labels. The suspicion is that the project
is stuck in a local minimum of its own taste constraints. This branch removes
the taste layer entirely and re-solves Night by direct numeric search.

## 2. Thrown out vs kept

**Thrown out (taste, per the owner's instruction):**

| Removed | Where it lived |
|---|---|
| contrast-band lightness targets (APCA centres) | `environments.yaml: contrast_bands` |
| salience-driven lightness hierarchy | `salience_apca_step`, salience ranking |
| chroma budgets: class fractions, multiplicative attenuation, night adaptation, absolute ceilings | `chroma_classes`, `chroma_attenuation`, `night_adaptation`, caps |
| the "5 hue families" economy; same-family UPPER bounds; per-role hues forbidden | binding anchors, `same_family.max_distance` |
| warm-anchor hue adaptation | `warm_anchor`, `hue_rotation` |
| hue sharing across candidates | shared bindings |
| the night foreground lightness ceiling | `foreground_ceiling` |
| the chroma-class vocabulary | `chroma_class` |

**Kept (technical), with the justification for each:**

1. **WCAG 2.x AA floors as hard constraints** — read from each role's
   `accessibility_floor` in `spec/roles.yaml`, resolved through
   `spec/environments.yaml: accessibility_floors` (body_text 4.5, non_text
   3.0). Enforced against the background **and** every co-occurring surface an
   ink can land on (the spirit of `model.CO_OCCURRING_SURFACES`). WCAG 2.x is
   the project's compliance instrument; accessibility wins over every
   preference, including numeric ones.
2. **sRGB gamut** — every emitted colour's chroma is projected to
   `max_chroma(L, h)`. No out-of-gamut requests, no silent clipping.
3. **The distance-matrix pair list, thresholds READ (never edited)** — the
   objective maximises the worst normalised margin over `must_distinguish`
   pairs (normal vision 0.13; simulated protan/deutan/tritan at severity 1.0,
   0.09) and `should_distinguish` pairs (normal vision, 0.08) at a lower
   weight. The legibility pairs the matrix already lists (fg/bg etc.) are part
   of the same list.
4. **Hue pinning across day/evening/night is NOT imposed** (choice, documented
   here): this branch produces Night only — night first and well. If a numeric
   Night palette is ever promoted, its per-role hues are the natural anchors
   for a re-solve of the other variants; enforcing cross-variant stability
   here would have re-imported a constraint the branch charter removes.

**One addition, and why:** an **anti-collapse floor**. The matrix's only link
for categorical pairs like number/constant was the same-family economy, which
this branch throws out; the objective was therefore *blind* to them and the
first smoke run collapsed such pairs to dE ≈ 0.005 (sampling noise). The fix
reuses a value READ from the same matrix — `same_family.min_distance: 0.03`,
the file's own "still not identical" distance — as a floor on categorical
pairs the matrix does not otherwise constrain. Only the *min* side is taken;
the *max* side (the hue economy) stays thrown out. It turned out to matter
for the comparison too: both committed candidates render number and constant
**byte-identically** (dE = 0.000), which the floor surfaces instead of hiding.

## 3. Declared objective (exact)

For a palette P, with all margins normalised by their class threshold:

```
M_norm    = min over must pairs, normal vision .......... dE / 0.13
M_cvd     = min over must pairs × {protan, deutan, tritan}@1.0 ... dE / 0.09
M_should  = min over should pairs, normal vision ........ dE / 0.08
M_anti    = min over unconstrained categorical pairs .... dE / 0.03

J(P) = min( M_norm, M_cvd, 2.0 · M_should, M_anti )
```

* `J > 1` means every must pair clears its threshold under all four vision
  conditions. No palette in this repo reaches it at night (see §5).
* `2.0 · M_should`: should pairs bind only once their margin falls below half
  the worst must margin (the "lower weight").
* Weights and thresholds are constants declared in
  `scripts/numeric_palette.py`; thresholds are read from
  `spec/distance-matrix.yaml` at runtime and never edited.
* Greedy acceptance is lexicographic on `(J, J2)` where `J2` is the mean of
  all normalised terms — a plateau tie-break that cannot trade the worst pair
  away (J must not decrease).

Caveat, stated plainly: CVD margins come from the **population-average
Brettel dichromat models** (severity 1.0); they predict collapse, not any
individual's experience. WCAG numbers are compliance checks; **APCA is not
used anywhere on this branch**.

## 4. Method

Deterministic, seeded (default seed 20260815). All numbers below are
reproducible with `uv run python scripts/numeric_palette.py` (~53 s wall clock
on the dev machine; stdout reports the measured runtime — the artifact files
carry no timestamps and are byte-identical across runs, verified by re-running
the full pipeline and diffing).

1. **Scaffold.** The neutral roles are copied **verbatim** from
   `themes/candidates/candidate-b-balanced.night.yaml`: bg, bg_elevated,
   bg_overlay, the fg tiers, comment/docstring, punctuation, operator, line
   numbers, ui_inactive, active_line, deprecated, parameter, property. The
   authored canvas is the WCAG reference and stays. The **23 chromatic roles**
   (syntax + diagnostics + highlight surfaces + focus/breakpoint) are
   optimised: free hue on the circle, free lightness within the WCAG-feasible
   interval (computed against the background/surfaces), free chroma within
   the gamut.
2. **Feasible-set repair.** Chroma is projected into the sRGB gamut; an ink's
   lightness is raised until its floor holds against bg **and** all
   co-occurring surfaces; a surface's lightness is lowered until every *fixed
   scaffold* ink keeps its floor on it (chromatic inks then repair against the
   final surfaces). Every candidate the search ever evaluates is a legal
   palette by construction.
3. **Multi-start structured sampling.** Four restart kinds — evenly spread hue
   ladders (shuffled assignment), ladders + shuffled lightness ladders,
   candidate-B hues ± 35°, free-uniform hues — with chroma biased high
   (f = 1 − 0.35·u² of `max_chroma`).
4. **Greedy coordinate refinement on the full objective** (normal + CVD; the
   coloraide Brettel simulation measures ~20–40 µs/call here, so no
   two-stage proxy was needed): deterministic move set on hue/L/chroma-fraction,
   incremental evaluation (only terms touching the moved role recompute).
5. **Roles the matrix ignores** (namespace, tag, info, debug_current,
   breakpoint in the full set) are placed deterministically *after* refinement
   by maximising their minimum dE to every other chromatic role on a coarse
   grid — pure margin logic, no thresholds.
6. **Output.** A diverse top-6 (best + greedy picks ≥ 20° mean hue distance
   apart — the anchor_search lesson: a max-min leaderboard is one narrow
   peak), each written in the repo's OKLCH yaml format with `candidate:
   false` and NON-CANDIDATE notes.

## 5. Findings

### 5.1 The numeric comparison (Night; margins normalised, bigger is better)

| palette | J | must-normal | must-CVD | should (×2 in J) | anti-collapse | min categorical dE | mean categorical C | min WCAG | WCAG violations |
|---|---|---|---|---|---|---|---|---|---|
| numeric-n01 | **0.506** | 0.780 | **0.506** | 0.363 | 0.531 | 0.016 | 0.205 | 3.03 | 0 |
| numeric-n02 | 0.477 | 0.769 | 0.477 | 0.363 | 0.560 | 0.017 | 0.242 | 3.09 | 0 |
| numeric-n03 | 0.459 | 0.587 | 0.459 | 0.363 | 0.488 | 0.015 | 0.229 | 3.00 | 0 |
| candidate-b night | 0.000 | 0.059 | 0.021 | 0.164 | 0.000 | **0.000** | 0.041 | 2.70 | 12 |
| candidate-c night | 0.000 | 0.047 | 0.021 | 0.191 | 0.000 | **0.000** | 0.060 | 2.71 | 12 |

* `worst matrix margin` (the mission objective without the anti-collapse
  floor): **numeric 0.506 vs candidate-b 0.021 vs candidate-c 0.021** — a
  ~24× improvement on the worst constrained pair.
* The candidates' worst pairs are the **diff surfaces collapsing under
  deutan/protan**: diff_added/diff_removed at dE **0.002** under deutan
  (candidate-b), diff_added/diff_changed at dE 0.002 (candidate-c). Both also
  render number/constant identically (dE 0.000). The numeric palettes lift the
  worst deutan margin to dE 0.046 — still below the 0.09 dichromat threshold,
  but a 24× recovery of the collapse.
* The numeric palettes' should-margin minimum (0.363) is **pinned by the
  scaffold itself**: bg_elevated/bg_overlay (dE 0.029, both verbatim from
  candidate-b) cannot satisfy should_distinguish at night under any
  optimisation, because the taste layer's authored elevation steps are frozen
  into the scaffold. The optimizer's should pairs (e.g. keyword/string) sit at
  0.34–0.44.
* The candidates' 12 WCAG violations are the transform's own recorded
  ink-on-surface warnings (fg_muted/line_number over selection/search/debug;
  this branch's gate additionally covers the border role ui_inactive with
  identical numbers). The numeric palettes have **0** — floors over
  co-occurring surfaces are hard constraints here, which is why their
  highlight surfaces are darker than the candidates'.

### 5.2 The binding constraint at the optimum

At the best numeric optimum (numeric-n01), measured over all 162 constraint
terms:

* **Argmin term: `must_deutan(selection, active_line)`** — the binding
  constraint is **CVD survival of the co-occurring-surface cluster**
  (selection/search/diff/active_line pairwise separation under deutan and
  tritan), not syntax. The worst 10 terms are dominated by surface pairs under
  dichromat simulation; the ink syntax pairs clear everything comfortably.
* **Gamut binds hard**: 17 of 23 chromatic roles sit on the sRGB gamut edge
  (C ≥ 99.5% of `max_chroma`) — the objective wants *more* chroma than the
  display can make. The numeric frontier is literally chroma-starved by sRGB,
  which is the direct refutation of the taste layer's chroma caps: given a
  free hand, the numbers spend every available chroma unit.
* **WCAG does not bind**: 0 ink roles sit at their WCAG-feasible lightness
  floor (worst ratio ≥ 0.02 above floor everywhere). Floors are cheap to
  satisfy against this canvas; they are not what makes Night hard.
* The optimum is **not** fully flattened: only 4/162 terms sit within 5% of
  the worst margin — the surface-cluster terms form a small, hard core;
  everything else has slack.

**Answer to the question "what binds at the optimum": (1) dichromat survival
of the highlight-surface cluster, (2) the sRGB gamut, (3) not WCAG.**

### 5.3 What the numeric palettes look like (description, not judgement)

* **Near-white outliers**: keyword, string and success sit at L ≈ 0.98–0.99
  with almost no chroma — the easiest way to buy distance from mid-lightness
  peers. Chromatic identity is not something the objective values; hue is
  only worth having when it separates.
* **Max-chroma everything else**: function/builtin/namespace cluster at
  L ≈ 0.67–0.69 with C ≈ 0.31 (the gamut edge), hues ~325–335°; type/constant/
  decorator/number at C ≈ 0.19–0.23 across scattered hues.
* **Saturated highlight surfaces**: selection C ≈ 0.15, diff washes C ≈
  0.10–0.16, all inside a ~0.22–0.26 lightness band with hues spread around
  the whole circle — this is how the optimizer keeps five co-occurring
  surfaces separable under dichromat vision: lightness room is scarce (the
  scaffold ink floors cap it), so it spends chroma and hue instead. The
  surfaces are *far* more colourful than anything the taste layer would emit.
* **No semantic hue conventions survive**: diff_added lands at hue ≈ 28°
  (red-orange, not green), keyword near-white, function violet. The matrix
  never required added≈green; only the taste layer did.
* **A wide lightness spread** among categorical roles (≈ 0.61–0.99) replaces
  the candidates' near-constant ≈ 0.80–0.88 band.

### 5.4 Honest limitations

* **Max-min is not taste.** The optimizer maximises the worst margin; it does
  not value elegance, hue semantics, cross-variant stability, or restraint.
  Numeric-n01 would read as a very colourful, semantically unconventional
  theme. That is the point: it is the frontier, not a proposal.
* **Local search only.** 24 restarts × greedy coordinate refinement; no
  proof of optimality. The frontier found is a lower bound on the true one.
* **J stays below 1.0.** Even the numeric frontier does not satisfy the
  distance matrix at night against this canvas: the worst surface pairs reach
  only ~56% of the dichromat threshold. Either the matrix's night expectations
  for co-occurring surfaces are stricter than sRGB + WCAG allow, or surfaces
  need the redundant channels (gutter signs, borders) the matrix itself says
  they must carry.
* **The scaffold is inherited taste.** The canvas, fg tiers and active_line
  are candidate-b verbatim; the whole search solves against an authored
  background (by design — it is the WCAG reference). Its own elevation steps
  fail a should pair (§5.1).
* **Brettel is a population-average model** of dichromat appearance at
  severity 1.0; anomalous trichromacy (the common case) is not modelled.
* **Chroma pushing the gamut edge means hue-linearity error is maximal
  there** (OKLab's known blue/purple curvature, RESEARCH.md R-8); hue
  distances in that sector are approximate.

## 6. Where everything lives

* `scripts/numeric_palette.py` — the optimizer (additive; imports grotto
  modules only).
* `out/numeric-night/numeric-n01..06.night.yaml` — the palettes (OKLCH yaml,
  `candidate: false`).
* `out/numeric-night/metrics.json`, `metrics.txt` — the full comparison, the
  per-palette worst-10 tables with `distance.breakdown` channels, and the
  binding-constraint analysis.
* `out/numeric-night/variants.html` — dark side-by-side page: categorical /
  diagnostics / surface swatch strips and the R specimen rendered per palette
  (numeric-n01..06 + candidate-b/c night for comparison).
* `out/numeric-night/vscode-preview/` — and **installed** to
  `/mnt/c/Users/m0hawk/.vscode/extensions/grotto-numeric-exploration/`
  (labels **Grotto N-Explore 01..03 Night**, uiTheme `vs-dark`, displayName
  "Grotto Numeric Exploration (NON-CANDIDATE)") for eyeballing in a real
  editor.
* `tests/test_numeric_palette.py` — unit tests (feasible-L interval, gamut
  projection, reduced-subset fixed-seed run: floors hold, worst margin beats
  the scaffold, byte-deterministic output).

Reproduce: `uv run python scripts/numeric_palette.py` (add `--no-install` to
skip the extension copy). Outputs are byte-stable; two consecutive full runs
were diffed to confirm it.

**Reminder: NON-CANDIDATE.** Promoting any of this — or any single number in
the objective — is the owner's call. The most defensible takeaway is not "use
numeric-n01" but: *the taste layer's night chroma caps and shared lightness
bands cost ~24× on the worst distance-matrix margin, WCAG is not the binding
constraint at night, and the real ceiling is dichromat survival of the
highlight-surface cluster inside the sRGB gamut.*
