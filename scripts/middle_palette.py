"""Middle-frontier Night palette optimizer (NON-CANDIDATE exploration).

Branch rationale (dev/numeric-palettes)
---------------------------------------
The numeric-first search (``scripts/numeric_palette.py``) showed the numeric
frontier sits at ~24x the committed candidates' worst distance-matrix margin
-- and the owner, after eyeballing the installed "Grotto N-Explore" themes in
a real editor, rejected that frontier's *look*: verbatim feedback
"Not sure if the 3 new N ones are visually pleasing. the magenta is very
in-your-face."  Numeric-first optimisation is chroma-starved by sRGB, so it
pins function/builtin/namespace to the magenta gamut edge (C ~= 0.315),
pushes keyword/string near-white, and abandons every hue convention users
bring with them.  That rejection is the primary design input for this script.

The middle frontier
-------------------
Optimise the SAME numeric objective as ``numeric_palette.py`` (worst
normalised distance-matrix margin under normal + simulated dichromat vision,
plus the same_family min_distance anti-collapse floor) but INSIDE taste
fences that keep grotto's character:

* Hue convention windows per chromatic role (string stays green-side,
  function blue-side, keyword violet-side, error red-side, diff_added
  green-side, ...).  These are the learned associations; breaking them is
  what made N-Explore unpleasant.
* Lightness structure stays: each chromatic ink's L may move at most
  +/-0.04 from its value in candidate-b-balanced.night.yaml, each highlight
  surface's L at most +/-0.06.  Lightness spread between co-occurring
  surfaces is the distance-matrix-sanctioned redundant channel, so the
  diff_added/diff_removed deutan fix is expected to come from HERE, not hue.
* Loudness ceilings (the direct answer to "magenta in-your-face"):
  syntax roles C <= 0.12, diagnostics C <= 0.16, highlight surfaces
  C <= 0.10, AND every role <= 70% of max_chroma(L, h) so nothing rides the
  gamut edge.  These supersede anything the margin objective wants.
* WCAG floors stay hard against the background AND every co-occurring
  surface (the committed candidate-b night palette carries 12
  ink-over-surface violations; here they are a hard constraint, not a
  warning).
* The neutral scaffold is copied verbatim from candidate-b-balanced.night
  (same scaffold as the numeric run; see numeric_palette.SCAFFOLD_ROLES).

Reuse, not rewrite: this module imports ``numeric_palette`` and reuses its
machinery -- the term table / margin computation, gamut projection, the
WCAG-feasible lightness interval, the greedy (J, J2) refinement loop and the
multi-start driver (via two documented injection points:
``numeric_palette._apply_move`` and ``numeric_palette._initial_state`` are
rebound to the fence-aware versions below), the diversity picker, the
feasibility check, the metrics block and the specimen renderer.  Only the
fence projection/repair, the fenced sampling, the fenced placement of
matrix-ignored roles, and the same_family min-distance enforcement are new.

Declared objective: UNCHANGED from numeric_palette.py
    J = min( must-normal dE/0.13, must-CVD dE/0.09 x {protan,deutan,tritan},
             2.0 x should dE/0.08, anti-collapse dE/0.03 )
with greedy acceptance lexicographic on (J, J2 = mean margin).  In addition,
the same_family min side is promoted from objective term to OUTPUT
constraint: every same_family pair of the distance matrix must end at
dE >= 0.03 (enforced by a deterministic repair pass; kills the
number/constant dE = 0.000 debt of the committed candidates).

Outputs (out/middle-night/ by default)
--------------------------------------
middle-mNN.night.yaml -- palettes in the repo OKLCH yaml format,
                         ``candidate: false``, NON-CANDIDATE notes
metrics.json / .txt   -- three-way comparison candidate-b / middle /
                         numeric-n01 (worst margins by class, the three
                         verified debts, loudness, per-pair worst-10 with
                         distance.breakdown channels)
variants.html         -- dark side-by-side page (swatches + R specimen)
vscode-preview/       -- top-3 extension dir, also installed to the real
                         extensions directory unless --no-install
                         (labels "Grotto M-Explore 01..03 Night")

Usage:
    uv run python scripts/middle_palette.py            # full run (~minutes)
    uv run python scripts/middle_palette.py --restarts 4 --samples 8   # smoke

NON-CANDIDATE: everything this script writes is exploration material.
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

import numeric_palette as np  # the machinery being reused

from grotto.color import hex_to_oklch, oklch_to_hex
from grotto.contrast import wcag_contrast
from grotto.spec import Palette

# ===========================================================================
# Taste fences (declared; hard constraints of this search)
# ===========================================================================

#: Hue convention windows per chromatic role, degrees OKLCH.  Rationale: the
#: learned associations users bring (green strings, blue functions, violet
#: keywords, red errors, green added / red removed diffs, ...).  ``tag`` is
#: allowed its committed family on either side of the fence boundary
#: (its committed hue 243.9 sits in 180-265).
HUE_WINDOWS: dict[str, tuple[tuple[float, float], ...]] = {
    # -- syntax ---------------------------------------------------------
    "string": ((95.0, 165.0),),
    "function": ((180.0, 265.0),),
    "keyword": ((275.0, 335.0),),
    "number": ((40.0, 110.0),),
    "constant": ((40.0, 110.0),),
    "builtin": ((0.0, 50.0),),
    "decorator": ((40.0, 110.0),),
    "type": ((160.0, 215.0),),
    "namespace": ((160.0, 215.0),),
    "tag": ((95.0, 165.0), (180.0, 265.0)),
    # -- diagnostics + attention borders --------------------------------
    "error": ((0.0, 40.0),),
    "warning": ((60.0, 110.0),),
    "info": ((180.0, 265.0),),
    "success": ((90.0, 160.0),),
    "focus": ((180.0, 265.0),),
    "breakpoint": ((0.0, 40.0),),
    # -- highlight surfaces ---------------------------------------------
    "selection": ((180.0, 265.0),),
    "search_match": ((40.0, 110.0),),
    "search_match_current": ((40.0, 110.0),),
    "diff_added": ((90.0, 160.0),),
    "diff_removed": ((0.0, 40.0),),
    "diff_changed": ((40.0, 110.0),),
    "debug_current": ((40.0, 110.0),),
}

#: Lightness fences: chromatic inks (paint ink/border) +/-0.04 around the
#: candidate-b night value; highlight surfaces +/-0.06 (the redundant
#: channel the distance matrix sanctions for CVD survival of surfaces).
INK_L_DELTA = 0.04
SURFACE_L_DELTA = 0.06

#: Loudness ceilings: per-class absolute chroma caps AND a fraction-of-gamut
#: rule so nothing rides the sRGB edge (the numeric run had 17 of 23 roles
#: at C >= 99.5% of max_chroma; that look is the rejected one).
SYNTAX_CAP = 0.12
DIAGNOSTIC_CAP = 0.16
SURFACE_CAP = 0.10
GAMUT_FRACTION_CAP = 0.70

#: Quantisation safety margins.  A fence is authored in OKLCH float space but
#: the palette ships as 8-bit hex; the round trip drifts chroma by ~0.001 and
#: -- at small chroma, where the hue angle is ill-conditioned under 8-bit
#: rounding -- hue by a few degrees.  Projection therefore keeps a small
#: margin INSIDE each fence, and the hex-space audit (fence_audit) allows the
#: residual.  In the hex audit, hue windows are only checked at
#: HUE_AUDIT_MIN_CHROMA and above: below ~0.02 chroma (the distance matrix's
#: own JND anchor) the hue channel carries no readable signal anyway.
HUE_MARGIN = 1.5
CHROMA_MARGIN = 0.002
HUE_AUDIT_TOL = 2.5
CHROMA_AUDIT_TOL = 0.0015
L_AUDIT_TOL = 0.006
HUE_AUDIT_MIN_CHROMA = 0.02

SYNTAX_ROLES = (
    "keyword", "string", "number", "constant", "type", "function",
    "builtin", "decorator", "namespace", "tag",
)
DIAGNOSTIC_ROLES = ("error", "warning", "info", "success", "focus", "breakpoint")
HIGHLIGHT_SURFACE_ROLES = (
    "selection", "search_match", "search_match_current",
    "diff_added", "diff_removed", "diff_changed", "debug_current",
)

#: Provenance of the fences, quoted for the artifacts (owner feedback on the
#: installed N-Explore themes, 2026-08).
OWNER_FEEDBACK = (
    "Not sure if the 3 new N ones are visually pleasing. "
    "the magenta is very in-your-face."
)

DEFAULT_SEED = 20260816

#: Extension install target (the owner's real VS Code extensions dir).
VSCODE_INSTALL_DIR = Path("/mnt/c/Users/m0hawk/.vscode/extensions/grotto-middle-exploration")

#: Where the numeric frontier palettes live for the three-way comparison.
NUMERIC_DIR = REPO / "out/numeric-night"


def chroma_cap(role: str) -> float:
    if role in SYNTAX_ROLES:
        return SYNTAX_CAP
    if role in DIAGNOSTIC_ROLES:
        return DIAGNOSTIC_CAP
    if role in HIGHLIGHT_SURFACE_ROLES:
        return SURFACE_CAP
    raise KeyError(f"no chroma-cap class declared for role {role!r}")


def _circ_dh(a: float, b: float) -> float:
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def project_hue(role: str, h: float) -> float:
    """Project a hue into the role's convention window(s) (circularly nearest
    point), keeping HUE_MARGIN inside the boundary so 8-bit quantisation
    cannot push the shipped hex back out.  Wrap-around matters for the
    rose-low windows that start at 0 degrees: a hue of 359 belongs to 1, not
    to the far end of the window."""
    windows = HUE_WINDOWS[role]
    best, best_d = None, None
    for lo, hi in windows:
        for h_turn in (h - 360.0, h, h + 360.0):
            if h_turn < lo - 180.0 or h_turn > hi + 180.0:
                continue
            cand = min(max(h_turn, lo + HUE_MARGIN), hi - HUE_MARGIN)
            d = _circ_dh(h, cand)
            if best_d is None or d < best_d or (d == best_d and cand < best):
                best, best_d = cand, d
    return best % 360.0


# ===========================================================================
# The fenced problem
# ===========================================================================


class MiddleProblem(np.NumericProblem):
    """The numeric problem plus the taste fences, on the same scaffold.

    Everything numeric_palette.NumericProblem builds (term table, floors,
    pair lists, co-occurring surfaces) is inherited untouched; this subclass
    adds, per chromatic role: the hue window, the lightness fence around the
    candidate-b night value, and the chroma ceiling
    min(class cap, GAMUT_FRACTION_CAP * max_chroma(L, h)).
    """

    def __init__(self, chromatic=tuple(np.CHROMATIC_ROLES)):
        super().__init__(chromatic=chromatic)
        missing = [r for r in self.chromatic if r not in HUE_WINDOWS]
        assert not missing, f"roles without hue windows: {missing}"
        assert set(HUE_WINDOWS) == set(np.CHROMATIC_ROLES), (
            "hue-window table drifted from numeric_palette.CHROMATIC_ROLES"
        )
        # same_family pairs of the distance matrix (min side -> output gate)
        self.same_family_pairs = sorted(
            (c.a, c.b)
            for c in self.dists.of_kind("same_family")
            if c.a in self.present and c.b in self.present
        )

    # -- fences -------------------------------------------------------------

    def l_range(self, role: str) -> tuple[float, float]:
        base = self.baseline_lch[role][0]
        d = INK_L_DELTA if self.paint[role] in ("ink", "border") else SURFACE_L_DELTA
        return (base - d, base + d)

    def chroma_ceiling(self, role: str, L: float, h: float) -> float:
        """Chroma ceiling = min(class cap, 70% of the gamut edge), kept
        CHROMA_MARGIN inside so quantisation cannot push the shipped hex
        over the fence."""
        return max(
            0.0,
            min(
                chroma_cap(role) - CHROMA_MARGIN,
                GAMUT_FRACTION_CAP * np.maxc(L, h) - CHROMA_MARGIN,
            ),
        )

    def fence_lch(
        self, role: str, L: float, C: float, h: float
    ) -> tuple[float, float, float]:
        """Project (L, C, h) into the role's full fence set."""
        h = project_hue(role, h)
        lo, hi = self.l_range(role)
        L = min(max(L, lo), hi)
        C = min(C, self.chroma_ceiling(role, L, h))
        return (L, C, h)

    def hexes(self, state: dict[str, tuple[float, float, float]]) -> dict[str, str]:
        out = dict(self.scaffold_hex)
        for r, lch in state.items():
            out[r] = oklch_to_hex(np.project_chroma(*self.fence_lch(r, *lch)))
        return out

    def fence_audit(self, hexes: dict[str, str]) -> list[str]:
        """Every fence violation of a COMPLETE palette as SHIPPED (8-bit hex),
        empty = compliant.  Tolerances absorb hex quantisation only (the
        projection already keeps a margin inside each fence); the hue window
        is checked only where the hue channel is perceptually present
        (C >= HUE_AUDIT_MIN_CHROMA)."""
        out = []
        for r in self.chromatic:
            L, C, h = hex_to_oklch(hexes[r])
            if C >= HUE_AUDIT_MIN_CHROMA and not any(
                lo_ - HUE_AUDIT_TOL <= h <= hi_ + HUE_AUDIT_TOL
                or lo_ - HUE_AUDIT_TOL <= h - 360.0 <= hi_ + HUE_AUDIT_TOL
                for lo_, hi_ in HUE_WINDOWS[r]
            ):
                out.append(f"hue {r}: {h:.2f} outside {[w for w in HUE_WINDOWS[r]]}")
            if C > chroma_cap(r) + CHROMA_AUDIT_TOL:
                out.append(f"chroma {r}: {C:.4f} > class cap {chroma_cap(r)}")
            if C > GAMUT_FRACTION_CAP * np.maxc(L, h) + CHROMA_AUDIT_TOL:
                out.append(
                    f"gamut-fraction {r}: C {C:.4f} > "
                    f"{GAMUT_FRACTION_CAP:.0%} of max_chroma {np.maxc(L, h):.4f}"
                )
            Llo, Lhi = self.l_range(r)
            if not (Llo - L_AUDIT_TOL <= L <= Lhi + L_AUDIT_TOL):
                out.append(f"lightness {r}: L {L:.4f} outside fence [{Llo:.4f}, {Lhi:.4f}]")
        return out

    def fence_audit_state(
        self, state: dict[str, tuple[float, float, float]]
    ) -> list[str]:
        """Exact audit of the AUTHORED coordinates (no quantisation slack):
        hue inside a window, C under min(cap, 70% gamut), L inside fence."""
        out = []
        for r, (L, C, h) in state.items():
            if not any(lo_ <= h <= hi_ or lo_ <= h + 360.0 <= hi_ for lo_, hi_ in HUE_WINDOWS[r]):
                out.append(f"hue {r}: {h:.2f} outside {HUE_WINDOWS[r]}")
            if C > min(chroma_cap(r), GAMUT_FRACTION_CAP * np.maxc(L, h)) + 1e-9:
                out.append(f"chroma {r}: {C:.4f} over ceiling")
            Llo, Lhi = self.l_range(r)
            if not (Llo - 1e-9 <= L <= Lhi + 1e-9):
                out.append(f"lightness {r}: {L:.4f} outside [{Llo:.4f}, {Lhi:.4f}]")
        return out


# ===========================================================================
# Fence-aware repair (adapts numeric_palette's climb loops with fence bounds)
# ===========================================================================


def repair_ink_fenced(
    problem: MiddleProblem,
    role: str,
    L: float,
    C: float,
    h: float,
    hexes: dict[str, str],
) -> tuple[float, float, float] | None:
    """Bring an ink/border colour into the feasible set WITHOUT leaving the
    fences.  Hue is projected into the window; lightness climbs (dark
    polarity) only up to the fence ceiling; chroma is re-clipped to the
    ceiling at every accepted lightness.  Returns None when the WCAG floor
    is unreachable within the fence (the move is then simply rejected)."""
    h = project_hue(role, h)
    Llo, Lhi = problem.l_range(role)
    L = min(max(L, Llo), Lhi)
    floor = problem.floors[role]
    refs = [problem.scaffold_hex["bg"]] + [hexes[s] for s in problem.surfaces]

    def ok(Lx: float, Cx: float) -> bool:
        hx = oklch_to_hex((Lx, Cx, h))
        return all(wcag_contrast(hx, ref) >= floor for ref in refs)

    Lc = L
    Cc = min(C, problem.chroma_ceiling(role, Lc, h))
    while True:
        if ok(Lc, Cc):
            return (Lc, Cc, h)
        if Lc >= Lhi - 1e-9:
            break
        Lc = min(Lc + 0.005, Lhi)
        Cc = min(C, problem.chroma_ceiling(role, Lc, h))
    # last resort inside the fence: the quietest legal colour at fence max
    if ok(Lhi, 0.0):
        return (Lhi, 0.0, h)
    return None


def repair_surface_fenced(
    problem: MiddleProblem,
    role: str,
    L: float,
    C: float,
    h: float,
) -> tuple[float, float, float] | None:
    """Bring a highlight surface into the feasible set without leaving the
    fences.  The binding constraint is the legibility of the FIXED scaffold
    inks over it (the committed candidate-b palette violates 12 of those);
    lightness descends only to the fence floor (never below the canvas
    +0.01).  Returns None when the scaffold inks cannot keep their floors
    anywhere in the fence -- the move is rejected."""
    h = project_hue(role, h)
    Llo, Lhi = problem.l_range(role)
    Llo = max(Llo, problem.scaffold["bg"][0] + 0.01)
    L = min(max(L, Llo), Lhi)
    inks = [
        (problem.floors[r], problem.scaffold_hex[r])
        for r in problem.scaffold_floor_inks
    ]

    def ok(Lx: float, Cx: float) -> bool:
        hx = oklch_to_hex((Lx, Cx, h))
        return all(wcag_contrast(ink_hex, hx) >= floor for floor, ink_hex in inks)

    Lc = L
    Cc = min(C, problem.chroma_ceiling(role, Lc, h))
    while True:
        if ok(Lc, Cc):
            return (Lc, Cc, h)
        if Lc <= Llo + 1e-9:
            break
        Lc = max(Lc - 0.005, Llo)
        Cc = min(C, problem.chroma_ceiling(role, Lc, h))
    if ok(Llo, 0.0):
        return (Llo, 0.0, h)
    return None


def surface_strands_inks(
    problem: MiddleProblem, hexes: dict[str, str], surf_hex: str
) -> bool:
    """A moved surface may not strand any CHROMATIC ink below its floor."""
    for other in problem.chromatic:
        floor = problem.floors[other]
        if floor <= 0.0 or problem.paint[other] not in ("ink", "border"):
            continue
        if wcag_contrast(hexes[other], surf_hex) < floor:
            return True
    return False


# ===========================================================================
# Injection points: fence-aware move application and sampling for the
# REUSED numeric_palette search loops (run_search / greedy_refine)
# ===========================================================================


def _apply_move_fenced(problem, role, lch, axis, d, hexes):
    """numeric_palette._apply_move with fence projection: hue moves project
    into the window, L moves clip to the fence, chroma-fraction moves are
    fractions of the role's chroma CEILING (class cap x 70% gamut rule)."""
    L, C, h = lch
    ceil0 = problem.chroma_ceiling(role, L, h)
    f = C / ceil0 if ceil0 > 1e-9 else 0.0
    if axis == "h":
        h2 = project_hue(role, h + d)
        L2, f2 = L, f
    elif axis == "L":
        Llo, Lhi = problem.l_range(role)
        L2, h2, f2 = min(max(L + d, Llo), Lhi), h, f
    else:
        L2, h2 = L, h
        f2 = min(max(f + d, 0.0), 1.0)
    C2 = f2 * problem.chroma_ceiling(role, L2, h2)
    if problem.paint[role] in ("ink", "border"):
        return repair_ink_fenced(problem, role, L2, C2, h2, hexes)
    got = repair_surface_fenced(problem, role, L2, C2, h2)
    if got is None:
        return None
    surf_hex = oklch_to_hex(np.project_chroma(*got))
    if surface_strands_inks(problem, hexes, surf_hex):
        return None
    return got


def _window_sampler(role: str, rng: random.Random) -> float:
    """Uniform hue sample inside the role's window(s), width-weighted."""
    windows = HUE_WINDOWS[role]
    if len(windows) == 1:
        win = windows[0]
    else:
        win = rng.choices(windows, weights=[hi - lo for lo, hi in windows], k=1)[0]
    return project_hue(role, rng.uniform(win[0], win[1]))


def _initial_state_fenced(problem, rng, kind):
    """numeric_palette._initial_state inside the fences.

    kinds (mapped from the numeric driver's rotation):
      'ladder'  -- hues evenly spread inside each window (shuffled offsets);
      'bladder' -- the same + a shuffled lightness ladder for the inks;
      'bseed'   -- candidate-B hues + jitter (projected back into windows);
      'free'    -- uniform inside each window.
    Every sample is repaired into the feasible set (WCAG floors over bg and
    every co-occurring surface, scaffold-ink floors under surfaces), so each
    sample is already a legal, fence-compliant palette."""
    n = len(problem.chromatic)
    if kind in ("ladder", "bladder"):
        hues = {}
        for i, r in enumerate(problem.chromatic):
            lo, hi = HUE_WINDOWS[r][0][0], HUE_WINDOWS[r][-1][1]
            t = (i / max(n - 1, 1) + rng.uniform(-0.12, 0.12)) % 1.0
            hues[r] = project_hue(r, lo + (hi - lo) * t)
    elif kind == "bseed":
        hues = {
            r: project_hue(r, problem.baseline_lch[r][2] + rng.uniform(-20, 20))
            for r in problem.chromatic
        }
    else:
        hues = {r: _window_sampler(r, rng) for r in problem.chromatic}

    inks = [r for r in problem.chromatic if problem.paint[r] in ("ink", "border")]
    surfaces = [r for r in problem.chromatic if problem.paint[r] == "surface"]
    l_ladder = None
    s_ladder = None
    if kind == "bladder":
        if len(inks) > 1:
            l_ladder = []
            for r in inks:
                lo, hi = problem.l_range(r)
                l_ladder.append(rng.uniform(lo, hi))
            rng.shuffle(l_ladder)
        if len(surfaces) > 1:
            # shuffled quantile ladder across the surface fences: starts with
            # MAXIMUM lightness spread inside the fences, the redundant
            # channel the diff-surface cluster needs most
            s_ladder = list(range(len(surfaces)))
            rng.shuffle(s_ladder)

    state: dict[str, tuple[float, float, float]] = {}
    hexes = dict(problem.scaffold_hex)
    li = si = 0
    # surfaces first (they depend only on the fixed scaffold inks), then inks
    ordered = [r for r in problem.chromatic if problem.paint[r] == "surface"]
    ordered += [r for r in problem.chromatic if problem.paint[r] != "surface"]
    for r in ordered:
        h = hues[r]
        f = 1.0 - np.CHROMA_BIAS * rng.random() ** 2
        if problem.paint[r] in ("ink", "border"):
            Llo, Lhi = problem.l_range(r)
            # reuse the numeric WCAG-feasible lightness interval (vs bg, at
            # the 70% gamut fraction the ceiling uses) to start inks legal
            iv = np.feasible_l_interval(
                problem.scaffold_hex["bg"], problem.floors[r], h,
                c_frac=GAMUT_FRACTION_CAP,
            )
            wcag_lo = iv[0] if iv is not None else Llo
            L = l_ladder[li] if l_ladder is not None else rng.uniform(
                min(max(wcag_lo, Llo), Lhi), Lhi
            )
            li += 1
            got = repair_ink_fenced(problem, r, L, f * problem.chroma_ceiling(r, L, h), h, hexes)
        else:
            Llo, Lhi = problem.l_range(r)
            if s_ladder is not None:
                t = s_ladder[si] / max(len(surfaces) - 1, 1)
                si += 1
                L = Llo + (Lhi - Llo) * (0.15 + 0.7 * t)
            else:
                L = rng.uniform(Llo, min(Lhi, Llo + 0.06))
            got = repair_surface_fenced(problem, r, L, f * problem.chroma_ceiling(r, L, h), h)
        if got is None:
            # cannot happen with this canvas (probes show big slack); the
            # fallback keeps the search total: quietest legal fence point.
            Lhi = problem.l_range(r)[1]
            if problem.paint[r] in ("ink", "border"):
                got = repair_ink_fenced(problem, r, Lhi, 0.0, h, hexes)
            else:
                got = repair_surface_fenced(problem, r, problem.l_range(r)[0], 0.0, h)
            if got is None:
                raise RuntimeError(f"role {r} infeasible inside its fences")
        state[r] = got
        hexes[r] = oklch_to_hex(np.project_chroma(*got))
    return state


def place_unconstrained_fenced(
    problem: MiddleProblem,
    state: dict[str, tuple[float, float, float]],
) -> dict[str, tuple[float, float, float]]:
    """Fenced version of numeric_palette.place_unconstrained: roles the
    distance matrix ignores entirely (namespace, tag, info, debug_current,
    breakpoint in the full set) are placed deterministically AFTER
    refinement, maximising their minimum dE to every other chromatic role
    on a coarse grid INSIDE their windows (same tie-breaks as numeric)."""
    hexes = problem.hexes(state)
    free = [r for r in problem.chromatic if not problem.term_ids_by_role.get(r)]
    for r in free:
        is_ink = problem.paint[r] in ("ink", "border")
        Llo, Lhi = problem.l_range(r)
        Ls = [round(Llo + (Lhi - Llo) * i / 6, 4) for i in range(7)]
        hue_grid = sorted(
            {project_hue(r, float(h)) for h in range(0, 360, 5)}
        )
        best, best_key = None, None
        for h in hue_grid:
            for L in Ls:
                for f in (1.0, 0.7, 0.4):
                    C = f * problem.chroma_ceiling(r, L, h)
                    if is_ink:
                        got = repair_ink_fenced(problem, r, L, C, h, hexes)
                    else:
                        got = repair_surface_fenced(problem, r, L, C, h)
                    if got is None:
                        continue
                    hx = oklch_to_hex(np.project_chroma(*got))
                    if not is_ink and surface_strands_inks(problem, hexes, hx):
                        continue
                    lab = np._oklab_of(hx)
                    dmin = min(
                        np._dE(lab, np._oklab_of(hexes[o]))
                        for o in problem.chromatic if o != r
                    )
                    key = (-round(dmin, 6), L, h, f)
                    if best_key is None or key < best_key:
                        best_key, best = key, got
        if best is not None:
            state[r] = best
            hexes[r] = oklch_to_hex(np.project_chroma(*best))
    return state


# ===========================================================================
# same_family min-distance enforcement (output gate, not just objective)
# ===========================================================================


def enforce_same_family_min(
    problem: MiddleProblem,
    state: dict[str, tuple[float, float, float]],
    j_tolerance_ladder: tuple[float, ...] = (0.02, 0.06, 0.15, 1.0),
) -> list[dict]:
    """Repair pass: every same_family pair of the distance matrix must end
    at dE >= same_family.min_distance (0.03), the file's own 'still not
    identical' bound -- a HARD output constraint, so it outranks the margin
    objective when the two collide.

    For a violating pair whose members are optimised roles, run a bounded
    coordinate search on the pair's dE (the numeric deterministic move set,
    repaired through the fences), accepting the best pair-improving move
    whose global worst margin J stays within a tolerance of its pre-repair
    value.  The tolerance is a ladder: try to repair for free (0.02), then
    progressively buy the constraint with margin (repair with a penalty,
    exactly as the mission phrase has it).  Pairs of scaffold roles
    (comment/docstring) are reported, not repaired: they are verbatim from
    the committed palette and already separated by lightness.

    J is recomputed incrementally (only the moved role's terms), the same
    pattern numeric_palette.greedy_refine uses."""
    th_min = problem.th_anticollapse  # same value: matrix same_family.min_distance
    terms = problem.terms
    report: list[dict] = []
    hexes = problem.hexes(state)
    vals = problem.term_values(hexes)

    def jmin() -> float:
        return min(
            (np.SHOULD_WEIGHT if t["cls"] == "should" else 1.0) * v
            for t, v in zip(terms, vals)
        )

    def pair_de(a: str, b: str, hx: dict[str, str] | None = None) -> float:
        hx = hexes if hx is None else hx
        return np._dE(np._oklab_of(hx[a]), np._oklab_of(hx[b]))

    def sf_violations(hx: dict[str, str]) -> list[tuple[str, str]]:
        return [
            (x, y) for x, y in problem.same_family_pairs
            if pair_de(x, y, hx=hx) < th_min
        ]

    for _round in range(4):  # repairs are non-regressing; one round should do
        pending = [
            (a, b) for a, b in problem.same_family_pairs
            if pair_de(a, b) < th_min
            and any(r in problem.chromatic for r in (a, b))
        ]
        if not pending:
            break
        for a, b in pending:
            entry = {
                "pair": [a, b], "de_before": round(pair_de(a, b), 4),
                "repaired": False, "round": _round,
            }
            movable = [r for r in (a, b) if r in problem.chromatic]
            j_base = jmin()
            for tol in j_tolerance_ladder:
                for _step in range(60):
                    if pair_de(a, b) >= th_min:
                        entry["repaired"] = True
                        break
                    best = None  # (pair_de, role, lch, new_hex, updates)
                    for role in movable:
                        for axis, d in np.MOVES:
                            got = _apply_move_fenced(
                                problem, role, state[role], axis, d, hexes
                            )
                            if got is None:
                                continue
                            new_hex = oklch_to_hex(np.project_chroma(*got))
                            # HARD: no same_family pair may (re)collapse --
                            # repairing one pair must not break a sibling.
                            trial_hex = dict(hexes)
                            trial_hex[role] = new_hex
                            if any(
                                p != (a, b) for p in sf_violations(trial_hex)
                            ):
                                continue
                            updates = {}
                            for i in problem.term_ids_by_role[role]:
                                t = terms[i]
                                ha = new_hex if t["a"] == role else hexes[t["a"]]
                                hb = new_hex if t["b"] == role else hexes[t["b"]]
                                if t["kind"] == "normal":
                                    updates[i] = (
                                        np._dE(np._oklab_of(ha), np._oklab_of(hb)) / t["th"]
                                    )
                                else:
                                    updates[i] = (
                                        np._dE(np._sim_oklab(ha, t["kind"]),
                                               np._sim_oklab(hb, t["kind"])) / t["th"]
                                    )
                            j_new = min(
                                (np.SHOULD_WEIGHT if terms[i]["cls"] == "should" else 1.0)
                                * updates.get(i, v)
                                for i, v in enumerate(vals)
                            )
                            if j_new < j_base - tol:
                                continue
                            other = b if role == a else a
                            de2 = np._dE(
                                np._oklab_of(new_hex), np._oklab_of(hexes[other])
                            )
                            if best is None or de2 > best[0] + 1e-9:
                                best = (de2, role, got, new_hex, updates)
                    if best is None:
                        break
                    _, role, got, new_hex, updates = best
                    state[role] = got
                    hexes[role] = new_hex
                    vals = [updates.get(i, v) for i, v in enumerate(vals)]
                if entry["repaired"]:
                    break
            entry["de_after"] = round(pair_de(a, b), 4)
            entry["repaired"] = entry["de_after"] >= th_min
            entry["j_before"] = round(j_base, 4)
            entry["j_after"] = round(jmin(), 4)
            report.append(entry)
    return report


# ===========================================================================
# Rebind the injection points so the REUSED numeric search loops are fenced
# ===========================================================================

np._apply_move = _apply_move_fenced
np._initial_state = _initial_state_fenced


# ===========================================================================
# Reporting: what the fences leave (pair-only bounds) + metrics
# ===========================================================================


def _sim_de(hex_a: str, hex_b: str, kind: str) -> float:
    return np._dE(np._sim_oklab(hex_a, kind), np._sim_oklab(hex_b, kind))


def fence_bound_diff_deutan(problem: MiddleProblem) -> dict:
    """The best diff_added/diff_removed deutan dE ANY fenced palette could
    reach on this pair alone (ignoring every other pair): grid search over
    the two fences with the surface repair applied, so the bound includes
    the scaffold-ink WCAG caps on surface lightness.  This is 'what the
    fences leave' for the deutan debt."""
    Llo = max(problem.l_range("diff_added")[0], problem.scaffold["bg"][0] + 0.01)
    Lhi = problem.l_range("diff_added")[1]
    n_steps = max(round((Lhi - Llo) / 0.01), 1)
    Ls = [round(Llo + 0.01 * i, 3) for i in range(n_steps + 1)]
    feas: dict[str, list[tuple[float, float, float]]] = {}
    for role, hues in (("diff_added", (95.0, 117.5, 140.0, 160.0)),
                       ("diff_removed", (0.0, 13.3, 26.7, 40.0))):
        combos = []
        for h in hues:
            for C in (0.02, 0.04, 0.06, 0.08, 0.10):
                for L in Ls:
                    got = repair_surface_fenced(problem, role, L, C, h)
                    if got is None:
                        continue
                    combos.append(got)
        feas[role] = combos
    best = None
    for a in feas["diff_added"]:
        for r in feas["diff_removed"]:
            de = _sim_de(
                oklch_to_hex(np.project_chroma(*a)),
                oklch_to_hex(np.project_chroma(*r)),
                "deutan",
            )
            if best is None or de > best[0]:
                best = (de, a, r)
    return {
        "best_deutan_de": round(best[0], 4) if best else None,
        "threshold": problem.th_must_cvd,
        "margin": round(best[0] / problem.th_must_cvd, 4) if best else None,
        "diff_added_lch": [round(x, 4) for x in best[1]] if best else None,
        "diff_removed_lch": [round(x, 4) for x in best[2]] if best else None,
        "note": (
            "pair-only bound: hues windows + chroma cap 0.10 + 70% gamut + L "
            "fence +/-0.06 + scaffold-ink WCAG floors, other pairs ignored"
        ),
    }


def diff_deutan_de(problem: MiddleProblem, hexes: dict[str, str]) -> float:
    return _sim_de(hexes["diff_added"], hexes["diff_removed"], "deutan")


def number_constant_de(problem: MiddleProblem, hexes: dict[str, str]) -> float:
    return np._dE(
        np._oklab_of(hexes["number"]), np._oklab_of(hexes["constant"])
    )


def middle_palette_metrics(problem: MiddleProblem, hexes: dict[str, str]) -> dict:
    """numeric_palette.palette_metrics + the middle-frontier extras:
    loudness max, the two distance debts, the fence audit."""
    m = np.palette_metrics(problem, hexes)
    cat = [r for r in problem.categorical if r in hexes]
    cat_C = [hex_to_oklch(hexes[r])[1] for r in cat]
    m["max_categorical_chroma"] = round(max(cat_C), 4) if cat_C else None
    if "diff_added" in hexes and "diff_removed" in hexes:
        m["diff_added_removed_deutan_de"] = round(
            diff_deutan_de(problem, hexes), 4
        )
        m["diff_added_removed_normal_de"] = round(
            np._dE(np._oklab_of(hexes["diff_added"]),
                   np._oklab_of(hexes["diff_removed"])), 4
        )
    if "number" in hexes and "constant" in hexes:
        m["number_constant_de"] = round(number_constant_de(problem, hexes), 4)
    return m


# ===========================================================================
# Output writers (deterministic, byte-stable, NON-CANDIDATE labelled)
# ===========================================================================

YAML_HEADER = """\
# NON-CANDIDATE middle-exploration palette (branch dev/numeric-palettes).
# Generated by scripts/middle_palette.py -- the SAME numeric objective as
# scripts/numeric_palette.py (worst normalised distance-matrix margin under
# normal + simulated dichromat vision, same-family anti-collapse floor) but
# optimised INSIDE taste fences: per-role hue convention windows, lightness
# +/-0.04 (inks) / +/-0.06 (surfaces) around candidate-b night, chroma caps
# syntax<=0.12 diagnostics<=0.16 surfaces<=0.10 and <=70% of max_chroma,
# WCAG floors hard against every co-occurring surface.  Fence provenance:
# the owner rejected the unconstrained numeric themes ("the magenta is very
# in-your-face"); see NUMERIC.md, section "Middle frontier".
# Promotion to a candidate is a HUMAN decision, not taken here."""


def write_palette_yaml(
    path: Path, name: str, state: dict, problem: MiddleProblem, seed: int,
    extra_meta: dict,
) -> None:
    lines = [YAML_HEADER]
    lines += [
        f"name: {name}",
        "variant: night",
        "format: oklch",
        "candidate: false",
        "source: middle-optimizer",
        f"seed: {seed}",
        "note: >",
        "  NON-CANDIDATE middle exploration. Numeric objective, taste fences:",
        "  hue windows, L +/-0.04 ink / +/-0.06 surface, chroma caps 0.12/0.16/0.10",
        "  and 70% of the sRGB gamut edge, WCAG floors vs every co-occurring",
        "  surface. NOT a candidate; promotion is a human decision.",
        "meta:",
        "  candidate: false",
        "  generated: middle-optimizer",
        f"  seed: {seed}",
        "  objective: 'min(dE/0.13 must-normal, dE/0.09 must-CVD, 2.0*dE/0.08 should, dE/0.03 anti-collapse)'",
        f"  scaffold: {np.SCAFFOLD_SOURCE}",
        "  fences: hue-windows+L-deltas+chroma-caps+0.70-gamut (see scripts/middle_palette.py)",
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
    return np._esc(s)


def write_variants_html(path: Path, problem: MiddleProblem, entries: list[dict]) -> None:
    """Self-contained dark page (numeric_palette.write_variants_html, with
    the middle banner): swatch strips + the R specimen per palette, candidate-b
    first, then the middle picks, then numeric-n01 as the frontier reference."""
    from grotto.specimens import specimen

    r_spec = specimen("r")

    def strip(hx, roles) -> str:
        spans = "".join(
            f'<span title="{r} {hx.get(r, "")}" style="background:{hx.get(r, "#000")};'
            f'color:{hx["fg"]};padding:1px 6px;margin-right:3px;border-radius:3px">{r}</span>'
            for r in roles if r in hx
        )
        return f"<div class='strip'>{spans}</div>"

    cells = []
    for e in entries:
        hx = e["hexes"]
        m = e["metrics"]
        extra = ""
        if "diff_added_removed_deutan_de" in m and m["diff_added_removed_deutan_de"] is not None:
            extra = (f" &middot; diff deutan dE {m['diff_added_removed_deutan_de']:.3f}"
                     f" &middot; number/constant dE {m.get('number_constant_de', float('nan')):.3f}")
        cells.append(
            "<div class='cell'>"
            f"<h3>{_esc(e['label'])} <span class='kind'>{_esc(e['kind'])}</span></h3>"
            f"<div class='meta'>worst matrix margin {m['worst_margin_matrix']:.3f} "
            f"({m['argmin']['pair'][0]}/{m['argmin']['pair'][1]}, {_esc(m['argmin']['class'])})"
            f" &middot; must-CVD {m['worst_margin_must_cvd']:.3f}"
            f" &middot; min categorical dE {m['min_categorical_de']:.3f}"
            f" &middot; categorical C mean {m['mean_categorical_chroma']:.3f}"
            f" / max {m['max_categorical_chroma']:.3f}"
            f" &middot; min WCAG {m['min_wcag']:.2f}{extra}</div>"
            f"{strip(hx, problem.categorical)}"
            f"{strip(hx, np.DIAGNOSTIC_SWATCH_ROLES)}"
            f"{strip(hx, np.SURFACE_SWATCH_ROLES)}"
            f"<pre style='background:{hx['bg']};color:{hx['fg']};padding:10px;margin:0;"
            f"border-radius:6px;overflow:auto'>{np.render_specimen_html(hx, r_spec)}</pre>"
            "</div>"
        )
    css = (
        "body{margin:0;background:#141414;color:#d8d8d8;font-family:ui-monospace,Menlo,Consolas,monospace;"
        "font-size:13px;padding:18px} h1{font-size:1.3rem} h3{margin:.2em 0 .1em}"
        ".meta{color:#999;font-size:.78rem} .kind{color:#7f9f7f;font-size:.7rem}"
        ".cell{margin:0 0 26px} pre{line-height:1.5;font-size:12px} .strip{margin:3px 0}"
        ".banner{background:#1f212b;padding:.6em .8em;border-radius:6px;margin:.8em 0;"
        "border-left:3px solid #8a7a4a}"
    )
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<title>middle night palettes</title><style>" + css + "</style></head><body>"
        "<h1>Middle-frontier Night palettes &middot; NON-CANDIDATE</h1>"
        "<div class='banner'>NON-CANDIDATE exploration (branch dev/numeric-palettes). "
        "Middle palettes optimise the SAME numeric objective as the N-Explore themes "
        "(worst normalised distance-matrix margin, normal + simulated dichromat vision) "
        "but INSIDE taste fences: hue convention windows, lightness +/-0.04/0.06 around "
        "candidate-b night, chroma caps (syntax 0.12, diagnostics 0.16, surfaces 0.10, "
        "70% of the gamut edge) and WCAG floors vs every co-occurring surface. Provenance: "
        "the owner rejected the unconstrained numeric look &mdash; <i>&ldquo;"
        + _esc(OWNER_FEEDBACK) + "&rdquo;</i>. candidate-b night is the baseline; "
        "numeric-n01 is the unconstrained frontier for reference.</div>"
        + "".join(cells)
        + "</body></html>"
    )
    path.write_text(html, encoding="utf-8")


def write_vscode_extension(
    out_dir: Path, problem: MiddleProblem, entries: list[dict], k: int = 3,
    install: bool = True,
) -> Path:
    """Top-K themes through the existing mapping, labels
    'Grotto M-Explore 01..03 Night'; copied into the real extensions dir
    unless suppressed (same pattern as numeric_palette.write_vscode_extension)."""
    from grotto import vscode as gv

    mapping = gv._load_mapping(REPO / "spec/mappings/vscode.yaml", problem.roles_spec)
    themes_dir = out_dir / "themes"
    themes_dir.mkdir(parents=True, exist_ok=True)
    themes = []
    for i, e in enumerate(entries[:k], 1):
        pal = Palette(
            e["label"], "night", e["hexes"], source="hex",
            note="NON-CANDIDATE middle exploration",
            meta={"candidate": False, "generated": "middle-optimizer"},
        )
        theme = gv._build_theme(
            pal, f"Grotto M-Explore {i:02d} Night", "night", mapping,
            source_name=e.get("source_name", "middle"),
            source_sha256=e.get("sha", "middle-exploration"),
        )
        theme["grotto"]["candidate"] = False
        theme["grotto"]["note"] = (
            "NON-CANDIDATE middle-exploration theme (branch dev/numeric-palettes). "
            "Numeric objective inside taste fences; see NUMERIC.md."
        )
        rel = f"themes/middle-explore-{i:02d}-night.json"
        (out_dir / rel).write_text(gv._dump(theme), encoding="utf-8", newline="\n")
        themes.append(
            {"label": f"Grotto M-Explore {i:02d} Night", "uiTheme": "vs-dark", "path": rel}
        )
    pkg = {
        "name": "grotto-middle-exploration",
        "displayName": "Grotto Middle Exploration (NON-CANDIDATE)",
        "description": (
            "Night themes from the middle-frontier optimizer (numeric objective "
            "inside taste fences); exploration material, not a candidate."
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
    ap.add_argument("--restarts", type=int, default=24)
    ap.add_argument("--samples", type=int, default=16)
    ap.add_argument("--refine-passes", type=int, default=30)
    ap.add_argument("--n-palettes", type=int, default=3)
    ap.add_argument("--out", default="out/middle-night")
    ap.add_argument("--no-install", action="store_true",
                    help="generate the extension dir but do not copy it into the "
                         "real VS Code extensions directory")
    args = ap.parse_args()

    t0 = time.monotonic()
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    problem = MiddleProblem()
    print(
        f"[problem] {len(problem.chromatic)} chromatic roles optimised inside fences, "
        f"{len(problem.scaffold)} scaffold roles verbatim from {np.SCAFFOLD_SOURCE}; "
        f"{len(problem.must_pairs)} must pairs, {len(problem.should_pairs)} should "
        f"pairs, {len(problem.terms)} objective terms, "
        f"{len(problem.same_family_pairs)} same_family pairs"
    )

    results = np.run_search(
        problem, seed=args.seed, restarts=args.restarts, samples=args.samples,
        refine_passes=args.refine_passes, log=print,
    )
    print(f"[search] {len(results)} refined results in {time.monotonic() - t0:.1f}s; "
          f"best J={results[0]['J']:.4f}")

    # what the fences leave on the two distance debts (independent of the run)
    diff_bound = fence_bound_diff_deutan(problem)
    print(f"[bound] diff_added/diff_removed deutan pair-only fence bound: "
          f"{diff_bound['best_deutan_de']} (margin {diff_bound['margin']})")

    base_hexes = problem.hexes(problem.baseline_lch)
    base_metrics = middle_palette_metrics(problem, base_hexes)
    print(f"[baseline] candidate-b night (= scaffold): worst matrix margin "
          f"{base_metrics['worst_margin_matrix']:.4f} argmin={base_metrics['argmin']}")

    picked = np.diverse_pick(results, args.n_palettes, min_mean_dh=15.0)
    entries = []
    sf_reports = []
    for i, r in enumerate(picked, 1):
        state = place_unconstrained_fenced(problem, dict(r["state"]))
        sf = enforce_same_family_min(problem, state)
        if sf:
            sf_reports.extend({"palette": i, **e} for e in sf)
            unfixable = [
                e for e in sf if not e["repaired"]
                and any(role in problem.chromatic for role in e["pair"])
            ]
            assert not unfixable, f"same_family min-distance unrepairable: {unfixable}"
        hexes = problem.hexes(state)
        bad = np.check_feasible(problem, hexes)
        assert not bad, f"optimized palette failed hard constraints: {bad}"
        fences = problem.fence_audit(hexes) + problem.fence_audit_state(state)
        assert not fences, f"optimized palette left the fences: {fences}"
        m = middle_palette_metrics(problem, hexes)
        assert m["number_constant_de"] >= problem.th_anticollapse, (
            f"debt 1 not fixed: number/constant dE {m['number_constant_de']}"
        )
        name = f"middle-m{i:02d}"
        path = out / f"{name}.night.yaml"
        write_palette_yaml(
            path, name, state, problem, args.seed,
            {"restart-kind": r["kind"], "j": round(m["worst_margin_overall"], 4),
             "j2-mean-margin": round(r["J2"], 4)},
        )
        entries.append(
            {"label": name, "kind": f"middle ({r['kind']} restart)", "hexes": hexes,
             "metrics": m, "source_name": path.name, "state": state}
        )
        print(f"[palette] {name}: J={m['worst_margin_overall']:.4f} "
              f"matrix={m['worst_margin_matrix']:.4f} argmin={m['argmin']} "
              f"minCatDE={m['min_categorical_de']:.3f} "
              f"meanC={m['mean_categorical_chroma']:.3f} maxC={m['max_categorical_chroma']:.3f} "
              f"diffDeutan={m['diff_added_removed_deutan_de']:.3f} "
              f"numConst={m['number_constant_de']:.3f}")

    # comparison entries: the baseline first, the numeric frontier last
    entries.insert(
        0,
        {"label": "candidate-b-balanced", "kind": "committed candidate (baseline)",
         "hexes": base_hexes, "metrics": base_metrics,
         "source_name": f"{np.SCAFFOLD_SOURCE}", "state": problem.baseline_lch},
    )
    n01_path = NUMERIC_DIR / "numeric-n01.night.yaml"
    if n01_path.exists():
        n01 = dict(Palette.from_yaml(n01_path).colors)
        entries.append(
            {"label": "numeric-n01", "kind": "numeric frontier (reference)",
             "hexes": n01, "metrics": middle_palette_metrics(problem, n01),
             "source_name": n01_path.name, "state": None}
        )

    metrics = {
        "schema": "grotto.middle-night",
        "schema_version": "1",
        "generated_by": "scripts/middle_palette.py",
        "seed": args.seed,
        "restarts": args.restarts,
        "samples": args.samples,
        "refine_passes": args.refine_passes,
        "objective": {
            "formula": "J = min(min_must_normal, min_must_cvd, 2.0 * min_should, min_anticollapse)",
            "must_normal_threshold": problem.th_must_normal,
            "must_cvd_threshold": problem.th_must_cvd,
            "should_threshold": problem.th_should,
            "should_weight": np.SHOULD_WEIGHT,
            "anticollapse_threshold": problem.th_anticollapse,
            "cvd": "protan/deutan/tritan at severity 1.0, Brettel (population-average models)",
            "secondary": "J2 = mean of all normalised terms (greedy plateau tie-break)",
        },
        "fences": {
            "hue_windows": {r: [list(w) for w in ws] for r, ws in sorted(HUE_WINDOWS.items())},
            "ink_l_delta": INK_L_DELTA,
            "surface_l_delta": SURFACE_L_DELTA,
            "chroma_caps": {"syntax": SYNTAX_CAP, "diagnostic": DIAGNOSTIC_CAP,
                            "surface": SURFACE_CAP, "gamut_fraction": GAMUT_FRACTION_CAP},
            "provenance": (
                "owner feedback on the installed numeric N-Explore themes: "
                + OWNER_FEEDBACK
            ),
            "scaffold_verbatim_from": np.SCAFFOLD_SOURCE,
            "roles": {
                "syntax": list(SYNTAX_ROLES),
                "diagnostic": list(DIAGNOSTIC_ROLES),
                "highlight_surface": list(HIGHLIGHT_SURFACE_ROLES),
            },
        },
        "roles": {
            "scaffold": sorted(problem.scaffold),
            "optimized": list(problem.chromatic),
            "categorical": list(problem.categorical),
        },
        "thresholds_source": "spec/distance-matrix.yaml (READ, not edited)",
        "floors_source": "spec/roles.yaml accessibility_floor via spec/environments.yaml",
        "debts": {
            "number_constant_min_distance": problem.th_anticollapse,
            "diff_deutan_threshold": problem.th_must_cvd,
            "diff_deutan_fence_bound": diff_bound,
            "same_family_enforcement": sf_reports,
        },
        "palettes": [
            {"name": e["label"], "kind": e["kind"], "source": e["source_name"], **e["metrics"]}
            for e in entries
        ],
        "note": (
            "NON-CANDIDATE middle exploration (branch dev/numeric-palettes). "
            "WCAG numbers are compliance checks; CVD simulations are population-"
            "average dichromat models; APCA is not used on this branch."
        ),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    write_metrics_txt(out / "metrics.txt", metrics)
    write_variants_html(out / "variants.html", problem, entries)

    top = [
        {"label": e["label"], "hexes": e["hexes"], "source_name": e["source_name"],
         "sha": "middle-exploration"}
        for e in entries if e["label"].startswith("middle-")
    ][:3]
    ext = write_vscode_extension(
        out / "vscode-preview", problem, top, k=3, install=not args.no_install
    )
    print(f"[vscode] exploration extension at {ext}")
    print(f"[done] {time.monotonic() - t0:.1f}s total; artifacts in {out}")


def write_metrics_txt(path: Path, metrics: dict) -> None:
    """Human-readable three-way comparison (deterministic formatting)."""
    L = []
    L.append("NON-CANDIDATE middle-night metrics (branch dev/numeric-palettes)")
    L.append("=" * 78)
    L.append("objective: UNCHANGED from numeric_palette.py -- J = min(must-normal")
    L.append(f"  dE/{metrics['objective']['must_normal_threshold']}, must-CVD "
             f"dE/{metrics['objective']['must_cvd_threshold']} (protan/deutan/tritan@1.0), "
             f"{metrics['objective']['should_weight']} * should dE/{metrics['objective']['should_threshold']}, "
             f"anticollapse dE/{metrics['objective']['anticollapse_threshold']})")
    f = metrics["fences"]
    L.append("fences: hue windows per role; L +/-"
             f"{f['ink_l_delta']} ink / +/-{f['surface_l_delta']} surface vs candidate-b night;")
    L.append(f"  chroma <= syntax {f['chroma_caps']['syntax']}, diagnostics "
             f"{f['chroma_caps']['diagnostic']}, surfaces {f['chroma_caps']['surface']}, "
             f"and <= {f['chroma_caps']['gamut_fraction']:.0%} of max_chroma(L,h)")
    L.append(f"  provenance: owner on the numeric N-Explore themes: \"{f['provenance'].split(': ', 1)[1]}\"")
    L.append(f"seed {metrics['seed']}, {metrics['restarts']} restarts")
    L.append("")
    hdr = (f"{'palette':<24}{'J':>7}{'matrix':>7}{'mustN':>7}{'mustCVD':>8}{'should':>7}"
           f"{'minCatDE':>9}{'meanC':>7}{'maxC':>7}{'minWCAG':>8}{'viol':>5}"
           f"{'diffDeut':>9}{'num/const':>10}")
    L.append(hdr)
    L.append("-" * len(hdr))
    for p in metrics["palettes"]:
        L.append(
            f"{p['name']:<24}{p['worst_margin_overall']:>7.3f}"
            f"{p['worst_margin_matrix']:>7.3f}"
            f"{p['worst_margin_must_normal']:>7.3f}{p['worst_margin_must_cvd']:>8.3f}"
            f"{p['worst_margin_should']:>7.3f}"
            f"{p['min_categorical_de']:>9.3f}"
            f"{p['mean_categorical_chroma']:>7.3f}{p['max_categorical_chroma']:>7.3f}"
            f"{p['min_wcag']:>8.2f}{p['wcag_violations']:>5d}"
            f"{p['diff_added_removed_deutan_de']:>9.3f}"
            f"{p['number_constant_de']:>10.3f}"
        )
    L.append("")
    db = metrics["debts"]["diff_deutan_fence_bound"]
    L.append("debt bounds (what the fences leave):")
    L.append(f"  diff_added/diff_removed deutan pair-only best inside fences: "
             f"{db['best_deutan_de']} (margin {db['margin']} vs threshold {db['threshold']})")
    L.append(f"    at diff_added LCH {db['diff_added_lch']} / diff_removed LCH {db['diff_removed_lch']}")
    L.append(f"  number/constant same_family min distance: "
             f"{metrics['debts']['number_constant_min_distance']}")
    if metrics["debts"]["same_family_enforcement"]:
        L.append("  same_family repairs applied:")
        for e in metrics["debts"]["same_family_enforcement"]:
            L.append(f"    m{e['palette']:02d} {'/'.join(e['pair'])}: "
                     f"{e['de_before']} -> {e.get('de_after', '-')} repaired={e['repaired']}")
    else:
        L.append("  same_family repairs: none needed (all pairs already >= min)")
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
    L.append("labels: WCAG = compliance; CVD = population-average Brettel models; "
             "APCA not used. NON-CANDIDATE exploration output.")
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
