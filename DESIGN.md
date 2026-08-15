# DESIGN.md — Grotto

A perceptually engineered adaptive coding colour system.

This document is the Phase 1 specification. It states what we are optimising,
what we believe and how strongly, what we have decided by judgement rather than
evidence, and which assumptions in the original brief we think are wrong.

**No palette is finalised here.** Section 9 fixes the *structure* of the
palette (how many hue families, what the transform is, what the constraints
are); the hue angles themselves are Phase 5 work.

Labels used throughout:
- **[E]** grounded in external evidence — see RESEARCH.md for the grade
- **[M]** result from this project's own modelling — reproducible in tests
- **[J]** design judgement — defensible, but not derived from evidence
- **[H]** hypothesis to be tested in Phase 7

---

## 1. The honest framing

The most important finding in Phase 1 is negative.

There is **no empirical evidence that any syntax colour scheme outperforms any
other** [E, R-10]. The evidence that highlighting beats no highlighting is
itself mixed and small-sample -- the randomized results that exist point both
ways -- and the literature is silent on the question this project actually
asks. Nothing in the perceptual-colour-science literature tells you what colour
a keyword should be.

So this project cannot be, and should not claim to be, evidence-driven palette
design. What it can honestly be is:

> A design system in which every decision is *stated*, *measured against a
> declared proxy metric*, and *falsifiable* — with the proxy metrics chosen
> because they are measurable and plausibly relevant, not because they have
> been shown to predict programmer performance.

That distinction matters for how the output should be read. The contrast,
perceptual-distance and CVD metrics are load-bearing engineering screens: they
detect likely failures under declared models. They do not certify comfort,
individual readability, or CVD accessibility by themselves.
The salience hierarchy and the aesthetic decisions are principled preference,
dressed in enough rigour to be argued with. Phase 7 is the only part that
tests the actual claim, and it is a single-subject preference study, not a
trial.

We would rather ship a defensible model with a modest palette than an
impressive-looking palette with a fabricated justification.

---

## 2. Challenges to the brief

The brief asked to be challenged. Six items.

### 2.1 Background area alone does not determine a dark theme's spectral budget [M, M-1]

The brief states: *"A slightly blue background covering 90% of the screen may
matter more than a saturated cyan token covering 1%."*

This is correct for the tested light fixture and **false as a general rule**.
Emission depends on linear channel drive as well as area. In one nominal dark
composition the synthetic display model assigns more melanopic-weighted output
to foreground text than to the much larger background [M, M-1]. Other dark
palettes and displays can distribute the budget differently.

The design implication is to evaluate the **complete rendered screen**, not to
optimize background hue from coverage alone. Foreground and accents dominate
the tested fixture; that is a scenario result, not a universal dark-theme law.

### 2.2 "Night should reduce blue" is the wrong control variable [E, R-4]

CIE alpha-opic quantities are more defensible than colour appearance alone,
but actual exposure requires spectral radiance at the eye. A dim saturated
blue can contribute less than a bright warm white. The Night transform may
compare *relative nominal melanopic-weighted display output* within one stated
model; it must not treat hue or this proxy as biological dose [E, R-4, R-13].

### 2.3 Palette is only one part of evening light exposure [E, R-5]

Evening guidance is expressed as melanopic EDI at the eye, but this project has
no measured display spectrum, viewing geometry, or absolute luminance. It
cannot quantify the palette's share of exposure or assert that one control
always dominates another.

**We should say this in the README rather than let the project imply
otherwise.** The Night variant's justification remains a hypothesis about
lower screen-average luminance and environmental fit [E, R-6], not a sleep or
eye-care claim. Monitor brightness and room lighting must be recorded during
human evaluation.

### 2.4 The Day variant is not the junior partner

The brief's structure (one light, two dark) and the reference themes all lean
dark. But the positive-polarity advantage is one of the better-replicated
findings in small-text display tasks [E, R-3], while long-duration coding
comfort and individual accessibility remain unresolved. The Day variant should be
designed first and to the same standard. If the system works, Day should be
the recommended default in any adequately lit room.

### 2.5 "Errors and warnings must be highest salience" needs qualification [J]

The brief's hierarchy puts errors at the top unconditionally. But in a file
mid-edit, a large fraction of "errors" are transient artefacts of incomplete
typing. A theme that makes every half-typed line maximally alarming trains the
user to ignore the alarm — the classic alarm-fatigue failure.

We keep errors at salience 6 but constrain them to **trace area** and to
**redundant, localised marking** (wavy underline, gutter icon) rather than
large-area or background treatment. Salience should come from *distinctiveness
and redundancy*, not from area or intensity.

### 2.6 Nine simultaneous objectives cannot all be optimised, and two pairs are directly opposed

Stated plainly in section 4.

---

## 3. Investigation: is the blue dark theme justified?

This was a specific research question in the brief. Our answer is
**"partly, and for reasons other than the usual ones."**

### Arguments we found for cool dark backgrounds

1. **Chromatic adaptation headroom [J].** A background with a slight cool bias
   leaves the warm half of the hue circle available for high-salience accents
   (errors, warnings, search) that then read as *advancing* against a
   *receding* field. A warm background puts accents and field in the same
   region and costs salience.
2. **Perceived depth [J, weak].** Cool, low-chroma fields are conventionally
   read as receding. This is a real convention in visual design; whether it
   reflects anything perceptual beyond convention is unclear.
3. **Avoiding the "dirty screen" percept [J].** Warm-biased dark greys at low
   chroma can read as brown or as a dirty display, particularly on panels with
   poor black uniformity. This is a genuine failure mode, and it is why
   "just make it warmer" is not free.

### Arguments against, and what does not survive scrutiny

4. **Area is not emission [M, M-1].** A blue background's large pixel share
   does not prove that it dominates a dark screen's spectral output. In our
   nominal dark fixture it does not; in the light fixture the bright background
   does. Neither result proves that a warm background is more comfortable.
5. **It is substantially aesthetic convention.** The cluster of navy/slate
   backgrounds with cyan/blue/purple accents across popular themes is best
   explained by lineage and taste, not by a perceptual advantage we can find.
   We say this without disparagement — taste is a legitimate design input.
   It just should not be dressed up as science.

### Our position

- **Day**: test a warm-neutral background against a neutral alternative. In
  our light fixture the background is the dominant emitter, but warmth and an
  off-white field remain aesthetic/model hypotheses rather than proven comfort
  interventions [J, M].
- **Evening**: near-neutral dark with a *very slight* cool bias, retained for
  the accent-headroom argument (1) — chroma low enough that it reads as
  neutral rather than as "blue theme."
- **Night**: neutral-to-slightly-warm dark. The shift is justified by
  adaptation coherence with a warm dim room [J] and by avoiding the
  cool-field/warm-accent tension at low luminance — **not** by spectral claims.

Critically, we distinguish the two cases the brief asked us to separate: a
blue-biased **background** and blue/cyan **syntax** must be weighted by both
linear output and area. In one nominal fixture, bright text and a small cyan
accent contribute disproportionately; this motivates complete-screen analysis,
not a universal rule about which palette class matters most.

---

## 4. Objectives and the conflicts between them

Nine objectives from the brief. The useful content is not the list but the
conflict structure.

| # | Objective | Primary metric |
|---|---|---|
| O1 | Readability | WCAG floor; APCA as an experimental diagnostic; rendered tests |
| O2 | Semantic distinction | dE_OK against the distance matrix |
| O3 | Visual salience | salience rank vs. measured distinctiveness |
| O4 | Accessibility | WCAG AA floors; CVD collapse detection |
| O5 | Low visual fatigue | human evaluation under controlled luminance; no validated palette proxy |
| O6 | Aesthetic coherence | chroma/lightness distribution; human judgement |
| O7 | Display robustness | sRGB gamut margin; behaviour under clipping |
| O8 | Environmental adaptation | luminance/melanopic delta across variants |
| O9 | Cross-variant semantic stability | hue drift and dE across variants |

### Hard conflicts

**O1 vs O5 — contrast.** Accessibility imposes lower bounds, while no strong
evidence establishes a universal comfortable upper bound for prolonged coding
[E, R-7, R-11]. *Resolution: accessibility floors plus experimental preference
bands (D-2), tested rather than asserted.*

**O2 vs O6 — distinction vs. restraint.** Every additional distinguishable hue
increases semantic capacity and decreases coherence. Chroma is zero-sum in a
bounded gamut. *Resolution: 5 hue families for ~14 syntax roles; the rest of
the distinction budget is spent on salience (D-1).*

**O4 vs O2 — CVD vs. hue economy.** Making pairs CVD-robust means
lightness-separating them, which consumes the lightness axis that salience also
needs. *Resolution: CVD robustness required only for `cvd_priority: critical`
pairs, and achieved through redundant non-colour channels rather than by
distorting the palette (D-3).*

**O8 vs O9 — adaptation vs. stability.** A strong environmental transform is
by definition a large cross-variant change. *Resolution: bound the transform
per role via `night_adaptation`, and measure the drift (D-5).*

**O3 vs O5 — salience vs. calm.** Salient elements are salient because they
break the visual field. *Resolution: salience is allocated as a budget; only
transient states may hold rank 5–6, and they are constrained to trace area
(section 6).*

There is no scalarisation of these that we would trust. We report the
tradeoffs and choose deliberately.

---

## 5. Colour model

**Canonical space: OKLCH.** Rationale: CSS-native, good hue linearity over
most of the circle, tractable gamut boundary (cubic), rich tooling.

**Known limitation [E, R-8]:** residual hue curvature in the blue/purple-blue
sector at low lightness — exactly where a dark background and a violet keyword
live. Consequences we accept:

- Hue arithmetic in 240–300° is treated as approximate; chromatic decisions in
  that region are verified visually.
- We expect this to be a leading source of numeric/visual disagreement in
  Phase 6, and disagreements there are findings, not failures.
- CAM16-UCS was considered and rejected: better hue-line straightness does not
  outweigh the cost, given that our tolerances are set by design judgement
  anyway.

**Gamut policy.** sRGB is the portable target. `gamut_status()` reports
excursion explicitly and `gamut_map()` returns the chroma lost, because a large
loss means the design asked for a colour the display cannot make — a design
bug, not a rounding detail. **Silent clipping is prohibited.** P3 is analysed
as an optional widening, but no P3-only colour may carry information that the
sRGB fallback loses.

---

## 6. Salience: the actual core of the design

Colour distinguishes; salience prioritises. Salience is the more important and
the more neglected axis, so we model it explicitly and treat it as a **budget**.

### The channels, and what each costs

| Channel | Strength | Cost | Notes |
|---|---|---|---|
| Lightness | strong | high — shared with contrast and CVD | The most robust cue; survives CVD and greyscale |
| Chroma | moderate | high — zero-sum in gamut | Effective at drawing the eye; expensive |
| Hue | categorical, not ordinal | moderate | Says *which*, not *how important*. Poor salience channel |
| Weight | strong | low | Underused; excellent for structural roles |
| Italic | weak | very low | Good for orthogonal properties (parameter-ness) |
| Underline/border | very strong | low but intrusive | Reserve for diagnostics and transient state |
| Background | very strong | very high | Reserve for selection/search/diff only |

The key point: **hue is a poor salience channel.** It tells you what category
something is, not how much it matters. Themes that try to express importance
through hue end up saturating everything. Our hierarchy is carried mainly by
lightness, chroma and weight, with hue reserved for category.

### Refinement of the brief's hierarchy

The brief's proposed hierarchy is broadly sound. Four changes:

1. **Split comments from docstrings.** A trailing aside and a module docstring
   have different reading intent. Comments sit at salience 1, docstrings at 2
   (full reading level) [J, D-4]. This is contested and flagged for Phase 7.
2. **Split operators from punctuation.** A comma carries no meaning; a `!`
   or a `-` changes program semantics, and losing one is a real bug class.
   Punctuation 1, operators 2.
3. **Question whether `function` deserves rank 4 [H].** The brief and our spec
   both put callables above keywords and strings, on the theory that call sites
   are the primary navigation targets. This is plausible but untested, and it
   may prove over-salient in call-dense code. Explicitly listed for Phase 7.
4. **Constrain rank 5–6 by area, not just by intensity.** See 2.5.

### The budget rule [J]

> Across a typical screen, no more than ~10% of *non-background* pixels should
> sit at salience ≥ 3, and no more than ~1% at salience ≥ 5.

This is a made-up number with a real purpose: it makes "this theme is too
busy" a measurable property rather than a matter of taste. It is enforced:
`salience_coverage()` computes the fractions from the declared coverage plan
and every palette report / candidate comparison carries a salience-budget
section against these thresholds. Enforcement produced a finding and a
decision: the declared hierarchy itself measures ~19% at salience >= 3 under
the "code" estimate (keyword/string/function/type/number are exactly the
roles the hierarchy wants marked, and no other salience-3 role carries
coverage weight), so the original 0.10 budget contradicted the hierarchy.
The hierarchy won: the >=3 limit is now 0.22 -- just above the measured
design, so the check still catches drift toward busier palettes -- and this
remains a judgment [J], not evidence about comfortable busyness.

---

## 7. Contrast policy

We report WCAG 2.x, APCA Lc, and raw OKLab ΔL, and treat disagreement as
signal [E, R-11].

**D-2: exploratory contrast targets are bands, with compliance minima.** [J, H]

| Target | Experimental APCA \|Lc\| band | Roles |
|---|---|---|
| maximal | 90–105 | reserved; not used by default |
| high | 75–90 | function, error, warning, focus |
| comfortable | 60–78 | fg, docstring, operator, most syntax |
| low | 35–55 | comment, fg_secondary, line_number |
| minimal | 18–32 | fg_muted, ui_inactive, active_line, backgrounds |

These bands are design hypotheses, not accessibility requirements or validated
comfort ranges. Two deliberate consequences:

- **Upper bounds trigger review, not failure.** A body-text pair above its
  preferred band is flagged for human testing; current evidence does not prove
  that it is fatiguing or harmful [E, R-7, R-11].
- **WCAG AA (4.5:1 body, 3:1 large/non-text) is a hard floor that the bands
  must not breach.** Where the comfort band and the accessibility floor
  conflict, accessibility wins and we record the conflict. APCA is reported as
  an experimental design diagnostic, not a replacement compliance claim.

---

## 8. Accessibility policy

**D-3: hue is never the sole carrier of critical meaning.** Every role with
`cvd_priority: critical` declares `redundant_channels` in `spec/roles.yaml`,
and the loader *rejects the spec* if one does not.

Enforcement (`check()` in `spec.py`): `must_distinguish` pairs are verified
under normal vision and under protan/deutan/tritan at severity 1.0. A CVD
failure is an **error** if neither role has a redundant channel, and a
**warning** if one does — the theme is then legitimately relying on that
channel, and the report should say so out loud.

The two structurally hostile constructs, both unavoidable in developer tooling:

- `error` / `warning` — red/amber, the second-worst pair under protan/deutan.
- `diff_added` / `diff_removed` — red/green, as large adjacent *background*
  washes. The worst construct in common developer tooling.

For both, lightness separation plus a glyph channel (icon, ± sign) is
mandatory. Our modelling shows why hue distance alone cannot be trusted here:
the same red/green pair retained dE 0.18 under protanopia but collapsed to
0.044 under deuteranopia [M, M-3] — the metric is not even consistent across
CVD types.

---

## 9. The environmental adaptation model

The central technical claim of the project: three variants should be one
system under a transform, not three palettes.

### Structure

```
roles.yaml                 abstract properties, no colour
      |
      v
candidate anchor binding   family -> hue angle, per candidate  (Phase 5)
      |
      v
environment transform      (this section)
      |
   +--------+----------+----------+
   |  Day   | Evening  |  Night   |
   +--------+----------+----------+
```

### The transform [J]

For a role *r* with base identity (L₀, C₀, h₀) and environment *e*:

**Lightness.** Roles are anchored by *contrast target relative to the
background*, not by absolute lightness. Each environment declares a background
lightness L_bg(e) and a polarity s(e) = +1 for dark variants, −1 for light.
The role's lightness is then solved so its APCA |Lc| lands in the middle of its
target band:

```
L_r(e) = solve_L( |Lc(L_r, L_bg(e))| = target_band_centre(r) , polarity s(e) )
```

This is the key move. It means **a role's identity is its contrast
relationship, not its lightness value** — which is what allows the same
semantic system to invert between Day and Night without hand-tuning every
colour.

**Chroma.** Scaled by an environment factor, modulated by the role's own
night-adaptation allowance:

```
C_r(e) = C₀ · [ 1 − a(e) · night_adaptation(r) ] · k_L(L_r)
```

where a(Day)=0, a(Evening)≈0.15, a(Night)≈0.35, and `k_L` is a small
correction for the fact that available chroma varies with lightness and hue.
Roles with `night_adaptation` near 0 (error, warning, focus) are effectively
pinned — deliberately, because desaturating a safety signal for comfort at
trace screen area is a bad trade in every direction.

**Hue.** A bounded warm-ward rotation, again gated per role:

```
h_r(e) = h₀ + Δh(e) · night_adaptation(r) · w(h₀)
```

with |Δh(Night)| ≤ 8°, and `w(h₀)` weighting the rotation toward cool hues so
that warm roles barely move. The 8° cap is chosen to stay **below the
categorical hue-change threshold** [J, H] — the whole point is adaptation
without re-categorisation.

Note that this is *not* a global orange overlay: the transform is per-role,
bounded, and leaves high-priority signals untouched. A `night shift` filter
would move everything including the error red, which is precisely what we are
avoiding.

**Backgrounds are specified directly**, not derived, because they are the
reference the rest of the system solves against.

### D-5: cross-variant stability constraints [J, H]

For every role, across every variant pair:

| Quantity | Constraint | Rationale |
|---|---|---|
| Hue drift | ≤ 12° total | Below categorical re-identification [H] |
| Family ordering | preserved | Relative hue order must never invert |
| Salience rank | preserved exactly | The hierarchy *is* the semantic system |
| Chroma rank order | preserved | Which roles are "more coloured" stays fixed |
| dE to same role in another variant | unconstrained | Lightness must be free to invert |

The last row is the important one: cross-variant dE is a *bad* stability
metric, because Day↔Night necessarily inverts lightness. Stability lives in
**hue, in ordering, and in rank** — not in colour distance. Measuring
cross-variant dE and calling large values "instability" would be a
methodological error.

### Phase 4 tests whether this works

The transform is a hypothesis. Phase 4 compares systematic output against
hand-tuned variants, and the expected outcome is that it works well for
mid-salience syntax and needs human correction for (a) backgrounds and
near-background surfaces, where small errors are very visible, and (b) the
blue/violet region, where OKLab hue curvature bites [E, R-8].

### Phase 4 senior-architecture corrections (implemented in `model.py`)

The section-9 sketch above was the *starting* design. The implemented Phase 4
transform departs from it in five load-bearing ways, recorded here so the
transform and the prose do not silently disagree:

1. **Paint types, not one formula.** Roles branch on `paint`
   (canvas|ink|surface|border). Canvas is authored; **ink** lightness and
   chroma are jointly solved in sRGB; **surface** uses perceptual lightness
   steps (solving contrast for a surface would silently destroy the legibility
   of the ink on it); **border** targets the non-text 3:1 floor.
2. **Chroma is an explicit chain** (max_chroma * class * candidate * family *
   role * environment * night term), then absolute cap, then gamut map, with
   the cap and gamut losses reported *independently*.
3. **Hue attracts toward a warm anchor** along the shortest arc, not a signed
   rotation. A signed rotation moves violet (h~300) toward blue (cooler); warm
   attraction moves it toward magenta/red (warmer).
4. **WCAG overrides the Night ceiling and APCA**, recording each conflict
   (`foreground_ceiling_overridden`, `wcag_apca_conflict`). APCA bands can
   overlap, so membership is tested against the role's *target* band.
5. **Corrected stability**: normalized C/max_chroma ordering, cyclic family
   sequence (not pairwise signed hue), a non-vacuous realized salience proxy,
   and total hue drift that includes the adjustment component. Two further
   checker corrections: (a) chroma-order inversions count a sign flip only
   when BOTH sides exceed a small tie epsilon (`CHROMA_ORDER_TIE_EPS` -- 8-bit
   quantisation alone moves realized chroma by more); near-tie flips are
   reported in `normalized_chroma_near_tie_flips` but do not fail the gate;
   (b) the salience proxy only orders roles with DIFFERENT declared salience
   -- equal-level pairs imply no ordering, so flagging them was a checker
   artifact.

`BindingError` is raised for malformed bindings; `TransformError` only for
infeasible hard constraints. Aesthetic, distance and legibility misses are
issues, never raised.

---

## 10. Architecture

Three layers, deliberately separated so the palette outlives any editor.

```
spec/roles.yaml            L1  semantics    — no colour, no environment
spec/distance-matrix.yaml  L1  constraints
        |
src/grotto/model.py        L2  transform    — semantics + environment -> OKLCH
spec/environments.yaml     L2  environment parameters
themes/candidates/*.yaml   L2  concrete per-variant palettes (generated)
        |
spec/mappings/*.yaml       L3  editor binding — TextMate scopes, LSP tokens
build/                     L3  generated editor themes
```

Evaluation tooling (`color`, `contrast`, `distance`, `cvd`, `spectral`,
`spec`, `render`, `report`) sits beside the layers and depends only on L1/L2.
No layer may reach downward: L1 contains no hex values, L2 contains no editor
scope names.

---

## 11. Metrics we propose to use

| Metric | Implementation | Role |
|---|---|---|
| OKLCH coordinates, gamut status, chroma lost | `color.py` | canonical representation; hard gate on gamut |
| WCAG 2.x ratio | `contrast.py` | compliance floor only |
| APCA Lc (signed) | `contrast.py` | experimental design diagnostic |
| OKLab ΔL | `contrast.py` | ordering and hierarchy checks |
| dE_OK + channel breakdown | `distance.py` | distance-matrix enforcement; the breakdown tells us *why* two colours differ |
| CVD collapse under Brettel/Machado | `cvd.py` | accessibility gate |
| Melanopic ratio, area-weighted screen output | `spectral.py` | exploratory only; within-model ranking |
| Salience budget by pixel coverage | `spec.py` | busyness as a measurable property |
| Cross-variant hue drift / rank preservation | Phase 4 | stability gate |

Explicitly **not** used as an objective: perceptual uniformity of the palette.
Uniform spacing is the right goal for a scalar colormap and the wrong goal
here — syntax roles are categorical and *hierarchical*, and an evenly spaced
palette destroys the hierarchy by construction.

---

## 12. Open questions

- **Q-1** Is `function` correctly ranked above `keyword` and `string`? [H]
- **Q-2** Should elevated surfaces be lighter or darker than the canvas in
  dark variants? Lighter is conventional; darker adds no luminance at night.
- **Q-3** What is the categorical hue-change threshold for a *learned* semantic
  association? Our 8°/12° caps are conservative guesses.
- **Q-4** Is the comment/docstring split worth its complexity?
- **Q-5** Does the contrast *upper* bound survive contact with real use, or
  will it read as washed out on a bright display?
- **Q-6** Can the transform handle backgrounds at all, or must all three
  backgrounds be hand-specified? (Currently we assume the latter.)
- **Q-7** Should Evening exist? It may be an unnecessary middle point between
  a well-designed Day and Night. Worth testing before committing to three.
- **Q-8** Does P3 buy anything real, or only more saturated colours we have
  already decided we do not want?
