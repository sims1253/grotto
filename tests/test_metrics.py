"""Validate contrast, distance, CVD and spectral metrics against known values."""

import numpy as np
import pytest

from grotto.contrast import apca_lc, oklab_l_delta, wcag_contrast
from grotto.cvd import check_pair, simulate
from grotto.distance import breakdown, delta_e_ok, hue_delta
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
