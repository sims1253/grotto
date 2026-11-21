"""Numeric-first Night optimizer (branch dev/numeric-palettes) unit tests.

Covered, per the branch charter (see NUMERIC.md):
  * the WCAG-feasible lightness interval computation (bisection against a
    fixed reference hex, at a chroma fraction of the gamut edge);
  * chroma projection into the sRGB gamut;
  * a small fixed-seed search on a REDUCED chromatic subset asserting the
    three contractual properties of the optimizer:
      - every hard floor holds on the emitted palette (WCAG vs bg and every
        co-occurring surface, sRGB gamut) -- check_feasible;
      - the worst normalised margin improves over the scaffold baseline
        (candidate-b's own values for the optimised roles);
      - two runs with the same seed produce byte-identical output.

The reduced run uses tiny budgets (2 restarts / 4 samples / 3 passes) and
completes in well under a second; the full 23-role run is exercised by the
script itself, not by the test suite.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "numeric_palette", REPO / "scripts/numeric_palette.py"
)
np_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(np_mod)

from grotto.color import hex_to_oklch, max_chroma, oklch_to_hex  # noqa: E402
from grotto.contrast import wcag_contrast  # noqa: E402
from grotto.spec import Palette  # noqa: E402

#: Reduced chromatic subset: enough must-pair coverage to be meaningful
#: (error/warning safety pairs, the diff_added/diff_removed opposite-meaning
#: pair, one syntax pair, one surface cluster member) while staying fast.
REDUCED_CHROMATIC = (
    "keyword", "string", "function",
    "error", "warning",
    "selection", "diff_added", "diff_removed",
)


def _problem() -> "np_mod.NumericProblem":
    return np_mod.NumericProblem(chromatic=REDUCED_CHROMATIC)


# ---------------------------------------------------------------------------
# WCAG-feasible lightness interval
# ---------------------------------------------------------------------------


def test_feasible_l_interval_meets_floor_at_lo_and_fails_below():
    p = _problem()
    bg = p.scaffold_hex["bg"]
    h = 250.0
    iv = np_mod.feasible_l_interval(bg, 4.5, h, c_frac=1.0)
    assert iv is not None
    lo, hi = iv
    assert hi == 1.0
    # at lo (gamut-edge chroma) the floor is met ...
    c_lo = max_chroma(lo, h)
    assert wcag_contrast(oklch_to_hex((lo, c_lo, h)), bg) >= 4.5
    # ... and two lightness steps below it, it is not (bisection boundary)
    below = lo - 0.02
    c_below = max_chroma(below, h)
    assert wcag_contrast(oklch_to_hex((below, c_below, h)), bg) < 4.5
    # dark polarity: the feasible set is above the canvas
    assert lo > p.scaffold["bg"][0]


def test_feasible_l_interval_none_when_floor_unreachable():
    # a 30:1 floor against the night canvas is physically unreachable
    assert np_mod.feasible_l_interval("#191714", 30.0, 250.0) is None


def test_feasible_l_interval_lo_is_hue_dependent_in_chroma():
    # Honest geometry: gamut-edge chroma at fixed OKLCH L changes relative
    # luminance in a hue-dependent way.  Blue chroma (260) LOWERS luminance,
    # so the WCAG floor needs MORE lightness at full chroma; green chroma
    # (130) raises it.  Both directions are asserted so the interval really
    # evaluates the quantised colour rather than assuming monotonicity.
    bg = "#191714"
    lo_blue_full = np_mod.feasible_l_interval(bg, 4.5, 260.0, c_frac=1.0)[0]
    lo_blue_achrom = np_mod.feasible_l_interval(bg, 4.5, 260.0, c_frac=0.0)[0]
    assert lo_blue_full > lo_blue_achrom
    lo_green_full = np_mod.feasible_l_interval(bg, 4.5, 130.0, c_frac=1.0)[0]
    lo_green_achrom = np_mod.feasible_l_interval(bg, 4.5, 130.0, c_frac=0.0)[0]
    assert lo_green_full < lo_green_achrom


def test_feasible_l_interval_monotone_in_floor():
    bg = "#191714"
    for h, frac in ((250.0, 1.0), (250.0, 0.0), (100.0, 0.6)):
        lo45 = np_mod.feasible_l_interval(bg, 4.5, h, c_frac=frac)[0]
        lo30 = np_mod.feasible_l_interval(bg, 3.0, h, c_frac=frac)[0]
        # a higher floor always demands more lightness on a dark canvas
        assert lo45 >= lo30


# ---------------------------------------------------------------------------
# Gamut projection
# ---------------------------------------------------------------------------


def test_project_chroma_clips_to_gamut_and_preserves_L_h():
    L, h = 0.80, 260.0
    out = np_mod.project_chroma(L, 0.40, h)  # far outside sRGB at this L, h
    assert out[0] == L and out[2] == h
    assert out[1] <= max_chroma(L, h) + 1e-9
    assert np_mod.maxc(out[0], out[2]) >= out[1] - 1e-9
    # already-in-gamut chroma is returned verbatim
    assert np_mod.project_chroma(0.62, 0.001, 30.0) == (0.62, 0.001, 30.0)


def test_project_chroma_quantised_hex_stays_in_srgb():
    from grotto.color import gamut_status

    hx = oklch_to_hex(np_mod.project_chroma(0.9, 0.5, 280.0))
    assert gamut_status(hex_to_oklch(hx)).in_srgb


# ---------------------------------------------------------------------------
# Reduced fixed-seed search run
# ---------------------------------------------------------------------------


def _reduced_run():
    problem = _problem()
    results = np_mod.run_search(
        problem, seed=7, restarts=2, samples=4, refine_passes=3, refine_top=1
    )
    assert results, "search returned no results"
    best = results[0]
    state = np_mod.place_unconstrained(problem, dict(best["state"]))
    return problem, state, best["J"]


def test_reduced_run_all_floors_hold():
    problem, state, _ = _reduced_run()
    hexes = problem.hexes(state)
    # include_inherited=False: scaffold-vs-scaffold violations (e.g. fg_muted
    # over candidate-b's own search_match) are inherited from the committed
    # palette, not something the reduced optimizer can move; the full problem
    # optimizes every co-occurring surface, so nothing is inherited there.
    bad = np_mod.check_feasible(problem, hexes, include_inherited=False)
    assert not bad, f"hard-constraint violations: {bad}"


def test_reduced_run_beats_scaffold_worst_margin():
    problem, state, j = _reduced_run()
    baseline = np_mod.evaluate(problem, problem.hexes(problem.baseline_lch))
    assert j > baseline["J"], (
        f"optimizer J {j:.4f} did not improve on the scaffold baseline "
        f"{baseline['J']:.4f} (candidate-b's own chromatic values)"
    )


def test_reduced_run_deterministic():
    problem1, state1, j1 = _reduced_run()
    problem2, state2, j2 = _reduced_run()
    assert j1 == j2
    assert state1 == state2


def test_written_yaml_is_loadable_non_candidate_palette(tmp_path):
    problem, state, _ = _reduced_run()
    out = tmp_path / "numeric-test.night.yaml"
    np_mod.write_palette_yaml(out, "numeric-test", state, problem, 7, {"j": 0.0})
    pal = Palette.from_yaml(out)
    assert not pal.is_candidate
    assert pal.variant == "night"
    # complete palette: scaffold + optimised roles = all 40 committed roles
    assert len(pal) == 40
    # the scaffold must be verbatim: bg hex matches candidate-b's authored bg
    committed = Palette.from_yaml(
        REPO / "themes/candidates/candidate-b-balanced.night.yaml"
    )
    assert pal["bg"] == committed["bg"]
    assert pal["fg"] == committed["fg"]
    # written twice -> byte-identical
    out2 = tmp_path / "numeric-test-2.night.yaml"
    np_mod.write_palette_yaml(out2, "numeric-test", state, problem, 7, {"j": 0.0})
    assert out.read_bytes() == out2.read_bytes()
