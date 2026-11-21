"""Middle-frontier Night optimizer (branch dev/numeric-palettes) unit tests.

Covered, per the branch charter (see NUMERIC.md, "Middle frontier"):
  * the taste fences as hard constraints -- hue convention windows, per-class
    chroma caps INCLUDING the 70%-of-gamut rule, lightness deltas around the
    candidate-b night values -- both on the projection primitives and on a
    palette the search actually emits (fence_audit, hex AND authored coords);
  * WCAG floors vs the background and every co-occurring surface on the
    emitted palette (the committed candidate-b carries 12 violations there;
    the middle optimizer must emit zero);
  * the number/constant same_family min-distance gate (dE >= 0.03) after a
    tiny reduced run -- the debt-1 fix;
  * determinism: same seed, byte-identical states.

The reduced run uses tiny budgets (2 restarts / 4 samples / 3 passes) and
completes in seconds; the full 23-role run is exercised by the script itself.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

_spec = importlib.util.spec_from_file_location(
    "middle_palette", REPO / "scripts/middle_palette.py"
)
mp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mp)
np = mp.np  # the reused numeric_palette machinery, as the script sees it

from grotto.color import hex_to_oklch, max_chroma, oklch_to_hex
from grotto.spec import Palette

#: Reduced chromatic subset: must-pair coverage (error/warning safety pairs,
#: the diff opposite-meaning pair, one syntax pair, one surface-cluster
#: member) PLUS number/constant so the same_family min-distance gate is
#: exercised end to end.
REDUCED_CHROMATIC = (
    "keyword", "string", "number", "constant", "function",
    "error", "warning",
    "selection", "diff_added", "diff_removed",
)


def _problem() -> mp.MiddleProblem:
    return mp.MiddleProblem(chromatic=REDUCED_CHROMATIC)


# ---------------------------------------------------------------------------
# Fences: hue windows
# ---------------------------------------------------------------------------


def test_project_hue_clamps_into_window_with_margin():
    # deep outside -> clamped to the inner boundary (margin kept inside)
    assert mp.project_hue("keyword", 180.0) == 275.0 + mp.HUE_MARGIN
    assert mp.project_hue("keyword", 359.0) == 335.0 - mp.HUE_MARGIN
    # already inside -> unchanged
    assert mp.project_hue("string", 130.0) == 130.0
    # windows that start at 0 treat near-360 hues circularly
    assert mp.project_hue("builtin", 359.0) == mp.HUE_MARGIN
    # tag has two allowed families; 170 sits between them -> nearest point
    assert mp.project_hue("tag", 170.0) in (165.0 - mp.HUE_MARGIN, 180.0 + mp.HUE_MARGIN)


def test_every_committed_candidate_b_hue_is_inside_its_window():
    # the fences were built around the committed hues; candidate-b night must
    # be fence-compliant by construction (projection is a no-op on it)
    committed = Palette.from_yaml(
        REPO / "themes/candidates/candidate-b-balanced.night.yaml"
    )
    for role in mp.HUE_WINDOWS:
        h = hex_to_oklch(committed[role])[2]
        assert mp.project_hue(role, h) == h, role


# ---------------------------------------------------------------------------
# Fences: chroma ceilings (class caps + the 70% gamut rule)
# ---------------------------------------------------------------------------


def test_chroma_ceiling_under_class_cap_and_gamut_fraction():
    p = _problem()
    for role in p.chromatic:
        cap = mp.chroma_cap(role)
        for L, h in ((0.24, 100.0), (0.80, 200.0), (0.88, 20.0)):
            ceil = p.chroma_ceiling(role, L, h)
            assert ceil <= cap, (role, ceil, cap)
            assert ceil <= 0.70 * max_chroma(L, h, "srgb") + 1e-12, (role, L, h)
            assert ceil >= 0.0


def test_fence_audit_flags_cap_and_gamut_fraction_violations():
    p = _problem()
    # a COMPLETE palette as the audit expects (scaffold + fenced baseline)
    hexes = p.hexes(p.baseline_lch)
    # a syntax role pushed over the class cap (0.12): fence_audit must flag it
    hexes["keyword"] = oklch_to_hex((0.80, 0.20, 310.0))
    bad = p.fence_audit(hexes)
    assert any("chroma keyword" in b for b in bad)
    # the 70% rule: full gamut-edge chroma in a sector where the class cap
    # does not bind first (diagnostics cap 0.16 vs the gamut edge ~0.20)
    L, h = 0.75, 30.0
    assert max_chroma(L, h, "srgb") * 0.70 < 0.16  # the fraction is the binder
    hexes["error"] = oklch_to_hex((L, max_chroma(L, h, "srgb"), h))
    bad = p.fence_audit(hexes)
    assert any("gamut-fraction error" in b for b in bad)


# ---------------------------------------------------------------------------
# Fenced repair
# ---------------------------------------------------------------------------


def test_repair_ink_fenced_returns_fence_legal_or_none():
    p = _problem()
    hexes = p.hexes(p.baseline_lch)  # complete palette (all surfaces present)
    for role in ("keyword", "string", "error"):
        got = mp.repair_ink_fenced(p, role, 0.5, 0.5, 300.0, hexes)
        if got is None:
            continue  # legal: floor unreachable inside the fence -> rejected
        L, C, h = got
        lo, hi = p.l_range(role)
        assert lo - 1e-9 <= L <= hi + 1e-9
        assert C <= p.chroma_ceiling(role, L, h) + 1e-9
        assert any(w[0] <= h <= w[1] for w in mp.HUE_WINDOWS[role])


def test_repair_surface_fenced_never_leaves_lightness_fence():
    p = _problem()
    got = mp.repair_surface_fenced(p, "selection", 0.45, 0.10, 240.0)
    assert got is not None
    L = got[0]
    lo = max(p.l_range("selection")[0], p.scaffold["bg"][0] + 0.01)
    assert lo - 1e-9 <= L <= p.l_range("selection")[1] + 1e-9


# ---------------------------------------------------------------------------
# Reduced fixed-seed search run
# ---------------------------------------------------------------------------


def _reduced_run():
    problem = _problem()
    results = np.run_search(
        problem, seed=7, restarts=2, samples=4, refine_passes=3, refine_top=1
    )
    assert results, "search returned no results"
    best = results[0]
    state = dict(best["state"])
    state = mp.place_unconstrained_fenced(problem, state)
    mp.enforce_same_family_min(problem, state)
    return problem, state, best["J"]


def test_reduced_run_fences_hold_on_output():
    problem, state, _ = _reduced_run()
    hexes = problem.hexes(state)
    assert not problem.fence_audit(hexes), problem.fence_audit(hexes)
    assert not problem.fence_audit_state(state), problem.fence_audit_state(state)


def test_reduced_run_wcag_over_surfaces_holds():
    problem, state, _ = _reduced_run()
    hexes = problem.hexes(state)
    # include_inherited=False: scaffold-vs-scaffold violations (search surfaces
    # outside the reduced subset, e.g. fg_muted over candidate-b's own
    # search_match) are inherited from the committed palette; the FULL run
    # optimizes every co-occurring surface and asserts zero violations.
    bad = np.check_feasible(problem, hexes, include_inherited=False)
    assert not bad, f"hard-constraint violations: {bad}"


def test_reduced_run_number_constant_separated():
    # debt 1: the committed candidates render number and constant
    # byte-identically (dE 0.000); the same_family min-distance gate must
    # leave them at dE >= 0.03 after even a tiny run.
    problem, state, _ = _reduced_run()
    hexes = problem.hexes(state)
    de = mp.number_constant_de(problem, hexes)
    assert de >= problem.th_anticollapse, f"number/constant dE {de:.4f}"


def test_reduced_run_beats_candidate_b_worst_margin():
    problem, _, j = _reduced_run()
    baseline = np.evaluate(problem, problem.hexes(problem.baseline_lch))
    assert j > baseline["J"]


def test_reduced_run_deterministic():
    _, state1, j1 = _reduced_run()
    _, state2, j2 = _reduced_run()
    assert j1 == j2
    assert state1 == state2


def test_written_yaml_is_loadable_non_candidate_palette(tmp_path):
    problem, state, _ = _reduced_run()
    out = tmp_path / "middle-test.night.yaml"
    mp.write_palette_yaml(out, "middle-test", state, problem, 7, {"j": 0.0})
    pal = Palette.from_yaml(out)
    assert not pal.is_candidate
    assert pal.variant == "night"
    # complete palette: scaffold + optimised roles = all 40 committed roles
    assert len(pal) == 40
    # the scaffold must be verbatim: bg/fg match candidate-b's authored values
    committed = Palette.from_yaml(
        REPO / "themes/candidates/candidate-b-balanced.night.yaml"
    )
    assert pal["bg"] == committed["bg"]
    assert pal["fg"] == committed["fg"]
    # byte-stable on rewrite
    out2 = tmp_path / "middle-test-2.night.yaml"
    mp.write_palette_yaml(out2, "middle-test", state, problem, 7, {"j": 0.0})
    assert out.read_bytes() == out2.read_bytes()
