"""Price Option A: could a reverse-contrast solve satisfy the shortfall list?

    uv run python scripts/contrast_solve.py out/soft-night/soft-s01.night.yaml

`contrast.solve_lightness` inverts the contrast metric: given a background and a
required ratio it returns the lightness a foreground needs.  Pi's system theme
is built on exactly that move (Earendil, "There are many themes, but this one
is yours") -- decide lightness from the requirement, keep hue from the source.

So the fair question is whether that machinery could have produced this theme.
This script answers it in two parts, and the answer to the first part is the
interesting one.

**Part 1 -- which shortfalls are even expressible as a contrast requirement.**
A contrast target says "this ink must read on that surface".  It cannot say
"these two washes must be tellable apart", because neither is a readability
constraint against a background -- they are peers.  Classifying the CVD
shortfalls by `paint` says how many the solve can even speak to.

**Part 2 -- feasibility for the ones it cannot.**  Holding hue and chroma and
moving only lightness, is there any assignment of L to the surface cluster that
clears every must-distinguish threshold?  That is placement on a line with
pairwise minimum separations, answered exactly: enumerate the orderings and
place each surface as early as its neighbours allow, then take the best.  At
seven surfaces that is 5040 orderings -- free, and the reason this stays a
script rather than becoming a gate over all 40 roles.

An earlier version computed a *lower bound* by longest-path relaxation and
reported the cluster as provably infeasible at 2.33 on a 1.0 axis.  The
constraint graph has cycles, so that relaxation is unbounded and the number was
meaningless -- it read as a proof without being one.  Do not reintroduce it; the
exact enumeration replaced it.  See docs/review/redundant-channel-audit.md §8.

Finally the seating is slid to minimise total movement, because a minimum-SPAN
seating is a feasibility witness rather than a palette: it piles every
unconstrained surface against the left edge.  The slide is exact (a 1-D median)
and the result is verified against every pair rather than assumed.
"""

from __future__ import annotations

import sys
from itertools import permutations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from grotto.color import hex_to_oklch, oklch_to_hex  # noqa: E402
from grotto.contrast import solve_lightness, wcag_contrast  # noqa: E402
from grotto.cvd import CVD_TYPES, simulate  # noqa: E402
from grotto.distance import delta_e_ok  # noqa: E402
from grotto.spec import DistanceSpec, Palette, RoleSpec  # noqa: E402

BODY_FLOOR = 4.5


def shortfalls(palette, dists, roles) -> list[tuple]:
    """must_distinguish pairs under the CVD threshold, tagged with their paint."""
    limit = dists.thresholds["must_distinguish"]["normal_vision"]
    cvd_limit = dists.thresholds["must_distinguish"]["cvd_dichromat"]
    out = []
    for c in dists.constraints:
        if c.kind != "must_distinguish":
            continue
        ca, cb = palette.get(c.a), palette.get(c.b)
        if not ca or not cb:
            continue
        worst = min(
            delta_e_ok(simulate(ca, k, 1.0), simulate(cb, k, 1.0))
            for k in CVD_TYPES
        )
        if worst < cvd_limit:
            out.append((c.a, c.b, roles.roles[c.a].paint, roles.roles[c.b].paint,
                        worst, limit))
    return out


def classify(rows):
    """Split into readability-typed and peer-typed."""
    read = [r for r in rows if {r[2], r[3]} == {"ink", "surface"}]
    peer = [r for r in rows if r not in read]
    return read, peer


def required_gaps(palette, dists, roles, *, cvd: str | None):
    """Per surface pair, the OKLab lightness gap needed to clear the threshold.

    ``delta_e_ok`` is euclidean in OKLab, so with hue and chroma held fixed the
    requirement ``sqrt(dL^2 + rest^2) >= limit`` rearranges to
    ``dL >= sqrt(limit^2 - rest^2)``.
    """
    limit = dists.thresholds["must_distinguish"]["normal_vision"]
    surfaces = {
        r for c in dists.constraints if c.kind == "must_distinguish"
        for r in (c.a, c.b)
        if r in roles and roles.roles[r].paint == "surface"
    }
    need: dict[tuple[str, str], float] = {}
    for c in dists.constraints:
        if c.kind != "must_distinguish":
            continue
        if c.a not in surfaces or c.b not in surfaces:
            continue
        a = palette.get(c.a)
        b = palette.get(c.b)
        if not a or not b:
            continue
        if cvd:
            a, b = simulate(a, cvd, 1.0), simulate(b, cvd, 1.0)
        la, lb = hex_to_oklch(a), hex_to_oklch(b)
        full = delta_e_ok(a, b)
        rest2 = max(full ** 2 - (la[0] - lb[0]) ** 2, 0.0)
        need[tuple(sorted((c.a, c.b)))] = max(0.0, limit ** 2 - rest2) ** 0.5
    return surfaces, need


def _span_for(order, need) -> tuple[float, dict[str, float]]:
    """Minimum span for one left-to-right ORDER of the surfaces.

    Placing each surface as early as every already-placed constraint allows is
    optimal for this order: pushing a point earlier can never force a later one
    further right, since every constraint is a lower bound of the form
    ``x_i >= x_j + d``.
    """
    x: dict[str, float] = {}
    for node in order:
        lo = 0.0
        for other, pos in x.items():
            g = need.get(tuple(sorted((node, other))))
            if g is not None:
                lo = max(lo, pos + g)
        x[node] = lo
    return max(x.values()) - min(x.values()), x


def min_span_exact(surfaces, need) -> tuple[float, dict[str, float]]:
    """Exact minimum span, by trying every ordering.

    Which surfaces sit left of which is the whole degree of freedom here, so
    enumerating the orderings and taking the best is exact rather than a bound
    or a sample.  It costs n! -- free for a seven-surface cluster, and the
    reason this stays a script rather than becoming a gate over all 40 roles.

    Prefer :func:`span_ties` for anything you intend to report.  Several
    orderings routinely tie at the minimum span, and this returns whichever one
    the loop happened to see first -- which depends on float-level differences
    in the CVD simulation between library versions, so its *seating* is not
    reproducible even though its *span* is.
    """
    best_span, best_x, best_order = float("inf"), {}, ()
    for order in permutations(sorted(surfaces)):
        span, x = _span_for(order, need)
        if span < best_span:
            best_span, best_x, best_order = span, x, order
    return best_span, best_x, best_order


def span_ties(surfaces, need, *, tol: float = 1e-9
              ) -> tuple[float, list[tuple[tuple[str, ...], dict[str, float]]]]:
    """Every ordering that achieves the minimum span, within ``tol``.

    Ties are the norm, not the exception -- seven surfaces under eleven
    pairwise minimums leaves a lot of slack -- so the set of span-optimal
    orderings is the honest input to any *cost* question.  Picking one of them
    arbitrarily made the printed least-movement row environment-dependent: two
    machines running the same script reported 0.6065 and 0.7429 total movement
    for the same palette, both valid, because a float difference chose a
    different tie.
    """
    best, out = float("inf"), []
    for order in permutations(sorted(surfaces)):
        span, x = _span_for(order, need)
        if span < best - tol:
            best, out = span, [(order, x)]
        elif span <= best + tol:
            out.append((order, x))
    return best, out


def best_seating(tied, need, current, *, objective: str = "total",
                 lo: float = 0.0, hi: float = 1.0) -> dict[str, float]:
    """The cheapest seating among the span-optimal orderings.

    ``objective`` is the cost being minimised: ``"total"`` sums the movement of
    every surface, ``"worst"`` minimises the largest single move.  They are
    different questions and can pick different orderings -- minimising the total
    does not minimise the worst surface -- so the report prints both rather than
    letting one stand in for the other.
    """
    def cost(seats: dict[str, float]) -> float:
        moves = [abs(seats[r] - current[r]) for r in seats]
        return sum(moves) if objective == "total" else max(moves)

    best, best_cost = None, float("inf")
    for order, _witness in tied:
        seats = slide_to_min_movement(order, need, current, lo=lo, hi=hi)
        c = cost(seats)
        if c < best_cost - 1e-12:
            best, best_cost = seats, c
    assert best is not None, "no span-optimal ordering to seat"
    return best


def slide_to_min_movement(order, need, current, *, lo=0.0, hi=1.0) -> dict[str, float]:
    """Re-seat in the same order, shifted to move the surfaces least.

    The minimum-span seating is a feasibility witness, not a palette: it piles
    every unconstrained surface against the left edge.  Since the span leaves
    slack on the axis, sliding the whole seating by a constant changes no pair's
    separation, so the best slide is a 1-D median problem -- exact, and it turns
    "a solution exists" into "a solution exists this far from where we are".
    """
    _span, base = _span_for(order, need)
    base_min = min(base.values())
    targets = [current[r] - base[r] + base_min for r in order]
    # minimise sum |(base_min + t) - target|  ->  t is the median of targets - base
    shifted = [t - base_min for t in targets]
    t = sorted(shifted)[len(shifted) // 2]
    seats = {r: base[r] + t for r in order}
    shift = max(0.0, lo - min(seats.values()))
    if shift:
        seats = {r: v + shift for r, v in seats.items()}
    over = max(seats.values()) - hi
    if over > 0:
        seats = {r: v - over for r, v in seats.items()}
    return seats


def verify_seating(seats, need, tol=1e-9) -> list[tuple[str, str]]:
    """Which pairs the seating still violates -- empty means it is a solution."""
    bad = []
    for (x, y), gap in need.items():
        if abs(seats[x] - seats[y]) + tol < gap:
            bad.append((x, y))
    return bad


def report(path: Path) -> None:
    palette = Palette.from_yaml(path)
    roles = RoleSpec.load("spec/roles.yaml")
    dists = DistanceSpec.load("spec/distance-matrix.yaml")

    rows = shortfalls(palette, dists, roles)
    read, peer = classify(rows)
    cvd_limit = dists.thresholds["must_distinguish"]["cvd_dichromat"]

    print(f"contrast-solve feasibility: {path.name}")
    print()
    print(f"{len(rows)} must_distinguish pair(s) short of the CVD threshold "
          f"({cvd_limit} dE)")
    print()

    print("== part 1: can a contrast requirement even express these? ==")
    print(f"  readability-typed (ink on a surface): {len(read)}")
    for r in read:
        print(f"      {r[0]} on {r[1]}")
    print(f"  peer-typed (surface/surface or ink/ink): {len(peer)}")
    for a, b, pa, pb, d, _ in peer:
        print(f"      {a:20s} / {b:20s} [{pa}/{pb}] worst dE {d:.3f}")
    print()
    print("  A reverse-contrast solve states 'ink must read on surface'. It has no")
    print("  way to state 'these two washes must differ from each other'.")
    print()

    print("== part 2: lightness-only feasibility for the surface cluster ==")
    for cvd in (None, "deutan"):
        surfaces, need = required_gaps(palette, dists, roles, cvd=cvd)
        label = "normal vision" if cvd is None else f"{cvd} @ 1.0"
        if not need:
            print(f"  {label}: no surface pairs to seat")
            continue

        span, tied = span_ties(surfaces, need)
        current = {r: hex_to_oklch(palette.get(r))[0] for r in surfaces}
        seats = best_seating(tied, need, current, objective="total")
        minimax = best_seating(tied, need, current, objective="worst")
        residual = verify_seating(seats, need)
        moved = sum(abs(seats[r] - current[r]) for r in surfaces)
        worst_move = max(abs(seats[r] - current[r]) for r in surfaces)
        mm_worst = max(abs(minimax[r] - current[r]) for r in surfaces)
        mm_total = sum(abs(minimax[r] - current[r]) for r in surfaces)
        gaps = list(need.values())

        print(f"  {label}: {len(surfaces)} surfaces, {len(need)} constrained pairs")
        print(f"     required lightness gap: min {min(gaps):.4f}, max {max(gaps):.4f}")
        print(f"     tightest seating (exact, over all orderings): {span:.4f} "
              f"of the 1.0 axis")
        print(f"        ({len(tied)} ordering(s) share that span; the seatings "
              f"below minimise")
        print(f"         movement over all of them, so they do not depend on "
              f"which tie a")
        print(f"         float comparison happened to keep)")

        if span > 1.0:
            print(f"     => INFEASIBLE: every ordering needs at least {span:.4f}, "
                  f"and the axis is 1.0")
            print(f"     => no palette can fix this by moving lightness alone")
        elif residual:
            print(f"     => INFEASIBLE: the min-movement seating still violates "
                  f"{len(residual)} pair(s)")
        else:
            print(f"     => FEASIBLE. A valid seating sits {span:.4f} of the axis;")
            print(f"        least TOTAL movement: {moved:.4f} OKLab L in total "
                  f"(worst single surface {worst_move:.4f})")
            print(f"        least WORST movement: {mm_worst:.4f} at the worst "
                  f"surface ({mm_total:.4f} in total)")
            for r in sorted(surfaces, key=lambda s: seats[s]):
                print(f"          {r:22s} L {current[r]:.3f} -> {seats[r]:.3f}")
        print()

        # readability cost of the seating we would actually use
        worst_dark = []
        for s, pos in seats.items():
            raw = palette.get(s)
            if not raw:
                continue
            _l, c, h = hex_to_oklch(raw)
            moved = oklch_to_hex((pos, c, h))
            ratio = wcag_contrast(palette.get("fg"), moved)
            if ratio < BODY_FLOOR:
                worst_dark.append((s, ratio))
        if worst_dark:
            print(f"     readability cost of that seating -- body text below "
                  f"{BODY_FLOOR}:1 on:")
            for s, r in sorted(worst_dark, key=lambda x: x[1]):
                print(f"        {s:20s} {r:.2f}:1")
            print()

    print("== part 3: what the solve WOULD buy, on the roles it can address ==")
    bg = palette.get("bg")
    for role in ("fg", "fg_muted", "comment"):
        raw = palette.get(role)
        l, c, h = hex_to_oklch(raw)
        r = solve_lightness(bg, BODY_FLOOR, chroma=c, hue=h, model="wcag")
        cur = wcag_contrast(raw, bg)
        print(f"  {role:12s} now {cur:5.2f}:1  ->  {r}")


def main(argv) -> int:
    path = Path(argv[1] if len(argv) > 1
                else "out/soft-night/soft-s01.night.yaml")
    report(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
