# The soft objective: what it found, and where the theme actually stops

Companion to `docs/review/optimizer-constraints.md`. That document proposes
the experiment and names the question; this one reports the measurement and
the answer.

**Question.** `middle_palette.py` maximises the *worst* normalised margin
`J = min_i(m_i)` with the *mean* margin as a plateau tie-break. Both terms keep
paying for separation a pair has already achieved, so the search spends the
entire chroma budget its fences allow and then some. The proposal says to
replace that incentive before adding any freedom, using a shortfall and an
emphasis budget:

> For a pair with normalized separation m, use a shortfall such as
> `max(0, 1 - m)^2`. This contributes zero above the target.

**Answer.** The objective change is worth a lot and costs nothing. After it,
the theme is at its ceiling inside the declared design: the remaining
separation gap is not reachable by a better search, and the two things that
*would* reach it are both forbidden by `DESIGN.md` and `spec/roles.yaml`
respectively. One of them is a design decision the owner has not yet made,
and it is priced.

---

## 1. The objective

`scripts/soft_metric.py` is the instrument. It is deliberately separate from
`scripts/soft_palette.py`, the search: it reads a palette YAML and re-derives
every number from the committed specs, so the benchmark can never be satisfied
by the search's own report. (The history of this repository is a series of
instruments that disagreed with their authors' expectations; that is the
failure mode being designed against.)

```
utility(P) = 1 - SEP(P) - EMPHASIS_WEIGHT * EMPHASIS_EXCESS(P)

SEP(P)             = mean over all 162 objective terms of max(0, 1 - m_i)^2
EMPH(P)            = area-weighted mean chroma, canvas excluded
EMPHASIS_EXCESS(P) = max(0, (EMPH(P) - 0.045) / 0.045)
EMHASIS_WEIGHT     = 0.35
```

`m_i` is each term's margin normalised by its own class threshold, **read from
`spec/distance-matrix.yaml`, never edited**: must-pairs under normal vision
(0.13), must-pairs under simulated protan/deutan/tritan at severity 1.0 (0.09),
should-pairs under normal vision (0.08), and an anti-collapse floor at the
matrix's own `same_family.min_distance` (0.03) for categorical pairs the matrix
does not otherwise constrain.

`EMPH` weights each role by the area it occupies: **measured** mean character
share across the eight specimens in `grotto.specimens` for inks, and the
**declared** `area_class` share of `spec/roles.yaml` for the highlight
surfaces, which no source specimen can measure. The canvas is excluded —
averaging a mostly-dark background into one mean would hide exactly the
intense syntax the budget exists to control.

`EMPHASIS_BUDGET = 0.045` is calibrated, not chosen. It is the middle
frontier's own measured level: the palette family that bought the most
separation while keeping every hue convention and every WCAG floor. Above it
the penalty starts pulling; below it, no palette could be produced at all.

## 2. The instrument ranks what the owner already decided

| palette | utility | SEP | EMPH | worst `J` | WCAG viol. |
|---|---|---|---|---|---|
| candidate-a restrained night | 0.7900 | 0.2735 | 0.0085 | 0.000 | 12 |
| candidate-b balanced night (committed) | 0.7896 | 0.2104 | 0.0199 | 0.000 | 12 |
| candidate-c expressive night | 0.8022 | 0.1978 | 0.0271 | 0.000 | 12 |
| fig-vivid night (PR #2 draft) | ~0.79 | 0.190 | 0.059 | 0.000 | 1 |
| middle-m01 night | 0.9361 | 0.0592 | 0.0456 | 0.282 | 0 |
| **soft-s01 night (this work)** | **0.9392** | 0.0608 | 0.0426 | 0.215 | 0 |
| numeric-n01 night (**rejected**) | 0.6605 | 0.0228 | 0.0857 | 0.507 | 0 |

Note what the shipped palette is *not* doing: its worst pair (0.215) is still
below the middle frontier's (0.282) while its mean shortfall is no worse and
its loudness is lower. The shortfall objective spends its budget evenly across
all 162 terms instead of protecting one pair — which is the behaviour the
proposal asked for and the reason `worst` alone is the wrong number to report.

The load-bearing row is the last one. The rejected numeric frontier has the
**best** separation of anything ever produced in this repository and the
**worst** utility here, because the shortfall pays nothing for margin a term
already has and the loudness has to come out of the emphasis budget. Under
max-min `J` it wins; under the proposal it loses to a palette a quarter as
loud. That inversion is the objective change doing its job, and it is the
single most useful thing this experiment produced.

It is also a tripwire: if a change to the instrument ever puts numeric-n01
back on top, the instrument has regressed to the max-min objective it
replaced.

## 3. The loss is not spread out — it is one six-role cluster

The objective decomposes into **six independent connected components** over the
23 optimised roles. A move inside one cannot change another's terms, so the
shortfall decomposes exactly.

| component | roles | terms | share of loss |
|---|---|---|---|
| **surface cluster** | selection, search_match, search_match_current, diff_added, diff_removed, diff_changed | 44 | **99.2%** |
| syntax + diagnostics | keyword, string, number, constant, type, function, builtin, decorator, namespace, tag, error, warning, success | 96 | 0.8% |
| unconstrained | info, focus, debug_current, breakpoint | 0 | 0% |

`info`, `focus`, `debug_current` and `breakpoint` appear in **no** matrix pair
at all. Inside the cluster the argmin is always a **must-CVD** term measured
against `active_line` — which is *scaffold*, copied verbatim from
candidate-b and never optimised.

NUMERIC.md §5.2 reached the same conclusion for the numeric frontier
("argmin term: `must_deutan(selection, active_line)` — the binding constraint
is CVD survival of the co-occurring-surface cluster, not syntax"), and §5.4
concluded the ceiling is real rather than a search artefact.

## 4. The search is saturated

Three independent lines of evidence, all pointing the same way:

| lever | result |
|---|---|
| 8x budget (24 x 16 x 30, 86 s vs 12.5 s) | 0.9474 → 0.9479, **below the seed spread** |
| loss-targeted iterated local search (component kicks) | +0.0001, for +50% wall clock |
| every single-fence relaxation | within seed noise (table below) |

The ascent converges in 6–8 passes from any sample; the remaining passes and
restarts buy nothing. **The bottleneck is the fences and the pinned scaffold,
not the search.** That is why this document is mostly negative results.

### Fence sensitivity (2–3 seeds each)

| change | utility | verdict |
|---|---|---|
| baseline (middle fences) | 0.9448 | — |
| `SURFACE_L_DELTA` 0.06 → 0.10 | 0.9448 | no effect at all |
| `SURFACE_L_DELTA` → 0.14 | 0.9459 | within noise |
| `SURFACE_CAP` 0.10 → 0.14 | 0.9458 | within noise |
| diff/search hue windows +90° | 0.9457 | within noise; breaks conventions |
| `INK_L_DELTA` 0.04 → 0.08 | 0.9468 | within noise; **forbidden, see §5** |
| `GAMUT_FRACTION_CAP` 0.70 → 0.85 | 0.9383 | within noise, non-monotonic; **inert** |
| surface L 0.10 **and** ink L 0.08 | 0.9572 | **forbidden, see §5** |

The last two rows are the instructive ones, and both were traps.

**`GAMUT_FRACTION_CAP` looked like the one reproducible lever** — in a probe it
gave +0.0015 with *zero* seed spread, which reads as a genuine effect. It is
not. That probe was measured *before* the post-refinement repairs were added;
run through the full pipeline, the gamut rule turns out to be **inert at every
setting tested**, because the class chroma caps (0.12 syntax / 0.16 diagnostic
/ 0.10 surface) bind first and no role reaches the gamut edge (0/23 at ≥99.5%
of `max_chroma` from 0.70 through 0.90). Relaxing a fence that is not binding
cannot help, and would only weaken the OKLab hue-linearity margin RESEARCH.md
R-8 warns about at the gamut edge.

**A lesson worth stating plainly: a probe that skips the post-processing
measures the wrong thing.** The same lesson applies to every number in §4 —
they are all post-repair.

### The emphasis budget is not the binding lever either

The emphasis frontier, run through the full pipeline:

| budget | utility | EMPH |
|---|---|---|
| 0.050 | 0.9365 | 0.0405 |
| **0.045** (current) | **0.9365** | **0.0405** |
| 0.042 | 0.9335 | 0.0408 |
| 0.038 | 0.9256 | 0.0389 |
| 0.035 | 0.9157 | 0.0366 |
| 0.032 | 0.9071 | 0.0333 |

Tightening it costs roughly **7 units of utility per 0.001 of quietness** — a
bad exchange. The reason is visible in the table: the palette already lands at
`EMPH = 0.0405`, *below* the budget, so the emphasis term is inactive and the
search is buying separation alone. The theme this produces is already quieter
than every palette the owner has accepted (candidate-b 0.0199, middle-m01
0.0456, numeric-n01 0.0857) and needs no further restraint to be so. The
proposal's third experiment — "add a lower surface-emphasis budget" — is
answered: **not at this operating point.**

## 5. What was refused, and why

**Widening the lightness fences (+0.012 to +0.020, the largest raw number in
this document).** This is the best lever available and it is forbidden by the
project's own design. `DESIGN.md` records the conflict as O4 vs O2:

> Making pairs CVD-robust means lightness-separating them, which consumes the
> lightness axis that salience also needs. *Resolution: CVD robustness …
> achieved through redundant non-colour channels rather than by distorting the
> palette (D-3).*

The shortfall objective cannot see this: lightness is invisible to it, and
spending it silently inverts the attention hierarchy. Section 6 below is the
gate that makes it visible, and it exists because of this lever.

**Widening the diff/search hue windows.** Breaks the learned conventions the
windows exist to protect — green added, red removed. Same conclusion as O4:
the CVD gap wants a *redundant non-colour* channel, not a hue that breaks
convention for everyone to fix a problem for 8% of men.

**The chroma floor's absence.** Every fence in the middle search is a
*ceiling*, and a ceiling-only feasible set has a degenerate optimum. This
repository hit it repeatedly before this session: NUMERIC.md §5.3 ("keyword,
string and success sit at L ≈ 0.98–0.99 with almost no chroma"), §10 ("it
zeroes one diagnostic's chroma to buy lightness separation"; "diff_changed
parks at the canvas floor … a nearly invisible changed-line wash"), and
`docs/review/optimizer-constraints.md` ("The fences as specified have
ceilings, not floors"). Under the shortfall objective it is not a corner
case: **the first admissible palette rendered `error` at C = 0.0011 in all
three seeds**, because a term that has cleared its threshold contributes
exactly zero and achromatic is the cheapest way to stay cleared.

The floor is `CHROMA_FLOOR = 0.02`, which is not a new number — it is the
repository's own `HUE_AUDIT_MIN_CHROMA`, the chroma below which
`middle_palette`'s fence audit skips the hue-window check because the hue
channel carries no readable signal. It constrains only the degenerate tail,
never a palette a person chose.

## 6. The instrument was wrong first, and fixing it cost 0.009

The shortfall objective is **structurally blind to the salience hierarchy**:
nothing in the distance matrix ranks attention, so nothing in `SEP` or the
emphasis term can see it. Measured on the first admissible palette: **5
within-family salience reversals**, against **0** for the committed
candidate-b and **1** for middle-m01.

`src/grotto/model.py` calls its realised-salience proxy "a soft signal" and
deliberately leaves it out of its own `ok`. That is right for a checker
reporting on hand-authored palettes and wrong for an optimiser, so
`scripts/soft_gate.py` promotes it to hard — using **model.py's own
definition** (chroma is the salience channel; compare within a hue family;
tied salience imposes no ordering; 2e-3 tolerance; normalised chroma
`C / max_chroma(L, h)`). An earlier attempt checked *lightness* rank across
all roles and flagged the committed palettes; that was a checker artefact
dressed up as a design constraint, and it was discarded.

| run | utility | admissible? |
|---|---|---|
| 1 — shortfall search, no salience gate | 0.9455 | no, 5 reversals |
| 2 — chroma floor + salience gate | 0.9365 | yes |

**The 0.009 fall is the point.** The previous number was measured on palettes
that broke a design constraint. A theme that buys its separation by inverting
the attention hierarchy is worse, and a metric that says otherwise is the
metric being wrong. The other half of the story: seed spread tightened from
0.0063 to 0.0013, because a constraint that removes a degree of freedom also
removes seed luck.

### Getting the search to satisfy it

Four findings, all in the commits, and the interactions are the reusable part:

1. **Evaluate repairs against the hexes the file will carry**, not
   `problem.hexes()`. The YAML writer stores authored OKLCH rounded to 6/4
   decimals and `Palette.from_yaml` converts back; the result differs from
   `problem.hexes()` by one 8-bit step, which is enough to make a repaired
   salience pair read as still broken. Snapping the authored coordinates onto
   the hex instead breaks `fence_audit_state`, which allows no quantisation
   slack — the coordinates must stay strictly inside the fences and the hexes
   may sit 0.006 outside them.
2. **Measure repair progress in normalised chroma, never in coordinates.** The
   chroma ceiling clamps a coordinate move to "no change" while the
   surrounding hexes still shift.
3. **Run repairs to a fixed point.** Nudging a surface to restore a WCAG floor
   changes its lightness, which changes `max_chroma(L, h)`, which changes its
   normalised chroma, which re-opens a salience pair the previous repair had
   just fixed. One pass of each repair is not enough.
4. **Accept a repair move only if it does not increase the reversals the moved
   role participates in.** Without this guard the operators fight each other:
   boosting `breakpoint` past `diff_removed` fixes one pair and breaks
   `breakpoint`/`error`, whose fallback then quietly undoes the boost.

`boost_normc` also yields a trick worth keeping: the salience channel can be
raised **without adding colour**, because `C / max_chroma(L, h)` rises if the
role moves to where the sRGB gamut holds less chroma. That matters because
raising chroma is blocked by the ceiling while the lower-salience partner
cannot go quieter — the chroma floor of §5 and the salience order are in
direct tension, and gamut capacity is the only way out.

## 7. The open decision, priced

**The one measured lever that is not blocked.** Freeing `active_line` — letting
the current-line band become an optimised highlight surface with free hue —
is worth **+0.0132** and is the largest gain found:

| `active_line` | utility | EMPH | worst `J` | terms at target | reversals left |
|---|---|---|---|---|---|
| pinned (current) | 0.9365 | 0.0405 | 0.132 | 111.7 | 0.0 |
| **movable** | **0.9497** | 0.0427 | 0.174 | 113.7 | 0.3 |

It is not blocked by `DESIGN.md` O4-vs-O2 (it buys separation with *hue*, not
lightness), and emphasis stays under budget. It was **not taken**, for two
reasons, both stated rather than massaged:

* `spec/roles.yaml` declares the role as `chroma_class: trace`,
  `family: neutral`, `salience: 0`, with the note: *"Must be findable in
  peripheral vision without being readable as a foreground element. A very
  small lightness step is usually enough; most themes overdo this and create a
  permanent bright band."* Freeing it contradicts the spec's own declaration
  and its own warning. `spec/roles.yaml` is read-only for this session:
  changing a role's declared chroma class is a design change, not an
  optimisation.
* The current line is the **largest non-canvas area in an editor**. The
  proposal's own constraint table says "large, persistent areas stay quieter
  than small accents", and colouring it inverts that principle for the one role
  where it matters most.
* It also does not fully converge: 0.3 salience reversals per seed survive the
  repair pass, i.e. the operators are still fighting.

**Decision for the owner:** is the +0.0132 worth colouring the current-line
band? If yes, the change is to `spec/roles.yaml` (its `chroma_class`,
`family` and notes) plus a hue window for it — a spec change, deliberately not
made here.

## 8. What the palette cannot do

The cluster's binding constraint is CVD survival of five co-occurring
surfaces against a *pinned* `active_line`, inside sRGB, under Brettel
population-average dichromat models at severity 1.0. The worst pair reaches
about 0.13 of its 0.09-dE threshold's scale — well short of clearing it — and
no amount of search, chroma, or permitted lightness moves that.

`docs/review/optimizer-constraints.md` already named the resolution:
*"surfaces need the redundant channels the matrix itself says they must
carry."* DESIGN.md D-3 says the same: redundant **non-colour** channels. So
the remaining gap is a **mapping-layer** problem, not a palette problem —
selection and diff borders, gutter signs, distinct icons. The matrix's own
`cvd_priority` and the use-of-colour criterion (WCAG 2.2) both require it, and
the simulation supplements those checks rather than replacing them.

That is the next piece of work, and it is not an optimisation: it is the
verification that the mapping delivers the channel the palette deliberately
does not encode.

**Done — see [redundant-channel-audit.md](redundant-channel-audit.md).** The
verification is run and the answer is no, for two pairs. `selection`/
`active_line` and `search_match`/`search_match_current` are warned about today
on channels that do not discriminate them: VS Code has no selectable selection
border, and two borders of different colour are still two borders. Both pairs
are unresolvable at the palette layer in *every* palette in the repository, so
half the gap named above was never a search problem at all.

## 9. Reproducing

```bash
uv run python scripts/soft_palette.py --restarts 24 --samples 16 \
    --refine-passes 30 --select 6 --out out/soft-night   # the deliverable
uv run python scripts/soft_metric.py out/soft-night/*.night.yaml   # score it
uv run python scripts/soft_gate.py out/soft-night     # hard gates
```

The shipped `out/soft-night/soft-s01.night.yaml` is the run recorded at seed
20260817: **utility 0.9392**, emphasis 0.0426, zero WCAG violations, zero
salience reversals, zero fence violations, all 162 terms scored.

One honest wart: the `free` restart kind is dropped on some seeds because the
salience repairs do not converge on the `rose` family — `breakpoint`
(salience 5), `error` (6) and `diff_removed` (3) are three levels in one hue
family, all needing monotone normalised chroma, inside fences authored for a
different purpose. That is the repair's weak point and it is reported per
candidate rather than silently swallowed.

Deterministic and byte-stable for a fixed seed; `--seed` reproduces any
individual palette. The benchmark used during the search lives in
`.auto/measure.sh` and scores through `soft_metric.py` rather than the search's
own report. Artefacts in `out/soft-night/`: the palette YAML, `metrics.json`,
a `variants.html` comparison against candidate-b / middle-m01 / numeric-n01 on
the same R specimen, and an installable `vscode-preview/` extension.

**Reminder: NON-CANDIDATE.** Whether any of this, or the §7 decision, becomes
the released theme is the owner's call. What is established here is the
frontier, the instrument that measures it honestly, and the price of the two
levers that would move it.