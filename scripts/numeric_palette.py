"""Numeric-first Night palette optimizer (NON-CANDIDATE exploration).

Branch rationale (dev/numeric-palettes)
---------------------------------------
The committed Night palettes of all three candidates look near-identical.
Verified root cause: the Layer-2 transform pins every role's LIGHTNESS to
APCA contrast-band centres shared by all candidates, shrinks chroma through a
multiplicative chain (night chroma_attenuation x night_adaptation x class
fractions x absolute caps ~0.14-0.20), and shares hue anchors, so categorical
roles land at C ~= 0.02-0.10 on almost the same lightness -- one theme, three
labels.  The owner suspects a local minimum of the project's own taste layer.

This script THROWS OUT the taste layer and keeps only technical constraints,
then searches directly over per-role OKLCH to see where the numeric frontier
actually sits.  Whether that frontier is *desirable* is a human decision; every
artifact it writes is labelled NON-CANDIDATE.

Thrown out (taste; per the owner's instruction)
-----------------------------------------------
* contrast-band lightness targets (APCA centres) and the salience-driven
  lightness hierarchy;
* chroma budgets: class fractions, multiplicative attenuation, night
  adaptation, absolute ceilings;
* the "5 hue families" economy and same-family upper bounds -- each role may
  claim its own hue;
* warm-anchor hue adaptation, hue sharing across candidates, the night
  foreground lightness ceiling, and the chroma-class vocabulary.

Kept (technical; each with its justification)
---------------------------------------------
1. WCAG 2.x AA floors as HARD constraints, read from the role's
   ``accessibility_floor`` (roles.yaml) and resolved through
   ``spec/environments.yaml: accessibility_floors`` (body_text 4.5, non_text
   3.0).  WCAG 2.x is the compliance instrument; it is enforced against the
   background AND against every co-occurring surface an ink can land on
   (the spirit of ``model.CO_OCCURRING_SURFACES``).
2. sRGB gamut: chroma is projected to ``max_chroma(L, h)``; requested colours
   never exceed the display gamut.
3. The distance-matrix pair list with thresholds READ (never edited): the
   objective maximises the worst normalised margin ``dE(pair)/threshold`` over
   must_distinguish pairs under normal vision (0.13) and under simulated
   protan/deutan/tritan at severity 1.0 (0.09), with should_distinguish pairs
   (normal vision, 0.08) at a lower weight.  Legibility pairs already listed
   in the matrix (fg/bg etc.) are part of the same list.
4. Hue pinning across variants is NOT imposed here: this branch produces
   Night palettes only (night first and well).  If a numeric Night palette is
   ever promoted, its per-role hues would be the natural anchors for a
   day/evening re-solve -- documented in NUMERIC.md, not enforced in code.

Declared objective (exact)
--------------------------
For a palette P (all margins normalised by their class threshold):

    M_norm   = min over must pairs, normal vision, of dE / th_must_normal
    M_cvd    = min over must pairs x {protan, deutan, tritan}@1.0
               of dE / th_must_cvd
    M_should = min over should pairs, normal vision, of dE / th_should
    M_anti   = min over categorical pairs NOT already in the matrix, of
               dE / same_family.min_distance   (the matrix's own
               "still not identical" distance, READ from the same file)

    J(P)  = min( M_norm, M_cvd, SHOULD_WEIGHT * M_should, M_anti )

J > 1 means every must pair clears its threshold under all four vision
conditions.  SHOULD_WEIGHT = 2.0: a should pair binds only once its margin
falls below half the worst must margin (lower weight, as instructed).  The
anti-collapse floor exists because the matrix's only link for pairs like
number/constant was the same-family economy this branch throws out; without
the floor the objective is blind to them and they collapse to sampling noise
(dE 0.005 measured in the first smoke run).  It uses the min side of the
matrix's own same_family entry; the max side (the hue economy) stays thrown
out.  Greedy acceptance is lexicographic on (J, J2) where J2 is the MEAN of
all normalised constraint terms -- a tie-break that keeps the search moving
on max-min plateaus without ever trading the worst pair away.

Method (deterministic, seeded)
------------------------------
Multi-start structured sampling (evenly spread hue ladders / candidate-B
seeds / free hues; lightness ladders or uniform; chroma biased high as a
fraction of ``max_chroma``) followed by greedy coordinate refinement on the
FULL objective (normal + CVD -- the coloraide Brettel simulation measures
~20-40 us/call here, so no two-stage proxy is needed).  Every move is
repaired into the feasible set: chroma projected into the sRGB gamut, ink
lightness raised until all floors hold, surface lightness lowered until every
scaffold ink keeps its floor.  The neutral scaffold (canvas, fg tiers,
punctuation-adjacent neutrals, line numbers, ui_inactive, active_line) is
copied VERBATIM from themes/candidates/candidate-b-balanced.night.yaml -- the
authored canvas is the WCAG reference and stays; only the chromatic subset is
optimised.

Outputs (out/numeric-night/ by default)
---------------------------------------
numeric-nNN.night.yaml  -- palettes in the repo OKLCH yaml format,
                           ``candidate: false``, NON-CANDIDATE notes
metrics.json / .txt     -- numeric vs candidate-b vs candidate-c night
variants.html           -- dark side-by-side page (swatches + R specimen)
vscode-preview/         -- top-3 extension dir, also installed to the real
                           extensions directory unless --no-install

Usage:
    uv run python scripts/numeric_palette.py            # full run (~minutes)
    uv run python scripts/numeric_palette.py --restarts 4 --samples 8   # smoke

NON-CANDIDATE: everything this script writes is exploration material.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
import time
from functools import lru_cache
from itertools import combinations
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from grotto.color import hex_to_oklch, max_chroma, oklch_to_hex  # noqa: E402
from grotto.contrast import wcag_contrast  # noqa: E402
from grotto.cvd import CVD_TYPES, simulate  # noqa: E402
from grotto.distance import breakdown  # noqa: E402
from grotto.environments import Environments  # noqa: E402
from grotto.model import CO_OCCURRING_SURFACES  # noqa: E402
from grotto.spec import DistanceSpec, Palette, RoleSpec  # noqa: E402

# ===========================================================================
# Declared problem definition (all of it technical, none of it taste)
# ===========================================================================

#: The committed palette that supplies the neutral scaffold verbatim.
SCAFFOLD_SOURCE = "candidate-b-balanced.night.yaml"

#: Neutral roles copied verbatim: the authored canvas (WCAG reference) plus
#: the neutral fg tiers, punctuation-adjacent neutrals, line numbers, chrome
#: borders, the current-line band and the style-differentiated neutrals.
#: Everything NOT in CHROMATIC_ROLES is scaffold; the explicit list documents
#: intent and is asserted against the committed palette at load time.
SCAFFOLD_ROLES = (
    "bg", "bg_elevated", "bg_overlay",
    "fg", "fg_secondary", "fg_muted",
    "comment", "docstring", "punctuation", "operator",
    "line_number", "line_number_active", "ui_inactive",
    "active_line", "deprecated", "parameter", "property",
)

#: The chromatic subset the optimizer owns: syntax roles, diagnostics, the
#: highlight surfaces (selection / search / diff / debug) and the two
#: chromatic border roles.  Everything the taste layer used to derive.
CHROMATIC_ROLES = (
    "keyword", "string", "number", "constant", "type", "function",
    "builtin", "decorator", "namespace", "tag",
    "error", "warning", "info", "success",
    "selection", "search_match", "search_match_current",
    "diff_added", "diff_removed", "diff_changed", "debug_current",
    "focus", "breakpoint",
)

#: Categorical roles for the metrics: the syntax colour categories a reader
#: must tell apart while scanning code.  Declared, not tuned.
CATEGORICAL_ROLES = (
    "keyword", "string", "number", "constant", "type", "function",
    "builtin", "decorator", "namespace", "tag",
)

#: Additional swatch strips on the HTML page (beyond the categorical set).
DIAGNOSTIC_SWATCH_ROLES = ("error", "warning", "info", "success", "focus", "breakpoint")
SURFACE_SWATCH_ROLES = (
    "selection", "search_match", "search_match_current",
    "diff_added", "diff_removed", "diff_changed", "debug_current", "active_line",
)

#: Objective weights (declared here and in NUMERIC.md).
SHOULD_WEIGHT = 2.0

#: Chroma sampling bias: fraction of max_chroma, f = 1 - CHROMA_BIAS*u^2.
CHROMA_BIAS = 0.35

#: Deterministic greedy move set (no RNG in refinement).
HUE_STEPS = (6.0, 15.0, 35.0)
L_STEPS = (0.02, 0.05)
F_STEPS = (0.12, 0.30)

DEFAULT_SEED = 20260815

#: Extension install target (the owner's real VS Code extensions dir).
VSCODE_INSTALL_DIR = Path("/mnt/c/Users/m0hawk/.vscode/extensions/grotto-numeric-exploration")


# ===========================================================================
# Cached colour primitives (lru so refinement revisits coordinates cheaply)
# ===========================================================================


@lru_cache(maxsize=400_000)
def _oklab_of(hx: str) -> tuple[float, float, float]:
    from grotto.color import oklch_to_oklab

    return oklch_to_oklab(hex_to_oklch(hx))


@lru_cache(maxsize=300_000)
def _sim_oklab(hx: str, kind: str) -> tuple[float, float, float]:
    """OKLab of the Brettel@1.0 simulation of ``hx`` (cached across the run)."""
    return _oklab_of(simulate(hx, kind, 1.0))


@lru_cache(maxsize=200_000)
def _maxc(Lr: float, hr: float) -> float:
    """max_chroma at (rounded) L, h -- the sRGB gamut ceiling for chroma."""
    return max_chroma(Lr, hr, "srgb")


def maxc(L: float, h: float) -> float:
    return _maxc(round(L, 4), round(h, 3) % 360.0)


def project_chroma(L: float, C: float, h: float) -> tuple[float, float, float]:
    """Project (L, C, h) into the sRGB gamut by clipping chroma (technical
    constraint 2).  Lightness and hue are preserved; the colour emitted is
    always displayable."""
    cmax = maxc(L, h)
    return (L, min(C, cmax), h)


def _dE(lab_a: tuple, lab_b: tuple) -> float:
    return math.dist(lab_a, lab_b)


def _load_scaffold_source() -> dict[str, tuple[float, float, float]]:
    raw = yaml.safe_load((REPO / "themes/candidates" / SCAFFOLD_SOURCE).read_text())
    return {
        r: (float(v["L"]), float(v["C"]), float(v["h"]))
        for r, v in raw["colors"].items()
    }


# ===========================================================================
# Problem: the technical constraint set read from the committed specs
# ===========================================================================


class NumericProblem:
    """Everything the optimizer is allowed to know, all of it technical.

    * the scaffold palette (verbatim neutral roles from the committed
      candidate-b night palette);
    * WCAG floors per role (roles.yaml accessibility_floor, resolved through
      environments.yaml accessibility_floors);
    * the must/should pair lists and thresholds from distance-matrix.yaml,
      filtered to roles present in this problem (a reduced chromatic subset is
      how the unit tests exercise the machinery);
    * the co-occurring surface set inks must stay legible over.
    """

    def __init__(self, chromatic: tuple[str, ...] = CHROMATIC_ROLES):
        self.roles_spec = RoleSpec.load(REPO / "spec/roles.yaml")
        self.envs = Environments.load(REPO / "spec/environments.yaml")
        self.dists = DistanceSpec.load(
            REPO / "spec/distance-matrix.yaml", self.roles_spec
        )
        authored = _load_scaffold_source()
        unknown = [r for r in chromatic if r not in authored]
        if unknown:
            raise ValueError(f"chromatic roles not in scaffold source: {unknown}")
        # Integrity of the role split: a reduced chromatic subset (tests) makes
        # the leftover chromatic roles de-facto scaffold, but the split must
        # still cover the committed palette exactly and never move a declared
        # scaffold role into the optimized set.
        assert set(chromatic) <= set(CHROMATIC_ROLES), (
            "optimized roles must come from CHROMATIC_ROLES; the neutral "
            "scaffold is never optimized"
        )
        assert set(authored) == set(SCAFFOLD_ROLES) | set(CHROMATIC_ROLES), (
            "scaffold role list drifted from the committed palette; update "
            "SCAFFOLD_ROLES/CHROMATIC_ROLES together"
        )
        self.chromatic = tuple(chromatic)
        self.scaffold = {r: lch for r, lch in authored.items() if r not in chromatic}
        self.present = set(self.scaffold) | set(self.chromatic)
        self.scaffold_hex = {
            r: oklch_to_hex(project_chroma(*lch)) for r, lch in self.scaffold.items()
        }
        #: candidate-b's authored coordinates for the chromatic roles -- the
        #: baseline the optimizer is compared against (it IS candidate-b night).
        self.baseline_lch = {r: lch for r, lch in authored.items() if r in chromatic}

        # -- WCAG floors, resolved via environments.yaml -------------------
        af = self.envs.accessibility_floors
        self.floors: dict[str, float] = {}
        for name, role in self.roles_spec.roles.items():
            if name not in self.present:
                continue
            if role.accessibility_floor == "body_text":
                self.floors[name] = float(af["body_text_wcag"])
            elif role.accessibility_floor == "non_text":
                self.floors[name] = float(af["non_text_wcag"])
            else:
                self.floors[name] = 0.0

        # -- pair lists (thresholds READ, never edited) --------------------
        th = self.dists.thresholds
        self.th_must_normal = float(th["must_distinguish"]["normal_vision"])
        self.th_must_cvd = float(th["must_distinguish"]["cvd_dichromat"])
        self.th_should = float(th["should_distinguish"]["normal_vision"])
        # Anti-collapse floor: the matrix's OWN "still not identical" distance
        # (same_family.min_distance) applied to categorical pairs it does not
        # otherwise constrain.  Without it, pairs like number/constant --
        # whose only spec link was the same-family economy this branch throws
        # out -- collapse to sampling noise (measured dE 0.005 in the first
        # smoke run).  This is the min side of the same_family entry only;
        # the max side (the hue economy) stays thrown out.
        self.th_anticollapse = float(th["same_family"]["min_distance"])
        self.must_pairs = sorted(
            (c.a, c.b)
            for c in self.dists.of_kind("must_distinguish")
            if c.a in self.present and c.b in self.present
        )
        self.should_pairs = sorted(
            (c.a, c.b)
            for c in self.dists.of_kind("should_distinguish")
            if c.a in self.present and c.b in self.present
        )

        # -- co-occurring surfaces: ink must keep its floor over each ------
        self.surfaces = tuple(s for s in CO_OCCURRING_SURFACES if s in self.present)
        # FIXED scaffold inks with a floor constrain surface lightness (they
        # cannot move, so the cap they induce is exact); chromatic inks adapt
        # through their own repair.
        self.scaffold_floor_inks = tuple(
            r
            for r in sorted(self.scaffold)
            if self.floors.get(r, 0.0) > 0.0
            and self.roles_spec.roles[r].paint == "ink"
        )
        self.categorical = tuple(r for r in CATEGORICAL_ROLES if r in self.present)
        self.paint = {r: self.roles_spec.roles[r].paint for r in self.chromatic}
        #: term table shared by evaluate() and the greedy loop (see evaluate).
        self.terms = self._build_terms()

    # -- term table ----------------------------------------------------------
    #
    # One entry per constraint term of the declared objective:
    #   ('must', pair, 'normal' | cvd kind, threshold)  -> margin = dE / threshold
    #   ('should', pair, 'normal', threshold)
    # Flattening the pairs this way lets the greedy loop recompute ONLY the
    # terms touching a moved role and take mins over the rest from cache.

    def _build_terms(self) -> list[dict]:
        terms = []
        for a, b in self.must_pairs:
            terms.append({"cls": "must", "a": a, "b": b, "kind": "normal",
                          "th": self.th_must_normal})
            for kind in CVD_TYPES:
                terms.append({"cls": "must", "a": a, "b": b, "kind": kind,
                              "th": self.th_must_cvd})
        for a, b in self.should_pairs:
            terms.append({"cls": "should", "a": a, "b": b, "kind": "normal",
                          "th": self.th_should})
        constrained = {frozenset(p) for p in self.must_pairs + self.should_pairs}
        chromatic = set(self.chromatic)
        for a, b in combinations(self.categorical, 2):
            if frozenset((a, b)) in constrained:
                continue
            # Only pairs the search can actually influence: a scaffold-scaffold
            # anticollapse pair (e.g. number/constant in a REDUCED problem,
            # where they stay verbatim from candidate-b) would pin J at 0 for
            # a reason the optimizer cannot fix.  In the full problem every
            # categorical role is chromatic, so nothing is excluded.
            if a not in chromatic and b not in chromatic:
                continue
            terms.append({"cls": "anticollapse", "a": a, "b": b, "kind": "normal",
                          "th": self.th_anticollapse})
        term_by_role: dict[str, list[int]] = {}
        for i, t in enumerate(terms):
            for r in (t["a"], t["b"]):
                term_by_role.setdefault(r, []).append(i)
        self.term_ids_by_role = term_by_role
        self.anticollapse_pairs = tuple(
            (t["a"], t["b"]) for t in terms if t["cls"] == "anticollapse"
        )
        return terms

    def hexes(self, state: dict[str, tuple[float, float, float]]) -> dict[str, str]:
        out = dict(self.scaffold_hex)
        for r, lch in state.items():
            out[r] = oklch_to_hex(project_chroma(*lch))
        return out

    def term_values(self, hexes: dict[str, str]) -> list[float]:
        """Normalised margin per term, in self.terms order."""
        out = []
        for t in self.terms:
            if t["kind"] == "normal":
                out.append(_dE(_oklab_of(hexes[t["a"]]), _oklab_of(hexes[t["b"]])) / t["th"])
            else:
                out.append(
                    _dE(_sim_oklab(hexes[t["a"]], t["kind"]),
                        _sim_oklab(hexes[t["b"]], t["kind"])) / t["th"]
                )
        return out


def _weighted_min_and_mean(terms: list[dict], vals: list[float]) -> tuple[float, float, int]:
    """(J, J2, argmin term index) for the declared objective."""
    jmin = 1e18
    argmin = -1
    total = 0.0
    for i, (t, v) in enumerate(zip(terms, vals)):
        w = SHOULD_WEIGHT if t["cls"] == "should" else 1.0  # must + anticollapse: 1.0
        wv = w * v
        if wv < jmin:
            jmin, argmin = wv, i
        total += v
    return jmin, (total / len(vals) if vals else 0.0), argmin


def evaluate(problem: NumericProblem, hexes: dict[str, str]) -> dict:
    """Full evaluation: per-class worst margins, J, J2, argmin term."""
    vals = problem.term_values(hexes)
    j, j2, arg = _weighted_min_and_mean(problem.terms, vals)
    must_n = min(
        (v for t, v in zip(problem.terms, vals) if t["cls"] == "must" and t["kind"] == "normal"),
        default=1e9,
    )
    must_c = min(
        (v for t, v in zip(problem.terms, vals) if t["cls"] == "must" and t["kind"] != "normal"),
        default=1e9,
    )
    should_n = min(
        (v for t, v in zip(problem.terms, vals) if t["cls"] == "should"),
        default=1e9,
    )
    antic = min(
        (v for t, v in zip(problem.terms, vals) if t["cls"] == "anticollapse"),
        default=1e9,
    )
    t = problem.terms[arg]
    return {
        "J": j, "J2": j2, "vals": vals,
        "min_must_normal": must_n, "min_must_cvd": must_c, "min_should": should_n,
        "min_anticollapse": antic,
        "argmin": (t["a"], t["b"], f"{t['cls']}{'_' + t['kind'] if t['kind'] != 'normal' else '_normal'}"),
    }


# ===========================================================================
# Feasibility: WCAG-feasible lightness intervals and repair
# ===========================================================================


def check_feasible(
    problem: NumericProblem, hexes: dict[str, str], include_inherited: bool = True
) -> list[str]:
    """All hard-constraint violations of a COMPLETE palette (empty = feasible).

    Checks exactly the two technical gates: every ink/border role with a WCAG
    floor clears it against the background and every co-occurring surface,
    and every role is inside the sRGB gamut.  A violation where BOTH the ink
    and the surface are scaffold roles is INHERITED from the committed
    candidate-b palette (the optimizer cannot move either endpoint); such
    entries are tagged ``inherited:`` and can be excluded with
    ``include_inherited=False`` -- used by the reduced-subset unit tests.  In
    the full problem every co-occurring surface except active_line is
    optimized, and scaffold inks pass over active_line, so nothing is
    inherited there.
    """
    from grotto.color import gamut_status

    out = []
    chromatic = set(problem.chromatic)
    for r, floor in sorted(problem.floors.items()):
        if floor <= 0.0 or r not in hexes:
            continue
        if problem.roles_spec.roles[r].paint not in ("ink", "border"):
            continue
        for sname, shx in [("bg", hexes["bg"])] + [(s, hexes[s]) for s in problem.surfaces]:
            if wcag_contrast(hexes[r], shx) >= floor:
                continue
            inherited = r not in chromatic and sname not in chromatic
            if inherited and not include_inherited:
                continue
            tag = "inherited: " if inherited else ""
            out.append(f"{tag}wcag {r} on {sname}: {wcag_contrast(hexes[r], shx):.3f} < {floor}")
    for r, hx in sorted(hexes.items()):
        if not gamut_status(hex_to_oklch(hx)).in_srgb:
            out.append(f"gamut {r}: {hx} outside sRGB")
    return out


def wcag_at(L: float, C: float, h: float, ref_hex: str) -> float:
    """WCAG contrast of the quantised colour at (L, C, h) vs a fixed hex.

    Computed on the 8-bit hex the palette will actually ship, so feasibility
    and the final report agree by construction.
    """
    return wcag_contrast(oklch_to_hex((L, C, h)), ref_hex)


def feasible_l_interval(
    ref_hex: str, floor: float, h: float, c_frac: float = 1.0,
    tol: float = 1e-3,
) -> tuple[float, float] | None:
    """WCAG-feasible lightness interval [lo, 1.0] against ``ref_hex``.

    Dark polarity (the night canvas is darker than any ink): contrast rises
    with L, so the feasible set is an upper interval.  ``lo`` is found by
    bisection at chroma ``c_frac * max_chroma(L, h)`` -- the interval is exact
    for a colour that will sit at that fraction of the gamut edge.  Returns
    None when even L=1.0 cannot reach the floor (a technical impossibility
    for this reference, not a taste judgement).
    """
    def ok(L: float) -> bool:
        C = c_frac * maxc(L, h)
        return wcag_at(L, C, h, ref_hex) >= floor

    if not ok(1.0):
        return None
    if ok(0.0):
        return (0.0, 1.0)
    lo, hi = 0.0, 1.0
    while hi - lo > tol:
        mid = (lo + hi) / 2
        if ok(mid):
            hi = mid
        else:
            lo = mid
    return (round(hi, 4), 1.0)


def repair_ink(
    problem: NumericProblem,
    role: str,
    L: float,
    C: float,
    h: float,
    hexes: dict[str, str],
) -> tuple[float, float, float] | None:
    """Bring an ink/border colour into the feasible set.

    Chroma is projected into the gamut first; then lightness is raised (dark
    polarity) until the role's WCAG floor holds against the background and
    EVERY co-occurring surface present.  The climb holds chroma fixed (cheap:
    hex + WCAG per step) and re-clips it once at the accepted lightness --
    the gamut edge moves smoothly in L, so a re-verification pass covers the
    rare case where the clip changed luminance enough to matter.  Returns
    None if L=0.99 still fails (cannot happen with this canvas; the escape
    keeps the search total).
    """
    floor = problem.floors[role]
    L = min(max(L, 0.30), 0.99)
    refs = [problem.scaffold_hex["bg"]] + [hexes[s] for s in problem.surfaces]

    def ok(Lx: float, Cx: float) -> bool:
        hx = oklch_to_hex((Lx, Cx, h))
        return all(wcag_contrast(hx, ref) >= floor for ref in refs)

    C0 = min(C, maxc(L, h))
    Lc = L
    for _ in range(80):
        if ok(Lc, C0):
            break
        Lc = min(Lc + 0.01, 0.99)
    else:
        return None
    C2 = min(C, maxc(Lc, h))  # gamut may have shrunk at the accepted L
    if ok(Lc, C2):
        return (Lc, C2, h)
    for _ in range(20):  # rare: the clip cost just enough luminance to matter
        Lc = min(Lc + 0.01, 0.99)
        C2 = min(C, maxc(Lc, h))
        if ok(Lc, C2):
            return (Lc, C2, h)
    return None


def repair_surface(
    problem: NumericProblem,
    L: float,
    C: float,
    h: float,
) -> tuple[float, float, float] | None:
    """Bring a highlight surface into the feasible set.

    The binding technical constraint on a surface is the legibility of the
    FIXED scaffold inks that sit on it: the surface may not get so light that
    any scaffold ink loses its WCAG floor.  Lightness is lowered until every
    scaffold ink passes; the surface also stays at/above the canvas +0.01 so
    elevation remains possible.  Chromatic inks adapt through their own
    repair against the final surfaces.  Same hold-chroma / re-clip pattern as
    repair_ink.
    """
    bg_L = problem.scaffold["bg"][0]
    L = min(max(L, bg_L + 0.01), 0.60)
    inks = [
        (problem.floors[r], problem.scaffold_hex[r])
        for r in problem.scaffold_floor_inks
    ]

    def ok(Lx: float, Cx: float) -> bool:
        hx = oklch_to_hex((Lx, Cx, h))
        return all(wcag_contrast(ink_hex, hx) >= floor for floor, ink_hex in inks)

    C0 = min(C, maxc(L, h))
    Lc = L
    for _ in range(80):
        if ok(Lc, C0):
            break
        Lc = max(Lc - 0.01, bg_L + 0.01)
    else:
        return None
    C2 = min(C, maxc(Lc, h))
    if ok(Lc, C2):
        return (Lc, C2, h)
    for _ in range(20):
        Lc = max(Lc - 0.01, bg_L + 0.01)
        C2 = min(C, maxc(Lc, h))
        if ok(Lc, C2):
            return (Lc, C2, h)
        if Lc <= bg_L + 0.01:
            break
    # last resort: zero chroma at canvas+0.01 (maximally canvas-like)
    if ok(bg_L + 0.01, 0.0):
        return (bg_L + 0.01, 0.0, h)
    return None


# ===========================================================================
# Search: multi-start structured sampling + greedy coordinate refinement
# ===========================================================================


def _initial_state(
    problem: NumericProblem, rng: random.Random, kind: str
) -> dict[str, tuple[float, float, float]]:
    """One structured sample of the full chromatic subset.

    kind: 'ladder'  -- evenly spread hue ladder, shuffled assignment;
          'bladder' -- ladder + shuffled lightness ladder for the inks;
          'bseed'   -- candidate-B hues + wide jitter;
          'free'    -- uniform hues.
    Lightness/chroma are repaired into the feasible set afterwards, so every
    sample is already a legal palette.
    """
    n = len(problem.chromatic)
    if kind in ("ladder", "bladder"):
        offset = rng.uniform(0, 360)
        hues = [(offset + i * 360.0 / n + rng.uniform(-8, 8)) % 360.0 for i in range(n)]
        rng.shuffle(hues)
    elif kind == "bseed":
        hues = [
            (h0 + rng.uniform(-35, 35)) % 360.0
            for h0 in (problem.baseline_lch[r][2] for r in problem.chromatic)
        ]
    else:
        hues = [rng.uniform(0, 360) for _ in range(n)]

    inks = [r for r in problem.chromatic if problem.paint[r] in ("ink", "border")]
    l_ladder = None
    if kind == "bladder" and len(inks) > 1:
        lo, hi = 0.55, 0.96
        l_ladder = [
            lo + (hi - lo) * i / (len(inks) - 1) + rng.uniform(-0.03, 0.03)
            for i in range(len(inks))
        ]
        rng.shuffle(l_ladder)

    state: dict[str, tuple[float, float, float]] = {}
    hexes = dict(problem.scaffold_hex)
    li = 0
    # Dependency order matters here: surfaces depend only on the FIXED
    # scaffold inks, so they are placed first; inks are then repaired against
    # the final surfaces (their floors must hold over every co-occurring
    # surface, not just the canvas).
    ordered = [r for r in problem.chromatic if problem.paint[r] == "surface"]
    ordered += [r for r in problem.chromatic if problem.paint[r] != "surface"]
    hue_of = dict(zip(problem.chromatic, hues))
    for r in ordered:
        h = hue_of[r]
        f = 1.0 - CHROMA_BIAS * rng.random() ** 2
        if problem.paint[r] in ("ink", "border"):
            L = l_ladder[li] if l_ladder is not None else rng.uniform(0.50, 0.97)
            li += 1
            got = repair_ink(problem, r, L, f * maxc(L, h), h, hexes)
        else:
            L = rng.uniform(problem.scaffold["bg"][0] + 0.02, 0.45)
            got = repair_surface(problem, L, f * maxc(L, h), h)
        if got is None:  # cannot happen with this canvas; keeps search total
            got = (0.90 if problem.paint[r] in ("ink", "border") else 0.24, 0.0, h)
        state[r] = got
        hexes[r] = oklch_to_hex(project_chroma(*got))
    return state


#: Deterministic move list: (axis, delta) pairs applied to (h, L, f).
MOVES = tuple(
    [("h", d) for d in HUE_STEPS]
    + [("h", -d) for d in HUE_STEPS]
    + [("L", d) for d in L_STEPS]
    + [("L", -d) for d in L_STEPS]
    + [("f", d) for d in F_STEPS]
    + [("f", -d) for d in F_STEPS]
)


def _apply_move(
    problem: NumericProblem, role: str, lch: tuple[float, float, float],
    axis: str, d: float, hexes: dict[str, str],
) -> tuple[float, float, float] | None:
    """One repaired candidate for ``role``; None if infeasible."""
    L, C, h = lch
    cmax = maxc(L, h)
    f = C / cmax if cmax > 1e-9 else 0.0
    if axis == "h":
        h2 = (h + d) % 360.0
        L2, f2 = L, f
    elif axis == "L":
        L2, h2, f2 = min(max(L + d, 0.30), 0.99), h, f
    else:
        L2, h2 = L, h
        f2 = min(max(f + d, 0.0), 1.0)
    C2 = f2 * maxc(L2, h2)
    if problem.paint[role] in ("ink", "border"):
        return repair_ink(problem, role, L2, C2, h2, hexes)
    got = repair_surface(problem, L2, C2, h2)
    if got is None:
        return None
    # A surface may not strand a CHROMATIC ink below its floor: scaffold inks
    # are already guarded inside repair_surface (they are fixed), but the
    # chromatic inks are variables of the search.  Reject the move rather
    # than cascading re-repairs -- the greedy can raise the inks first and
    # retry the surface move on a later pass.
    surf_hex = oklch_to_hex(project_chroma(*got))
    for other in problem.chromatic:
        floor = problem.floors[other]
        if floor <= 0.0 or problem.paint[other] not in ("ink", "border"):
            continue
        if wcag_contrast(hexes[other], surf_hex) < floor:
            return None
    return got


def greedy_refine(
    problem: NumericProblem,
    state: dict[str, tuple[float, float, float]],
    max_passes: int,
) -> tuple[dict[str, tuple[float, float, float]], dict]:
    """Greedy coordinate refinement on the FULL objective (normal + CVD).

    For each chromatic role in a fixed order, try every deterministic move;
    each candidate is repaired into the feasible set and evaluated
    incrementally (only terms touching the role are recomputed).  Accept the
    best move when it lexicographically improves (J, J2): strict on J, with
    the mean-margin J2 as tie-break when J is flat -- max-min plateaus are
    exactly where the tie-break earns its keep, and it never trades the worst
    pair away.
    """
    hexes = problem.hexes(state)
    terms = problem.terms
    vals = problem.term_values(hexes)
    j, j2, _ = _weighted_min_and_mean(terms, vals)

    def eval_with(role: str, new_hex: str, vals: list[float]):
        """(J, J2, {term_idx: new_margin}) with only role's terms recomputed."""
        updates = {}
        for i in problem.term_ids_by_role[role]:
            t = terms[i]
            ha = new_hex if t["a"] == role else hexes[t["a"]]
            hb = new_hex if t["b"] == role else hexes[t["b"]]
            if t["kind"] == "normal":
                updates[i] = _dE(_oklab_of(ha), _oklab_of(hb)) / t["th"]
            else:
                updates[i] = _dE(_sim_oklab(ha, t["kind"]), _sim_oklab(hb, t["kind"])) / t["th"]
        jmin, total, arg = 1e18, 0.0, -1
        for i, v in enumerate(vals):
            v = updates.get(i, v)
            w = SHOULD_WEIGHT if terms[i]["cls"] == "should" else 1.0
            wv = w * v
            if wv < jmin:
                jmin, arg = wv, i
            total += v
        return jmin, total / len(vals), updates

    for _pass in range(max_passes):
        improved = False
        for role in problem.chromatic:
            if not problem.term_ids_by_role.get(role):
                # Role appears in NO matrix pair: the objective cannot see it.
                # It is placed deterministically after refinement by
                # place_unconstrained(); refining it here would be a no-op.
                continue
            best = None
            best_key = (j, j2)
            for axis, d in MOVES:
                got = _apply_move(problem, role, state[role], axis, d, hexes)
                if got is None:
                    continue
                new_hex = oklch_to_hex(project_chroma(*got))
                jj, jj2, updates = eval_with(role, new_hex, vals)
                if jj > best_key[0] + 1e-9 or (
                    jj > best_key[0] - 1e-9 and jj2 > best_key[1] + 1e-9
                ):
                    best_key = (jj, jj2)
                    best = (got, new_hex, updates)
            if best is not None:
                got, new_hex, updates = best
                state[role] = got
                hexes[role] = new_hex
                vals = [updates.get(i, v) for i, v in enumerate(vals)]
                j, j2 = best_key
                improved = True
        if not improved:
            break

    ev = evaluate(problem, hexes)
    return state, ev


def run_search(
    problem: NumericProblem,
    seed: int = DEFAULT_SEED,
    restarts: int = 20,
    samples: int = 16,
    refine_passes: int = 30,
    refine_top: int = 2,
    log=None,
) -> list[dict]:
    """Multi-start search; returns refined results sorted by (J, J2) desc.

    Each result: {'state': {...oklch per chromatic role...}, 'J', 'J2',
    'kind'}.  Deterministic for a fixed (problem, seed, restarts, samples).
    """
    rng = random.Random(seed)
    kinds = ("ladder", "bladder", "bseed", "free")
    results: list[dict] = []
    for ri in range(restarts):
        kind = kinds[ri % len(kinds)]
        pool = []
        for _ in range(samples):
            st = _initial_state(problem, rng, kind)
            ev = evaluate(problem, problem.hexes(st))
            pool.append((ev["J"], ev["J2"], st))
        pool.sort(key=lambda t: (-t[0], -t[1]))
        for _, _, st in pool[:refine_top]:
            st2, ev2 = greedy_refine(problem, st, refine_passes)
            results.append({"state": st2, "J": ev2["J"], "J2": ev2["J2"], "kind": kind})
        if log:
            best = max(results, key=lambda r: (r["J"], r["J2"]))
            log(f"[restart {ri + 1}/{restarts} kind={kind}] best J so far {best['J']:.4f}")
    results.sort(key=lambda r: (-r["J"], -r["J2"]))
    # drop byte-identical duplicates (same refined optimum from two restarts)
    seen: set = set()
    unique = []
    for r in results:
        key = tuple(
            sorted((k, round(v[0], 4), round(v[1], 4), round(v[2], 3)) for k, v in r["state"].items())
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(r)
    return unique


def diverse_pick(results: list[dict], k: int, min_mean_dh: float = 20.0) -> list[dict]:
    """A comparison set, not a leaderboard (same lesson as anchor_search):
    the score-sorted top of a max-min search is one narrow peak, and three
    palettes 3 hue-degrees apart are 'the same theme' to a human eye.  Keep
    the best, then greedily add the best-scoring palette whose MEAN circular
    hue distance from every already-picked palette is >= the threshold,
    relaxing by 5 degrees when the pool cannot fill k otherwise.
    """
    if not results:
        return []
    picked = [results[0]]
    threshold = min_mean_dh
    while len(picked) < k and threshold >= 0.0:
        for r in results[1:]:
            if len(picked) >= k:
                break
            ok = True
            for p in picked:
                dhs = [
                    abs(((a[2] - b[2] + 180.0) % 360.0) - 180.0)
                    for rk, pk in zip(sorted(r["state"]), sorted(p["state"]))
                    for a, b in [(r["state"][rk], p["state"][pk])]
                ]
                if statistics.fmean(dhs) < threshold:
                    ok = False
                    break
            if ok and r not in picked:
                picked.append(r)
        threshold -= 5.0
    return picked


def place_unconstrained(
    problem: NumericProblem,
    state: dict[str, tuple[float, float, float]],
) -> dict[str, tuple[float, float, float]]:
    """Deterministic placement for chromatic roles the distance matrix does
    not constrain at all (in the full set: namespace, tag, info,
    debug_current, breakpoint).

    The declared objective is blind to these roles -- leaving them at their
    sampled coordinates would make the reporting metric 'min categorical dE'
    reflect sampling noise rather than any requirement.  They are therefore
    placed on a coarse grid to MAXIMISE their minimum dE to every other
    chromatic role, subject to the same repairs (floors, gamut, surface
    caps).  Pure margin maximisation: no thresholds, no taste.  Ties break
    deterministically by grid order.
    """
    hexes = problem.hexes(state)
    free = [r for r in problem.chromatic if not problem.term_ids_by_role.get(r)]
    for r in free:
        is_ink = problem.paint[r] in ("ink", "border")
        Ls = [round(0.55 + 0.05 * i, 2) for i in range(9)] if is_ink else [
            round(problem.scaffold["bg"][0] + 0.02 + 0.03 * i, 3) for i in range(9)
        ]
        best, best_key = None, None
        for h in range(0, 360, 10):
            for L in Ls:
                for f in (1.0, 0.8):
                    C = f * maxc(L, float(h))
                    if is_ink:
                        got = repair_ink(problem, r, L, C, float(h), hexes)
                    else:
                        got = repair_surface(problem, L, C, float(h))
                    if got is None:
                        continue
                    hx = oklch_to_hex(project_chroma(*got))
                    if not is_ink:
                        # a moved surface must not strand any chromatic ink
                        stranded = any(
                            problem.floors[o] > 0.0
                            and problem.paint[o] in ("ink", "border")
                            and wcag_contrast(hexes[o], hx) < problem.floors[o]
                            for o in problem.chromatic
                        )
                        if stranded:
                            continue
                    lab = _oklab_of(hx)
                    dmin = min(
                        _dE(lab, _oklab_of(hexes[o]))
                        for o in problem.chromatic if o != r
                    )
                    key = (-round(dmin, 6), L, h, f)
                    if best_key is None or key < best_key:
                        best_key, best = key, got
        if best is not None:
            state[r] = best
            hexes[r] = oklch_to_hex(project_chroma(*best))
    return state


# ===========================================================================
# Reporting: metrics for numeric vs committed candidates
# ===========================================================================


def palette_metrics(problem: NumericProblem, hexes: dict[str, str]) -> dict:
    """Full metric block for one complete palette (any provenance).

    Everything is derived from the shipped hexes.  Labels never overstate:
    WCAG numbers are compliance checks; CVD margins come from the
    population-average Brettel dichromat models; APCA is not used here.
    """
    ev = evaluate(problem, hexes)
    cat = [r for r in problem.categorical if r in hexes]
    cat_de = [_dE(_oklab_of(hexes[a]), _oklab_of(hexes[b])) for a, b in combinations(cat, 2)]
    cat_C = [hex_to_oklch(hexes[r])[1] for r in cat]

    # WCAG audit: every ink/border role with a floor vs bg + co-occurring
    # surfaces (the spirit of model._evaluate_legibility, promoted to a gate).
    wcag_checks = []
    for r, floor in sorted(problem.floors.items()):
        if floor <= 0.0 or r not in hexes:
            continue
        if problem.roles_spec.roles[r].paint not in ("ink", "border"):
            continue
        for sname, shx in [("bg", hexes["bg"])] + [(s, hexes[s]) for s in problem.surfaces]:
            w = wcag_contrast(hexes[r], shx)
            wcag_checks.append(
                {"ink": r, "surface": sname, "wcag": round(w, 4),
                 "floor": floor, "ok": w >= floor}
            )
    min_wcag = min((c["wcag"] for c in wcag_checks), default=None)
    violations = [c for c in wcag_checks if not c["ok"]]

    # worst constraint terms (normalised margin ascending across all classes)
    rows = []
    for t, v in zip(problem.terms, ev["vals"]):
        rows.append(
            {"pair": [t["a"], t["b"]],
             "class": f"{t['cls']}_{t['kind']}",
             "de": round(v * t["th"], 4), "threshold": t["th"],
             "margin": round(v, 4)}
        )
    rows.sort(key=lambda r: (r["margin"], r["pair"], r["class"]))
    for r in rows:
        bd = breakdown(hexes[r["pair"][0]], hexes[r["pair"][1]])
        r["dL"], r["dC"], r["dH"] = round(bd.d_lightness, 4), round(bd.d_chroma, 4), round(bd.d_hue, 4)

    return {
        "worst_margin_overall": round(ev["J"], 4),
        # the mission-declared objective (matrix terms only, no anti-collapse
        # floor) -- the honest headline for numeric-vs-candidate comparison
        "worst_margin_matrix": round(
            min(ev["min_must_normal"], ev["min_must_cvd"], SHOULD_WEIGHT * ev["min_should"]),
            4,
        ),
        "argmin": {"pair": list(ev["argmin"][0:2]), "class": ev["argmin"][2]},
        "worst_margin_must_normal": round(ev["min_must_normal"], 4),
        "worst_margin_must_cvd": round(ev["min_must_cvd"], 4),
        "worst_margin_should": round(ev["min_should"], 4),
        "worst_margin_anticollapse": round(ev["min_anticollapse"], 4),
        "min_categorical_de": round(min(cat_de), 4) if cat_de else None,
        "mean_categorical_chroma": round(statistics.fmean(cat_C), 4) if cat_C else None,
        "total_categorical_chroma": round(sum(cat_C), 4) if cat_C else None,
        "min_wcag": min_wcag,
        "wcag_violations": len(violations),
        "wcag_check_count": len(wcag_checks),
        "worst_pairs": rows[:10],
    }


def binding_constraint(problem: NumericProblem, state: dict, hexes: dict[str, str]) -> dict:
    """What actually binds at the optimum: the argmin term's class, how many
    chromatic roles sit on the gamut edge (C >= 99.5% of max_chroma), how
    many inks sit on their WCAG-feasible lightness floor (worst surface
    ratio within 0.02 of the floor), and how many constraint terms sit
    within 5% of the worst weighted margin (max-min flattening).
    """
    ev = evaluate(problem, hexes)
    gamut_edge, wcag_edge = [], []
    for r, (L, C, h) in state.items():
        if C >= 0.995 * maxc(L, h):
            gamut_edge.append(r)
        floor = problem.floors[r]
        if floor > 0.0 and problem.paint.get(r) in ("ink", "border"):
            refs = [hexes["bg"]] + [hexes[s] for s in problem.surfaces]
            worst = min(wcag_contrast(hexes[r], s) for s in refs)
            if worst - floor < 0.02:
                wcag_edge.append(r)
    weighted = [
        (SHOULD_WEIGHT if t["cls"] == "should" else 1.0) * v
        for t, v in zip(problem.terms, ev["vals"])
    ]
    jmin = min(weighted)
    flat = sum(1 for w in weighted if w <= jmin * 1.05)
    return {
        "argmin_class": ev["argmin"][2],
        "argmin_pair": [ev["argmin"][0], ev["argmin"][1]],
        "n_gamut_edge_roles": len(gamut_edge),
        "gamut_edge_roles": sorted(gamut_edge),
        "n_wcag_edge_roles": len(wcag_edge),
        "wcag_edge_roles": sorted(wcag_edge),
        "n_terms": len(weighted),
        "n_terms_within_5pct_of_min": flat,
    }


# ===========================================================================
# Output writers (deterministic, byte-stable, NON-CANDIDATE labelled)
# ===========================================================================

YAML_HEADER = """\
# NON-CANDIDATE numeric-exploration palette (branch dev/numeric-palettes).
# Generated by scripts/numeric_palette.py -- deterministic seeded search over
# per-role OKLCH under TECHNICAL constraints only (WCAG floors, sRGB gamut,
# the distance-matrix pair list under normal + simulated dichromat vision).
# Every Layer-2 taste parameter (contrast bands, salience hierarchy, chroma
# budgets, hue-family economy) was discarded for this search; see NUMERIC.md.
# Promotion to a candidate is a HUMAN decision, not taken here."""


def write_palette_yaml(
    path: Path, name: str, state: dict, problem: NumericProblem, seed: int,
    extra_meta: dict,
) -> None:
    lines = [YAML_HEADER]
    lines += [
        f"name: {name}",
        "variant: night",
        "format: oklch",
        "candidate: false",
        "source: numeric-optimizer",
        f"seed: {seed}",
        "note: >",
        "  NON-CANDIDATE numeric exploration. Optimised for the worst normalised",
        "  distance-matrix margin (normal vision + protan/deutan/tritan at severity",
        "  1.0) subject to WCAG floors and the sRGB gamut. NOT a design proposal;",
        "  whether the numeric frontier is desirable is a human decision.",
        "meta:",
        "  candidate: false",
        "  generated: numeric-optimizer",
        f"  seed: {seed}",
        "  objective: 'min(dE/0.13 must-normal, dE/0.09 must-CVD, 2.0*dE/0.08 should, dE/0.03 anti-collapse)'",
        f"  scaffold: {SCAFFOLD_SOURCE}",
    ]
    for k, v in sorted(extra_meta.items()):
        lines.append(f"  {k}: {v}")
    lines.append("colors:")
    allroles = dict(problem.scaffold)
    allroles.update(state)
    for role in sorted(allroles):
        L, C, h = allroles[role]
        lines.append(
            f"  {role}: {{L: {round(L, 6)}, C: {round(C, 6)}, h: {round(h % 360.0, 4)}}}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_specimen_html(palette_hexes: dict[str, str], specimen) -> str:
    """Span-render the R specimen under this palette (same approach as
    scripts/anchor_search.render_specimen_html, kept local so this branch
    does not depend on another exploration script's internals)."""
    out = []
    for line in specimen.lines:
        for role, text in line:
            hx = palette_hexes.get(role) or palette_hexes["fg"]
            out.append(f'<span style="color:{hx}">{_esc(text)}</span>')
        out.append("\n")
    return "".join(out)


def write_variants_html(path: Path, problem: NumericProblem, entries: list[dict]) -> None:
    """Self-contained dark page: per palette, categorical/diagnostic/surface
    swatch strips and the R specimen rendered per-role."""
    from grotto.specimens import specimen

    r_spec = specimen("r")

    def strip(roles) -> str:
        spans = "".join(
            f'<span title="{r} {hx.get(r, "")}" style="background:{hx.get(r, "#000")};'
            f'color:{hx["bg"]};padding:1px 6px;margin-right:3px;border-radius:3px">{r}</span>'
            for r in roles if r in hx
        )
        return f"<div class='strip'>{spans}</div>"

    cells = []
    for e in entries:
        hx = e["hexes"]
        m = e["metrics"]
        cells.append(
            "<div class='cell'>"
            f"<h3>{_esc(e['label'])} <span class='kind'>{_esc(e['kind'])}</span></h3>"
            f"<div class='meta'>worst margin {m['worst_margin_overall']:.3f} "
            f"({m['argmin']['pair'][0]}/{m['argmin']['pair'][1]}, {_esc(m['argmin']['class'])})"
            f" &middot; min categorical dE {m['min_categorical_de']:.3f} "
            f"&middot; mean categorical C {m['mean_categorical_chroma']:.3f} "
            f"&middot; min WCAG {m['min_wcag']:.2f}</div>"
            f"{strip(problem.categorical)}"
            f"{strip(DIAGNOSTIC_SWATCH_ROLES)}"
            f"{strip(SURFACE_SWATCH_ROLES)}"
            f"<pre style='background:{hx['bg']};color:{hx['fg']};padding:10px;margin:0;"
            f"border-radius:6px;overflow:auto'>{render_specimen_html(hx, r_spec)}</pre>"
            "</div>"
        )
    css = (
        "body{margin:0;background:#141414;color:#d8d8d8;font-family:ui-monospace,Menlo,Consolas,monospace;"
        "font-size:13px;padding:18px} h1{font-size:1.3rem} h3{margin:.2em 0 .1em}"
        ".meta{color:#999;font-size:.78rem} .kind{color:#7f9f7f;font-size:.7rem}"
        ".cell{margin:0 0 26px} pre{line-height:1.5;font-size:12px} .strip{margin:3px 0}"
        ".banner{background:#1f212b;padding:.6em .8em;border-radius:6px;margin:.8em 0;"
        "border-left:3px solid #8a4a4a}"
    )
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>numeric night palettes</title><style>" + css + "</style></head><body>"
        "<h1>Numeric-first Night palettes &middot; NON-CANDIDATE</h1>"
        "<div class='banner'>NON-CANDIDATE exploration (branch dev/numeric-palettes). "
        "Numeric palettes maximise the worst normalised distance-matrix margin under "
        "technical constraints only (WCAG floors, sRGB gamut, normal + simulated "
        "dichromat vision); candidate-b/c night are shown for comparison. Margin &gt; 1 "
        "means every must-pair clears its threshold under all four vision conditions. "
        "Whether the numeric frontier is desirable is a human decision.</div>"
        + "".join(cells)
        + "</body></html>"
    )
    path.write_text(html, encoding="utf-8")


def write_vscode_extension(
    out_dir: Path, problem: NumericProblem, entries: list[dict], k: int = 3,
    install: bool = True,
) -> Path:
    """Generate the top-K exploration themes through the existing mapping
    (labels 'Grotto N-Explore 01..03 Night') and, unless suppressed, copy the
    extension into the real VS Code extensions directory for eyeballing."""
    from grotto import vscode as gv

    mapping = gv._load_mapping(REPO / "spec/mappings/vscode.yaml", problem.roles_spec)
    themes_dir = out_dir / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)
    themes = []
    for i, e in enumerate(entries[:k], 1):
        pal = Palette(
            e["label"], "night", e["hexes"], source="hex",
            note="NON-CANDIDATE numeric exploration",
            meta={"candidate": False, "generated": "numeric-optimizer"},
        )
        theme = gv._build_theme(
            pal, f"Grotto N-Explore {i:02d} Night", "night", mapping,
            source_name=e.get("source_name", "numeric"),
            source_sha256=e.get("sha", "numeric-exploration"),
        )
        theme["grotto"]["candidate"] = False
        theme["grotto"]["note"] = (
            "NON-CANDIDATE numeric-exploration theme (branch dev/numeric-palettes). "
            "Optimised under technical constraints only; see NUMERIC.md."
        )
        rel = f"themes/numeric-explore-{i:02d}-night.json"
        (out_dir / rel).write_text(gv._dump(theme), encoding="utf-8", newline="\n")
        themes.append(
            {"label": f"Grotto N-Explore {i:02d} Night", "uiTheme": "vs-dark", "path": rel}
        )
    pkg = {
        "name": "grotto-numeric-exploration",
        "displayName": "Grotto Numeric Exploration (NON-CANDIDATE)",
        "description": (
            "Night themes from the numeric-first optimizer (technical constraints "
            "only); exploration material, not a candidate."
        ),
        "version": "0.0.1",
        "publisher": "grotto-exploration",
        "engines": {"vscode": "^1.70.0"},
        "categories": ["Themes"],
        "contributes": {"themes": themes},
    }
    (out_dir / "package.json").write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
    if install:
        import shutil

        if VSCODE_INSTALL_DIR.parent.exists():
            if VSCODE_INSTALL_DIR.exists():
                shutil.rmtree(VSCODE_INSTALL_DIR)
            shutil.copytree(out_dir, VSCODE_INSTALL_DIR)
            print(f"[install] extension copied to {VSCODE_INSTALL_DIR}")
        else:
            print(f"[install] {VSCODE_INSTALL_DIR.parent} not found; skipping install")
    return out_dir


# ===========================================================================
# Main
# ===========================================================================


def candidate_night_hexes(name: str) -> dict[str, str]:
    return dict(Palette.from_yaml(REPO / "themes/candidates" / f"{name}.night.yaml").colors)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--restarts", type=int, default=20)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--refine-passes", type=int, default=30)
    ap.add_argument("--n-palettes", type=int, default=6)
    ap.add_argument("--out", default="out/numeric-night")
    ap.add_argument("--no-install", action="store_true",
                    help="generate the extension dir but do not copy it into the "
                         "real VS Code extensions directory")
    args = ap.parse_args()

    t0 = time.monotonic()
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    problem = NumericProblem()
    print(
        f"[problem] {len(problem.chromatic)} chromatic roles optimised, "
        f"{len(problem.scaffold)} scaffold roles verbatim from {SCAFFOLD_SOURCE}; "
        f"{len(problem.must_pairs)} must pairs, {len(problem.should_pairs)} should "
        f"pairs, {len(problem.terms)} objective terms"
    )

    results = run_search(
        problem, seed=args.seed, restarts=args.restarts, samples=args.samples,
        refine_passes=args.refine_passes, log=print,
    )
    t_search = time.monotonic() - t0
    print(f"[search] {len(results)} refined results in {t_search:.1f}s; "
          f"best J={results[0]['J']:.4f}")

    base_hexes = problem.hexes(problem.baseline_lch)
    base_metrics = palette_metrics(problem, base_hexes)
    print(f"[baseline] candidate-b night (= scaffold): worst margin "
          f"{base_metrics['worst_margin_overall']:.4f} argmin={base_metrics['argmin']}")

    picked = diverse_pick(results, args.n_palettes)
    entries = []
    for i, r in enumerate(picked, 1):
        # roles absent from every matrix pair are blind to the objective;
        # give them a deterministic max-min-distance placement before writing
        r["state"] = place_unconstrained(problem, r["state"])
        hexes = problem.hexes(r["state"])
        bad = check_feasible(problem, hexes)
        assert not bad, f"optimized palette failed hard constraints: {bad}"
        m = palette_metrics(problem, hexes)
        name = f"numeric-n{i:02d}"
        path = out / f"{name}.night.yaml"
        write_palette_yaml(
            path, name, r["state"], problem, args.seed,
            {"restart-kind": r["kind"], "j": round(r["J"], 4),
             "j2-mean-margin": round(r["J2"], 4)},
        )
        entries.append(
            {"label": name, "kind": f"numeric ({r['kind']} restart)", "hexes": hexes,
             "metrics": m, "source_name": path.name, "state": r["state"]}
        )
        print(f"[palette] {name}: J={m['worst_margin_overall']:.4f} "
              f"argmin={m['argmin']} minCatDE={m['min_categorical_de']:.3f} "
              f"meanC={m['mean_categorical_chroma']:.3f}")

    for cname in ("candidate-b-balanced", "candidate-c-expressive"):
        hx = candidate_night_hexes(cname)
        entries.append(
            {"label": cname, "kind": "committed candidate (comparison)", "hexes": hx,
             "metrics": palette_metrics(problem, hx),
             "source_name": f"{cname}.night.yaml", "state": None}
        )

    metrics = {
        "schema": "grotto.numeric-night",
        "schema_version": "1",
        "generated_by": "scripts/numeric_palette.py",
        "seed": args.seed,
        "restarts": args.restarts,
        "samples": args.samples,
        "refine_passes": args.refine_passes,
        # NOTE: no runtime field -- artifacts stay byte-stable across runs;
        # timing is reported on stdout only.
        "objective": {
            "formula": "J = min(min_must_normal, min_must_cvd, 2.0 * min_should, min_anticollapse)",
            "must_normal_threshold": problem.th_must_normal,
            "must_cvd_threshold": problem.th_must_cvd,
            "should_threshold": problem.th_should,
            "should_weight": SHOULD_WEIGHT,
            "anticollapse_threshold": problem.th_anticollapse,
            "anticollapse_note": (
                "matrix same_family.min_distance ('still not identical'), applied to "
                "categorical pairs the matrix does not otherwise constrain"
            ),
            "cvd": "protan/deutan/tritan at severity 1.0, Brettel (population-average models)",
            "secondary": "J2 = mean of all normalised terms (greedy plateau tie-break)",
        },
        "roles": {
            "scaffold_verbatim_from": SCAFFOLD_SOURCE,
            "scaffold": sorted(problem.scaffold),
            "optimized": list(problem.chromatic),
            "categorical": list(problem.categorical),
        },
        "thresholds_source": "spec/distance-matrix.yaml (READ, not edited)",
        "floors_source": "spec/roles.yaml accessibility_floor via spec/environments.yaml",
        "palettes": [
            {"name": e["label"], "kind": e["kind"], "source": e["source_name"], **e["metrics"]}
            for e in entries
        ],
        "binding_constraint_best_numeric": binding_constraint(
            problem, entries[0]["state"], entries[0]["hexes"]
        ),
        "note": (
            "NON-CANDIDATE numeric exploration (branch dev/numeric-palettes). "
            "WCAG numbers are compliance checks; CVD simulations are population-"
            "average dichromat models; APCA is not used on this branch."
        ),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    write_metrics_txt(out / "metrics.txt", metrics)
    write_variants_html(out / "variants.html", problem, entries)

    top = [
        {"label": e["label"], "hexes": e["hexes"], "source_name": e["source_name"],
         "sha": "numeric-exploration"}
        for e in entries if e["label"].startswith("numeric-")
    ][:3]
    ext = write_vscode_extension(
        out / "vscode-preview", problem, top, k=3, install=not args.no_install
    )
    print(f"[vscode] exploration extension at {ext}")
    print(f"[done] {time.monotonic() - t0:.1f}s total; artifacts in {out}")


def write_metrics_txt(path: Path, metrics: dict) -> None:
    """Human-readable comparison tables (deterministic formatting)."""
    L = []
    L.append("NON-CANDIDATE numeric-night metrics (branch dev/numeric-palettes)")
    L.append("=" * 78)
    L.append(
        f"objective: J = min(must-normal dE/{metrics['objective']['must_normal_threshold']}, "
        f"must-CVD dE/{metrics['objective']['must_cvd_threshold']}, "
        f"{metrics['objective']['should_weight']} * should dE/{metrics['objective']['should_threshold']}, "
        f"anticollapse dE/{metrics['objective']['anticollapse_threshold']})"
    )
    L.append(f"seed {metrics['seed']}, {metrics['restarts']} restarts")
    L.append("")
    hdr = (f"{'palette':<26}{'J':>7}{'mustN':>7}{'mustCVD':>8}{'should':>7}{'antiC':>7}"
           f"{'minCatDE':>9}{'meanC':>7}{'minWCAG':>8}{'viol':>5}")
    L.append(hdr)
    L.append("-" * len(hdr))
    for p in metrics["palettes"]:
        L.append(
            f"{p['name']:<26}{p['worst_margin_overall']:>7.3f}"
            f"{p['worst_margin_must_normal']:>7.3f}{p['worst_margin_must_cvd']:>8.3f}"
            f"{p['worst_margin_should']:>7.3f}{p['worst_margin_anticollapse']:>7.3f}"
            f"{p['min_categorical_de']:>9.3f}"
            f"{p['mean_categorical_chroma']:>7.3f}{p['min_wcag']:>8.2f}"
            f"{p['wcag_violations']:>5d}"
        )
    L.append("")
    L.append("worst 10 constraint terms per palette (normalised margin ascending)")
    L.append("-" * 78)
    for p in metrics["palettes"]:
        L.append(f"{p['name']}  argmin: {p['argmin']['pair']} [{p['argmin']['class']}]")
        L.append(f"{'pair':<34}{'class':<18}{'dE':>7}{'th':>6}{'margin':>8}{'dL':>7}{'dC':>7}{'dH':>7}")
        for w in p["worst_pairs"]:
            L.append(
                f"{'/'.join(w['pair']):<34}{w['class']:<18}{w['de']:>7.3f}{w['threshold']:>6.2f}"
                f"{w['margin']:>8.3f}{w['dL']:>7.3f}{w['dC']:>7.3f}{w['dH']:>7.3f}"
            )
        L.append("")
    bc = metrics["binding_constraint_best_numeric"]
    L.append("binding constraint at the best numeric optimum")
    L.append("-" * 78)
    L.append(f"argmin class : {bc['argmin_class']} (pair {bc['argmin_pair']})")
    L.append(f"roles on the sRGB gamut edge (C>=99.5% max): {bc['n_gamut_edge_roles']}"
             f" -> {', '.join(bc['gamut_edge_roles']) or '-'}")
    L.append(f"inks on their WCAG lightness floor (worst ratio within 0.02): "
             f"{bc['n_wcag_edge_roles']} -> {', '.join(bc['wcag_edge_roles']) or '-'}")
    L.append(f"constraint terms within 5% of the worst margin: "
             f"{bc['n_terms_within_5pct_of_min']}/{bc['n_terms']}")
    L.append("")
    L.append("labels: WCAG = compliance; CVD = population-average Brettel models; "
             "APCA not used. NON-CANDIDATE exploration output.")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
