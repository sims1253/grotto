"""Contrast metrics: WCAG 2.x, APCA (SAPC-98G-4g), and plain OKLab lightness gap.

We deliberately report all three.  They disagree, and *where* they disagree is
informative -- see DESIGN.md section on contrast.
"""

from __future__ import annotations

from dataclasses import dataclass

from .color import hex_to_oklch, hex_to_srgb, relative_luminance, srgb_to_linear

# --------------------------------------------------------------------------
# WCAG 2.x
# --------------------------------------------------------------------------


def wcag_contrast(fg_hex: str, bg_hex: str) -> float:
    """WCAG 2.x contrast ratio, 1.0 .. 21.0."""
    lf = relative_luminance(hex_to_srgb(fg_hex))
    lb = relative_luminance(hex_to_srgb(bg_hex))
    hi, lo = max(lf, lb), min(lf, lb)
    return (hi + 0.05) / (lo + 0.05)


# --------------------------------------------------------------------------
# APCA -- constants from the 0.1.9 / W3C "4g" release.
# --------------------------------------------------------------------------

_S_TRC = 2.4
_R_CO, _G_CO, _B_CO = 0.2126729, 0.7151522, 0.0721750

_N_BG, _N_TX = 0.56, 0.57  # normal polarity (dark text on light)
_R_BG, _R_TX = 0.65, 0.62  # reverse polarity (light text on dark)

_SCALE_BOW, _SCALE_WOB = 1.14, 1.14
_LO_CLIP, _LO_OFFSET = 0.1, 0.027
_BLK_THRS, _BLK_CLMP = 0.022, 1.414
_DELTA_Y_MIN = 0.0005


def _apca_y(hex_color: str) -> float:
    r, g, b = hex_to_srgb(hex_color)
    y = _R_CO * r**_S_TRC + _G_CO * g**_S_TRC + _B_CO * b**_S_TRC
    # soft black clamp
    return y if y >= _BLK_THRS else y + (_BLK_THRS - y) ** _BLK_CLMP


def apca_lc(fg_hex: str, bg_hex: str) -> float:
    """APCA lightness contrast Lc.

    Positive => dark text on light background.
    Negative => light text on dark background.
    Magnitude is roughly comparable across polarities, which is the whole
    point: WCAG 2 is polarity-blind and systematically mis-ranks dark themes.

    APCA is independent work in progress, not a W3C Recommendation or a
    current WCAG success criterion. We use it as an experimental *design*
    signal and keep WCAG 2 for the compliance claim.
    """
    ytx, ybg = _apca_y(fg_hex), _apca_y(bg_hex)
    if abs(ybg - ytx) < _DELTA_Y_MIN:
        return 0.0
    if ybg > ytx:  # normal polarity: dark text, light bg
        s = (ybg**_N_BG - ytx**_N_TX) * _SCALE_BOW
        out = 0.0 if s < _LO_CLIP else s - _LO_OFFSET
    else:  # reverse polarity
        s = (ybg**_R_BG - ytx**_R_TX) * _SCALE_WOB
        out = 0.0 if s > -_LO_CLIP else s + _LO_OFFSET
    return out * 100.0


def apca_min_lc(font_px: float, weight: int = 400) -> float:
    """Coarse APCA readability floor for a given size/weight.

    Simplified from the APCA author's experimental font lookup table. These are
    not W3C accessibility requirements or validated comfort thresholds.
    """
    if font_px >= 24 or weight >= 700:
        return 60.0
    if font_px >= 18:
        return 65.0
    if font_px >= 16:
        return 70.0
    return 75.0


# --------------------------------------------------------------------------
# Lightness gap
# --------------------------------------------------------------------------


def oklab_l_delta(fg_hex: str, bg_hex: str) -> float:
    """Signed OKLab L difference (fg - bg).  Cheap, polarity-aware, no model
    of spatial frequency.  Useful for ordering, not for compliance."""
    return hex_to_oklch(fg_hex)[0] - hex_to_oklch(bg_hex)[0]


@dataclass(frozen=True)
class ContrastReport:
    fg: str
    bg: str
    wcag: float
    apca: float
    dl: float

    @property
    def wcag_aa_body(self) -> bool:
        return self.wcag >= 4.5

    @property
    def wcag_aa_large(self) -> bool:
        return self.wcag >= 3.0

    def apca_ok(self, font_px: float = 14, weight: int = 400) -> bool:
        return abs(self.apca) >= apca_min_lc(font_px, weight)


def contrast_report(fg_hex: str, bg_hex: str) -> ContrastReport:
    return ContrastReport(
        fg=fg_hex,
        bg=bg_hex,
        wcag=wcag_contrast(fg_hex, bg_hex),
        apca=apca_lc(fg_hex, bg_hex),
        dl=oklab_l_delta(fg_hex, bg_hex),
    )
