# The soft objective, v2: the palette was boxed in by its muted text

Companion to [soft-objective.md](soft-objective.md) (v1, PR #3) and
[redundant-channel-audit.md](redundant-channel-audit.md). v1 ended
"converged inside the declared design" and left the design decisions to the
owner. This round takes those decisions, one at a time, each measured on the
**unchanged instrument** (`scripts/soft_metric.py`) and each looked at in a
rendered sheet, not just scored.

**Result.** `out/soft-night-v2/soft2-s01.night.yaml` — utility **0.9797**
against v1's **0.9392** and the committed candidate-b's 0.7896. Zero WCAG
violations, zero salience reversals, zero prominence reversals, 124 of 162
terms at target (v1: 108). It got there under a gate that is **stricter** than
v1's, which v1's own shipped palette now fails (washed-out `error`, see §4).

| palette | utility | SEP | EMPH | worst | at target |
|---|---|---|---|---|---|
| candidate-b balanced night (committed) | 0.7896 | 0.2104 | 0.0199 | 0.000 | — |
| middle-m01 | 0.9361 | 0.0592 | 0.0456 | 0.282 | — |
| soft-s01 (v1, PR #3) | 0.9392 | 0.0608 | 0.0426 | 0.215 | 108 |
| **soft2-s01 (v2)** | **0.9797** | **0.0203** | 0.0405 | 0.270 | **124** |
| numeric-n01 (rejected) | 0.6605 | 0.0228 | 0.0857 | 0.507 | — |

Loudness did not go up: EMPH 0.0405, under v1. The tripwire still holds:
numeric-n01 ranks last.

![soft2-s01](../../out/soft-night-v2/preview-soft2-s01.night.png)

---

## 1. The binding constraint was never the fence (run 7, +0.031)

v1 and the audit both concluded the surface cluster needed a wider lightness
fence (audit §8: "the fence is 1.6–2.9× too tight"). Widening it alone
**did nothing** (0.9322, and inadmissible). The surfaces did not move.

The reason is one rule upstream of the fence: every highlight surface must keep
every floored scaffold ink legible on it. `fg_muted` and `line_number` (and the
border `ui_inactive`) sit on the 3:1 non-text floor at L 0.528:

| scaffold ink | floor | highest surface L it allows |
|---|---|---|
| fg_muted, line_number, ui_inactive | 3.0 | **0.250** |
| comment, punctuation, fg_secondary, deprecated | 4.5 | 0.312 |
| fg, docstring, operator, … | 4.5 | 0.430 |

With surfaces held at the canvas +0.01 (0.215), **all seven co-occurring
surfaces shared a 0.035 band of lightness.** The §8 seating that called the
cluster "feasible with 0.68 of the axis to spare" did not model this, which is
why it put surfaces at L 0.13–0.45.

**Decision:** lift the three to L 0.585. Muted text goes from 3.37:1 to
4.24:1 on the canvas, which `spec/roles.yaml` explicitly sanctions ("Floor is
set by accessibility, not aesthetics… even though it looks 'too visible'"). It
stays 0.09 below comments, so the hierarchy holds. The surface ceiling moves to
0.31, set by the 4.5:1 body-text inks, which are deliberately not touched.

Together with that, the fence widens **only for roles whose spec declares
`lightness_offset`** (selection, search_match_current, the diff washes, error,
success, focus). That is ±0.12 for surfaces, and −0.08 for inks, downward only,
because an early probe parked `error` at L 0.96, C 0.012, i.e. white. Every
other role keeps the middle fence.

## 2. Things the number cannot see, found by looking (runs 8, 9, 12)

Each of these raised or held utility while making the theme worse. Each is now
a hard constraint in the search **and** in `scripts/soft_gate.py`.

| defect, as rendered | fix |
|---|---|
| `diff_added` at h 95: an olive/khaki "added" | soft hue window [120,160] (`success` too, its same_family pair); `diff_removed` [10,40] (not crimson-magenta) |
| `search_match_current` at L 0.215, C 0.020: **the dimmest surface on screen**, beside a brighter ordinary match. Normalised chroma flatters a wash parked at the canvas, so the salience gate passed it. | **surface prominence rank**: inside a hue family, a higher-salience surface stands at least as far off the canvas (OKLab ΔE) as a lower-salience one |
| `error` at L 0.92, C 0.02: pale pink, read as body text. `warning` at L 0.92, C 0.034: peach. `breakpoint`: a white dot | role chroma floors (error/warning 0.065, breakpoint 0.05) at L ≤ 0.83/0.86/0.86, where the 70% gamut ceiling can hold them |
| unconstrained roles placed below the 0.02 chroma floor | placement output is re-projected through the fences |

The diagnostics only showed up because `scripts/soft_preview.py` now draws
them: a strip with the `4px double` underline VS Code actually uses, with
gutter marks, shown as authored and under **tritanopia** (the CVD that
collapses error/warning). The preview also had a defect of its own. It drew
the code specimens on a fixed cool `#161b22` card rather than the palette's
warm canvas, so every syntax colour was being judged against a background the
theme never draws. It now uses `bg`. The cluster shows all seven surfaces.

The `error` floor is the one constraint that cost utility: **−0.0062**. That
is the price of an error that looks like an error, and it is paid.

## 3. The search (runs 8, 10)

* **Salience-aware ascent.** The objective cannot see salience, so the ascent
  walked into states the post-repair could not leave (`error` 0.19 below
  `breakpoint` in normalised chroma). Moves are now accepted
  lexicographically: fewer salience/prominence reversals for the moved role
  first, then utility. The guard uses a closed-form OKLab→sRGB gamut test,
  because `grotto.color.max_chroma` costs ~1 ms per call. It agrees with the
  exact definition to < 0.002, and `finalize` and the gate still use the exact
  one.
* **The salience repair tries both orders.** It always raised the
  higher-salience role first, which meant boosting `error` (9 objective terms)
  past `breakpoint` (0 terms, free to quiet). That cost ~0.02 on every seed.
  Both orders now run on copies, and the better final utility wins. The
  benchmark went **0.9718 → 0.9845** and the seed spread **0.0167 → 0.0025**.
  This also fixed a latent bug: the "lower" pass left a rejected step applied.

## 4. Benchmark record

`.auto/log.jsonl`, runs 7–12 (fixed budget, three seeds, `.auto/measure.sh`):

| run | change | utility | spread | verdict |
|---|---|---|---|---|
| 6 (v1) | — | 0.9369 | 0.0021 | baseline |
| 7 | lift muted inks; lightness_offset fences | 0.9676 | 0.0050 | keep |
| 8 | convention windows, prominence rank, salience-aware ascent | 0.9782 | 0.0190 | keep |
| 9 | success in the green window | 0.9718 | 0.0167 | keep (constraint; drop inside spread) |
| 10 | salience repair tries both orders | 0.9845 | 0.0025 | keep |
| 11 | post-process 5 candidates, not 3 | 0.9845 | 0.0025 | discard (identical) |
| 12 | diagnostic chroma floors + preview | 0.9783 | 0.0029 | keep (constraint) |

**Benchmark change, declared:** the per-seed cap is now **process CPU time**
(still 16 s), not wall clock. This VM is a shared 2-core machine. Under
another job's load, the *unchanged* run-7 search measured 17.5 s wall, so the
wall cap was measuring the neighbours. The iteration budget is unchanged.

`soft_gate.py` now reads the fence table from `soft_palette.SoftProblem`
(never a score), so the gate and the search cannot disagree about where the
fences are.

## 5. What is left, and whose call it is

Remaining SEP on the shipped palette is 0.0203. About a quarter of it is two
**scaffold-only** should-pairs that no search can move: `bg`/`bg_elevated`
(dE 0.033 vs 0.08) and `bg_elevated`/`bg_overlay` (0.027). Closing them means
much larger elevation steps for panels. That is the open DESIGN question Q-2
(direction and size of elevation), and **is the owner's**.

The rest is the irreducible red/green core: `diff_added`/`diff_removed` under
deutan, and the tritan error/warning pair. Both now sit well above v1's
margins, but D-3's redundant channels (gutter signs, a distinct diagnostic
mark) remain the real fix, as the channel audit says.

Visible in the sheet and not scored: `diff_changed` and `search_match` are
both dark sand-brown washes and nearly the same colour. They are not a
`must_distinguish` pair in `spec/distance-matrix.yaml`, so nothing asks for a
difference. If they co-occur in practice (a search inside a modified hunk), the
matrix should say so.

Not done, deliberately:

* `active_line` stays pinned scaffold (run 4's "free it" lever is still the
  owner's decision).
* No `src/grotto` or `spec/` change. Everything is a declared trial setting in
  `scripts/soft_palette.py`.
* v1's artifacts in `out/soft-night/` are untouched. Several tests and the
  channel audit pin numbers to them, and they are the comparison point.

## 6. Reproducing

```bash
uv run python scripts/soft_palette.py --restarts 24 --samples 16 \
    --refine-passes 30 --select 6 --no-install          # -> out/soft-night-v2
uv run python scripts/soft_gate.py out/soft-night-v2
uv run python scripts/soft_metric.py out/soft-night/soft-s01.night.yaml \
    out/soft-night-v2/soft2-s01.night.yaml
uv run python scripts/soft_preview.py out/soft-night-v2 \
    out/soft-night-v2/soft2-s01.night.yaml out/soft-night/soft-s01.night.yaml \
    themes/candidates/candidate-b-balanced.night.yaml
uv run pytest tests/test_soft_v2.py -q
```

**NON-CANDIDATE.** Promotion is the owner's call. Install
`out/soft-night-v2/vscode-preview/` to look at it in a real editor. Nothing
here substitutes for that.
