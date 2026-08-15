# Candidate reports (Phase 5 / Phase 6)

Reproducible reports for the three Grotto **candidate** families. Rebuild
everything with:

```bash
uv run grotto candidates --out out/candidates
```

## Tree

```
index.json / index.yaml          registry of the 3 candidates (NOT a ranking)
comparison.json/.yaml/.txt       cross-candidate comparative evaluation (Phase 6)
comparison.html                  matrix + drift + side-by-side specimen + diagnostics
comparison.svg                   night-variant key-role swatches across candidates
<candidate>/
  <candidate>.build.json/.yaml/.txt/.html   derivation provenance (Phase 4 report)
  <candidate>.eval.json/.yaml                per-variant full audit (colors/contrast/
                                             distance/CVD/spectral)
  <candidate>.specimens.html                 every language specimen x 3 variants,
                                             critical-state diagnostics, CVD-toggleable
```

The generated concrete palettes themselves live under `themes/candidates/`.

## How to read this (important)

These are **CANDIDATE** families — the first produced here. They are **not** a
selected or final theme, and **no aggregate score, ranking, or recommendation**
is made (DESIGN.md section 1). Candidates are listed in binding-file
(alphabetical) order: Restrained, Balanced, Expressive.

Metric framing, repeated near every number:

- **WCAG 2.x** ratios are the hard compliance floor. All candidates pass it or
  generation fails (`ok=True`); soft distance/CVD/legibility misses stay visible
  as issues and thresholds are **not** massaged to make a candidate pass.
- **APCA** is independent work in progress, not a W3C Recommendation or current
  WCAG criterion (R-11).
- **CVD** models are population-average dichromat (Brettel) simulations; they
  detect collapse, they do not certify accessibility or reproduce an
  individual's experience (R-9).
- **Spectral** numbers are **nominal within-model** only. An sRGB triple does
  not determine a spectral power distribution; this never claims actual retinal
  exposure or a circadian/medical effect (R-4, R-5). The coverage weighting is a
  **declared estimate**, not a screenshot pixel count.
- **Pixel area** is a declared estimate (no rasterization/counting), grouped into
  background / normal-foreground / comments / syntax-accents / UI-chrome /
  selection-highlights / diagnostics categories and propagated into the nominal
  spectral comparison.

The metrics-vs-visual-judgment **disagreement log** in `comparison.*` records
expected places where metrics and a human eye will disagree; that disagreement
is a finding, not a failure. Phase 7 (human evaluation) is the only part that
tests the actual preference claim.
