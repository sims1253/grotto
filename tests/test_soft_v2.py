"""Soft-objective search, v2 (branch feat/palette-autoresearch-2).

Each v2 change to the search's constraint set is pinned here, together with
the defect that motivated it (docs/review/soft-objective-v2.md):

  * the lifted muted inks, which give the surface cluster a lightness axis;
  * the wider lightness fence, ONLY for roles whose spec declares
    ``lightness_offset``, and downward-only for inks;
  * the narrower convention windows (added/success green, removed red);
  * the surface prominence rank -- which v1's shipped palette breaks;
  * the role chroma floors -- which v1's shipped palette also breaks;
  * the closed-form gamut test the ascent's guard uses.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, REPO / f"scripts/{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sp = _load("soft_palette")
gate_mod = _load("soft_gate")

from grotto.color import oklch_to_hex  # noqa: E402
from grotto.contrast import wcag_contrast  # noqa: E402
from grotto.spec import Palette  # noqa: E402

V1 = REPO / "out/soft-night/soft-s01.night.yaml"
V2 = REPO / "out/soft-night-v2/soft2-s01.night.yaml"


@pytest.fixture(scope="module")
def problem():
    return sp.SoftProblem()


def _hexes(path: Path, problem) -> dict[str, str]:
    colors = {r: str(v) for r, v in Palette.from_yaml(path).colors.items()}
    return {r: colors[r] for r in problem.present}


# -- the lightness axis ------------------------------------------------------


def test_lifted_muted_inks_raise_the_surface_ceiling(problem):
    """At candidate-b's L 0.528, fg_muted at 3:1 capped every surface at
    L ~0.25.  Lifted, a surface at L 0.30 keeps every floored scaffold ink."""
    surf = oklch_to_hex((0.30, 0.0, 70.0))
    for r in problem.scaffold_floor_inks:
        assert wcag_contrast(problem.scaffold_hex[r], surf) >= problem.floors[r], r
    # and the old value really was the cap
    old_muted = oklch_to_hex((0.5286, 0.0053, 78.3))
    assert wcag_contrast(old_muted, surf) < 3.0


def test_lightness_fence_widens_only_where_the_spec_declares_it(problem):
    roles = problem.roles_spec.roles
    for r in problem.chromatic:
        base = problem.baseline_lch[r][0]
        lo, hi = problem.l_range(r)
        declared = "lightness_offset" in roles[r].redundant_channels
        ink = problem.paint[r] in ("ink", "border")
        if not declared:
            d = sp.mp.INK_L_DELTA if ink else sp.mp.SURFACE_L_DELTA
            assert lo == pytest.approx(base - d), r
        elif ink:
            assert lo == pytest.approx(base - sp.OFFSET_INK_L_DELTA), r
            # inks never widen upward: above ~0.9 a hue cannot hold chroma
            assert hi <= base + sp.mp.INK_L_DELTA + 1e-9, r
        else:
            assert lo == pytest.approx(base - sp.OFFSET_SURFACE_L_DELTA), r
            assert hi == pytest.approx(base + sp.OFFSET_SURFACE_L_DELTA), r


# -- convention windows ------------------------------------------------------


@pytest.mark.parametrize("role,h", [("diff_added", 95.0), ("success", 100.0),
                                    ("diff_removed", 1.5), ("diff_added", 175.0)])
def test_soft_windows_project_inside(role, h):
    out = sp.soft_project_hue(role, h)
    assert sp._in_soft_window(role, out), (role, h, out)
    # and every soft window is a subset of the middle window (so v2 palettes
    # still pass the middle audit)
    lo, hi = sp.SOFT_HUE_WINDOWS[role][0]
    assert any(mlo <= lo and hi <= mhi for mlo, mhi in sp.mp.HUE_WINDOWS[role])


def test_fence_audit_reports_an_olive_diff_added(problem):
    hexes = dict(problem.hexes(problem.baseline_lch))
    hexes["diff_added"] = oklch_to_hex((0.30, 0.04, 95.0))
    assert any("diff_added" in e and "soft window" in e for e in problem.fence_audit(hexes))


# -- prominence rank and diagnostic floors ---------------------------------------


def test_prominence_rank_flags_a_dim_current_match(problem):
    """The rule: inside a family, a higher-salience wash stands at least as far
    off the canvas.  A current match parked next to the canvas is flagged."""
    hexes = _hexes(V1, problem)
    hexes["search_match_current"] = oklch_to_hex((0.215, 0.02, 41.5))
    hexes["search_match"] = oklch_to_hex((0.315, 0.06, 41.5))
    bad = sp.prominence_violations(problem, hexes)
    assert ("sand", "search_match", "search_match_current") in [b[:3] for b in bad]


def test_role_chroma_floors_flag_v1s_washed_out_error(problem):
    assert problem.chroma_floor("error") == sp.ROLE_CHROMA_FLOOR["error"]
    assert problem.chroma_floor("keyword") == sp.sm.CHROMA_FLOOR
    found = gate_mod.gate(V1)
    assert any("error below the chroma floor" in f for f in found), found


def test_role_floor_is_reachable_under_its_lightness_cap(problem):
    """A floor above the 70% gamut ceiling would be a fence nothing can meet."""
    for r, floor in sp.ROLE_CHROMA_FLOOR.items():
        lo, hi = problem.l_range(r)
        assert hi <= sp.ROLE_L_MAX[r] + 1e-9
        for wlo, whi in sp.mp.HUE_WINDOWS[r]:
            for h in (wlo + 2.0, (wlo + whi) / 2, whi - 2.0):
                if r in sp.SOFT_HUE_WINDOWS and not sp._in_soft_window(r, h):
                    continue
                assert problem.chroma_ceiling(r, lo, h) >= floor - 1e-9, (r, h)


# -- the guard's fast gamut test -----------------------------------------------


def test_fast_normc_tracks_the_exact_definition():
    import random

    rng = random.Random(7)
    for _ in range(200):
        hx = "#%06x" % rng.randrange(1 << 24)
        assert abs(sp._normc(hx) - sp._normc_fast(hx)) < sp.SAL_RANK_TOL


# -- the shipped v2 palette -----------------------------------------------------


def test_shipped_v2_palette_passes_the_gate():
    assert V2.exists()
    assert gate_mod.gate(V2) == []


def test_shipped_v2_beats_v1_on_the_unchanged_instrument():
    v1, v2 = sp.sm.score(V1), sp.sm.score(V2)
    assert v2["utility"] > v1["utility"] + 0.03
    assert v2["wcag_violations"] == 0
