"""Perceptual distance metrics.

Primary metric is Euclidean distance in OKLab (often written dE_OK).  For
palette work we also want *decomposed* distances, because "these two colours
differ by 0.08" is much less useful than knowing whether they differ in
lightness (survives CVD, survives greyscale, reads as hierarchy) or in hue
(does not survive CVD, reads as category).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .color import hex_to_oklch, oklch_to_oklab


def delta_e_ok(a_hex: str, b_hex: str) -> float:
    """Euclidean distance in OKLab.

    Rough calibration: ~0.02 is a just-noticeable step for large patches,
    ~0.05 is comfortably distinguishable side by side, and small text needs
    considerably more than that to be reliably told apart when the two colours
    are *not* adjacent -- which is the normal case in code.
    """
    la = oklch_to_oklab(hex_to_oklch(a_hex))
    lb = oklch_to_oklab(hex_to_oklch(b_hex))
    return math.dist(la, lb)


def delta_e_ok_scaled(a_hex: str, b_hex: str, l_weight: float = 2.0) -> float:
    """dE_OK with lightness up-weighted.

    Rationale (design judgement, not measurement): for small glyphs on a
    common background, a lightness difference is a far more robust cue than a
    chroma difference of the same OKLab magnitude, because it survives colour
    vision deficiency, low display gamut, and peripheral vision.  Default
    weight 2.0 is a tunable knob, not a published constant.
    """
    la = oklch_to_oklab(hex_to_oklch(a_hex))
    lb = oklch_to_oklab(hex_to_oklch(b_hex))
    dl = (la[0] - lb[0]) * l_weight
    da = la[1] - lb[1]
    db = la[2] - lb[2]
    return math.sqrt(dl * dl + da * da + db * db)


@dataclass(frozen=True)
class DistanceBreakdown:
    total: float
    d_lightness: float
    d_chroma: float
    d_hue: float  # arc length at mean chroma, comparable to the others

    def dominant_channel(self) -> str:
        return max(
            (("lightness", self.d_lightness), ("chroma", self.d_chroma), ("hue", self.d_hue)),
            key=lambda kv: kv[1],
        )[0]


def breakdown(a_hex: str, b_hex: str) -> DistanceBreakdown:
    la, ca, ha = hex_to_oklch(a_hex)
    lb, cb, hb = hex_to_oklch(b_hex)
    dh_deg = abs(((ha - hb + 180.0) % 360.0) - 180.0)
    c_mean = (ca + cb) / 2.0
    return DistanceBreakdown(
        total=delta_e_ok(a_hex, b_hex),
        d_lightness=abs(la - lb),
        d_chroma=abs(ca - cb),
        d_hue=math.radians(dh_deg) * c_mean,
    )


def hue_delta(a_hex: str, b_hex: str) -> float:
    """Absolute hue difference in degrees, 0..180."""
    ha = hex_to_oklch(a_hex)[2]
    hb = hex_to_oklch(b_hex)[2]
    return abs(((ha - hb + 180.0) % 360.0) - 180.0)
