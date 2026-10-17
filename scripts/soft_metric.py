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


def score(palette_path: Path) -> dict:
    """Every number the benchmark reports, re-derived from one palette file."""
    palette = Palette.from_yaml(palette_path)
    colors = {r: str(v) for r, v in palette.colors.items()}
    problem = np_.NumericProblem()
    hexes = {r: colors[r] for r in problem.present if r in colors}
    missing = [r for r in problem.present if r not in colors]
    vals = problem.term_values(hexes)
    ev = np_.evaluate(problem, hexes)
    sf = shortfall(vals)
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
        "emphasis_budget": EMPHASIS_BUDGET,
        "emphasis_weight": EMPHASIS_WEIGHT,
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("palettes", nargs="+")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    rows = []
    for p in args.palettes:
        path = Path(p)
        if not path.is_absolute():
            path = REPO / path
        rows.append(score(path))
    if args.json:
        print(json.dumps(rows, indent=2))
        return
    hdr = (f"{'palette':<34}{'utility':>9}{'sep':>8}{'emph':>8}{'worst':>8}"
           f"{'meanM':>8}{'tgt':>5}{'meanC':>7}{'maxC':>7}{'wcag':>6}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        print(f"{r['palette']:<34}{r['utility']:>9.4f}{r['sep']:>8.4f}"
              f"{r['emph']:>8.4f}{r['worst_margin']:>8.4f}{r['mean_margin']:>8.4f}"
              f"{r['at_target']:>5d}{r['mean_cat_chroma']:>7.3f}"
              f"{r['max_cat_chroma']:>7.3f}{r['wcag_violations']:>6d}")


if __name__ == "__main__":
    main()