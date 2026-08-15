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

---

# The middle frontier (NON-CANDIDATE, part 2)

## 7. The question, and where the fences come from

The owner looked at the installed "Grotto N-Explore" themes in a real editor
and rejected the numeric frontier's *look*. Verbatim feedback:

> "Not sure if the 3 new N ones are visually pleasing. the magenta is very
> in-your-face."

That is the primary design input for the middle frontier: optimise the SAME
numeric objective (§3, unchanged) but INSIDE taste fences that keep grotto's
character, and buy back as much margin as the fences allow. The fences are
the direct answers to the rejection:

* **Hue convention windows** per chromatic role (degrees OKLCH): string
  95–165 · function 180–265 · keyword 275–335 · number/constant/decorator
  40–110 · builtin 0–50 · type/namespace 160–215 · tag 95–165 or 180–265
  (its committed family) · error 0–40 · warning 60–110 · info 180–265 ·
  success 90–160 · diff_added 90–160 · diff_removed 0–40 · diff_changed
  40–110 · search_match[_current] 40–110 · selection/focus 180–265 ·
  breakpoint 0–40 · debug_current 40–110. Rationale: these are the learned
  associations users bring; breaking them is what made N-Explore unpleasant.
  Every committed candidate-b night hue is inside its window by construction.
* **Lightness structure stays**: each chromatic ink's L may move at most
  ±0.04 from its candidate-b night value; each highlight surface's L at most
  ±0.06 (surface lightness spread is the distance-matrix-sanctioned
  redundant channel — the deutan fix for the diff pairs was expected from
  here, not from hue). The 17 neutral scaffold roles stay verbatim from
  `candidate-b-balanced.night.yaml`, as in §4.
* **Loudness ceilings** (the direct answer to "magenta in-your-face"):
  syntax roles C ≤ 0.12, diagnostics ≤ 0.16, highlight surfaces ≤ 0.10, AND
  every role ≤ 70 % of `max_chroma(L, h)` so nothing rides the gamut edge
  (numeric-n01 had 17 of 23 roles at ≥ 99.5 % of the edge). These supersede
  anything the margin objective wants.
* **WCAG floors stay hard** against the background AND every co-occurring
  surface — the committed candidate-b night palette carries 12
  ink-over-surface violations (fg_muted / line_number / ui_inactive, floor
  3.0, over selection / search_match / search_match_current / debug_current);
  here they become constraints, not warnings.

Two quantisation notes, documented because they matter for reproduction:
projection keeps a small margin *inside* every fence (hue 1.5°, chroma
0.002) because the palette ships as 8-bit hex and hue at very small chroma
is ill-conditioned under rounding; the hex-space fence audit therefore
checks hue windows only at C ≥ 0.02 (below the matrix's own JND anchor the
hue channel carries no readable signal).

## 8. Method (reuse, not rewrite)

`scripts/middle_palette.py` imports `numeric_palette` and reuses its
machinery: the term table and margin computation, gamut projection, the
WCAG-feasible lightness interval (used to start inks legal), the greedy
(J, J2) refinement loop and the multi-start driver — the latter two through
two documented injection points (`numeric_palette._apply_move` and
`._initial_state` are rebound to fence-aware versions), the diversity
picker, the feasibility check, the metrics block and the specimen renderer.
New code is only: fence projection and the fenced repairs (the numeric
climb loops with fence bounds — a move whose floor is unreachable inside
the fence is rejected), fenced sampling inside windows, fenced placement of
matrix-ignored roles, and the same_family enforcement below.

**same_family min-distance is an output gate, not just an objective term.**
Every same_family pair of the distance matrix must END at
dE ≥ `same_family.min_distance` (0.03, the file's own "still not identical"
bound). After refinement, a deterministic repair pass runs a bounded
coordinate search on any violating pair (numeric move set, fence-repaired),
under two guards: no sibling same_family pair may (re)collapse (hard), and
the global worst margin J may only be spent gradually (a tolerance ladder
0.02 → 0.06 → 0.15 → 1.0: repair for free first, buy the constraint with
margin if necessary). This kills the number/constant debt.

Deterministic, seeded (default seed 20260816, 24 restarts × 16 samples × 30
refine passes, ~45 s wall clock). Two consecutive full runs were diffed:
byte-identical artifacts.

## 9. Success criteria and the three-way comparison

Night; margins normalised by their class threshold; bigger is better.
`matrix` = the mission objective (worst must/should margin, without the
anti-collapse floor); `meanC`/`maxC` = categorical loudness.

| palette | J | matrix | must-N | must-CVD | should | min cat dE | meanC | maxC | min WCAG | WCAG viol | diff deutan dE | number/constant dE |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| candidate-b night | 0.000 | **0.021** | 0.059 | 0.021 | 0.164 | **0.000** | 0.041 | 0.081 | 2.70 | **12** | **0.002** | **0.000** |
| middle-m01 | 0.282 | **0.282** | 0.301 | 0.282 | 0.363 | 0.047 | 0.106 | 0.119 | 3.01 | **0** | 0.026 | 0.117 |
| middle-m02 | 0.267 | 0.267 | 0.330 | 0.267 | 0.363 | 0.051 | 0.107 | 0.118 | 3.00 | 0 | 0.025 | 0.083 |
| middle-m03 | 0.264 | 0.264 | 0.267 | 0.264 | 0.363 | 0.011 | 0.109 | 0.118 | 3.01 | 0 | 0.024 | 0.092 |
| numeric-n01 | **0.506** | **0.506** | 0.780 | 0.506 | 0.363 | 0.016 | 0.205 | 0.315 | 3.03 | 0 | 0.126 | 0.350 |

The three verified debts of the committed candidate, and what the middle
frontier did to each:

* **(a) number/constant byte-identical (dE 0.000)** → **0.083–0.117**, all
  ≥ the 0.03 same-family minimum (enforced as an output gate; m02 needed the
  repair pass: 0.021 → 0.083, J unchanged). Fixed.
* **(b) diff_added/diff_removed collapse to dE 0.002 under deutan** →
  **0.024–0.026**, a 12–13× recovery of the collapse — but still below the
  0.09 dichromat threshold. What the fences leave, measured exactly:
  * pair-only bound inside all fences (hue windows, C ≤ 0.10, L ±0.06,
    scaffold-ink WCAG): **dE 0.0547** (margin 0.61);
  * joint bound of the diff cluster (diff_added + diff_removed + diff_changed
    vs each other and vs the scaffold active_line, brute-forced by
    coordinate descent over the fenced grids): **margin ≈ 0.26** — and the
    greedy reaches 0.26–0.28. The gap between 0.61 and 0.26 is the *joint*
    cost: diff_added must clear active_line, diff_changed and selection at
    the same time, and the scaffold-ink WCAG floors pin all highlight
    surfaces into a narrow lightness band (roughly L 0.215–0.26), so the
    ±0.06 lightness-spread channel the redundant encoding was supposed to
    use is mostly spent before the diff pair itself gets any. This — not
    hue, not chroma — is what bounds the deutan fix under these fences.
* **(c) 12 ink-over-surface WCAG violations** → **0** (surfaces darken to
  the bottom of their fences until fg_muted / line_number / ui_inactive
  clear 3.0; min contrast 3.00–3.01). Fixed.

The margin/loudness tradeoff, stated plainly: candidate-b's committed
tastes sit at worst matrix margin **0.021** with mean categorical chroma
**0.041**; the unconstrained numeric frontier buys **0.506** (24×) at mean
chroma **0.205** and max **0.315** — gamut-edge magenta. The middle frontier
buys **0.267–0.282** (13–13.5×) at mean **0.106** and max **0.119**: roughly
half the numeric margin for roughly half the numeric loudness, with every
hue convention intact. Note also that the optimizer *spends the whole
loudness budget the fences allow* (meanC ≈ 0.106 is 88 % of the 0.12 syntax
cap) — the caps bind, the taste layer's old budgets do not exist anymore.

What binds at the middle optimum is the same thing that binds at the
numeric one — argmin in all three middles is a must-CVD term of the
co-occurring-surface cluster (active_line/diff_added deutan·tritan,
diff_added/diff_removed deutan) — but now bounded by the lightness fences
and the scaffold-ink floors rather than by the sRGB gamut edge. The
should-margin minimum (0.363) is the scaffold's own bg_elevated/bg_overlay
pair, inherited verbatim from candidate-b, unchanged from §5.1.

## 10. What the middle palettes look like (description, and honest doubts)

Description of middle-m01 (the best): keyword violet at the cap
(h 319.7, C 0.118), string sage-green at the cap (h 159, C 0.118), function
light azure (L 0.92, C 0.086), type teal (h 208.5, C 0.10), number sand
(h 108.5, C 0.115) vs constant rose-sand (h 41.5, C 0.097) — the literal
pair now reads as two members of one warm family — builtin rose (h 1.5,
C 0.10), tag sage (h 96.5, C 0.118), warning bright amber (L 0.92, C 0.137),
selection a confident blue-violet wash (h 263.5, C 0.066), diff_added a
green wash at h 145.8 and diff_removed a red wash at h 26.9, separated
mostly by lightness (0.242 vs 0.215). Reads like Balanced Night with
visibly more confident colours: same families, same lightness hierarchy,
roughly 2.5× the chroma.

Honest doubts — things the optimizer does inside the fences that a human
may still not want, reported rather than hidden:

* **It zeroes one diagnostic's chroma to buy lightness separation.** m01/m02
  render error as a near-white achromatic mark (L 0.92, C 0.000–0.003);
  m03 flips the trade (warning achromatic, error C 0.008). The hue windows
  bind only when chroma is present — C = 0 voids the "error reads red"
  intent while technically sitting at h 1.5. The fences as specified have
  ceilings, not floors; whether diagnostics need a chroma floor is a fence
  decision for the owner.
* **diff_changed parks at the canvas floor** (L 0.215 = bg + 0.01, C 0.000)
  in all three middles: a nearly invisible changed-line wash. No matrix pair
  requires diff_changed to differ from *bg*, so the objective is blind to
  its visibility. Same in candidate-b? No — candidate-b's diff_changed sits
  at L 0.235 (ΔL 0.03 from bg), visible if subtle.
* **m03 lets an unconstrained categorical pair drift to dE 0.011**
  (constant/decorator — not a matrix same_family pair, so only the soft
  anti-collapse floor applies at margin 0.37 > J). m01 keeps it at 0.047.
* The **whole chroma budget is spent** everywhere the matrix allows; nothing
  comes out quieter than the fences permit where margin is on the table.

## 11. Where the middle-frontier artifacts live

* `scripts/middle_palette.py` — the optimizer (additive; imports
  `numeric_palette` and grotto modules only).
* `out/middle-night/middle-m01..03.night.yaml` — the palettes (OKLCH yaml,
  `candidate: false`); top-3 diverse picks (mean chromatic hue separation
  18.5° / 25.8° / 22.0° between picks).
* `out/middle-night/metrics.json`, `metrics.txt` — the three-way comparison
  (candidate-b / middle / numeric-n01): worst margins by class, the three
  debts, loudness, per-pair worst-10 with `distance.breakdown` channels.
* `out/middle-night/variants.html` — dark side-by-side page: swatch strips +
  the R specimen for candidate-b, middle-m01..03 and numeric-n01.
* `out/middle-night/vscode-preview/` — and **installed** to
  `/mnt/c/Users/m0hawk/.vscode/extensions/grotto-middle-exploration/`
  (labels **Grotto M-Explore 01..03 Night**, uiTheme `vs-dark`, displayName
  "Grotto Middle Exploration (NON-CANDIDATE)").
* `tests/test_middle_palette.py` — fast reduced-subset tests: fences
  enforced (hue windows, chroma caps incl. the 70 % gamut rule, on shipped
  hexes AND authored coords), WCAG-vs-surfaces holds, number/constant ≥ 0.03
  after a tiny run, determinism.

Reproduce: `uv run python scripts/middle_palette.py` (`--no-install` skips
the extension copy). Outputs are byte-stable; two consecutive full runs
were diffed to confirm it.

**Reminder: NON-CANDIDATE.** The middle frontier is the measured answer to
"how much margin do the conventions and a loudness ceiling actually cost?"
— about half of what throwing them away buys. Whether that trade, or the
specific degenerate choices listed in §10, is desirable remains the owner's
call.
