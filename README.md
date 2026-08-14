# Grotto

A perceptually engineered, *adaptive* coding colour system. Grotto does not ship
a finished theme yet. It ships **a stated, measured, falsifiable design system**
together with the evaluation tooling that holds the system to its own rules.

> No palette is finalised here. `DESIGN.md` is the Phase 1 specification; this
> repository currently contains the Phase 1 spec plus the **Phase 2 evaluation
> tooling**. Final candidate palettes are later work, and every palette in this
> repo is explicitly labelled a non-candidate (evaluation fixture or reference).

The honest framing, the evidence base, and the challenges to the original brief
live in [`DESIGN.md`](DESIGN.md) and [`RESEARCH.md`](RESEARCH.md). Read those
first: several of the project's most important conclusions are *negative* (the
review found no evidence selecting one syntax palette over another; "blue
light" is an underspecified control variable; coverage fraction alone does not
determine emitted light in dark themes).

## What is here

```
spec/roles.yaml            L1  semantics     -- what each role MEANS (no colour)
spec/distance-matrix.yaml  L1  constraints   -- which distinctions are obligatory
spec/environments.yaml     L2  parameters    -- contrast bands, backgrounds, stability
spec/bindings/candidate-*.yaml  L2  candidate hue-anchor + chroma-budget bindings (Phase 5)
themes/references/*.yaml        reference themes (Nord, Solarized, ...), hex, non-candidate
themes/fixtures/*.yaml          evaluation fixtures, OKLCH-first, non-candidate
themes/candidates/*.yaml        GENERATED candidate palettes, OKLCH-first (Phase 5)
src/grotto/                     implementation + evaluation tooling
tests/                          cross-validated test suite
out/                            generated reports (reproducible)
```

The evaluation tooling depends only on L1/L2 and never reaches into editor
bindings. No layer reaches downward: L1 has no hex values; the tooling has no
editor scope names. Phase 3 reference analysis output lives under
`out/references/` (per-reference `.json`/`.yaml`/`.txt`/`.html` plus
`comparison.{json,yaml,txt,html,svg}`).

## Install

```bash
uv sync                 # creates the venv and installs grotto + deps (coloraide, numpy, pyyaml)
uv run pytest           # run the suite
```

`grotto` is also installed as a console script (`uv run grotto ...`).

## CLI

All commands read `spec/roles.yaml`, `spec/distance-matrix.yaml` and
`spec/environments.yaml` from the repo root (override with `--roles` /
`--distances` / `--environments`). Inputs may be fixtures or reference themes;
none are treated as candidate palettes.

```bash
# Audit one palette: JSON + YAML + text report, plus a self-contained HTML
# page (swatches, contrast, distance-matrix, CVD, spectral, CVD-toggleable
# specimens) and an SVG swatch strip.
uv run grotto palette themes/fixtures/eval-night-full.yaml --out out/fixture-night

# Cross-variant stability for a day/evening/night trio (DESIGN.md D-5).
uv run grotto stability themes/fixtures/eval-day.yaml \
    themes/fixtures/eval-evening.yaml themes/fixtures/eval-night.yaml --out out/fixture-trio

# Write the plaintext code specimens (Python, Rust, TS, shell, JSON, YAML, Markdown, R).
uv run grotto specimens --out out/specimens

# A reference theme works too (editor 'variant: dark' is accepted):
uv run grotto palette themes/references/nord.yaml --out out/nord

# Phase 3: consistent quantitative analysis of ALL six reference themes.
# Writes per-reference .json/.yaml/.txt/.html plus a side-by-side
# comparison.{json,yaml,txt,html,svg}. Descriptive only -- no ranking
# or winner is declared (DESIGN.md section 1).
uv run grotto references --out out/references
# Analyse a subset explicitly:
uv run grotto references themes/references/nord.yaml \
    themes/references/solarized.yaml --out out/refs-subset

# Phase 4: build the environmental-transform family from a semantic-anchor
# binding. Writes a deterministic derivation report (per-role requested/capped/
# realized OKLCH, independent cap+gamut losses, winning constraint, conflicts)
# as JSON/YAML/text + a self-contained HTML page. NON-CANDIDATE experiment.
uv run grotto family spec/bindings/calibration.yaml --out out/model-calibration

# Phase 4: systematic-vs-hand-tuned comparison. Reports per-role dE_OK deltas
# and whether the systematic output needed hand adjustment, and where.
uv run grotto compare-families spec/bindings/calibration.yaml \
    themes/experiments/handtuned-day.yaml \
    themes/experiments/handtuned-evening.yaml \
    themes/experiments/handtuned-night.yaml --out out/model-calibration

# Phase 5/6: rebuild all canonical candidates + reports in one pass.
# Writes the 9 generated palettes (themes/candidates/), per-candidate family
# reports + family specimen pages, and the cross-candidate comparison
# (matrix, drift, specimens/CVD/spectral visuals) under out/candidates/.
# No score, rank, or recommendation is produced.
uv run grotto candidates --out out/candidates
```

Reports are **reproducible**: identical inputs produce byte-identical output
(no wall-clock timestamp); a content hash of the inputs is embedded for
provenance.

## Python API

```python
from grotto.spec import RoleSpec, DistanceSpec, load, audit_palette, check
from grotto.environments import Environments
from grotto.contrast import contrast_report       # WCAG 2.x, APCA Lc, OKLab dL
from grotto.distance import delta_e_ok, breakdown # dE_OK + per-channel breakdown
from grotto.cvd import simulate, check_pair       # Brettel dichromacy / Machado anomaly
from grotto.spectral import melanopic, screen_melanopic  # nominal-display, exploratory
from grotto.stability import cross_variant_report # cross-variant semantic reporting
from grotto.reference_analysis import (        # Phase 3 reference-theme analysis
    load_reference_dir, analyze_reference, compare_references,
)
from grotto.report import palette_report_dict, to_json
from grotto.model import (        # Phase 4 environmental transform
    CandidateBinding, ModelSpec, build_family, compare_families,
    hand_tuned_build, BindingError, TransformError,
)
from grotto.family_report import family_build_text, family_build_html
from grotto.render import palette_html_report, palette_svg_strip

# Phase 5/6: candidate bindings -> generated palettes + comparative evaluation.
from grotto.candidates import (        # Phase 5 generation
    build_candidates, candidate_family_report, write_all_candidate_artifacts,
)
from grotto.candidate_report import (   # Phase 6 comparison
    compare_candidates, candidate_comparison_html, candidate_family_specimens_html,
)

roles  = RoleSpec.load("spec/roles.yaml")
dists  = DistanceSpec.load("spec/distance-matrix.yaml", roles)
env    = Environments.load("spec/environments.yaml")
pal    = load("themes/fixtures/eval-night-full.yaml")   # OKLCH-first or hex

audit_palette(pal, roles)        # per-role OKLCH/OKLab/hex + sRGB & P3 gamut status
check(pal, roles, dists)         # distance-matrix + CVD violations
contrast_report(pal["fg"], pal.bg)
cross_variant_report({"day": p_day, "night": p_night}, roles)

# Phase 4: build the three-variant family from a semantic-anchor binding.
binding = CandidateBinding.load("spec/bindings/calibration.yaml")
spec4   = ModelSpec(roles, env, dists)
family  = build_family(binding, spec4)        # -> FamilyBuild (NON-CANDIDATE)
family.palettes            # {"day": Palette, "evening": Palette, "night": Palette}
family.trace("night", "keyword")  # RoleTrace: requested/capped/realized, losses,
                                  #   winning constraint, conflicts, adjustments
family.stability           # corrected cross-variant stability report

# Compare a systematic family against a hand-tuned target.
hand = {v: load(f"themes/experiments/handtuned-{v}.yaml")
        for v in ("day", "evening", "night")}
cmp = compare_families(family, hand_tuned_build(hand, spec4), spec4)
cmp["summary"]["systematic_needed_hand_adjustment"]   # the headline finding

# Phase 5/6: build the three canonical candidates and compare them.
families = build_candidates(spec4)            # 3 FamilyBuilds (A/B/C)
artifacts = write_all_candidate_artifacts(spec4)   # palettes + reports + visuals
comparison = compare_candidates(families, spec4)   # cross-candidate matrix
comparison["matrix"]                          # descriptive columns, NOT a score
# (No aggregate score, rank, or winner is produced; Phase 7 decides.)

# Phase 3: analyse every reference consistently and compare side by side.
# (Descriptive only -- no ranking or winner; see DESIGN.md section 1.)
from grotto.reference_analysis import primary_variant
refs   = load_reference_dir("themes/references")        # stem -> [ReferenceVariant]
ref_an = {
    stem: analyze_reference(primary_variant(vs), roles, dists, env)
    for stem, vs in refs.items()
}
compare_references(ref_an, roles, dists, env)            # side-by-side dict
```

## The metrics and their limits

Grotto reports several metrics *together* and treats disagreement as signal.

| Metric | Module | Status / caveat |
|---|---|---|
| OKLCH / OKLab / sRGB hex | `color` | auditable from published matrices; cross-validated against `coloraide`. OKLab is not hue-linear in the blue/purple sector (R-8). |
| sRGB & Display-P3 gamut status + mapping | `color` | excursion reported explicitly; chroma lost to mapping is recorded, never silently clipped (DESIGN.md §5). |
| WCAG 2.x ratio | `contrast` | current W3C Recommendation and the compliance claim. Its equation is polarity-independent and does not model font rendering (R-11). |
| APCA Lc | `contrast` | **Independent work in progress, not a W3C Recommendation or current WCAG criterion.** Used only as an experimental design signal. |
| OKLab ΔL | `contrast` | cheap, polarity-aware ordering check. |
| dE_OK + channel breakdown | `distance` | Euclidean OKLab; decomposed into lightness/chroma/hue. Lightness is often a more robust redundant cue, but no channel guarantees CVD separation. |
| CVD simulation (protan/deutan/tritan) | `cvd` | dichromacy via Brettel 1997, anomaly via Machado 2009, tritan always Brettel. **Population-average dichromat models** — they detect collapse, they do not reproduce an individual's experience (R-9). |
| Cross-variant stability | `stability` | hue drift, family/hue ordering, salience rank, chroma rank. Cross-variant dE is informational **only** (Day↔Night inverts lightness by design). |
| Melanopic, area-weighted | `spectral` | **exploratory, nominal-display, within-model ranking only.** An sRGB triple does not determine a spectral power distribution; this never claims actual retinal exposure (R-4, R-5). |
| Reference analysis (Phase 3) | `reference_analysis` | consistent six-reference comparison: background OKLCH (hue suppressed when achromatic), fg/bg WCAG+APCA, lightness/chroma distributions, declared-constraint coverage, chroma-weighted warm/cool balance, nominal spectral background-vs-token split, CVD behaviour. **Descriptive only; no ranking** (DESIGN.md §1). |
| Environmental transform (Phase 4) | `model` | `build_family` derives day/evening/night from a semantic-anchor binding: ink jointly lightness+chroma-solved (lexicographic WCAG>ceiling>APCA>adjustment), surface perceptual steps, border non-text contrast, canvas authored; independent cap+gamut losses; warm-anchor hue attraction; corrected cross-variant stability. **NON-CANDIDATE experiment** (DESIGN.md §1). APCA experimental (R-11); WCAG floors hard. |
| Candidate bindings & generation (Phase 5) | `candidates`, `model` | Three candidate bindings (Restrained / Balanced / Expressive) — each ONE semantic binding with its own chroma budget (class fractions + per-category caps) turned into day/evening/night by the SAME shared transform. Candidate-specific classes/caps are first-class inputs (in the hash/provenance); family may be overridden per role while the derivation PATH (paint) stays protected. Generated OKLCH-first/sRGB palettes under `themes/candidates/`. **CANDIDATE; no winner ranked.** |
| Cross-candidate comparison (Phase 6) | `candidate_report` | Descriptive 3×3 evaluation matrix, per-role cross-variant and cross-candidate drift, declared area-weighted nominal spectral for BOTH display models, CVD retention summaries, side-by-side specimens (8 languages × 3 variants) + critical-state diagnostics with redundant markers, normal/protan/deutan/tritan views, and a metrics-vs-visual-judgment disagreement log. **No aggregate score, rank, or recommendation.** |

D-3 is enforced at load time: every role with `cvd_priority: critical` must
declare a `redundant_channels` entry, because **hue is never the sole carrier of
critical meaning.** The loader rejects a spec that violates this.

## Canonical inputs are perceptual-space-first

Fixtures and (future) candidates are authored in **OKLCH**; hex is the
serialised form. The loader gamut-maps each coordinate to sRGB and records any
chroma lost, so a colour the display cannot make is surfaced as a design bug,
not a rounding detail.

```yaml
# themes/fixtures/eval-night-full.yaml  (NON-candidate fixture)
format: oklch
candidate: false
colors:
  bg:    {L: 0.205, C: 0.007, h: 70}
  focus: {L: 0.720, C: 0.190, h: 245}   # deliberately past sRGB -> gamut-mapped
```

## Status

Phases implemented: **Phase 1** (specification, `DESIGN.md` / `RESEARCH.md` /
`spec/`), **Phase 2** (evaluation tooling: colour/contrast/distance/CVD/
spectral metrics, palette loading/validation, cross-variant reporting,
specimens, reproducible reports and self-contained visual render, tests), and
**Phase 3** (consistent quantitative reference-theme analysis across all six
references: background OKLCH with achromatic hue suppression, fg/bg WCAG +
experimental APCA, lightness/chroma distributions, declared-constraint
distances and coverage, an explicitly defined chroma-weighted warm/cool
balance, nominal area-weighted spectral comparison with background-vs-token
decomposition, and CVD behaviour; per-reference JSON/YAML/text/HTML plus a
side-by-side comparison JSON/YAML/text/HTML/SVG under `out/references/`;
descriptive only, no ranking).

**Phase 4** (environmental transform): `build_family(binding, spec) ->
FamilyBuild` in `src/grotto/model.py` turns a semantic-anchor binding into
three per-variant palettes with full derivation provenance. It implements the
senior-architecture review, not the DESIGN.md section-9 sketch: roles branch on
`paint` (canvas authored / ink jointly lightness+chroma-solved under a
lexicographic WCAG>ceiling>APCA>adjustment stack / surface perceptual steps /
border non-text contrast); chroma is an explicit multiplicative chain with
independent cap+gamut loss reporting; hue attracts toward a warm anchor
(correcting the violet-goes-blue bug of a signed rotation); WCAG overrides the
Night foreground ceiling and APCA, recording each conflict; ink legibility
over every co-occurring surface is evaluated as issues. `BindingError` for
malformed bindings, `TransformError` only for infeasible hard constraints.
`compare_families(systematic, hand_tuned, spec)` sits beside it and reports
whether the systematic output needed hand adjustment. Cross-variant stability
uses the corrected checks (normalized C/max_chroma ordering, cyclic family
sequence, non-vacuous realized salience proxy, drift including adjustments).
Everything is NON-CANDIDATE: `spec/bindings/calibration.yaml` and the
`themes/experiments/handtuned-*.yaml` comparison target are Phase 4 calibration
experiments, not Candidate A/B/C. Reports live under `out/model-calibration/`
(JSON/YAML/text + self-contained HTML). Build with `grotto family`, compare
with `grotto compare-families`.

Not done here: final candidate palettes (Phase 5) and human evaluation
(Phase 7). Reference themes are inputs only; the Phase 3 analysis is
descriptive and draws no conclusion about which reference is "best"
(DESIGN.md section 1). Phase 4 output is a NON-CANDIDATE experiment.

**Phase 5 (candidates)** and **Phase 6 (comparative evaluation)** are now
implemented: three candidate bindings live under `spec/bindings/`, the nine
generated palettes under `themes/candidates/`, and the per-candidate family
reports + cross-candidate comparison under `out/candidates/`. These are
**CANDIDATE** families — the first produced here — but **no aggregate score,
ranking, or recommendation** is made and no winner is selected; Phase 7 (human
evaluation) is the only part that tests the actual preference claim. Rebuild
everything with `uv run grotto candidates --out out/candidates`.

## License

See [LICENSE](LICENSE).
