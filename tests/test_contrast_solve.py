"""Inverse contrast, and the surface-cluster seating that priced §8.

The seating tests matter more than the solver tests.  The first version of
scripts/contrast_solve.py computed a "lower bound" by longest-path relaxation
over the constraint graph and reported the cluster as provably infeasible at
2.33 on a 1.0 axis.  That graph has cycles, so the relaxation is unbounded and
the number meant nothing -- but it looked exactly like a proof.  These tests pin
the exact enumeration so that failure mode cannot come back quietly.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from grotto.contrast import (
    solve_lightness,
    solve_wcag_luminance,
    wcag_contrast,
)
from grotto.color import hex_to_oklch

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

from contrast_solve import (  # noqa: E402
    classify,
    min_span_exact,
    required_gaps,
    shortfalls,
    slide_to_min_movement,
    verify_seating,
)
from grotto.spec import DistanceSpec, Palette, RoleSpec  # noqa: E402

NIGHT = REPO / "out/soft-night/soft-s01.night.yaml"
DARK_BG = "#1a1d23"


# --------------------------------------------------------------------------
# Inverse contrast
# --------------------------------------------------------------------------


@pytest.mark.parametrize("target", [3.0, 4.5, 7.0, 12.0])
def test_solve_lightness_hits_its_wcag_target(target):
    """Tolerance is RELATIVE: the bisection is on lightness, and contrast is a
    ratio, so a fixed absolute epsilon would be unmeetable at 12:1 and far too
    loose at 3:1."""
    r = solve_lightness(DARK_BG, target, chroma=0.02, hue=250.0, model="wcag")
    assert r.reachable
    assert wcag_contrast(r.hex, DARK_BG) == pytest.approx(target, rel=0.02)


def test_analytic_and_bisected_agree():
    """The closed form and the bisection must not drift apart."""
    y = solve_wcag_luminance(DARK_BG, 4.5)
    assert y is not None
    r = solve_lightness(DARK_BG, 4.5, model="wcag")
    assert r.achieved == pytest.approx(4.5, rel=0.02)
    assert r.hex != DARK_BG


def test_unreachable_is_reported_not_faked():
    """21:1 needs pure white on pure black; anything less cannot reach it."""
    r = solve_lightness(DARK_BG, 21.0, model="wcag")
    assert not r.reachable
    assert solve_wcag_luminance(DARK_BG, 21.0) is None or r.achieved < 21.0


def test_solve_respects_the_requested_polarity():
    """Each polarity only exists against a background it can move away from.

    Asking for 4.5:1 by going DARKER on an already-dark canvas is not a small
    ask, it is an impossible one -- there is nowhere further to go.
    """
    light_bg = "#e8e6e1"
    light = solve_lightness(DARK_BG, 4.5, prefer="lighter", model="wcag")
    dark = solve_lightness(light_bg, 4.5, prefer="darker", model="wcag")
    assert light.reachable and dark.reachable
    assert hex_to_oklch(light.hex)[0] > hex_to_oklch(DARK_BG)[0]
    assert hex_to_oklch(dark.hex)[0] < hex_to_oklch(light_bg)[0]

    # and the impossible direction is reported as unreachable, not invented
    away = solve_lightness(DARK_BG, 4.5, prefer="darker", model="wcag")
    assert not away.reachable


@pytest.mark.parametrize("bg,prefer", [(DARK_BG, "lighter"), ("#e8e6e1", "darker")])
@pytest.mark.parametrize("target", [3.0, 4.5, 7.0])
def test_both_polarities_actually_hit_the_target(bg, prefer, target):
    """Reachability is not the same as correctness.

    The darker polarity was seeded with an inverted bisection bracket: it still
    terminated and still reported reachable=True, but returned a colour that
    missed the target.  Asserting the ACHIEVED contrast on both polarities is
    what catches that; asserting `reachable` alone does not.
    """
    r = solve_lightness(bg, target, prefer=prefer, model="wcag")
    assert r.reachable, f"{prefer} {target} reported unreachable"
    assert wcag_contrast(r.hex, bg) == pytest.approx(target, rel=0.02), (
        f"{prefer} polarity returned {wcag_contrast(r.hex, bg):.3f} for a "
        f"{target} target"
    )


def test_unknown_model_is_rejected():
    with pytest.raises(ValueError, match="unknown contrast model"):
        solve_lightness(DARK_BG, 4.5, model="nope")


def test_solve_result_reports_its_background():
    """A regression: the unreachable message once printed the wrong colour."""
    r = solve_lightness(DARK_BG, 21.0, model="wcag")
    assert r.bg == DARK_BG


# --------------------------------------------------------------------------
# Seating: the maths behind the §8 reversal
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def palette() -> Palette:
    return Palette.from_yaml(NIGHT)


@pytest.fixture(scope="module")
def dists() -> DistanceSpec:
    return DistanceSpec.load(REPO / "spec/distance-matrix.yaml")


@pytest.fixture(scope="module")
def roles() -> RoleSpec:
    return RoleSpec.load(REPO / "spec/roles.yaml")


def test_no_cvd_shortfall_is_readability_typed(palette, dists, roles):
    """The §8 part-1 result: the inverse-contrast approach cannot address these.

    Every shortfall is a PEER obligation.  A contrast solve states 'ink must
    read on a surface', and none of these are that.
    """
    rows = shortfalls(palette, dists, roles)
    read, peer = classify(rows)
    assert rows, "expected the known shortfall list to be non-empty"
    assert read == [], f"unexpected readability-typed shortfalls: {read}"
    assert len(peer) == len(rows)


def test_the_cluster_is_feasible_on_lightness(palette, dists, roles):
    """The corrected result.  If this flips to infeasible, §8 is wrong."""
    for cvd in (None, "deutan"):
        surfaces, need = required_gaps(palette, dists, roles, cvd=cvd)
        span, _x, _order = min_span_exact(surfaces, need)
        assert span < 1.0, f"{cvd or 'normal'}: seating needs {span:.4f} of the axis"


def test_min_movement_seating_actually_satisfies_every_pair(palette, dists, roles):
    """A construction is only worth reporting if it is verified, not assumed."""
    for cvd in (None, "deutan"):
        surfaces, need = required_gaps(palette, dists, roles, cvd=cvd)
        _span, _x, order = min_span_exact(surfaces, need)
        current = {r: hex_to_oklch(palette.get(r))[0] for r in surfaces}
        seats = slide_to_min_movement(order, need, current)
        assert verify_seating(seats, need) == [], f"{cvd or 'normal'} seating violated"
        assert all(-1e-9 <= v <= 1 + 1e-9 for v in seats.values()), "seating off-axis"


def test_required_gap_is_zero_when_the_pair_already_clears(dists):
    """The §8 feasibility result is only falsifiable if the gaps are real.

    A pair already at the threshold needs no lightness at all; a pair at dE 0
    needs the whole threshold.  Those two endpoints pin the formula from both
    sides, so a bug that made every gap small would fail here rather than
    quietly turning the cluster feasible.
    """
    limit = dists.thresholds["must_distinguish"]["normal_vision"]
    roles_spec = RoleSpec.load(REPO / "spec/roles.yaml")
    base = {r: "#1a1d23" for r in ("bg", "selection", "active_line")}

    identical = Palette(name="t", variant="night",
                        colors={**base, "selection": "#2a2f38",
                                "active_line": "#2a2f38"})
    _s, need_same = required_gaps(identical, dists, roles_spec, cvd=None)
    assert need_same[tuple(sorted(("selection", "active_line")))] == pytest.approx(limit)

    apart = Palette(name="t", variant="night",
                    colors={**base, "selection": "#2a2f38",
                            "active_line": "#3a414d"})
    _s, need_apart = required_gaps(apart, dists, roles_spec, cvd=None)
    gap = need_apart[tuple(sorted(("selection", "active_line")))]
    assert 0.0 <= gap < limit, "a pair already separated should need less than the limit"


def test_longest_path_style_relaxation_is_unbounded_on_cycles():
    """The bug that produced the false 'provably infeasible' result.

    Relaxing longest paths over a cyclic graph diverges, so any bound computed
    that way is meaningless no matter how large it looks.  This test exists so
    the failure mode is named rather than rediscovered.
    """
    from itertools import permutations

    def _span_for(order, need):
        x = {}
        for node in order:
            lo = 0.0
            for other, pos in x.items():
                g = need.get(tuple(sorted((node, other))))
                if g is not None:
                    lo = max(lo, pos + g)
            x[node] = lo
        return max(x.values()) - min(x.values())

    # a triangle: no ordering can fit these on the axis
    need = {tuple(sorted(p)): 0.4 for p in
            (("a", "b"), ("b", "c"), ("a", "c"))}
    spans = [_span_for(o, need) for o in permutations("abc")]
    assert min(spans) == pytest.approx(0.8)
    assert min(spans) > 1.0 - 0.8, "a triangle of 0.4 gaps cannot fit in 1.0"
