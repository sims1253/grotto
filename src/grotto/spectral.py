"""Exploratory melanopic ("short-wavelength") analysis for sRGB palettes.

READ THIS BEFORE USING ANY NUMBER FROM THIS MODULE
--------------------------------------------------
An sRGB triple does **not** determine a spectral power distribution.  Two
displays showing the identical hex value emit measurably different spectra:
a blue-pump white-LED LCD, a quantum-dot LCD and an OLED have different
primary SPDs, and their melanopic content at the same nominal colour differs
substantially.  Nothing in this module measures light entering anyone's eye.

What this module *is*: a nominal display model that lets us rank *candidate
palettes against each other* under a stated, fixed assumption.  The claim it
supports is of the form

    "Under the LED-LCD nominal model, palette A emits ~18% less
     melanopic-weighted radiance than palette B at equal photopic
     luminance and equal screen coverage."

The claim it does **not** support is "palette A is better for your sleep."
Circadian outcome depends on absolute corneal illuminance, exposure duration,
prior light history, timing relative to a person's own circadian phase, and
large individual differences -- none of which a palette knows.  See
RESEARCH.md R-4 and R-5.

Model structure
---------------
1. Display primaries are modelled as Gaussian emitters (two archetypes).
2. Colour -> SPD: linearise sRGB, weight the primaries, sum.
3. Action spectra: CIE 1931 V(lambda) via the Wyman/Sloan/Shirley (2013)
   multi-lobe fit; melanopsin via the Govardovskii (2000) A1 template at
   lambda_max = 480 nm, attenuated by an approximate ocular-media transmittance.
4. Everything is reported *relative to full display white*, so the arbitrary
   absolute normalisation cancels.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .color import hex_to_srgb, srgb_to_linear

LAMBDA = np.arange(380.0, 781.0, 1.0)


# --------------------------------------------------------------------------
# Action spectra
# --------------------------------------------------------------------------


def _piecewise_gauss(x, mu, s1, s2):
    s = np.where(x < mu, s1, s2)
    return np.exp(-0.5 * ((x - mu) / s) ** 2)


def v_lambda() -> np.ndarray:
    """Photopic luminous efficiency V(lambda), CIE 1931.

    Multi-lobe Gaussian fit from Wyman, Sloan & Shirley, "Simple Analytic
    Approximations to the CIE XYZ Color Matching Functions", JCGT 2(2), 2013.
    Accurate to about 1% of peak, which is far below the uncertainty
    introduced by the display model itself.
    """
    return 0.821 * _piecewise_gauss(LAMBDA, 568.8, 46.9, 40.5) + 0.286 * _piecewise_gauss(
        LAMBDA, 530.9, 16.3, 31.1
    )


def _govardovskii_a1(lmax: float) -> np.ndarray:
    """Govardovskii et al. (2000) A1 visual-pigment template, alpha + beta band."""
    x = lmax / LAMBDA
    a = 0.8795 + 0.0459 * math.exp(-((lmax - 300.0) ** 2) / 11940.0)
    alpha = 1.0 / (
        np.exp(69.7 * (a - x)) + np.exp(28.0 * (0.922 - x)) + np.exp(-14.9 * (1.104 - x)) + 0.674
    )
    lmb = 189.0 + 0.315 * lmax
    b = -40.5 + 0.195 * lmax
    beta = 0.26 * np.exp(-(((LAMBDA - lmb) / b) ** 2))
    return alpha + beta


def _ocular_media_transmittance() -> np.ndarray:
    """Approximate transmittance of the crystalline lens + macular-free path.

    A smooth short-wavelength roll-off standing in for the CIE standard
    32-year-old observer's ocular media.  This is a shape approximation, not
    the tabulated CIE S 026 function; it matters mostly below ~440 nm where
    display emission is already small.
    """
    return np.clip(1.0 / (1.0 + np.exp(-(LAMBDA - 400.0) / 14.0)), 0.0, 1.0)


def s_mel() -> np.ndarray:
    """Melanopic action spectrum, normalised to unit peak.

    Approximates the CIE S 026 melanopic function (peak near 490 nm at the
    cornea) as melanopsin (lambda_max 480 nm) behind ocular media.
    """
    s = _govardovskii_a1(480.0) * _ocular_media_transmittance()
    return s / s.max()


# --------------------------------------------------------------------------
# Display models
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class DisplayModel:
    """A nominal display: three primary SPDs, unit-normalised in shape."""

    name: str
    r: np.ndarray
    g: np.ndarray
    b: np.ndarray
    note: str

    def spd(self, hex_color: str) -> np.ndarray:
        """SPD of a gamma-encoded sRGB colour on this display."""
        lin = [srgb_to_linear(c) for c in hex_to_srgb(hex_color)]
        return lin[0] * self.r + lin[1] * self.g + lin[2] * self.b


def _gauss(mu, sigma):
    return np.exp(-0.5 * ((LAMBDA - mu) / sigma) ** 2)


def _balanced(r, g, b) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Scale primaries so their photopic luminances hit the sRGB ratios.

    This forces the model's full white to be photopically consistent with
    sRGB's luminance coefficients, which is the property we actually rely on
    when comparing palettes at matched luminance.
    """
    v = v_lambda()
    out = []
    for prim, target in zip((r, g, b), (0.2126, 0.7152, 0.0722)):
        y = float(np.trapezoid(prim * v, LAMBDA))
        out.append(prim * (target / y))
    return tuple(out)  # type: ignore[return-value]


def led_lcd() -> DisplayModel:
    """Blue-pump white LED behind colour filters -- the common laptop/monitor.

    Characterised here by a tall narrow ~450 nm blue spike that the blue
    subpixel passes almost unattenuated. This is a synthetic scenario, not a
    measured or bounding model of real LED-LCD hardware.
    """
    r, g, b = _balanced(
        _gauss(612, 26) + 0.18 * _gauss(578, 30),
        _gauss(535, 38),
        _gauss(450, 14) + 0.06 * _gauss(490, 25),
    )
    return DisplayModel("led-lcd", r, g, b, "blue-pump white LED + RGB colour filters")


def oled() -> DisplayModel:
    """Emissive RGB OLED: narrower primaries, blue peak nearer 460 nm."""
    r, g, b = _balanced(_gauss(624, 20), _gauss(530, 28), _gauss(460, 18))
    return DisplayModel("oled", r, g, b, "emissive RGB OLED, narrow primaries")


DISPLAYS = {"led-lcd": led_lcd, "oled": oled}


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class MelanopicResult:
    photopic: float  # relative to display white = 1.0
    melanopic: float  # relative to display white = 1.0
    mel_ratio: float  # melanopic / photopic, i.e. melanopic DER-like ratio

    def __repr__(self) -> str:
        return (
            f"MelanopicResult(photopic={self.photopic:.4f}, "
            f"melanopic={self.melanopic:.4f}, mel_ratio={self.mel_ratio:.3f})"
        )


def melanopic(hex_color: str, display: DisplayModel | None = None) -> MelanopicResult:
    """Photopic and melanopic output of one colour, relative to display white.

    `mel_ratio` is analogous to the melanopic daylight efficacy ratio: it is
    1.0 for the display's own white and rises for bluer colours, falls for
    warmer ones.  It is a *per-unit-luminance* quantity, so it says nothing
    about how much light is actually emitted -- for that use `melanopic`, or
    better, the area-weighted aggregate below.
    """
    d = display or led_lcd()
    v, m = v_lambda(), s_mel()
    spd = d.spd(hex_color)
    white = d.r + d.g + d.b

    p = float(np.trapezoid(spd * v, LAMBDA))
    q = float(np.trapezoid(spd * m, LAMBDA))
    pw = float(np.trapezoid(white * v, LAMBDA))
    qw = float(np.trapezoid(white * m, LAMBDA))

    photopic = p / pw
    melanopic_rel = q / qw
    ratio = (melanopic_rel / photopic) if photopic > 1e-9 else 0.0
    return MelanopicResult(photopic, melanopic_rel, ratio)


@dataclass(frozen=True)
class ScreenSpectralResult:
    """Aggregate over a coverage-weighted screen composition."""

    photopic: float
    melanopic: float
    mel_ratio: float
    display: str
    contributions: dict[str, float]  # per-colour share of total melanopic output

    def top_contributors(self, n: int = 5) -> list[tuple[str, float]]:
        return sorted(self.contributions.items(), key=lambda kv: -kv[1])[:n]


def screen_melanopic(
    coverage: dict[str, float], display: DisplayModel | None = None
) -> ScreenSpectralResult:
    """Area-weighted melanopic output for a whole screen composition.

    `coverage` maps hex colour -> fraction of visible pixels. Area weighting is
    necessary, but emitted contribution also depends on linear channel drive
    and the assumed primary spectra: neither an 85% dark background nor a 1%
    bright cyan accent can be dismissed from area alone. Treating palette
    swatches as equally prevalent is also invalid.
    """
    d = display or led_lcd()
    total = sum(coverage.values())
    if not math.isclose(total, 1.0, abs_tol=0.02):
        raise ValueError(f"coverage should sum to ~1.0, got {total:.3f}")

    v, m = v_lambda(), s_mel()
    white = d.r + d.g + d.b
    pw = float(np.trapezoid(white * v, LAMBDA))
    qw = float(np.trapezoid(white * m, LAMBDA))

    p_tot = q_tot = 0.0
    contrib: dict[str, float] = {}
    for hx, frac in coverage.items():
        spd = d.spd(hx) * frac
        p_tot += float(np.trapezoid(spd * v, LAMBDA)) / pw
        q = float(np.trapezoid(spd * m, LAMBDA)) / qw
        q_tot += q
        contrib[hx] = q

    contrib = {k: (val / q_tot if q_tot else 0.0) for k, val in contrib.items()}
    ratio = (q_tot / p_tot) if p_tot > 1e-9 else 0.0
    return ScreenSpectralResult(p_tot, q_tot, ratio, d.name, contrib)
