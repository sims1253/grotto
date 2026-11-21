"""Core colour-space conversions.

Canonical representation for the project is OKLCH (polar OKLab).  Everything
here is implemented from published matrices rather than pulled from a library
so the numbers are auditable; `tests/test_color.py` cross-validates against
`coloraide`.

Conventions
-----------
* `srgb`  : tuple of 3 floats in [0, 1], *gamma-encoded* (i.e. what a hex
            literal means).
* `linear`: tuple of 3 floats, linear-light sRGB primaries, may exceed [0, 1].
* `xyz`   : CIE XYZ, D65, Y in [0, 1] for in-gamut colours.
* `oklab` : (L, a, b), L in [0, 1].
* `oklch` : (L, C, h) with h in degrees [0, 360).

Note on OKLab: it is *not* perfectly hue-linear.  Published analyses show
residual curvature in the blue/purple-blue sector, so hue-rotation operations
in that region should be treated as approximate.  See RESEARCH.md R-8.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# --------------------------------------------------------------------------
# sRGB transfer function (IEC 61966-2-1)
# --------------------------------------------------------------------------


def srgb_to_linear(c: float) -> float:
    """Decode one gamma-encoded sRGB channel to linear light."""
    if c <= 0.04045:
        return c / 12.92
    return ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    """Encode one linear-light channel as gamma-encoded sRGB."""
    if c <= 0.0031308:
        return c * 12.92
    return 1.055 * (abs(c) ** (1 / 2.4)) * (1 if c >= 0 else -1) - 0.055


# --------------------------------------------------------------------------
# Matrices
# --------------------------------------------------------------------------

# linear sRGB -> XYZ (D65), sRGB spec primaries
M_SRGB_TO_XYZ = np.array(
    [
        [0.41239079926595934, 0.357584339383878, 0.1804807884018343],
        [0.21263900587151027, 0.715168678767756, 0.07219231536073371],
        [0.01933081871559182, 0.11919477979462598, 0.9505321522496607],
    ]
)
M_XYZ_TO_SRGB = np.linalg.inv(M_SRGB_TO_XYZ)

# linear Display P3 -> XYZ (D65)
M_P3_TO_XYZ = np.array(
    [
        [0.4865709486482162, 0.26566769316909306, 0.1982172852343625],
        [0.2289745640697488, 0.6917385218365064, 0.079286914093745],
        [0.0000000000000000, 0.04511338185890264, 1.043944368900976],
    ]
)
M_XYZ_TO_P3 = np.linalg.inv(M_P3_TO_XYZ)

# OKLab (Ottosson 2020): XYZ(D65) -> LMS'
M_XYZ_TO_LMS = np.array(
    [
        [0.8190224379967030, 0.3619062600528904, -0.1288737815209879],
        [0.0329836539323885, 0.9292868615863434, 0.0361446663506424],
        [0.0481771893596242, 0.2642395317527308, 0.6335478284694309],
    ]
)
M_LMS_TO_XYZ = np.linalg.inv(M_XYZ_TO_LMS)

# nonlinear LMS -> OKLab
M_LMS_TO_LAB = np.array(
    [
        [0.2104542683093140, 0.7936177747023054, -0.0040720430116193],
        [1.9779985324311684, -2.4285922420485799, 0.4505937096174110],
        [0.0259040424655478, 0.7827717124575296, -0.8086757549230774],
    ]
)
M_LAB_TO_LMS = np.linalg.inv(M_LMS_TO_LAB)


# --------------------------------------------------------------------------
# Conversions
# --------------------------------------------------------------------------


def hex_to_srgb(s: str) -> tuple[float, float, float]:
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        raise ValueError(f"not a 6-digit hex colour: {s!r}")
    return tuple(int(s[i : i + 2], 16) / 255.0 for i in (0, 2, 4))  # type: ignore[return-value]


def srgb_to_hex(rgb: tuple[float, float, float], clip: bool = True) -> str:
    """Quantise to 8-bit hex.  Raises if out of gamut and ``clip`` is False."""
    out = []
    for c in rgb:
        if not clip and not (-1e-6 <= c <= 1 + 1e-6):
            raise ValueError(f"channel {c} out of sRGB range; refusing to clip")
        out.append(round(min(1.0, max(0.0, c)) * 255))
    return "#{:02x}{:02x}{:02x}".format(*out)


def srgb_to_xyz(rgb: tuple[float, float, float]) -> np.ndarray:
    lin = np.array([srgb_to_linear(c) for c in rgb])
    return M_SRGB_TO_XYZ @ lin


def xyz_to_srgb(xyz) -> tuple[float, float, float]:
    lin = M_XYZ_TO_SRGB @ np.asarray(xyz)
    return tuple(linear_to_srgb(c) for c in lin)  # type: ignore[return-value]


def xyz_to_p3(xyz) -> tuple[float, float, float]:
    lin = M_XYZ_TO_P3 @ np.asarray(xyz)
    return tuple(linear_to_srgb(c) for c in lin)  # type: ignore[return-value]


def xyz_to_oklab(xyz) -> tuple[float, float, float]:
    lms = M_XYZ_TO_LMS @ np.asarray(xyz)
    lms_ = np.cbrt(lms)
    lab = M_LMS_TO_LAB @ lms_
    return (float(lab[0]), float(lab[1]), float(lab[2]))


def oklab_to_xyz(lab) -> np.ndarray:
    lms_ = M_LAB_TO_LMS @ np.asarray(lab)
    lms = lms_**3
    return M_LMS_TO_XYZ @ lms


def oklab_to_oklch(lab) -> tuple[float, float, float]:
    L, a, b = (float(lab[0]), float(lab[1]), float(lab[2]))
    C = math.hypot(a, b)
    h = math.degrees(math.atan2(b, a)) % 360.0
    if C < 1e-9:  # achromatic: hue is meaningless, pin to 0
        h = 0.0
    return (L, C, h)


def oklch_to_oklab(lch) -> tuple[float, float, float]:
    L, C, h = lch
    r = math.radians(h)
    return (L, C * math.cos(r), C * math.sin(r))


# convenience round-trips ---------------------------------------------------


def hex_to_oklch(s: str) -> tuple[float, float, float]:
    return oklab_to_oklch(xyz_to_oklab(srgb_to_xyz(hex_to_srgb(s))))


def oklch_to_srgb(lch) -> tuple[float, float, float]:
    return xyz_to_srgb(oklab_to_xyz(oklch_to_oklab(lch)))


def oklch_to_hex(lch, clip: bool = True) -> str:
    return srgb_to_hex(oklch_to_srgb(lch), clip=clip)


def relative_luminance(rgb: tuple[float, float, float]) -> float:
    """WCAG 2.x relative luminance (== CIE Y for sRGB)."""
    r, g, b = (srgb_to_linear(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# --------------------------------------------------------------------------
# Gamut
# --------------------------------------------------------------------------

EPS = 1e-4  # tolerance for 8-bit-quantisable rounding slack


@dataclass(frozen=True)
class GamutStatus:
    in_srgb: bool
    in_p3: bool
    srgb_excursion: float  # max distance outside [0,1] in sRGB channels
    p3_excursion: float


def gamut_status(lch) -> GamutStatus:
    xyz = oklab_to_xyz(oklch_to_oklab(lch))
    s = xyz_to_srgb(xyz)
    p = xyz_to_p3(xyz)

    def excursion(rgb):
        return max(max(0.0, -c, c - 1.0) for c in rgb)

    es, ep = float(excursion(s)), float(excursion(p))
    return GamutStatus(bool(es <= EPS), bool(ep <= EPS), es, ep)


def in_srgb(lch) -> bool:
    return gamut_status(lch).in_srgb


def max_chroma(L: float, h: float, gamut: str = "srgb", tol: float = 1e-5) -> float:
    """Largest chroma at (L, h) that stays inside `gamut`, by bisection.

    The sRGB solid is star-shaped in C at fixed (L, h), so bisection is exact
    up to `tol`.
    """
    check = in_srgb if gamut == "srgb" else (lambda lch: gamut_status(lch).in_p3)
    if not check((L, 0.0, h)):
        return 0.0  # L itself is out of range
    lo, hi = 0.0, 0.5
    if check((L, hi, h)):
        return hi
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if check((L, mid, h)):
            lo = mid
        else:
            hi = mid
    return lo


def gamut_map(lch, gamut: str = "srgb") -> tuple[tuple[float, float, float], float]:
    """Reduce chroma until in gamut, preserving L and h.

    Returns (mapped_lch, chroma_lost).  This is the CSS Color 4 style
    "hold lightness and hue, clip chroma" approach.  We *report* the loss
    rather than silently swallowing it -- a large loss means the palette
    is asking for a colour the display cannot make, which is a design bug,
    not a rounding detail.
    """
    L, C, h = lch
    if gamut_status(lch).in_srgb if gamut == "srgb" else gamut_status(lch).in_p3:
        return (L, C, h), 0.0
    cmax = max_chroma(L, h, gamut)
    return (L, cmax, h), C - cmax
