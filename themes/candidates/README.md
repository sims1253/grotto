# Generated candidate palettes (Phase 5)

This directory holds the **generated concrete candidate palettes** for Phase 5:
nine OKLCH-first/sRGB palettes — three candidate *strategies* × three
environment variants (day / evening / night).

These are **not** nine independently authored palettes. Each row is ONE
semantic binding (`spec/bindings/candidate-<strategy>.yaml`) that the shared
environmental transform (`grotto.model.build_family`) turns into day/evening/
night. Candidates differ only in their chroma budget (class fractions +
per-category caps), hue anchors, bounded semantic overrides, and (for C) a few
role scales — never in the shared environments or the contrast reference.

| file | candidate | variant |
|---|---|---|
| `candidate-a-restrained.{day,evening,night}.yaml` | A — Restrained | day / evening / night |
| `candidate-b-balanced.{day,evening,night}.yaml`   | B — Balanced   | day / evening / night |
| `candidate-c-expressive.{day,evening,night}.yaml` | C — Expressive | day / evening / night |

## Provenance

Every file is `format: oklch` with explicit generated/source metadata:

```yaml
format: oklch
candidate: true
source: generated
meta:
  generated: true
  source: phase5-transform
  transform: phase4-model
  binding: candidate-a-restrained
  strategy: restrained
  input_hash: 025bb0e71b16c7e9          # binding + model spec content hash
  shared_environments: spec/environments.yaml
  srgb_primary: true
```

The perceptual coordinates stored are the *realized* (post-gamut-map) OKLCH the
display actually shows; hex is the derived sRGB serialisation. Re-loading a file
reproduces the same hex losslessly. Regenerate everything with:

```bash
uv run grotto candidates --out out/candidates
```

## Status — read this

These are **CANDIDATE** palettes (Phase 5), the first produced here. They are
**not** a selected or final theme, and **no aggregate score, ranking, or
recommendation** is made (DESIGN.md section 1). Each candidate documents its own
hypothesis and tradeoffs in its binding file; the cross-candidate comparison
lives under `out/candidates/`. Phase 7 (human evaluation) is the only part that
tests the actual preference claim.

Honest metric framing (see `DESIGN.md` / `RESEARCH.md`): WCAG 2.x ratios are
the hard compliance floor; APCA is independent work in progress, not a W3C
Recommendation; CVD models are population-average dichromat simulations that
detect collapse but do not reproduce an individual's experience; spectral
numbers are nominal within-model only.
