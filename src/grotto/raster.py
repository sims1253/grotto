"""Bounded raster analysis of a screenshot against a generated palette.

Phase 8c measurement tool. Takes an existing PNG screenshot (taken manually
by the user in their installed VS Code -- there is no capture automation
here, no browser, no Electron) plus a generated palette/variant YAML, and
reports pixel statistics with strictly bounded memory.

!! Screenshot pixel measurement is NOT semantic ground truth !!
Antialiasing blends foreground and background into colours that match no
role; transparency, embedded images, terminal output, extension decorations,
zoom/scaling and window chrome all introduce colours the theme never
defined. Exact-match and nearest-role numbers are coverage estimates under a
documented threshold, never a claim about what the user perceived.

Memory bound: the image is processed in row chunks (<= chunk_rows rows at a
time); nearest-colour classification of non-palette pixels uses a fixed
32,768-bin RGB555 histogram (5 bits/channel), so memory does not grow with
image content diversity. Pixels that exactly match a palette colour are
counted exactly to that colour; only the residual goes through the
quantised nearest-colour pass (documented threshold in OKLab dE), so
near-identical palette colours cannot steal each other's pixels. Roles that
share one colour (legitimately, in Restrained) are attributed to a
deterministic representative role and reported in
`shared_colour_ambiguity`.

Photopic/melanopic metrics are EXACT area-weighted values despite one
integration per display model: the display SPD is linear in linear sRGB, and
photopic/melanopic quantities are linear functionals of the SPD, so the mean
linear RGB over all pixels yields exactly the area-weighted result. SPDs are
never integrated per unique pixel. Values are NOMINAL within the synthetic
display models (see spectral.py) -- not measured light at the eye.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .color import hex_to_oklch, hex_to_srgb, oklch_to_oklab, srgb_to_linear
from .spec import Palette, RoleSpec
from .spectral import DISPLAYS, LAMBDA as _LAMBDA, s_mel, v_lambda

SCHEMA = "grotto.raster/1"

DEFAULT_CHUNK_ROWS = 128       # 128 rows x 3840 px x 3 bytes ~ 1.4 MB max chunk
QUANT_BITS = 5                 # RGB555: 32768 bins, ~256 KiB histogram
QUANT_BINS = 1 << (3 * QUANT_BITS)
DEFAULT_THRESHOLD = 0.05       # OKLab dE for nearest-role classification

CAVEATS = [
    "screenshot pixel measurement is not semantic ground truth",
    "antialiasing blends roles into colours that match no palette entry",
    "window transparency, images, terminals, extension decorations, scaling, "
    "and non-editor UI introduce colours the theme never defined",
    "nearest-role classification is approximate: RGB555 bin centres plus a "
    "documented OKLab distance threshold",
    "photopic/melanopic values are nominal, area-weighted within the "
    "synthetic led-lcd/oled display models; they are not measured light at "
    "the eye (see spectral.py)",
]

# Coarse pixel categories for reporting (fixed vocabulary).
ROLE_CATEGORIES: dict[str, str] = {
    "bg": "background", "bg_elevated": "background", "bg_overlay": "background",
    "fg": "normal foreground", "fg_secondary": "normal foreground",
    "fg_muted": "normal foreground", "punctuation": "normal foreground",
    "operator": "normal foreground", "parameter": "normal foreground",
    "property": "normal foreground",
    "comment": "comments", "docstring": "comments",
    "keyword": "syntax accents", "string": "syntax accents",
    "number": "syntax accents", "constant": "syntax accents",
    "type": "syntax accents", "function": "syntax accents",
    "builtin": "syntax accents", "decorator": "syntax accents",
    "tag": "syntax accents", "namespace": "syntax accents",
    "ui_inactive": "UI chrome", "line_number": "UI chrome",
    "line_number_active": "UI chrome", "focus": "UI chrome",
    "selection": "selection/highlights", "search_match": "selection/highlights",
    "search_match_current": "selection/highlights", "active_line": "selection/highlights",
    "diff_added": "selection/highlights", "diff_removed": "selection/highlights",
    "diff_changed": "selection/highlights", "debug_current": "selection/highlights",
    "error": "diagnostics", "warning": "diagnostics", "info": "diagnostics",
    "success": "diagnostics", "breakpoint": "diagnostics",
    "deprecated": "diagnostics",
}
CATEGORIES = ("background", "normal foreground", "comments", "syntax accents",
              "UI chrome", "selection/highlights", "diagnostics")


@dataclass(frozen=True)
class ChunkInfo:
    """Observability for the memory bound (tests assert on it)."""

    rows: int
    max_chunk_rows: int
    max_chunk_bytes: int


def _row_chunks(im, chunk_rows: int):
    """Yield (offset, np.ndarray[rows, width, 3] uint8) with rows <= chunk_rows.

    Uses crop-then-convert so at most ``chunk_rows`` rows are ever resident.
    """
    w, h = im.size
    for y in range(0, h, chunk_rows):
        rows = min(chunk_rows, h - y)
        band = im.convert("RGB").crop((0, y, w, y + rows))
        yield y, np.asarray(band, dtype=np.uint8)


def _oklab_from_u8(r: int, g: int, b: int) -> np.ndarray:
    l, c, h = hex_to_oklch(f"#{r:02x}{g:02x}{b:02x}")
    return np.array(oklch_to_oklab((l, c, h)))


def _linear_rgb_spectral(lin_rgb, display) -> tuple[float, float]:
    """(photopic, melanopic) of one linear RGB triplet, display-white normalised.

    Exact because the SPD is linear in linear RGB and the weightings are
    linear functionals of the SPD.
    """
    spd = lin_rgb[0] * display.r + lin_rgb[1] * display.g + lin_rgb[2] * display.b
    white = display.r + display.g + display.b
    pw = float(np.trapezoid(white * v_lambda(), _LAMBDA))
    qw = float(np.trapezoid(white * s_mel(), _LAMBDA))
    photopic = float(np.trapezoid(spd * v_lambda(), _LAMBDA)) / pw
    melanopic = float(np.trapezoid(spd * s_mel(), _LAMBDA)) / qw
    return photopic, melanopic



def _representative(hex_roles: list[str], order: dict[str, int]) -> str:
    """Deterministic representative role for a shared colour.

    Earliest role in spec/roles.yaml declaration order (the neutral hierarchy
    precedes syntax roles, so e.g. an fg/docstring/parameter/decoration
    collapse is attributed to `fg`, not to a syntax accent).  The sharing
    itself is always reported in `shared_colour_ambiguity`.
    """
    return min(hex_roles, key=lambda r: order.get(r, len(order)))


def analyze_screenshot(
    png_path: str | Path,
    palette_path: str | Path,
    *,
    threshold: float = DEFAULT_THRESHOLD,
    chunk_rows: int = DEFAULT_CHUNK_ROWS,
    max_width: int = 7680,
    roles: RoleSpec | None = None,
) -> dict:
    """Analyse one PNG against one generated palette; returns a JSON-ready dict."""
    from PIL import Image  # local import keeps the module import-cheap

    palette = Palette.from_yaml(palette_path)
    if roles is None:
        try:
            roles = RoleSpec.load("spec/roles.yaml")
        except FileNotFoundError:
            roles = None
    # declaration order from L1 (neutral hierarchy first) for tie-breaks
    order = {r.name: i for i, r in enumerate(roles)} if roles else {}
    roles_sorted = sorted(palette.colors)
    roles = roles_sorted
    # Pixel measurement cannot distinguish roles that share one colour (e.g.
    # the Restrained strategy collapses comment/parameter/property).  All
    # accounting is therefore per UNIQUE colour, with the sharing made
    # explicit instead of being silently double-counted.
    unique_hex = sorted(set(palette.colors.values()))
    hex_roles = {hx: [r for r in roles if palette[r] == hx] for hx in unique_hex}
    hex8 = {hx: tuple(int(hx[i:i + 2], 16) for i in (1, 3, 5)) for hx in unique_hex}
    hex_oklab = {hx: _oklab_from_u8(*v) for hx, v in hex8.items()}

    with Image.open(png_path) as im:
        w, h = im.size
        if w > max_width:
            raise ValueError(f"width {w} exceeds max_width {max_width}; refusing")
        exact = {hx: 0 for hx in unique_hex}
        hist = np.zeros(QUANT_BINS, dtype=np.int64)
        lin_sum = np.zeros(3, dtype=np.float64)
        # 8-bit -> linear lookup table (bounded, exact for stored pixels)
        lut = np.array([srgb_to_linear(i / 255.0) for i in range(256)])
        max_rows_seen = 0
        for _, chunk in _row_chunks(im, chunk_rows):
            max_rows_seen = max(max_rows_seen, chunk.shape[0])
            residual_mask = np.zeros(chunk.shape[:2], dtype=bool)
            for hx, rgb8 in hex8.items():
                m = np.all(chunk == rgb8, axis=-1)
                exact[hx] += int(np.count_nonzero(m))
                residual_mask |= m
            residual = chunk[~residual_mask]
            q = (residual >> (8 - QUANT_BITS)).astype(np.int64)
            idx = (q[..., 0] << (2 * QUANT_BITS)) | (q[..., 1] << QUANT_BITS) | q[..., 2]
            hist += np.bincount(idx.ravel(), minlength=QUANT_BINS)
            lin = lut[chunk]                       # (rows, w, 3) float64, chunk-bounded
            lin_sum += lin.reshape(-1, 3).sum(axis=0)

    total = w * h
    if total == 0:
        raise ValueError("empty image")
    mean_lin = lin_sum / total

    # classification: exact palette pixels count EXACTLY to their colour;
    # only the residual goes through the quantised nearest-colour pass (so
    # near-identical palette colours cannot steal each other's pixels).
    # A matched shared colour is attributed to its representative role
    # (spec/roles.yaml declaration order) with the ambiguity reported below.
    classified = dict(exact)
    nearest = {hx: exact[hx] for hx in unique_hex}
    unclassified = 0
    occupied = np.nonzero(hist)[0]
    for bin_idx in occupied:
        count = int(hist[bin_idx])
        r8 = ((int(bin_idx) >> (2 * QUANT_BITS)) & 0x1F) << (8 - QUANT_BITS) | (1 << (8 - QUANT_BITS - 1))
        g8 = ((int(bin_idx) >> QUANT_BITS) & 0x1F) << (8 - QUANT_BITS) | (1 << (8 - QUANT_BITS - 1))
        b8 = (int(bin_idx) & 0x1F) << (8 - QUANT_BITS) | (1 << (8 - QUANT_BITS - 1))
        lab = _oklab_from_u8(r8, g8, b8)
        best_hex, best_d = None, float("inf")
        for hx in unique_hex:
            d = float(np.linalg.norm(lab - hex_oklab[hx]))
            if d < best_d:
                best_hex, best_d = hx, d
        if best_hex is not None and best_d <= threshold:
            nearest[best_hex] += count
            classified[best_hex] += count
        else:
            unclassified += count

    classified_total = sum(classified.values())
    by_category = {c: 0 for c in CATEGORIES}
    nearest_by_role = {r: 0 for r in roles}
    shared = {}
    for hx, px in nearest.items():
        first = _representative(hex_roles[hx], order)
        nearest_by_role[first] += px
        by_category[ROLE_CATEGORIES.get(first, "UI chrome")] += px
        if len(hex_roles[hx]) > 1:
            shared[hx] = hex_roles[hx]

    spectral = {}
    for name, factory in sorted(DISPLAYS.items()):
        photopic, melanopic = _linear_rgb_spectral(mean_lin, factory())
        spectral[name] = {
            "photopic": round(photopic, 6),
            "melanopic": round(melanopic, 6),
            "mel_ratio": round(melanopic / photopic, 6) if photopic > 1e-9 else 0.0,
        }

    return {
        "schema": SCHEMA,
        "image": {
            "path": str(png_path),
            "width": w,
            "height": h,
            "pixels": total,
            "chunk": {
                "rows": chunk_rows,
                "max_rows_seen": max_rows_seen,
                "max_bytes": max_rows_seen * w * 3,
            },
        },
        "palette": {
            "file": str(palette_path),
            "sha256": hashlib.sha256(Path(palette_path).read_bytes()).hexdigest(),
            "name": palette.name,
            "variant": palette.variant,
            "roles": len(roles),
        },
        "classification": {
            "threshold_de_ok": threshold,
            "quantization": (
                f"{QUANT_BITS} bits/channel (RGB555) bin centres for the residual "
                "(exact palette pixels are counted exactly); a shared colour "
                "is attributed to its representative role (earliest "
                "spec/roles.yaml declaration; see shared_colour_ambiguity)"
            ),
            "exact_fraction": round(sum(exact.values()) / total, 6),
            "exact_by_color": {
                hx: {"roles": hex_roles[hx], "pixels": exact[hx],
                     "fraction": round(exact[hx] / total, 6)}
                for hx in unique_hex
            },
            "classified_fraction": round(classified_total / total, 6),
            "unclassified_fraction": round(unclassified / total, 6),
            "nearest_by_role": {
                r: {"fraction": round(nearest_by_role[r] / total, 6)} for r in roles
            },
            "nearest_by_category": {
                c: {"fraction": round(v / total, 6)} for c, v in by_category.items()
            },
            "shared_colour_ambiguity": {
                hx: {"roles": role_list,
                     "fraction": round(nearest[hx] / total, 6)}
                for hx, role_list in sorted(shared.items())
            },
        },
        "spectral": {
            "method": (
                "area-weighted nominal photopic/melanopic relative to display "
                "white, computed exactly from mean linear RGB (SPD linear in "
                "linear RGB; one integration per display model, never per pixel)"
            ),
            "displays": spectral,
        },
        "caveats": CAVEATS,
    }


def write_report(report: dict, out_path: str | Path) -> Path:
    path = Path(out_path)
    path.write_text(json.dumps(report, indent=2, sort_keys=False) + "\n",
                    encoding="utf-8", newline="\n")
    return path
