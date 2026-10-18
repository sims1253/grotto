# Redundant-channel audit: does the mapping deliver the channel D-3 excuses?

Follow-up to `docs/review/soft-objective.md` §8, which closed with:

> the remaining gap is a **mapping-layer** problem, not a palette problem […]
> That is the next piece of work, and it is not an optimisation: it is the
> verification that the mapping delivers the channel the palette deliberately
> does not encode.

This is that verification. The answer is: **for two of the surface pairs, it
does not — and neither pair is reachable by any palette.**

---

## 1. The question

DESIGN.md D-3:

> **D-3: hue is never the sole carrier of critical meaning.** Every role with
> `cvd_priority: critical` declares `redundant_channels` in `spec/roles.yaml`,
> and the loader *rejects the spec* if one does not.
>
> Enforcement (`check()` in `spec.py`): `must_distinguish` pairs are verified
> under normal vision and under protan/deutan/tritan at severity 1.0. A CVD
> failure is an **error** if neither role has a redundant channel, and a
> **warning** if one does — the theme is then legitimately relying on that
> channel, and the report should say so out loud.

Two clauses do different work. The first is a **role** obligation: a critical
role may not rely on hue alone. The second is a **pair** obligation: the pair
must be distinguishable, and the report should say what is carrying it.

`spec.check()` resolves the pair obligation against the role one:

```python
def _has_redundancy(c, roles) -> bool:
    if c.channel:
        return True
    for n in (c.a, c.b):
        r = roles.roles.get(n)
        if r is not None and r.redundant_channels:
            return True
    return False
```

Any declared channel, on either role, excuses the pair. That is a sound test
only if a role's declared channel necessarily discriminates the pairs it
appears in. **It does not**, and there are three ways it fails — all three
present in this repository.

---

## 2. Three ways a declared channel fails to cover a pair

**(a) The channel is never delivered.** `selection` declares
`redundant_channels: [lightness_offset, border]`. The mapping's own prose
block says:

> `selection` — `redundant_channels: [lightness_offset, border]`: VS Code has
> no selectable selection border; only the lightness offset survives.

Confirmed from the ids rather than the prose: `selection` maps to
`editor.selectionBackground`, `editorBracketMatch.background`,
`editorSuggestWidget.selectedBackground`, `list.activeSelectionBackground` and
five others — **no `*Border` and no `*Outline` id** (nine ids in total).
`search_match` and
`search_match_current` both do have them (`editor.findMatchHighlightBorder`,
`editor.findMatchBorder`). The declaration is half-real; the half that would
carry the weight is the half the editor does not have.

**(b) The channel is the same on both sides.** `search_match` declares
`[border]`; `search_match_current` declares `[border, lightness_offset]`. Both
are delivered. Both draw a border. **A border is a shape, not a colour** — two
borders of different colour are still two borders, so the channel does not
discriminate these two roles from each other at all. The role-level test reads
the presence of a channel, not whether its *value* differs.

**(c) The channel is not independent of the metric.** `lightness_offset` is
declared by four roles including `selection` and `search_match_current`. But
`delta_e_ok` is an OKLab distance: it already integrates lightness. Citing a
lightness offset to excuse a *distance* shortfall is the metric vouching for
itself. This one is not a claim about the editor — it is arithmetic, and it
holds everywhere.

`src/grotto/channels.py` implements all three. `lightness_offset` is declared
`independent=False`, which is what makes (c) structural rather than editorial.

---

## 3. The audit

```bash
uv run python scripts/channel_audit.py out/soft-night/soft-s01.night.yaml
uv run python scripts/channel_audit.py themes/candidates/*.night.yaml
```

The instrument answers the question `check()` does not ask — *which* declared
channel covers *this* pair — and it reads delivery out of
`spec/mappings/vscode.yaml` rather than assuming it, so a mapping change
surfaces instead of silently invalidating the conclusion.

Coverage requires two **different** marks. The marks are facts about what an
editor draws, not about what a palette scores: VS Code renders the wavy
squiggle, the `+`/`-` gutter signs and the severity glyphs from the severity
and the diff, **not** from theme colours, so no palette can remove them. The
one channel the theme genuinely controls is `strikethrough`, via `fontStyle`.
The vocabulary is in the module and is asserted against `roles.yaml` in
`tests/test_channels.py`; an unknown channel name fails a test rather than
being silently skipped as coverage.

**`spec.check()` is unchanged.** The audit is report-only — see §6.

---

## 4. Result

Sixteen `must_distinguish` pairs fall short of the CVD threshold on
`soft-s01`. Fourteen are genuinely covered. Two are not:

```
== NOT COVERED by any channel (2) ==
 ! search_match /search_match_current  worst dE 0.034 -- declared
       ['border','lightness_offset'] but none discriminates them as rendered
 ! selection        /active_line       worst dE 0.046 -- declared
       ['border','lightness_offset'] but none discriminates them as rendered
```

The fourteen that do survive are the intuitive ones: `diff_added`/`diff_removed`
(`+` vs `-`), `error`/`warning` (wavy vs dotted), `error`/`string` (squiggle vs
nothing), `selection`/`search_match_current` (a ring vs no ring). The audit
is not a blanket pessimism — it declines to excuse only the two pairs where the
excuse is hollow.

**The same two pairs, in every palette in the repository:**

| palette | `selection`/`active_line` normal | `search_match`/`search_match_current` normal |
|---|---|---|
| `soft-s01.night` | 0.085 | 0.047 |
| `candidate-a-restrained.night` | 0.024 | 0.026 |
| `candidate-b-balanced.night` | 0.028 | 0.027 |
| `candidate-c-expressive.night` | 0.026 | 0.027 |

(threshold 0.130; all CVD shortfalls are in the 0.019–0.046 band.)

This is the load-bearing result. The previous session established that the
remaining separation gap is not reachable by better search, and attributed it to
the fences. The obvious next question is whether it is reachable by *any*
palette at all — and the answer, measured in §9, is **yes**.

So the channel claim and the palette claim have to be kept apart:

* **The channel claim stands.** VS Code has no selectable selection border, and
  two borders of different colour are still two borders. Whatever carries these
  two pairs, it is not what D-3 says carries them.
* **The palette claim was too strong.** A valid lightness seating of all seven
  surfaces exists on 0.21 of the OKLab L axis (§9). The palette does not take it
  because the spec tells it these pairs are already covered — so the search
  spends that lightness on salience and emphasis instead.

That is a sharper failure than "the palette cannot do it". It is a **spec bug
producing a palette defect**: an excused pair is an unpurchased one.

---

## 5. A detail that sharpens the `lightness_offset` point

The three committed candidates show *near-identical* distance under normal,
protan, deutan **and** tritan — 0.024 to 0.028 for every cell, across all four
simulations. That is the signature of a pair separated almost entirely in
lightness, since lightness is the one axis all three simulations preserve.

So these pairs are not short of chroma separation. They are short of **lightness
separation** — which is precisely the axis `lightness_offset` names. The channel
the spec cites for them is the axis already in use and already insufficient.
That is the clearest possible demonstration of failure mode (c): the declared
channel is not merely non-independent, it is *diagnostic* of the problem.

---

## 6. What this does not claim

- **It does not amend D-3, and `check()` still passes.** Promoting these two
  CVD shortfalls from warning to error is a design decision about the severity
  ladder, not a bug fix. The rule as written is unambiguous — "a warning if one
  [role declares a channel] does" — and this repository does not change
  DESIGN.md as a side effect of a measurement. §7 proposes the amendment; it is
  not applied. `tests/test_channels.py` asserts the current behaviour so the
  change cannot happen by accident.
- **It does not claim the two pairs are unfixable.** They are fixable two ways,
  and §8 measures the second. At the mapping layer: a selection border that VS
  Code does not support cannot be added by us, but `search_match` vs
  `search_match_current` could in principle be given genuinely different shapes
  (border vs border-plus-underline) — an editor-capability question. At the
  palette layer: the surfaces *are* separable on lightness, and the fence is
  ~1.6× tighter than the requirement. Neither is applied here.
- **It does not re-litigate the previous session's ranking.** The salience-rank
  gate, the shortfall objective and the saturation evidence are untouched. The
  audit is orthogonal: it runs on all four palettes and returns the same two
  pairs.
- **The host-draw claims are checked against the mapping, not against a running
  VS Code.** `tests/test_channels.py::test_mapping_has_no_selection_border`
  fails loudly if a selection border id ever appears, which is the signal to
  revisit §2(a). Confirming the squiggle and gutter-glyph behaviour against a
  live editor is human work and is still owed.

---

## 7. The amendment this implies

Two options, both owner decisions, neither taken here.

**Option A — make the test pair-scoped.** Replace `_has_redundancy` with
`grotto.channels.judge`, so a CVD failure is a warning only when a delivered
channel puts different marks on the two roles. Cost: these two pairs become
errors on **every** palette, including all three committed candidates. §8 prices
what that actually demands: the worst surface moves **0.0985** OKLab L against a
declared fence of **±0.06**. So Option A is not merely a re-labelling — it makes
the fence the binding constraint and says so, which is the argument for widening
it by roughly 1.6× on the surface roles. The honest version of Option A pairs the
tightened test with a *mapping-layer* obligation the gate can check: "a pair that
no palette can resolve must be carried by a channel the adapter verifies it
emits."

**Option B — close the two declarations and re-state the obligation.**
`active_line` currently declares **no** channels at all (`cvd_priority: low`)
while carrying three `must_distinguish` pairs; `diff_changed` likewise (two
pairs, no channels). D-3 only forces channels onto *critical* roles, so these
two escape the loader's rule while participating fully in the pair obligations.
Promoting them, or stating explicitly that a surface role may rely on hue
against other surfaces, would make the spec say what it currently implies.

Option B is smaller and makes the remaining gap visible in the spec rather than
in a report. Option A is the one that would have caught this earlier.

---

## 8. Is the gap reachable by any palette? (the measurement §4 defers to)

`docs/review/soft-objective.md` §7 flagged Earendil's system theme as prior art:
solve contrast *backwards* — given a background and a required ratio, derive the
lightness — instead of searching for colours and scoring them afterwards.
`contrast.solve_lightness` is that inverse, and `scripts/contrast_solve.py`
asks the fair question: could it have produced this theme?

**Part 1 — can a contrast requirement express these shortfalls at all?**

**No. Zero of sixteen.** A contrast target says *"this ink must read on that
surface"*. Every one of the sixteen CVD shortfalls is a **peer** obligation —
two surfaces that must differ from each other, or two inks that must differ from
each other — and neither is a readability constraint against a background.
Classifying by `paint`:

| type | count | example |
|---|---:|---|
| readability-typed (ink on a surface) | **0** | — |
| peer-typed (surface/surface, ink/ink) | **16** | `selection` / `active_line` |

This is worth stating plainly because it is the most transferable result here:
the inverse-contrast approach and this shortfall list do not intersect. Solving
contrast backwards would have produced a perfectly readable palette and left
every one of these pairs exactly where it was.

**Part 2 — is the surface cluster separable on lightness anyway?**

Holding hue and chroma fixed, the requirement `sqrt(dL² + rest²) ≥ limit`
rearranges to a minimum lightness gap per pair, and seating 7 surfaces under 11
pairwise minimums on a line is solvable exactly — enumerate the orderings, place
each surface as early as its constraints allow. Not a sample: exact, at n! = 5040.

| | normal vision | deutan @ 1.0 |
|---|---:|---:|
| constrained surface pairs | 11 | 11 |
| required lightness gap | 0.052 – 0.126 | 0.084 – 0.130 |
| tightest seating (exact) | **0.2065** of the axis | **0.3200** of the axis |
| total OKLab L moved, least-movement seating | 0.4421 | 0.6065 |
| worst single surface | 0.0985 | 0.2075 |
| readability cost | none | `diff_added` → 4.06:1 |

**Feasible, with roughly 0.68 of the axis to spare.** The surfaces are close
together and the required gaps are small; nothing about the problem is
over-constrained.

So the conclusion of §4 sharpens rather than reverses:

* The **channel** claim stands. VS Code has no selectable selection border, and
  two borders of different colour are still two borders. Whatever carries these
  two pairs is not what D-3 says carries them.
* The **palette** claim was too strong. A valid lightness seating exists. The
  palette does not take it because the spec tells it these pairs are already
  covered — so the search spends that lightness on salience and emphasis.

That is a **spec bug producing a palette defect**: an excused pair is an
unpurchased one. And it puts a number on §7's Option A — the worst single
surface has to move **0.0985** against a declared fence of **±0.06**, so the
fence is roughly 1.6× too tight for the requirement it is protecting.

### An earlier version of this section was wrong

The first implementation computed a *lower bound* via longest-path relaxation
over the constraint graph and reported the cluster as provably infeasible
(2.33 on a 1.0 axis). That graph has cycles, so a longest-path relaxation over
it is unbounded and the number was meaningless. The exact enumeration above
replaces it. Recording this because a bound that inflates without limit looks
exactly like a proof, and it was not one.

---

## 9. Reproducing

```bash
uv run python scripts/channel_audit.py out/soft-night/soft-s01.night.yaml
uv run python scripts/contrast_solve.py out/soft-night/soft-s01.night.yaml
uv run python scripts/soft_preview.py out/soft-night out/soft-night/soft-s01.night.yaml
uv run pytest tests/test_channels.py tests/test_contrast_solve.py -q
```

`scripts/soft_preview.py` renders the sheet as authored and under deutan; the
lower half is the surface cluster, which is the region this document is about.
The vocabulary tests in `test_channels.py` are the ones that matter long-term:
they are what stops "VS Code draws a squiggle" from becoming folklore.
