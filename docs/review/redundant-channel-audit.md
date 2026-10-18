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
the fences. **Half of it is not reachable by any palette at all**, because the
thing that is supposed to carry it does not exist in the editor. No search will
find a `selection` border, and no amount of lightness separates two borders by
shape.

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
- **It does not claim the two pairs are unfixable.** They are fixable *at the
  mapping layer*, which is the point: a selection border that VS Code does not
  support cannot be added by us, but `search_match` vs `search_match_current`
  could in principle be given genuinely different shapes (border vs
  border-plus-underline), and that is an editor-capability question, not a
  palette question.
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
errors on **every** palette, including all three committed candidates. That is
probably the correct outcome — they *are* unresolvable at the palette layer —
but it makes the current gate unpassable, so it needs a matching decision about
what a passing theme looks like. The honest version of Option A pairs the
tightened test with a *mapping-layer* obligation the gate can check: "a pair
that no palette can resolve must be carried by a channel the adapter verifies
it emits."

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

## 8. Reproducing

```bash
uv run python scripts/channel_audit.py out/soft-night/soft-s01.night.yaml
uv run pytest tests/test_channels.py -q
```

17 tests. The vocabulary tests are the ones that matter long-term: they are what
stops "VS Code draws a squiggle" from becoming folklore.
