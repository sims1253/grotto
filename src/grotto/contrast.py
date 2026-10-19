"""Contrast metrics: WCAG 2.x, APCA (SAPC-98G-4g), and plain OKLab lightness gap.

We deliberately report all three.  They disagree, and *where* they disagree is
informative -- see DESIGN.md section on contrast.
"""

from __future__ import annotations

from dataclasses import dataclass

from .color import (
    gamut_map,
    hex_to_oklch,
    hex_to_srgb,
    oklch_to_hex,
    relative_luminance,
    srgb_to_linear,
)

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


# --------------------------------------------------------------------------
# Inverse contrast: given a background and a target, solve for the foreground
# --------------------------------------------------------------------------
#
# Everything above this line answers "how different are these two colours?".
# That is the wrong direction for *authoring*.  A theme is written as a list of
# requirements -- "body text on the canvas, 4.5:1", "muted text on the active
# line, still 4.5:1" -- and then colours are chosen to satisfy them.  Reading
# contrast forwards forces the search to propose colours and be told they were
# wrong; solving backwards lets a requirement *place* a colour.  Pi's system
# theme is built exactly this way (Earendil, "There are many themes, but this
# one is yours", 2026-10-09): lightness comes from the contrast rules, hue from
# the source palette.
#
# The reachability result matters as much as the solution.  A target can be
# unsatisfiable on a given background -- too much contrast for the gamut on one
# side, not enough on the other -- and knowing that *before* searching is the
# difference between a bounded search and an unbounded one.

_MODELS = ("wcag", "apca", "dl")


@dataclass(frozen=True)
class SolveResult:
    """A foreground lightness that meets a contrast target on a background."""

    lightness: float
    hex: str
    bg: str
    model: str
    target: float
    achieved: float
    reachable: bool
    in_gamut: bool
    chroma_lost: float

    def __str__(self) -> str:
        if not self.reachable:
            return f"unreachable: {self.model} target {self.target:.2f} on {self.bg}"
        return (
            f"L={self.lightness:.4f} {self.hex} on {self.bg} "
            f"({self.model} {self.achieved:.2f} vs target {self.target:.2f})"
        )


def solve_wcag_luminance(bg_hex: str, target: float,
                         prefer: str = "auto") -> float | None:
    """Analytic WCAG inverse: the relative luminance a foreground needs.

    Returns ``None`` when no foreground luminance can reach ``target`` on this
    background.  Cheap and exact -- WCAG is a closed form in luminance, so this
    is the right tool for asking whether a requirement is satisfiable at all
    before spending a search on it.
    """
    yb = relative_luminance(hex_to_srgb(bg_hex))
    sides = ("lighter", "darker") if prefer == "auto" else (prefer,)
    for side in sides:
        if side == "lighter":
            y = target * (yb + 0.05) - 0.05
        else:
            y = (yb + 0.05) / target - 0.05
        if 0.0 <= y <= 1.0:
            return y
    return None


def _model_contrast(model: str, fg_lch, bg_hex: str) -> float:
    fg = oklch_to_hex(fg_lch)
    if model == "wcag":
        return wcag_contrast(fg, bg_hex)
    if model == "apca":
        return abs(apca_lc(fg, bg_hex))
    if model == "dl":
        return abs(oklab_l_delta(fg, bg_hex))
    raise ValueError(f"unknown contrast model {model!r}, expected one of {_MODELS}")


def solve_lightness(
    bg_hex: str,
    target: float,
    *,
    chroma: float = 0.0,
    hue: float = 0.0,
    model: str = "wcag",
    prefer: str = "auto",
    tol: float = 1e-5,
    max_iter: int = 60,
) -> SolveResult:
    """Solve for the OKLab L a foreground needs to hit ``target`` on ``bg``.

    Hue and chroma are held and only lightness is solved, which is the
    constraint the rest of the repository already works under: DESIGN.md
    treats lightness as the axis contrast owns and chroma as the axis salience
    owns, and the fences exist to stop either from being spent twice.

    Contrast rises monotonically as the foreground moves away from the
    background's lightness, so a bisection is exact rather than iterative-in-
    spirit.  Chroma is gamut-mapped at every probe: holding a chroma that
    cannot be displayed would make the curve non-monotonic and the answer a
    function of the probe path.

    ``reachable`` is False when even the far end of the axis misses the
    target.  That is a real answer, not a failure to converge.
    """
    if model not in _MODELS:
        raise ValueError(f"unknown contrast model {model!r}, expected one of {_MODELS}")

    l_bg = hex_to_oklch(bg_hex)[0]
    side = prefer
    if side == "auto":
        side = "lighter" if l_bg < 0.5 else "darker"
    lo, hi = (l_bg, 1.0) if side == "lighter" else (0.0, l_bg)

    def probe(L: float) -> tuple[float, float]:
        """Contrast and chroma lost at lightness ``L``."""
        lch, lost = gamut_map((L, chroma, hue), "srgb")
        return _model_contrast(model, lch, bg_hex), lost

    # The far end of the axis we are allowed to move along.  Getting this wrong
    # makes a reachable target look unreachable: on a light canvas, "darker"
    # runs from l_bg down to 0, so the far end is `lo`, not `hi`.
    far_L = hi if side == "lighter" else lo
    far, far_lost = probe(far_L)
    if far < target:
        return SolveResult(far_L, oklch_to_hex((far_L, chroma, hue)), bg_hex,
                           model, target, far, False, far_lost == 0.0, far_lost)

    # The bracket invariant is: `a` MISSES the target, `b` MEETS it.  Going
    # lighter that is (lo, hi) -- the background is too close, white is far.
    # Going darker it is (hi, lo), because there the background is the FAILING
    # end and black is the meeting one.  Seeding it the other way round still
    # terminates and still returns reachable=True, but hands back a colour that
    # does not meet the target.
    a, b = (lo, hi) if side == "lighter" else (hi, lo)
    for _ in range(max_iter):
        if abs(b - a) < tol:
            break
        mid = (a + b) / 2
        if probe(mid)[0] < target:
            a = mid          # mid is on the missing side; narrow towards b
        else:
            b = mid          # mid already meets it; narrow towards a
    L = (a + b) / 2
    achieved, lost = probe(L)
    lch, _ = gamut_map((L, chroma, hue), "srgb")
    return SolveResult(L, oklch_to_hex(lch), bg_hex, model, target, achieved,
                       True, lost == 0.0, lost)

