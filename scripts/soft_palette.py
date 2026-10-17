"""Soft-objective Night palette search -- the experiment from
``docs/review/optimizer-constraints.md`` (§ "Smallest useful next experiment").

What changes relative to ``scripts/middle_palette.py``
-------------------------------------------------------
The middle frontier maximises ``J = min_i(m_i)`` with the MEAN margin ``J2``
as a plateau tie-break.  Both keep paying for separation that has already
been achieved, so the search spends the entire chroma budget the fences
allow (NUMERIC.md §9: "the optimizer *spends the whole loudness budget the
fences allow*"), and the uncapped mean makes oversaturation even after the
worst pair is comfortable.  The proposal in ``docs/review/optimizer-constraints.md``
says to replace that incentive *before* adding degrees of freedom:

    For a pair with normalized separation m, use a shortfall such as
    ``max(0, 1 - m)^2``.  This contributes zero above the target.

and to add a restrained-emphasis preference weighted by visible ink area.

So this search maximises, over palettes that satisfy every hard constraint and
stay inside the middle taste fences:

    UTILITY(P) = 1 - SEP(P) - EMPHASIS_WEIGHT * EMPHASIS_EXCESS(P)

    SEP(P)              = mean over all objective terms of max(0, 1 - m_i)^2
    EMPHASIS_EXCESS(P)  = max(0, (EMPH(P) - EMPHASIS_BUDGET) / EMPHASIS_BUDGET)
    EMPH(P)             = area-weighted mean chroma (scripts/soft_metric.py)

Unlike ``J``, SEP pays nothing for margin a term already has, and unlike J2 it
is not unbounded, so a term that clears its threshold three times over
contributes exactly as much as one that just clears it.  Unlike a plain
"reduce chroma" rule, SEP still pays for the separations that are genuinely
missing -- it just stops overpaying for the ones that are not.

What does NOT change
--------------------
Everything technical and every taste fence from the middle search is reused
untouched: the hue convention windows, the +/-0.04 ink and +/-0.06 surface
lightness fences around candidate-b Night, the class chroma caps and the 70%
of-gamut rule, WCAG 2.x floors against the canvas AND every co-occurring
surface, the verbatim neutral scaffold, gamut projection, the
``same_family.min_distance`` output gate, and the distance-matrix pair list
with its thresholds READ from ``spec/distance-matrix.yaml``.

Usage:
    uv run python scripts/soft_palette.py                       # full run
    uv run python scripts/soft_palette.py --restarts 4 --samples 8 \\
        --refine-passes 10 --out out/soft-night                # benchmark size

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

from grotto.color import oklch_to_hex  # noqa: E402

import numeric_palette as np_  # noqa: E402
import middle_palette as mp  # noqa: E402
import soft_metric as sm  # noqa: E402

DEFAULT_SEED = 20260817

#: Deterministic move list, inherited from the numeric search.  Each entry is
#: (axis, delta): hue degrees, absolute OKLCH lightness, or a fraction of the
#: role's chroma ceiling.
MOVES = np_.MOVES


# ===========================================================================
# The soft objective
# ===========================================================================


class SoftProblem(mp.MiddleProblem):
    """MiddleProblem plus the soft-objective bookkeeping.

    The fences, floors, pair list and term table are inherited exactly; this
    subclass only adds the emphasis area table (constant across a run) and a
    cached per-role chroma accessor, because the emphasis sum is the one part
    of the objective that touches every role rather than the few the term
    table constrains.
    """

    def __init__(self, chromatic=tuple(np_.CHROMATIC_ROLES)):
        super().__init__(chromatic=chromatic)
        self.area = sm.area_table()
        # Roles the emphasis sum counts, with their weights resolved once.
        self._emph_roles = {
            r: float(self.area[r]["weight"])
            for r in self.area
            if r in self.present and float(self.area[r]["weight"]) > 0.0
        }
        self._emph_total = sum(self._emph_roles.values()) or 1.0

    # -- emphasis ---------------------------------------------------------

    def chroma_table(self, hexes: dict[str, str]) -> dict[str, float]:
        """Chroma of every weighted role, keyed by role (for incremental use)."""
        from grotto.color import hex_to_oklch

        return {
            r: (hex_to_oklch(hexes[r])[1] if r in hexes else 0.0)
            for r in self._emph_roles
        }

    def emphasis_from(self, chroma: dict[str, float]) -> float:
        """Area-weighted mean chroma over the whole palette (canvas excluded)."""
        acc = 0.0
        for r, w in self._emph_roles.items():
            acc += w * chroma.get(r, 0.0)
        return acc / self._emph_total

    def emphasis(self, hexes: dict[str, str]) -> float:
        return self.emphasis_from(self.chroma_table(hexes))

    # -- objective --------------------------------------------------------

    def utility_from(self, hexes: dict[str, str], sep: float) -> float:
        e = self.emphasis(hexes)
        excess = max(0.0, (e - sm.EMPHASIS_BUDGET) / sm.EMPHASIS_BUDGET)
        return 1.0 - sep - sm.EMPHASIS_WEIGHT * excess

    def state_score(self, state: dict) -> dict:
        hexes = self.hexes(state)
        vals = self.term_values(hexes)
        sep = sm.shortfall(vals)["sep"]
        e = self.emphasis(hexes)
        excess = max(0.0, (e - sm.EMPHASIS_BUDGET) / sm.EMPHASIS_BUDGET)
        return {
            "utility": self.utility_from(hexes, sep),
            "sep": sep,
            "emph": e,
            "emph_excess": excess,
            "worst_margin": min(vals) if vals else 0.0,
            "mean_margin": (sum(vals) / len(vals)) if vals else 0.0,
            "at_target": sum(1 for v in vals if v >= 1.0),
            "terms": len(vals),
        }


# ===========================================================================
# Greedy coordinate refinement on the soft objective
# ===========================================================================


def soft_refine(
    problem: SoftProblem,
    state: dict[str, tuple[float, float, float]],
    max_passes: int,
    moves=MOVES,
) -> tuple[dict[str, tuple[float, float, float]], dict]:
    """Coordinate ascent on UTILITY, one role at a time, fixed role order.

    Each candidate move is repaired into the feasible set (WCAG floors over the
    canvas and every co-occurring surface, gamut, and every taste fence) and
    scored with the same incremental pattern numeric_palette.greedy_refine
    uses: only the terms touching the moved role are recomputed, the shortfall
    is re-summed from the cached term values, and the emphasis term is
    re-summed from the ~40 roles the area table covers.

    Acceptance is STRICT on utility.  There is deliberately no mean-margin
    tie-break: an uncapped tie-break is exactly the incentive the proposal
    asks to remove, and it would let the search buy margin the shortfall
    already scores at zero.
    """
    from grotto.color import hex_to_oklch

    hexes = problem.hexes(state)
    terms = problem.terms
    vals = problem.term_values(hexes)
    exp = sm.SHORTFALL_EXP
    loss = sum(max(0.0, 1.0 - v) ** exp for v in vals) / max(len(vals), 1)
    chroma = problem.chroma_table(hexes)
    emph = problem.emphasis_from(chroma)
    util = problem.utility_from(hexes, loss)

    def eval_with(role: str, new_hex: str):
        """(utility, updated term values) with only this role's terms redone."""
        updates = {}
        for i in problem.term_ids_by_role.get(role, ()):  # roles the matrix ignores have none
            t = terms[i]
            ha = new_hex if t["a"] == role else hexes[t["a"]]
            hb = new_hex if t["b"] == role else hexes[t["b"]]
            if t["kind"] == "normal":
                updates[i] = np_._dE(np_._oklab_of(ha), np_._oklab_of(hb)) / t["th"]
            else:
                updates[i] = (
                    np_._dE(np_._sim_oklab(ha, t["kind"]), np_._sim_oklab(hb, t["kind"]))
                    / t["th"]
                )
        tot = 0.0
        for i, v in enumerate(vals):
            v2 = updates.get(i, v)
            tot += max(0.0, 1.0 - v2) ** exp
        e = emph
        w = problem._emph_roles.get(role, 0.0)
        if w > 0.0:
            e += w * (hex_to_oklch(new_hex)[1] - chroma.get(role, 0.0)) / problem._emph_total
        excess = max(0.0, (e - sm.EMPHASIS_BUDGET) / sm.EMPHASIS_BUDGET)
        return 1.0 - (tot / max(len(vals), 1)) - sm.EMPHASIS_WEIGHT * excess, updates

    for _ in range(max_passes):
        improved = False
        for role in problem.chromatic:
            if not problem.term_ids_by_role.get(role) and role not in problem._emph_roles:
                continue
            best = None
            best_util = util
            for axis, d in moves:
                got = mp._apply_move_fenced(problem, role, state[role], axis, d, hexes)
                if got is None:
                    continue
                new_hex = oklch_to_hex(np_.project_chroma(*problem.fence_lch(role, *got)))
                u, updates = eval_with(role, new_hex)
                if u > best_util + 1e-12:
                    best_util = u
                    best = (got, new_hex, updates)
            if best is not None:
                got, new_hex, updates = best
                state[role] = got
                hexes[role] = new_hex
                vals = [updates.get(i, v) for i, v in enumerate(vals)]
                if role in chroma:
                    chroma[role] = hex_to_oklch(new_hex)[1]
                loss = sum(max(0.0, 1.0 - v) ** exp for v in vals) / max(len(vals), 1)
                emph = problem.emphasis_from(chroma)
                util = best_util
                improved = True
        if not improved:
            break

    return state, problem.state_score(state)


def run_search(
    problem: SoftProblem,
    seed: int = DEFAULT_SEED,
    restarts: int = 8,
    samples: int = 8,
    refine_passes: int = 12,
    refine_top: int = 2,
    moves=MOVES,
    log=None,
) -> list[dict]:
    """Multi-start sampling, then coordinate ascent on UTILITY.

    Each result: {'state', 'utility', 'sep', 'emph', 'kind'}.  Deterministic
    for a fixed (problem, seed, restarts, samples, moves).
    """
    rng = random.Random(seed)
    kinds = ("ladder", "bladder", "bseed", "free")
    results: list[dict] = []
    for ri in range(restarts):
        kind = kinds[ri % len(kinds)]
        pool = []
        for _ in range(samples):
            st = mp._initial_state_fenced(problem, rng, kind)
            pool.append((problem.state_score(st)["utility"], st))
        pool.sort(key=lambda t: -t[0])
        for _, st in pool[:refine_top]:
            st2, sc = soft_refine(problem, st, refine_passes, moves=moves)
            results.append({"state": st2, "kind": kind, **sc})
        if log:
            best = max(results, key=lambda r: r["utility"])
            log(
                f"[restart {ri + 1}/{restarts} kind={kind}] best utility "
                f"{best['utility']:.4f} (sep {best['sep']:.4f}, emph {best['emph']:.4f})"
            )
    results.sort(key=lambda r: (-r["utility"], r["sep"], r["emph"]))
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


# ===========================================================================
# Driver
# ===========================================================================


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument("--restarts", type=int, default=8)
    ap.add_argument("--samples", type=int, default=8)
    ap.add_argument("--refine-passes", type=int, default=12)
    ap.add_argument("--n-palettes", type=int, default=1)
    ap.add_argument("--out", default="out/soft-night")
    ap.add_argument("--no-install", action="store_true")
    args = ap.parse_args()

    t0 = time.monotonic()
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    problem = SoftProblem()
    print(
        f"[problem] {len(problem.chromatic)} chromatic roles inside the middle "
        f"fences; {len(problem.terms)} objective terms; "
        f"{len(problem.same_family_pairs)} same_family pairs; "
        f"emphasis over {len(problem._emph_roles)} weighted roles, "
        f"budget {sm.EMPHASIS_BUDGET:.3f} weight {sm.EMPHASIS_WEIGHT:.2f}"
    )

    results = run_search(
        problem, seed=args.seed, restarts=args.restarts, samples=args.samples,
        refine_passes=args.refine_passes, log=print,
    )
    print(
        f"[search] {len(results)} refined results in {time.monotonic() - t0:.1f}s; "
        f"best utility={results[0]['utility']:.4f}"
    )

    picked = np_.diverse_pick(results, args.n_palettes, min_mean_dh=15.0)
    entries = []
    for i, r in enumerate(picked, 1):
        state = mp.place_unconstrained_fenced(problem, dict(r["state"]))
        sf = mp.enforce_same_family_min(problem, state)
        unfixable = [
            e for e in sf
            if not e["repaired"] and any(role in problem.chromatic for role in e["pair"])
        ]
        assert not unfixable, f"same_family min-distance unrepairable: {unfixable}"
        hexes = problem.hexes(state)
        bad = np_.check_feasible(problem, hexes)
        assert not bad, f"hard constraint violation: {bad}"
        fences = problem.fence_audit(hexes) + problem.fence_audit_state(state)
        assert not fences, f"left the fences: {fences}"
        sc = problem.state_score(state)
        name = f"soft-s{i:02d}"
        path = out / f"{name}.night.yaml"
        mp.write_palette_yaml(
            path, name, state, problem, args.seed,
            {"restart-kind": r["kind"], "utility": round(sc["utility"], 5),
             "sep": round(sc["sep"], 5), "emphasis": round(sc["emph"], 5),
             "worst-margin": round(sc["worst_margin"], 5),
             "at-target": sc["at_target"]},
        )
        entries.append({"label": name, "state": state, "hexes": hexes,
                        "metrics": sc, "source_name": path.name,
                        "kind": f"soft ({r['kind']} restart)"})
        print(
            f"[palette] {name}: utility={sc['utility']:.4f} sep={sc['sep']:.4f} "
            f"emph={sc['emph']:.4f} worst={sc['worst_margin']:.4f} "
            f"atTarget={sc['at_target']}/{sc['terms']}"
        )

    # The committed candidate-b Night palette, scored on the same instrument,
    # so every run reports its own reference point.
    base_path = REPO / "themes/candidates" / np_.SCAFFOLD_SOURCE
    base = sm.score(base_path)
    m01_path = REPO / "out/middle-night/middle-m01.night.yaml"
    n01_path = REPO / "out/numeric-night/numeric-n01.night.yaml"

    metrics = {
        "schema": "grotto.soft-night",
        "schema_version": "1",
        "generated_by": "scripts/soft_palette.py",
        "seed": args.seed,
        "restarts": args.restarts,
        "samples": args.samples,
        "refine_passes": args.refine_passes,
        "objective": {
            "formula": "utility = 1 - SEP - EMPHASIS_WEIGHT * EMPHASIS_EXCESS",
            "shortfall": "SEP = mean over all terms of max(0, 1 - margin)**SHORTFALL_EXP",
            "shortfall_exp": sm.SHORTFALL_EXP,
            "emphasis": "area-weighted mean chroma; measured character share for inks, "
                        "declared area_class share for surfaces (canvas excluded)",
            "emphasis_budget": sm.EMPHASIS_BUDGET,
            "emphasis_weight": sm.EMPHASIS_WEIGHT,
            "area_class_share": sm.AREA_CLASS_SHARE,
            "surface_area_weight": sm.SURFACE_AREA_WEIGHT,
            "acceptance": "strict on utility; no mean-margin tie-break",
        },
        "fences": "inherited unchanged from scripts/middle_palette.py",
        "palettes": entries,
        "reference": base,
        "wall_seconds": round(time.monotonic() - t0, 2),
    }
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")
    print(
        f"[reference] candidate-b night: utility={base['utility']:.4f} "
        f"sep={base['sep']:.4f} emph={base['emph']:.4f} "
        f"worst={base['worst_margin']:.4f} wcag_violations={base['wcag_violations']}"
    )
    for ref in (m01_path, n01_path):
        if ref.exists():
            r = sm.score(ref)
            print(
                f"[reference] {ref.name}: utility={r['utility']:.4f} "
                f"sep={r['sep']:.4f} emph={r['emph']:.4f} "
                f"worst={r['worst_margin']:.4f}"
            )
    print(f"[done] {time.monotonic() - t0:.1f}s total; artifacts in {out}")


if __name__ == "__main__":
    main()