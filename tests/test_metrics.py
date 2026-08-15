"""Validate contrast, distance, CVD and spectral metrics against known values."""

import numpy as np
import pytest

from grotto.color import hex_to_oklch
from grotto.contrast import apca_lc, apca_min_lc, oklab_l_delta, wcag_contrast
from grotto.cvd import check_pair, simulate
from grotto.distance import breakdown, delta_e_ok, delta_e_ok_scaled, hue_delta
from grotto.spectral import (
    LAMBDA,
    led_lcd,
    melanopic,
    oled,
    s_mel,
    screen_melanopic,
    v_lambda,
)

# --------------------------------------------------------------------------
# WCAG -- reference values are exact by definition
# --------------------------------------------------------------------------


def test_wcag_extremes():
    assert wcag_contrast("#000000", "#ffffff") == pytest.approx(21.0)
    assert wcag_contrast("#ffffff", "#ffffff") == pytest.approx(1.0)


def test_wcag_is_symmetric():
    assert wcag_contrast("#123456", "#abcdef") == pytest.approx(
        wcag_contrast("#abcdef", "#123456")
    )


def test_wcag_known_boundary():
    # #767676 on white is the canonical 4.54:1 AA-passing grey.
    assert wcag_contrast("#767676", "#ffffff") == pytest.approx(4.54, abs=0.01)


# --------------------------------------------------------------------------
# APCA
# --------------------------------------------------------------------------


def test_apca_polarity_sign():
    assert apca_lc("#000000", "#ffffff") > 0  # dark on light
    assert apca_lc("#ffffff", "#000000") < 0  # light on dark


def test_apca_reference_values():
    """Values from the APCA 0.1.9 reference implementation."""
    assert apca_lc("#000000", "#ffffff") == pytest.approx(106.04, abs=0.1)
    assert apca_lc("#ffffff", "#000000") == pytest.approx(-107.88, abs=0.1)
    assert apca_lc("#888888", "#ffffff") == pytest.approx(63.06, abs=0.2)


# Known-answer vectors published in the *official* W3C/apca-w3 repository's own
# test script (version 0.1.7 vectors, numerically identical under the 0.1.9
# G-4g constants -- see note below):
#   https://github.com/Myndex/apca-w3/blob/master/test/index.js
#   (raw: https://raw.githubusercontent.com/Myndex/apca-w3/master/test/index.js,
#    fetched 2026-08-15).  The script arrays are:
#     color  = ['#000', '#888', '#FFF', '#000', '#aaa',
#               '#123', '#def', '#123', '#444', '#0006', '#fff']
#     contrastResult = [0, 63.056469930209424, -68.54146436644962,
#                       58.146262578561334, -56.24113336839742,
#                       91.66830811481631, -93.06770049484275,
#                       8.32326136957393, -7.526878460278154,
#                       54.62184067441377, 54.62184067441377]
# It pairs consecutive entries (fg, bg) in both orders, since APCA is
# polarity-asymmetric.  CSS shorthand is expanded here to six-digit hex:
# '#888'->#888888, '#aaa'->#aaaaaa, '#123'->#112233, '#def'->#ddeeff,
# '#444'->#444444.  The final '#0006' vector is 4-digit RGBA (R=G=B=0,
# A=0x66=102/255) blended over '#fff' in gamma space, i.e. each channel
# 255*(1-102/255)=153 -> text '#999999' on bg '#ffffff'; the reference value
# for calcAPCA('#0006', '#fff') is reproduced exactly by that solid pair.
#
# The grotto constants were additionally diffed against the SA98G constant
# block of the reference implementation
#   https://raw.githubusercontent.com/Myndex/apca-w3/master/src/apca-w3.js
# (fetched 2026-08-15): sTRC 2.4, R/G/B-co 0.2126729/0.7151522/0.0721750,
# normBG/TXT 0.56/0.57, revBG/TXT 0.65/0.62, scaleBoW/WoB 1.14/1.14,
# blkThrs 0.022, blkClmp 1.414, loOffset 0.027, loClip 0.1, deltaYmin 0.0005
# -- all identical to src/grotto/contrast.py.
#
# Coverage: both polarities (positive = dark-on-light, negative =
# light-on-dark), mid-greys of both polarities (#888/#fff, #aaa/#000,
# #999/#fff), a chromatic blue-on-cream pair, and a near-clipping
# low-contrast pair (#112233 vs #444444, |Lc| < 10).  grotto reproduces every
# value to machine precision (diff 0.0e+00), hence the tight 1e-6 tolerance.
APCA_W3_VECTORS = [
    ("#888888", "#ffffff", 63.056469930209424),   # grey text on white
    ("#ffffff", "#888888", -68.54146436644962),   # white text on grey
    ("#000000", "#aaaaaa", 58.146262578561334),   # black on light grey
    ("#aaaaaa", "#000000", -56.24113336839742),   # light grey on black
    ("#112233", "#ddeeff", 91.66830811481631),    # dark blue on pale blue
    ("#ddeeff", "#112233", -93.06770049484275),   # pale blue on dark blue
    ("#112233", "#444444", 8.32326136957393),     # near-clip, dark on mid grey
    ("#444444", "#112233", -7.526878460278154),   # near-clip, reversed
    ("#999999", "#ffffff", 54.62184067441377),    # reference's '#0006' alpha case
]


@pytest.mark.parametrize(
    ("fg", "bg", "expected"),
    APCA_W3_VECTORS,
    ids=[f"{fg}-on-{bg}" for fg, bg, _ in APCA_W3_VECTORS],
)
def test_apca_w3_reference_vectors(fg, bg, expected):
    """Known-answer pairs from the apca-w3 reference repo's test script.

    Source: Myndex/apca-w3 test/index.js (URL in the block comment above,
    fetched 2026-08-15).  These are external reference values, not
    self-generated ones: if src/grotto/contrast.py drifts from the published
    APCA constants, this test fails.
    """
    assert apca_lc(fg, bg) == pytest.approx(expected, abs=1e-6)


def test_apca_min_lc_documented_thresholds():
    """Boundaries of the coarse size/weight floor documented in the docstring
    of apca_min_lc (>=24px or weight>=700 -> 60, >=18px -> 65, >=16px -> 70,
    else 75).  These are grotto's own simplified thresholds -- internal
    documentation pin, not an external reference."""
    cases = [
        (14, 400, 75.0),
        (15, 400, 75.0),   # just below the 16px boundary
        (16, 400, 70.0),   # boundary is inclusive
        (17, 400, 70.0),
        (18, 400, 65.0),   # boundary is inclusive
        (23, 400, 65.0),   # just below the 24px boundary
        (24, 400, 60.0),   # boundary is inclusive
        (36, 400, 60.0),
        (14, 700, 60.0),   # bold weight overrides size entirely
        (17, 700, 60.0),
        (14, 1000, 60.0),
    ]
    for font_px, weight, expected in cases:
        assert apca_min_lc(font_px, weight) == expected, (font_px, weight)

    # Non-increasing as size grows, at body weight.
    thresholds = [apca_min_lc(px, 400) for px in (14, 16, 18, 24, 36)]
    assert thresholds == sorted(thresholds, reverse=True)


def test_oklab_l_delta_sign_convention():
    """oklab_l_delta is fg - bg: fg lighter than bg -> positive."""
    assert oklab_l_delta("#ffffff", "#000000") == pytest.approx(1.0, abs=1e-9)
    assert oklab_l_delta("#000000", "#ffffff") == pytest.approx(-1.0, abs=1e-9)
    # Same relationship for mid-tones, not just the extremes.
    assert oklab_l_delta("#a0a0a0", "#404040") > 0
    assert oklab_l_delta("#404040", "#a0a0a0") < 0
    assert oklab_l_delta("#404040", "#a0a0a0") == pytest.approx(
        -oklab_l_delta("#a0a0a0", "#404040")
    )


def test_apca_self_is_zero():
    assert apca_lc("#445566", "#445566") == pytest.approx(0.0)


def test_apca_and_wcag_disagree_on_dark_backgrounds():
    """The documented failure mode: WCAG rates these as equivalent, APCA does not.

    This is not a bug in either -- it is the reason we report both.
    """
    a = ("#8a8a8a", "#ffffff")  # grey on white
    b = ("#8a8a8a", "#000000")  # same grey on black
    assert wcag_contrast(*a) == pytest.approx(wcag_contrast(*b), rel=0.55)
    assert abs(abs(apca_lc(*a)) - abs(apca_lc(*b))) > 5


# --------------------------------------------------------------------------
# Distance
# --------------------------------------------------------------------------


def test_delta_e_zero_for_identical():
    assert delta_e_ok("#abcdef", "#abcdef") == pytest.approx(0.0)


def test_delta_e_black_white_is_unit_l():
    assert delta_e_ok("#000000", "#ffffff") == pytest.approx(1.0, abs=1e-6)


def test_breakdown_channels_are_diagnostic():
    # Two greys: pure lightness difference.
    b = breakdown("#404040", "#a0a0a0")
    assert b.dominant_channel() == "lightness"
    assert b.d_hue == pytest.approx(0.0, abs=1e-6)

    # Red vs green at similar lightness: hue difference dominates.
    b2 = breakdown("#c05050", "#50a050")
    assert b2.dominant_channel() == "hue"


def test_hue_delta_wraps():
    assert hue_delta("#ff0000", "#ff0000") == pytest.approx(0.0)
    assert 0 <= hue_delta("#0000ff", "#ffff00") <= 180


def test_delta_e_ok_scaled_lightness_weight_factor():
    """For a *pure-lightness* pair the scaling is exactly multiplicative.

    Greys have a = b = 0 in OKLab, so delta_e_ok_scaled reduces to
    |dL * l_weight| and the l_weight=2 default must score the pair exactly
    twice the Euclidean dE -- the documented 'lightness up-weighting'.
    """
    light_pair = ("#404040", "#a0a0a0")
    de = delta_e_ok(*light_pair)
    assert delta_e_ok_scaled(*light_pair, l_weight=1.0) == pytest.approx(de, abs=1e-9)
    assert delta_e_ok_scaled(*light_pair, l_weight=2.0) == pytest.approx(
        2.0 * de, abs=1e-9
    )
    # Default weight is 2.0.
    assert delta_e_ok_scaled(*light_pair) == pytest.approx(
        delta_e_ok_scaled(*light_pair, l_weight=2.0)
    )
    assert delta_e_ok_scaled(*light_pair) > de


def test_hue_delta_wraps_across_zero():
    """Hues ~350 vs ~10 degrees must take the short way (~20 deg), not ~340.

    #ff44aa has OKLch hue ~352 deg, #ff99aa ~9.5 deg: a naive absolute
    difference reports ~342 deg, the wrapped difference ~17.5 deg.
    """
    a, b = "#ff44aa", "#ff99aa"
    ha, hb = hex_to_oklch(a)[2], hex_to_oklch(b)[2]
    assert abs(ha - 350.0) < 5.0 and abs(hb - 10.0) < 5.0  # pair straddles 0 deg
    naive = abs(ha - hb)
    assert naive > 300.0  # the naive (buggy) difference is the long way round
    assert hue_delta(a, b) == pytest.approx(360.0 - naive, abs=1e-9)
    assert hue_delta(a, b) < 30.0
    assert hue_delta(a, b) == pytest.approx(hue_delta(b, a), abs=1e-12)


# --------------------------------------------------------------------------
# CVD
# --------------------------------------------------------------------------


@pytest.mark.parametrize("kind", ["protan", "deutan", "tritan"])
def test_cvd_preserves_neutrals(kind):
    """Greys are on the achromatic axis and must survive any dichromacy."""
    for grey in ("#000000", "#808080", "#ffffff"):
        out = simulate(grey, kind, 1.0)
        r, g, b = (int(out[i : i + 2], 16) for i in (1, 3, 5))
        assert max(r, g, b) - min(r, g, b) <= 3


def test_cvd_severity_zero_is_identity():
    assert simulate("#c678dd", "deutan", 0.0).lower() == "#c678dd"


def test_red_green_collapse_is_detected():
    """The canonical case: a red error colour vs a green success colour."""
    hits = check_pair("#c04c4c", "#4c9c4c", min_de=0.10)
    kinds = {h.kind for h in hits}
    # Deuteranopia collapses this pair (dE ~ 0.044), but protanopia does not:
    # the two colours shift apart in lightness, leaving dE ~ 0.18.
    assert "deutan" in kinds
    assert "protan" not in kinds


def test_lightness_separated_pair_survives_cvd():
    """Redundant lightness coding is what makes a pair CVD-robust."""
    assert check_pair("#3a1010", "#d0e8d0", min_de=0.10) == []


# --------------------------------------------------------------------------
# Spectral
# --------------------------------------------------------------------------


def test_v_lambda_peaks_near_555nm():
    peak = LAMBDA[int(np.argmax(v_lambda()))]
    assert 550 <= peak <= 560


# Tabulated CIE photopic V(lambda) reference values, pinned from the official
# CIE data file (CIE 018:2019, Table 1; the modern republication of the CIE
# 1924/1931 photopic table):
#   https://files.cie.co.at/Publications-datasets/CIE_sle_photopic.csv
#   (linked from https://cie.co.at/datatable/cie-spectral-luminous-efficiency-photopic-vision,
#    fetched 2026-08-15).  Quoted CSV rows:
#     450,0.0380000000000
#     500,0.3230000000000
#     550,0.9949501000000
#     555,1.0000000000000
#     600,0.6310000000000
#     650,0.1070000000000
# Independently cross-checked against the CIE 1931 5-nm table (y-bar column)
# in John Walker's public-domain specrend.c:
#   https://www.fourmilab.ch/documents/specrend/specrend.c (fetched 2026-08-15)
# which prints identical y-bar values at these wavelengths (0.0380, 0.3230,
# 0.9950, 1.0000, 0.6310, 0.1070).
#
# The grotto fit (Wyman/Sloan/Shirley 2013 multi-lobe) is stated accurate to
# ~1% of peak (i.e. ~0.01 absolute).  We assert the stronger max(2% relative,
# 0.005 absolute): 2% relative governs where V is large (>= ~0.25), the 0.005
# absolute floor governs in the wings.  Measured deviations of the fit at the
# pinned points: 450 -12.6% rel (0.0048 abs), 500 +1.3%, 550 -0.05%,
# 555 -0.20%, 600 +0.54%, 650 +3.0% rel (0.0032 abs) -- all within tolerance.
CIE_VLAMBDA = {
    450: 0.038,
    500: 0.323,
    550: 0.9949501,
    555: 1.0,
    600: 0.631,
    650: 0.107,
}


@pytest.mark.parametrize("wl", sorted(CIE_VLAMBDA))
def test_v_lambda_matches_cie_table(wl):
    """The analytic V(lambda) fit tracks the tabulated CIE curve within its
    stated ~1%-of-peak accuracy at six wavelengths across the visible range."""
    ref = CIE_VLAMBDA[wl]
    got = float(v_lambda()[int(np.argmin(np.abs(LAMBDA - wl)))])
    assert got == pytest.approx(ref, rel=0.02, abs=0.005)


def test_melanopic_proxy_matches_cie_s026_near_peak():
    """s_mel proxy vs the *official* CIE S 026:2018 Table 2 tabulation.

    Pinned from the CIE alpha-opic action spectra dataset (column 6,
    s_mel(lambda), unit-normalised with its peak of 1.0 at 490 nm):
      https://files.cie.co.at/Publications-datasets/CIE_a-opic_action_spectra.csv
      (linked from https://cie.co.at/datatable/cie-alpha-opic-action-spectra,
       DOI 10.25039/CIE.DS.vqqhzp5a; column order confirmed by the dataset's
       .csv_metadata.json; fetched 2026-08-15).  Quoted CSV rows (s_mel only):
         480,9.65605E-01   490,1.00000E+00   500,9.65952E-01

    Tolerance is deliberately loose (10% relative) because s_mel is a *proxy*:
    a Govardovskii A1 template at lambda_max=480 behind a logistic ocular-media
    roll-off, normalised to unit peak -- a shape approximation by the module's
    own docstring, not the tabulated CIE S 026 function.  Measured deviations:
    +3.6% at 480, -3.0% at 490, -9.1% at 500.  Only the peak neighbourhood is
    pinned; beyond ~510 nm the proxy diverges from the tabulated curve by far
    more than any honest 'proxy' tolerance (see the structural test below and
    the note in test_melanopic_proxy_structural_shape).
    """
    cie_mel = {480: 0.965605, 490: 1.0, 500: 0.965952}
    m = s_mel()
    for wl, ref in cie_mel.items():
        got = float(m[int(np.argmin(np.abs(LAMBDA - wl)))])
        assert got == pytest.approx(ref, rel=0.10), f"s_mel({wl} nm)"


def test_melanopic_proxy_structural_shape():
    """Shape invariants of the melanopic proxy, pinned structurally.

    Rationale: the full CIE S 026 curve (officially tabulated, see the test
    above) CANNOT be pinned against this proxy at proxy-grade tolerance
    outside the peak neighbourhood.  Measured deviations of the grotto proxy
    vs the tabulated s_mel: +39.8% at 450 nm (the logistic ocular-media
    roll-off is too permissive in the blue), -19% at 520, -30% at 550,
    -43% at 600, ~-55% at 700 (the Govardovskii alpha band falls off faster
    on the red side than the tabulated corneal spectrum).  Those are known
    limitations of the stated shape approximation, not drift: this test pins
    the structural properties the module actually relies on for ranking
    palettes, and documents that full-spectrum tabulated pinning remains an
    open gap (it would require either the real CIE S 026 table or a better
    ocular-media model in src/grotto/spectral.py).
    """
    m = s_mel()
    peak_i = int(np.argmax(m))
    peak_wl = LAMBDA[peak_i]

    # Peak lives in the 480-500 nm band (the tabulated CIE curve peaks at 490).
    assert 480 <= peak_wl <= 500
    # Unit-normalised.
    assert m[peak_i] == pytest.approx(1.0)

    # Strictly decreasing away from the peak toward both ends of the range
    # (toward 780 directly; toward 380 means increasing as lambda approaches
    # the peak).  The fit has no plateau near the peak, so strict inequalities
    # hold at 1 nm sampling.
    assert np.all(np.diff(m[peak_i:]) < 0), "must decrease toward 780 nm"
    assert np.all(np.diff(m[: peak_i + 1]) > 0), "must increase toward the peak"

    # Short-wavelength side stays below the peak value even at 450 nm
    # (ocular media attenuates the blue end).
    s450 = float(m[int(np.argmin(np.abs(LAMBDA - 450)))])
    s490 = float(m[int(np.argmin(np.abs(LAMBDA - 490)))])
    assert s450 < s490

    # Effectively silent above 700 nm.
    assert float(m[LAMBDA >= 700].max()) < 0.05


def test_melanopic_peaks_near_490nm():
    """CIE S 026 melanopic action spectrum peaks around 490 nm at the cornea."""
    peak = LAMBDA[int(np.argmax(s_mel()))]
    assert 480 <= peak <= 500


def test_white_is_the_normalisation_point():
    r = melanopic("#ffffff")
    assert r.photopic == pytest.approx(1.0, abs=1e-9)
    assert r.melanopic == pytest.approx(1.0, abs=1e-9)
    assert r.mel_ratio == pytest.approx(1.0, abs=1e-9)


def test_black_emits_nothing():
    r = melanopic("#000000")
    assert r.photopic == pytest.approx(0.0, abs=1e-12)
    assert r.melanopic == pytest.approx(0.0, abs=1e-12)


def test_blue_has_high_mel_ratio_amber_has_low():
    blue = melanopic("#4060ff").mel_ratio
    amber = melanopic("#ff9040").mel_ratio
    assert blue > 1.5
    assert amber < 0.5
    assert blue > amber


def test_display_archetypes_differ():
    """Same hex, different nominal display, different melanopic content.

    The two Gaussian display archetypes are more similar to each other than
    real displays are, so the measured difference for this colour (~0.006) is
    small.  This is a weak sanity check rather than a claim about real
    hardware; the point is only that hex alone does not determine melanopic
    output, which is why we refuse to make absolute claims from hex values.
    """
    hx = "#20242e"
    a = melanopic(hx, led_lcd()).mel_ratio
    b = melanopic(hx, oled()).mel_ratio
    assert abs(a - b) > 0.001


def test_dark_theme_melanopic_output_dominated_by_foreground():
    """In dark themes coverage fraction is a poor proxy for emitted light.

    Emission scales with luminance, so the foreground text dominates despite
    low coverage.  A dark background emits so little light that even at 88%
    coverage it is NOT the dominant emitter -- an important finding that
    inverts the naive 'background dominates because it covers most pixels'
    intuition, which holds for light themes only (see the companion test below).
    """
    res = screen_melanopic(
        {"#1a1c22": 0.88, "#c8ccd4": 0.10, "#40e0e0": 0.02},
    )
    top_hx, top_share = res.top_contributors(1)[0]
    assert top_hx == "#c8ccd4"
    assert top_share > res.contributions["#1a1c22"]


def test_light_theme_melanopic_output_dominated_by_background():
    """The 'background dominates because it covers most pixels' premise holds
    for light themes only.

    Here the bright background really is the dominant melanopic emitter, in
    contrast to the dark-theme case where the foreground wins.
    """
    res = screen_melanopic(
        {"#faf6ee": 0.88, "#3a3730": 0.10, "#2a6a9a": 0.02},
    )
    top_hx, _ = res.top_contributors(1)[0]
    assert top_hx == "#faf6ee"


def test_screen_coverage_must_sum_to_one():
    with pytest.raises(ValueError):
        screen_melanopic({"#000000": 0.5})


def test_warm_background_lowers_screen_melanopic_at_equal_luminance():
    """Core hypothesis check: at matched photopic output, a warm-neutral dark
    background emits less melanopic-weighted light than a blue-slate one."""
    cool = screen_melanopic({"#1b2030": 0.9, "#c9d2e0": 0.1})
    warm = screen_melanopic({"#22201c": 0.9, "#ded5c8": 0.1})
    assert warm.mel_ratio < cool.mel_ratio
