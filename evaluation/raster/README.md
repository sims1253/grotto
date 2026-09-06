# Bounded screenshot area analysis (Phase 8c)

`grotto raster` measures what fraction of an **existing PNG screenshot** is
covered by each palette role/category, and reports nominal area-weighted
photopic/melanopic output under the project's two synthetic display models.
It is a coarse area audit, nothing more.

## What it is NOT

- **Not semantic ground truth.** Antialiasing blends foreground and
  background into colours that match no role; window transparency, embedded
  images, terminal output, extension decorations, zoom/scaling and window
  chrome all add colours the theme never defined. Exact-match and
  nearest-role numbers are coverage estimates under a documented threshold.
- **Not a capture tool.** This repo does not control VS Code or Zed. You take
  the screenshot yourself.
- **Not a light measurement.** Photopic/melanopic values are nominal,
  within-model, relative to the model display's white (see `spectral.py`);
  they say nothing about absolute light at your eye.

## Use

```bash
uv run grotto raster shot.png \
    --palette themes/candidates/candidate-a-restrained.evening.yaml \
    --out out/raster/evening-restrained.json
# options: --threshold 0.05 (OKLab dE), --chunk-rows 128
```

Report contents: image dimensions and the honest memory-bound fields
(maximum input RGB chunk bytes, fixed RGB555 histogram bytes, fixed
per-channel histogram bytes — each field names exactly what it measures);
palette name/variant and file SHA-256; exact per-role colour coverage;
nearest-role and per-category coverage (background / normal foreground /
comments / syntax accents / UI chrome / selection-highlights / diagnostics)
plus unclassified fraction; and area-weighted nominal photopic/melanopic
metrics for **both** display models (`led-lcd`, `oled`).

How it stays bounded: rows are processed in chunks of at most `--chunk-rows`,
each band cropped *before* conversion to RGB (≈1.4 MB of input RGB at 4K
width); nearest-role classification uses a fixed 32,768-bin RGB555 histogram,
and the mean linear RGB is accumulated from fixed 256-bin per-channel
counts dotted with the sRGB→linear LUT, so no float64 pixel plane is ever
materialised; the spectral numbers are computed **exactly** from the mean
linear RGB — the display SPD is linear in linear RGB and the weighting is a
linear functional, so one integration per display model equals the
per-pixel area-weighted integral without ever integrating per unique pixel.

## Capturing a screenshot (manual, your installed editor)

1. Install either the VS Code or Zed evaluation preview, then pick the exact
   theme label you will analyse. See `editors/vscode/README.md` or
   `editors/zed/README.md`.
2. Fix the environment first (same as any scan condition in
   `HUMAN_EVALUATION.md`): display brightness, OS colour profile, zoom,
   font size, panel layout; disable HDR/True Tone if you cannot hold them
   constant.
3. Open a representative file (e.g. an `evaluation/r-corpus` item or one of
   the frozen specimens) at a fixed window size; let syntax colouring settle
   (semantic tokens can arrive a moment later).
4. Screenshot only the editor area where possible (crop later is fine);
   PNG, not JPEG. Note the display scale — 2× scaling doubles effective
   pixel dimensions.
5. Fill in `capture-metadata-template.yaml` next to the PNG and keep both
   together (committing is fine for small captures); the report records the
   palette's SHA-256 so palette drift is detectable.

**HDR and tone mapping.** HDR and OS tone mapping can change the pixel values
in a PNG even when the theme is unchanged. Record the HDR state in
`capture-metadata-template.yaml`. Use SDR captures when you need exact
palette-colour comparison; keep your normal display conditions for subjective
evaluation. Before exact-match analysis, sample a flat background region and
confirm that its PNG value matches the theme value.

## Template

Copy `capture-metadata-template.yaml` for each screenshot. Do not commit
large screenshots to the repo; fixtures in tests are tiny generated PNGs.
