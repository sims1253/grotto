"""Phase 8c: bounded raster area analysis.

Acceptance points:
  * tiny generated PNG fixtures only (no committed screenshots);
  * chunking is bounded: no yielded chunk exceeds chunk_rows rows, each
    band is cropped before RGB conversion (the whole image is never
    converted at once), and analysis is chunk-size independent;
  * the linear-RGB mean is accumulated from fixed 256-bin per-channel
    counts dotted with the sRGB->linear LUT (no float64 pixel plane) and
    still matches direct per-pixel expansion;
  * memory-bound reporting is honest: fields name the maximum input RGB
    chunk bytes and the fixed RGB555 / per-channel histogram bytes;
  * exact colour coverage counts exact palette pixels correctly;
  * nearest-role classification respects the documented threshold and
    reports the fixed category vocabulary;
  * area-weighted spectral numbers from mean linear RGB are EXACTLY the
    coverage-weighted per-colour values (linearity), for both display
    models, without per-pixel SPD integration;
  * the report states that pixel measurement is not semantic ground truth.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from grotto.raster import (
    CATEGORIES,
    DEFAULT_CHUNK_ROWS,
    ROLE_CATEGORIES,
    _linear_rgb_spectral,
    _row_chunks,
    analyze_screenshot,
)
from grotto.color import srgb_to_linear
from grotto.spec import load as load_palette
from grotto.spectral import DISPLAYS, melanopic

PAL = "themes/candidates/candidate-a-restrained.evening.yaml"


@pytest.fixture(scope="module")
def palette():
    return load_palette(PAL)


def _write_png(path, array) -> str:
    Image.fromarray(np.asarray(array, dtype=np.uint8), "RGB").save(path, format="PNG")
    return str(path)


def test_chunk_rows_bounded(tmp_path):
    # tall skinny image; chunk bound must hold for every yielded band
    w, h = 9, 300
    arr = np.tile(np.arange(h, dtype=np.uint8)[:, None, None], (1, w, 3))
    p = _write_png(tmp_path / "tall.png", arr)
    im = Image.open(p)
    sizes = [c.shape[0] for _, c in _row_chunks(im, chunk_rows=17)]
    assert max(sizes) <= 17 and len(sizes) == 18  # ceil(300/17)
    assert sum(sizes) == h


def test_row_chunks_crop_before_convert(tmp_path, monkeypatch):
    # the whole image must never be converted: every .convert("RGB") call
    # must see a band of at most chunk_rows rows (crop first, then convert)
    heights = []
    real_convert = Image.Image.convert

    def spying_convert(self, mode, *args, **kwargs):
        heights.append(self.size[1])
        return real_convert(self, mode, *args, **kwargs)

    monkeypatch.setattr(Image.Image, "convert", spying_convert)
    w, h = 8, 40
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    p = _write_png(tmp_path / "bands.png", arr)
    with Image.open(p) as im:
        bands = [c for _, c in _row_chunks(im, chunk_rows=9)]
    assert heights and max(heights) <= 9          # never the full 40 rows
    assert sum(b.shape[0] for b in bands) == h


def test_chunk_bound_fields_are_honest(tmp_path, palette):
    # each field names exactly what it measures; no vague max_bytes
    w, h = 6, 40
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    arr[..., 1] = np.arange(h, dtype=np.uint8)[:, None]   # non-flat content
    p = _write_png(tmp_path / "mem.png", arr)
    rep = analyze_screenshot(p, PAL, chunk_rows=16)
    ch = rep["image"]["chunk"]
    assert ch["rows"] == 16
    assert ch["max_rows_seen"] == 16              # chunks of 16, 16, 8
    assert ch["max_input_rgb_chunk_bytes"] == 16 * w * 3
    assert ch["rgb555_histogram_bytes"] == 32768 * 8   # fixed, int64
    assert ch["channel_histogram_bytes"] == 256 * 8    # fixed, int64
    assert "max_bytes" not in ch


def test_chunk_size_independence_and_exact_coverage(tmp_path, palette):
    # image made ONLY of exact palette colours: 60% bg, 30% fg, 10% keyword
    w = 10
    rows = []
    for _ in range(6):
        rows.append(np.full((1, w, 3), _rgb8(palette["bg"]), dtype=np.uint8))
    for _ in range(3):
        rows.append(np.full((1, w, 3), _rgb8(palette["fg"]), dtype=np.uint8))
    rows.append(np.full((1, w, 3), _rgb8(palette["keyword"]), dtype=np.uint8))
    p = _write_png(tmp_path / "flat.png", np.vstack(rows))

    r1 = analyze_screenshot(p, PAL, chunk_rows=1)
    r2 = analyze_screenshot(p, PAL, chunk_rows=128)
    assert r1["classification"] == r2["classification"]

    ex = r1["classification"]["exact_by_color"]
    assert r1["classification"]["exact_fraction"] == 1.0
    assert ex[palette["bg"]]["fraction"] == pytest.approx(0.6, abs=1e-6)
    assert ex[palette["fg"]]["fraction"] == pytest.approx(0.3, abs=1e-6)
    assert ex[palette["keyword"]]["fraction"] == pytest.approx(0.1, abs=1e-6)
    # bg/fg/keyword are unique colours; their exact rows carry one role each
    assert ex[palette["bg"]]["roles"] == ["bg"]
    assert r1["classification"]["unclassified_fraction"] == pytest.approx(0.0, abs=1e-6)
    cats = r1["classification"]["nearest_by_category"]
    assert cats["background"]["fraction"] == pytest.approx(0.6, abs=1e-6)
    assert cats["normal foreground"]["fraction"] == pytest.approx(0.3, abs=1e-6)
    assert cats["syntax accents"]["fraction"] == pytest.approx(0.1, abs=1e-6)


def _rgb8(hex_color: str):
    return tuple(int(hex_color[i:i + 2], 16) for i in (1, 3, 5))


def test_nearest_threshold_and_unclassified(tmp_path, palette):
    # pure red (not in the palette) at increasing blends with bg
    bg = np.array(_rgb8(palette["bg"]), dtype=float)
    red = np.array((255, 0, 0), dtype=float)
    rows = []
    fractions = [0.0, 0.5, 1.0]     # bg, half-blend, pure red
    for f in fractions:
        c = (bg * (1 - f) + red * f).round().astype(np.uint8)
        rows.append(np.tile(c[None, None, :], (1, 3, 1)))
    p = _write_png(tmp_path / "blend.png", np.vstack(rows))
    rep = analyze_screenshot(p, PAL, threshold=0.02, chunk_rows=2)

    cls = rep["classification"]
    assert cls["exact_by_color"][palette["bg"]]["pixels"] == 3   # exact row
    assert cls["unclassified_fraction"] == pytest.approx(2 / 3, abs=1e-6)
    assert cls["threshold_de_ok"] == 0.02


def test_spectral_matches_coverage_weighted_exact(tmp_path, palette):
    # exact-palette image -> mean-linear-RGB method must equal the
    # coverage-weighted per-colour melanopic()/photopic() values exactly.
    rows = [
        np.full((2, 4, 3), _rgb8(palette["bg"]), dtype=np.uint8),
        np.full((1, 4, 3), _rgb8(palette["fg"]), dtype=np.uint8),
        np.full((1, 4, 3), _rgb8(palette["string"]), dtype=np.uint8),
    ]
    p = _write_png(tmp_path / "spec.png", np.vstack(rows))
    rep = analyze_screenshot(p, PAL, chunk_rows=3)

    total = 16
    coverage = {
        palette["bg"]: 8 / total,
        palette["fg"]: 4 / total,
        palette["string"]: 4 / total,
    }
    for name in DISPLAYS:
        disp = DISPLAYS[name]()
        p_tot = q_tot = 0.0
        for hx, frac in coverage.items():
            m = melanopic(hx, disp)
            p_tot += frac * m.photopic
            q_tot += frac * m.melanopic
        got = rep["spectral"]["displays"][name]
        assert got["photopic"] == pytest.approx(p_tot, abs=5e-6)
        assert got["melanopic"] == pytest.approx(q_tot, abs=5e-6)


def test_linear_accumulation_matches_direct_lut(tmp_path, palette):
    # arbitrary (non-palette) pixels: the per-channel bincount + LUT dot
    # accumulation must equal direct per-pixel LUT expansion of the image
    rng = np.random.default_rng(8)
    arr = rng.integers(0, 256, (7, 11, 3), dtype=np.uint8)
    p = _write_png(tmp_path / "rand.png", arr)
    rep = analyze_screenshot(p, PAL, chunk_rows=3)
    lut = np.array([srgb_to_linear(i / 255.0) for i in range(256)])
    mean_lin = np.array([lut[arr[..., c].ravel()].mean() for c in range(3)])
    for name in DISPLAYS:
        photopic, melanopic = _linear_rgb_spectral(mean_lin, DISPLAYS[name]())
        got = rep["spectral"]["displays"][name]
        assert got["photopic"] == pytest.approx(photopic, abs=5e-6)
        assert got["melanopic"] == pytest.approx(melanopic, abs=5e-6)


def test_categories_complete():
    assert set(ROLE_CATEGORIES.values()) == set(CATEGORIES)
    from grotto.spec import RoleSpec
    roles = RoleSpec.load("spec/roles.yaml")
    every_role = {r.name for r in roles}
    assert every_role <= set(ROLE_CATEGORIES), every_role - set(ROLE_CATEGORIES)


def test_report_states_ground_truth_limits(tmp_path, palette):
    p = _write_png(tmp_path / "one.png", np.full((2, 2, 3), _rgb8(palette["bg"]), np.uint8))
    rep = analyze_screenshot(p, PAL)
    joined = " ".join(rep["caveats"]).lower()
    assert "not semantic ground truth" in joined
    assert rep["schema"] == "grotto.raster/1"
    assert rep["palette"]["variant"] == "evening"
    assert len(rep["palette"]["sha256"]) == 64
    assert rep["image"]["chunk"]["rows"] == DEFAULT_CHUNK_ROWS


def test_cli_raster(tmp_path, palette):
    import json
    from grotto.cli import main

    png = _write_png(tmp_path / "cli.png", np.full((4, 5, 3), _rgb8(palette["bg"]), np.uint8))
    out = tmp_path / "report.json"
    rc = main(["raster", png, "--palette", PAL, "--out", str(out)])
    assert rc == 0
    rep = json.loads(out.read_text())
    pal = load_palette(PAL)
    assert rep["classification"]["exact_by_color"][pal["bg"]]["fraction"] == 1.0
    assert set(rep["spectral"]["displays"]) == {"led-lcd", "oled"}


def test_shared_colour_ambiguity_is_reported(tmp_path, palette):
    """Roles sharing one hex cannot be separated by pixels -- must be explicit."""
    # the Restrained evening candidate collapses fg/docstring/parameter/property
    shared_hex = palette["fg"]
    assert "parameter" in [r for r in palette.colors if palette[r] == shared_hex]
    # representative is the earliest-declared role (fg, a neutral)
    rows = [np.full((1, 4, 3), _rgb8(palette["fg"]), dtype=np.uint8),
            np.full((1, 4, 3), _rgb8(palette["bg"]), dtype=np.uint8)]
    p = _write_png(tmp_path / "shared.png", np.vstack(rows))
    rep = analyze_screenshot(p, PAL)
    cls = rep["classification"]
    amb = cls["shared_colour_ambiguity"]
    assert shared_hex in amb
    assert amb[shared_hex]["roles"] == ["docstring", "fg", "parameter", "property"]
    assert "fg" in amb[shared_hex]["roles"]
    assert amb[shared_hex]["fraction"] == pytest.approx(0.5, abs=1e-6)
    # accounting is fraction-consistent: classified + unclassified == 1
    assert cls["classified_fraction"] + cls["unclassified_fraction"] == pytest.approx(1.0, abs=1e-6)
