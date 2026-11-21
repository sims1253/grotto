"""Scoring instrument for the soft-objective Night palettes.

This module is deliberately SEPARATE from the search (``soft_palette.py``).
It never looks at the search's own report: it takes a palette YAML on disk and
re-derives every number from the committed specs.  That is the point -- the
project's own history (PR #1, PR #2, NUMERIC.md) is a series of instruments
that disagreed with their authors' expectations, so the benchmark number must
be produced by code that cannot see the optimiser.

It implements the two proposals in ``docs/review/optimizer-constraints.md``:

1. **Shortfall instead of max-min.**  The middle/numeric searches maximise the
   WORST normalised margin ``J = min_i(m_i)`` and break plateaus on the mean
   margin.  Both terms keep paying for separation that has already been
   achieved, which is why the numeric frontier spent the whole gamut on it
   and looked like in-your-face magenta.  The proposal replaces them with a
   shortfall: ``s_i = max(0, 1 - m_i) ** 2``.  A term contributes zero once
   it clears its own threshold, so excess buys nothing.

2. **An emphasis budget.**  "Large, persistent areas stay quieter than small
   accents" and "reduce distracting accents".  Chroma is summed weighted by
   the visible area each role occupies, taken from real data in the repo where
   it exists (character share of the eight code specimens in
   ``grotto.specimens``) and from the declared ``area_class`` of
   ``spec/roles.yaml`` for the highlight surfaces, which no specimen can
   measure.  The canvas is excluded: averaging a mostly-dark background into
   one mean would hide the intense syntax the budget exists to control.

Both are declared trial settings, not perceptual laws.  See ``CONSTANTS``
below -- every number is named, sourced, and stated as adjustable.

Usage:
    uv run python scripts/soft_metric.py out/soft-night/soft-s01.night.yaml
    uv run python scripts/soft_metric.py --json PATH...
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from grotto.color import hex_to_oklch  # noqa: E402
from grotto.spec import Palette, RoleSpec  # noqa: E402
from grotto.specimens import SPECIMENS  # noqa: E402

import numeric_palette as np_  # noqa: E402

# ===========================================================================
# Declared constants -- every one is a trial setting, stated as such
# ===========================================================================

#: Exponent of the shortfall.  The proposal says ``max(0, 1 - m)^2``; squared
#: makes the gradient vanish near the target, so a term that is 0.95 of its
#: threshold does not compete with one that is 0.20 of it.
SHORTFALL_EXP = 2.0

#: Area share attributed to each declared ``area_class`` of spec/roles.yaml.
#: Used ONLY for the highlight surfaces and borders, which occupy screen area
#: that no source specimen can measure.  Ink areas come from measured
#: character share instead -- see ``ink_shares``.
#:
#: Declared shape (not a research constant): a selection or diff wash can
#: cover most of the editor viewport, a search highlight a fraction of it, a
#: breakpoint gutter mark a few pixels.  The numbers below are ordered
#: correctly and sum to 1.0 over a complete composition; their absolute scale
#: only matters through the surface/ink weight ratio ``SURFACE_AREA_WEIGHT``.
AREA_CLASS_SHARE = {
    "dominant": 0.550,
    "major": 0.220,
    "minor": 0.100,
    "trace": 0.020,
}

#: Relative weight of a declared surface area against a measured ink area.
#: Surfaces are genuinely large, but their chroma is capped low by the fences;
#: weighting them equally with per-character ink shares would make the budget
#: a surface-chroma budget in disguise.
SURFACE_AREA_WEIGHT = 0.60

#: Area-weighted chroma allowed before the emphasis penalty starts to bite.
#:
#: CALIBRATED BY MEASUREMENT, not chosen.  Scores on this instrument at the
#: values written here (see ``docs/review/soft-objective.md`` for the full
#: table):
#:
#:     candidate-a restrained night   0.0085
#:     candidate-b balanced  night    0.0199
#:     candidate-c expressive night   0.0271
#:     middle frontier   (best)       0.0456
#:     rejected numeric frontier     0.0857
#:
#: The budget sits at the middle frontier's own level.  That is the palette
#: family that bought the most separation while keeping every hue convention
#: intact and every WCAG floor met -- in other words, the most emphasis the
#: conventions have been shown to justify.  Above it the penalty starts
#: pulling the search back; below it, no palette could be produced at all.
EMPHASIS_BUDGET = 0.045

#: How hard the emphasis penalty pushes, relative to one unit of SEP.
#: Chosen so that halving the emphasis excess buys about as much utility as
#: closing 5% of the total shortfall -- large enough that the numeric
#: frontier's 0.086 lands clearly BELOW the middle frontier it out-separates,
#: small enough that it never overrides an accessibility or fence constraint.
EMPHASIS_WEIGHT = 0.35

#: Roles whose chroma is counted with a declared surface area rather than a
#: measured ink area.
SURFACE_ROLES = frozenset(
    {
        "selection",
        "search_match",
        "search_match_current",
        "diff_added",
        "diff_removed",
        "diff_changed",
        "debug_current",
        "active_line",
        "line_number_active",
        "focus",
        "breakpoint",
    }
)

#: Minimum chroma for every chromatic role: a role with a hue convention must
#: actually carry that hue.
#:
#: NOT a new number.  It is the repository's own declared "hue is
#: perceptually present" threshold, ``HUE_AUDIT_MIN_CHROMA`` in
#: ``scripts/middle_palette.py`` -- the chroma below which that fence audit
#: skips the hue-window check because the hue channel carries no readable
#: signal.  Reading a floor off the same constant that already decides
#: whether hue matters keeps the two in agreement.
#:
#: Why a floor at all: every fence in the middle search is a CEILING.  A
#: ceiling-only search has a degenerate optimum, and this repository has hit
#: it repeatedly -- NUMERIC.md §5.3 ("keyword, string and success sit at
#: L ~= 0.98-0.99 with almost no chroma"), §10 ("it zeroes one diagnostic's
#: chroma to buy lightness separation"; "diff_changed parks at the canvas
#: floor ... a nearly invisible changed-line wash"), and PR #2's own
#: ``docs/review/optimizer-constraints.md`` ("The fences as specified have
#: ceilings, not floors; whether diagnostics need a chroma floor is a fence
#: decision for the owner").  Under the shortfall objective this is not a
#: corner case: a term that has cleared its threshold contributes exactly
#: zero, so achromatic is always the cheapest way to stay cleared.
#:
#: Owner decision (this session): diagnostics, diff and search states carry
#: meaning by hue and must keep it.  The floor applies to every chromatic
#: role; 0.02 is well under the 0.10-0.16 class caps, so it constrains only
#: the degenerate tail, never a palette a person chose.
CHROMA_FLOOR = 0.02

#: Hex-round tolerance for the chroma floor, the same scale the fence audit
#: already uses for its chroma ceilings (CHROMA_AUDIT_TOL).
CHROMA_FLOOR_TOL = 0.0015


#: Instrument version.  2 adds the surface terms below and credits CVD terms
#: a delivered channel discharges (``channel_covered_cvd``); SEP is a mean
#: over the term table, so v1 and v2 numbers are NOT comparable.
INSTRUMENT_VERSION = 2

#: Order of ``contrast_target`` classes, quietest first.  A highlight
#: surface's VISIBILITY band runs from its own class's lightness step to the
#: next class's: ``src/grotto/model.py`` SURFACE_STEPS is the transform's own
#: "how far a surface of this class stands off the canvas".  The committed
#: candidate-b night -- that transform's output -- sits inside the band for
#: every highlight surface; this instrument (v1) checked none of them, and was
#: blind both ways: a ``low`` search match parked at the canvas cost nothing,
#: and a ``minimal`` diff wash stepped 4x too far (to buy CVD separation with
#: lightness, the O4-vs-O2 trade DESIGN.md resolves AGAINST) cost nothing.
CONTRAST_TARGET_ORDER = ("minimal", "low", "comfortable", "high", "maximal")


# ===========================================================================
# Surface terms (instrument v2)
# ===========================================================================


def visibility_band(contrast_target: str) -> tuple[float, float]:
    """(lo, hi) OKLab dE off the canvas for a surface of this class."""
    from grotto.model import SURFACE_STEPS

    i = CONTRAST_TARGET_ORDER.index(contrast_target)
    lo = SURFACE_STEPS[contrast_target]
    hi = (SURFACE_STEPS[CONTRAST_TARGET_ORDER[i + 1]]
          if i + 1 < len(CONTRAST_TARGET_ORDER) else math.inf)
    return lo, hi


def surface_terms(problem) -> list[dict]:
    """The instrument-v2 terms, in the term-table format.

    * ``visibility`` -- one per co-occurring surface with a contrast_target:
      dE(surface, bg) inside ``visibility_band``.  Margin
      ``min(dE/lo, hi/dE)``, so the same shortfall ``max(0, 1-m)^2`` charges
      a wash that vanishes into the canvas and one that shouts, each bounded
      by 1 like every other term.
    * ``anticollapse`` -- co-occurring surface pairs the matrix does not
      constrain, at its own ``same_family.min_distance`` ("still not
      identical"): the rule v1 applied to categorical inks only.  v2's
      shipped diff_changed and search_match were dE 0.01 apart.
    """
    roles = problem.roles_spec.roles
    surfaces = [s for s in problem.surfaces if s in problem.present]
    out = []
    for s in surfaces:
        ct = roles[s].contrast_target
        if ct is None:
            continue
        lo, hi = visibility_band(ct)
        out.append({"cls": "visibility", "a": s, "b": "bg", "kind": "band",
                    "lo": lo, "hi": hi, "th": lo})
    constrained = {frozenset(p) for p in problem.must_pairs + problem.should_pairs}
    for i, a in enumerate(surfaces):
        for b in surfaces[i + 1:]:
            if frozenset((a, b)) in constrained:
                continue
            out.append({"cls": "anticollapse", "a": a, "b": b, "kind": "normal",
                        "th": problem.th_anticollapse})
    return out


def channel_covered_cvd(problem) -> set[tuple[str, str]]:
    """must pairs whose CVD obligation a DELIVERED channel discharges.

    ``spec/distance-matrix.yaml``: "Pairs that cannot meet this [CVD floor]
    must carry a redundant channel" -- the floor OR a channel, not both.
    ``grotto.channels.judge`` (the redundant-channel audit) answers, per PAIR,
    whether a channel the editor really draws puts different marks on the two
    roles.  Only those pairs are credited, and only their CVD terms: no channel
    excuses a normal-vision shortfall, and the three pairs the audit found
    uncovered (error/warning, search_match/search_match_current,
    selection/active_line) keep every term.
    """
    from grotto.channels import judge, load_delivery

    delivery = load_delivery(REPO / "spec/mappings/vscode.yaml")
    return {
        (a, b) for a, b in problem.must_pairs
        if judge(problem.roles_spec, a, b, delivery).covered
    }


def instrument_terms(problem, channel_credit: bool = True) -> list[dict]:
    """The full v2 term table: the matrix terms, minus channel-discharged
    CVD terms, plus the surface terms.

    ``channel_credit=False`` keeps every CVD term: CVD is scored on COLOUR
    ALONE.  That is the objective of the experimental CVD profile.
    """
    covered = channel_covered_cvd(problem) if channel_credit else set()
    base = [
        t for t in problem.terms
        if not (t["cls"] == "must" and t["kind"] != "normal"
                and (t["a"], t["b"]) in covered)
    ]
    return base + surface_terms(problem)


def band_margin(de: float, lo: float, hi: float) -> float:
    return min(de / lo, (hi / de) if de > 0 else math.inf)


def term_value(t: dict, hexes: dict[str, str]) -> float:
    """Normalised margin of one term, any kind (shared with the search)."""
    if t["kind"] == "band":
        de = np_._dE(np_._oklab_of(hexes[t["a"]]), np_._oklab_of(hexes[t["b"]]))
        return band_margin(de, t["lo"], t["hi"])
    if t["kind"] == "normal":
        return np_._dE(np_._oklab_of(hexes[t["a"]]), np_._oklab_of(hexes[t["b"]])) / t["th"]
    return np_._dE(np_._sim_oklab(hexes[t["a"]], t["kind"]),
                   np_._sim_oklab(hexes[t["b"]], t["kind"])) / t["th"]


# ===========================================================================
# Area model
# ===========================================================================

_ink_shares: dict[str, float] | None = None


def ink_shares() -> dict[str, float]:
    """Mean per-character share of each role across the eight specimens.

    Measured, not declared.  Every span of every specimen is counted in
    characters (whitespace included -- it is painted as ``fg``), and the
    per-language shares are averaged so a language does not dominate by length.
    A role that appears in no specimen gets 0 and is simply not counted.
    """
    global _ink_shares
    if _ink_shares is not None:
        return _ink_shares
    acc: dict[str, float] = {}
    for spec in SPECIMENS.values():
        counts: dict[str, int] = {}
        total = 0
        for role, text in spec.spans():
            n = len(text)
            counts[role] = counts.get(role, 0) + n
            total += n
        if not total:
            continue
        for role, n in counts.items():
            acc[role] = acc.get(role, 0.0) + (n / total) / len(SPECIMENS)
    _ink_shares = acc
    return acc


def area_weights(role: str, area_class: str) -> float:
    """Weight one role contributes to the emphasis sum.

    Inks use their measured character share.  Surfaces and borders use their
    declared area class, scaled so that ``bg`` alone would not dominate.
    """
    if role in SURFACE_ROLES:
        return SURFACE_AREA_WEIGHT * AREA_CLASS_SHARE.get(area_class, 0.02)
    return ink_shares().get(role, 0.0)


def area_table() -> dict[str, dict[str, float | str]]:
    """role -> {area_class, weight, source} -- reported with every result."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml").roles
    out: dict[str, dict[str, float | str]] = {}
    for name, role in roles.items():
        ac = str(getattr(role, "area_class", "minor") or "minor")
        w = area_weights(name, ac)
        if w <= 0.0:
            continue
        out[name] = {
            "area_class": ac,
            "weight": w,
            "source": "declared" if name in SURFACE_ROLES else "measured",
        }
    return out


# ===========================================================================
# Scoring
# ===========================================================================


def emphasis(colors: dict[str, str], table: dict[str, dict[str, float | str]]) -> dict:
    """Area-weighted mean chroma, split into its ink and surface halves."""
    tot_w = 0.0
    acc = 0.0
    ink_acc = ink_w = 0.0
    surf_acc = surf_w = 0.0
    per_role: dict[str, float] = {}
    for role, info in table.items():
        hexv = colors.get(role)
        if hexv is None:
            continue
        c = hex_to_oklch(hexv)[1]
        w = float(info["weight"])
        tot_w += w
        acc += w * c
        per_role[role] = c
        if info["source"] == "declared":
            surf_w += w
            surf_acc += w * c
        else:
            ink_w += w
            ink_acc += w * c
    if tot_w <= 0.0:
        return {"emph": 0.0, "emph_ink": 0.0, "emph_surface": 0.0, "per_role": {}}
    return {
        "emph": acc / tot_w,
        "emph_ink": (ink_acc / ink_w) if ink_w else 0.0,
        "emph_surface": (surf_acc / surf_w) if surf_w else 0.0,
        "per_role": per_role,
    }


def shortfall(vals: list[float], exp: float = SHORTFALL_EXP) -> dict:
    """SEP = mean_i max(0, 1 - m_i)**exp over the whole term table."""
    if not vals:
        return {"sep": 0.0, "terms": 0, "at_target": 0, "worst": 0.0}
    losses = [max(0.0, 1.0 - v) ** exp for v in vals]
    return {
        "sep": sum(losses) / len(losses),
        "terms": len(vals),
        "at_target": sum(1 for v in vals if v >= 1.0),
        "worst": min(vals),
    }


def cvd_colour_only(problem, hexes: dict[str, str]) -> tuple[int, int]:
    """(passing, total) must-pair CVD checks on colour alone, no channel credit."""
    cvd = [t for t in problem.terms if t["cls"] == "must" and t["kind"] != "normal"]
    return sum(1 for t in cvd if term_value(t, hexes) >= 1.0), len(cvd)


def score(palette_path: Path, channel_credit: bool = True) -> dict:
    """Every number the benchmark reports, re-derived from one palette file."""
    palette = Palette.from_yaml(palette_path)
    colors = {r: str(v) for r, v in palette.colors.items()}
    problem = np_.NumericProblem()
    hexes = {r: colors[r] for r in problem.present if r in colors}
    missing = [r for r in problem.present if r not in colors]
    ev = np_.evaluate(problem, hexes)   # v1 monitors (J, per-class minima)
    cvd_pass, cvd_total = cvd_colour_only(problem, hexes)
    terms = instrument_terms(problem, channel_credit=channel_credit)
    vals = [term_value(t, hexes) for t in terms]
    sf = shortfall(vals)
    vis = {t["a"]: v for t, v in zip(terms, vals) if t["cls"] == "visibility"}
    extra = [t for t in terms if t["cls"] == "anticollapse" and t["a"] in problem.surfaces]
    extra_vals = [term_value(t, hexes) for t in extra]
    table = area_table()
    em = emphasis(colors, table)

    sep = sf["sep"]
    excess = max(0.0, (em["emph"] - EMPHASIS_BUDGET) / EMPHASIS_BUDGET)
    utility = 1.0 - sep - EMPHASIS_WEIGHT * excess

    wcag_bad = np_.check_feasible(problem, hexes)
    cat = [colors[r] for r in problem.categorical if r in colors]
    chromas = [hex_to_oklch(h)[1] for h in cat]
    return {
        "palette": palette_path.name,
        "utility": utility,
        "sep": sep,
        "emph": em["emph"],
        "emph_ink": em["emph_ink"],
        "emph_surface": em["emph_surface"],
        "emph_excess": excess,
        "worst_margin": ev["J"],
        "mean_margin": ev["J2"],
        "terms": sf["terms"],
        "at_target": sf["at_target"],
        "min_must_normal": ev["min_must_normal"],
        "min_must_cvd": ev["min_must_cvd"],
        "min_should": ev["min_should"],
        "min_anticollapse": ev["min_anticollapse"],
        "mean_cat_chroma": (sum(chromas) / len(chromas)) if chromas else 0.0,
        "max_cat_chroma": max(chromas) if chromas else 0.0,
        "wcag_violations": len(wcag_bad),
        "missing_roles": missing,
        "argmin": list(ev["argmin"]),
        "instrument_version": INSTRUMENT_VERSION,
        "channel_credit": channel_credit,
        "cvd_pass": cvd_pass,
        "cvd_total": cvd_total,
        "min_visibility": min(vis.values()) if vis else 0.0,
        "visibility": vis,
        "min_surface_anticollapse": min(
            (v for t, v in zip(extra, extra_vals) if t["cls"] == "anticollapse"),
            default=0.0),
        "emphasis_budget": EMPHASIS_BUDGET,
        "emphasis_weight": EMPHASIS_WEIGHT,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("palettes", nargs="+")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--colour-only", action="store_true",
                    help="score CVD on colour alone (no credit for drawn channels)")
    args = ap.parse_args()
    rows = []
    for p in args.palettes:
        path = Path(p)
        if not path.is_absolute():
            path = REPO / path
        rows.append(score(path, channel_credit=not args.colour_only))
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    hdr = (f"{'palette':<34}{'utility':>9}{'sep':>8}{'emph':>8}{'worst':>8}"
           f"{'meanM':>8}{'tgt':>5}{'meanC':>7}{'maxC':>7}{'wcag':>6}{'cvd':>7}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['palette']:<34}{r['utility']:>9.4f}{r['sep']:>8.4f}"
              f"{r['emph']:>8.4f}{r['worst_margin']:>8.4f}{r['mean_margin']:>8.4f}"
              f"{r['at_target']:>5d}{r['mean_cat_chroma']:>7.3f}"
              f"{r['max_cat_chroma']:>7.3f}{r['wcag_violations']:>6d}"
              f"{r['cvd_pass']:>4d}/{r['cvd_total']}")


if __name__ == "__main__":
    main()