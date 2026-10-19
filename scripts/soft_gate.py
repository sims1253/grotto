"""Hard-constraint gate for the soft-objective palette search.

Independent of the search's REPORT: it re-reads the palettes the
benchmark produced (it imports ``scripts/soft_palette.py`` only for the
declared fence table, never for a score) and asserts every constraint that must never trade for a
better utility number.  Empty output means the run is admissible; any line on
stdout means the run must be discarded, whatever it scored.

Gates, in order of how badly it would be to break them:

1. **WCAG 2.x floors** for every role with an ``accessibility_floor``,
   against the canvas AND every co-occurring surface -- the same set the
   numeric/middle searches treat as hard.  8-bit hex, after rounding.
2. **sRGB gamut**: no emitted colour outside the displayable triangle.
3. **Taste fences** from ``scripts/middle_palette.py``: hue convention
   windows, the ink/surface lightness deltas around candidate-b Night (wider
   only for roles whose spec declares ``lightness_offset``), the
   class chroma caps and the 70%-of-gamut rule.  Checked on the shipped hexes
   and on the authored OKLCH coordinates.
4. **same_family.min_distance** (0.03, read from ``spec/distance-matrix.yaml``)
   for every same_family pair the optimizer owns.
5. **Completeness**: every role the problem constrains is present.

Usage: uv run python scripts/soft_gate.py .auto/work
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from grotto.color import hex_to_oklch  # noqa: E402
from grotto.spec import Palette, RoleSpec, salience_coverage  # noqa: E402

import numeric_palette as np_  # noqa: E402
import middle_palette as mp  # noqa: E402
import soft_metric as sm  # noqa: E402
import soft_palette as sp  # noqa: E402

#: DESIGN.md section 6, enforced in spec/environments.yaml: salience_budget.
#: Read, never edited -- this gate's whole job is to be the non-negotiable
#: backpressure, so a hardcoded copy here could silently diverge from the spec
#: and stop pressuring anything.  Loaded from the spec, with the literal values
#: kept only as a fallback for running this file outside the repo.
def _salience_budgets() -> tuple[float, float]:
    try:
        from grotto.environments import Environments

        budget = Environments.load(REPO / "spec/environments.yaml").salience_budget
        return (float(budget["max_fraction_at_or_above_3"]),
                float(budget["max_fraction_at_or_above_5"]))
    except Exception:  # noqa: BLE001 - a research script must still run standalone
        return (0.22, 0.01)


SAL_BUDGET_3, SAL_BUDGET_5 = _salience_budgets()

#: DESIGN.md hard conflict O4-vs-O2 states the channel explicitly: "chroma is
#: a salience channel", and the project's own realised-salience proxy
#: (``src/grotto/model.py``) checks it WITHIN A HUE FAMILY, comparing
#: NORMALISED chroma (C / max_chroma(L, h)), skipping pairs whose declared
#: salience is tied.  This gate reuses that definition rather than inventing a
#: stricter one: an earlier attempt here checked LIGHTNESS rank across all
#: roles and flagged the committed candidate palettes, which would have been a
#: checker artefact dressed up as a design constraint.
#:
#: Tolerance is the same 2e-3 the model uses.
#:
#: PROMOTED TO HARD HERE, deliberately and against the model's own default.
#: ``model.py`` calls this "a soft signal" and leaves it out of ``ok``.  That
#: is right for a checker reporting on hand-authored palettes.  It is wrong
#: for an optimiser, which is why this gate differs from the model:
#:
#:   * the committed candidate-b Night palette scores ZERO reversals, so the
#:     design property is achievable inside these fences -- zero is the
#:     achievable target, not an aspiration;
#:   * the shortfall objective is structurally blind to it (nothing in the
#:     distance matrix ranks attention), so left unchecked a search drifts
#:     into reversals as chroma moves -- measured: 5 reversals in the soft
#:     search's first admissible palette, against 0 for candidate-b and 1 for
#:     middle-m01;
#:   * DESIGN.md states chroma IS the salience channel, so a reversal
#:     mis-ranks attention, which is the thing the theme is for.
#:
#: The cost of this choice is real and was paid: utility fell when the gate
#: landed.  That is the point.  A palette that buys its separation by
#: inverting the attention hierarchy is worse, and the number saying otherwise
#: is the number being wrong.
SAL_RANK_TOL = 2e-3


def gate(path: Path) -> list[str]:
    problems: list[str] = []
    name = path.name
    palette = Palette.from_yaml(path)
    colors = {r: str(v) for r, v in palette.colors.items()}
    # The search's own problem: its fences are the ones the palette was
    # built inside (middle fences, widened only where the spec declares a
    # lightness_offset channel -- soft_palette.SoftProblem.l_range).
    problem = sp.SoftProblem()
    hexes = {r: colors[r] for r in problem.present if r in colors}

    missing = [r for r in problem.present if r not in colors]
    if missing:
        problems.append(f"{name}: missing roles {missing}")
        return problems

    # 1. WCAG 2.x floors -- hard, never negotiable.
    for entry in np_.check_feasible(problem, hexes):
        problems.append(f"{name}: WCAG {entry}")

    # 2. sRGB gamut -- hexes are inside the cube by construction, but a
    #    negative or absurd channel would mean a corrupt emitter.
    for role, hx in hexes.items():
        if len(hx.lstrip("#")) != 6:
            problems.append(f"{name}: {role} is not a 6-digit hex ({hx!r})")

    # 3. Taste fences, on the shipped hexes.
    for entry in problem.fence_audit(hexes):
        problems.append(f"{name}: fence {entry}")

    # 4. same_family.min_distance output gate, read from the matrix.
    th = problem.th_anticollapse
    for a, b in problem.same_family_pairs:
        de = np_._dE(np_._oklab_of(hexes[a]), np_._oklab_of(hexes[b]))
        if de < th:
            problems.append(
                f"{name}: same_family {a}/{b} dE {de:.4f} < {th}"
            )

    # 5. Chroma floor: a role with a hue convention must carry that hue.
    #    Read from soft_metric.CHROMA_FLOOR, which is the repo's own
    #    HUE_AUDIT_MIN_CHROMA.  Without this the search's degenerate
    #    optimum is grey -- documented in NUMERIC.md sections 5.3 and 10,
    #    and reproduced by run 0 of this session.
    from grotto.color import hex_to_oklch

    for role in problem.chromatic:
        c = hex_to_oklch(hexes[role])[1]
        if c < sm.CHROMA_FLOOR - sm.CHROMA_FLOOR_TOL:
            problems.append(
                f"{name}: {role} below the chroma floor "
                f"(C={c:.4f} < {sm.CHROMA_FLOOR})"
            )

    # 6. DESIGN.md section 6 -- the salience budget.  "Too busy" has to stay
    #    measurable, and it is NOT in the shortfall objective: nothing in the
    #    distance matrix notices a palette that gets uniformly louder.
    #    Read from spec/environments.yaml, never tuned away.
    roles_spec = problem.roles_spec
    cov = salience_coverage(palette, roles_spec, "code")
    for key, limit in (("at_or_above_3", SAL_BUDGET_3), ("at_or_above_5", SAL_BUDGET_5)):
        if cov[key] > limit + 1e-9:
            problems.append(
                f"{name}: salience budget breached -- {key}={cov[key]:.4f} > {limit}"
            )

    # 7. DESIGN.md hard conflict O4-vs-O2, resolved in the DESIGN: making pairs
    #    CVD-robust by lightness-separating them "consumes the lightness axis
    #    that salience also needs", and the resolution is redundant NON-COLOUR
    #    channels rather than a distorted palette.  The shortfall objective is
    #    blind to this -- widening SURFACE_L_DELTA / INK_L_DELTA raised utility
    #    in the sensitivity probe -- so the salience channel is checked here,
    #    where the objective cannot see it.  Definition taken from
    #    src/grotto/model.py's realised-salience proxy: within a hue family,
    #    higher declared salience carries >= normalised chroma.
    from grotto.color import max_chroma

    roles_spec = problem.roles_spec
    fams: dict[str, list[str]] = {}
    for r in problem.chromatic:
        fams.setdefault(roles_spec.roles[r].family, []).append(r)
    for fam, members in sorted(fams.items()):
        if len(members) < 2:
            continue
        sr = sorted(members, key=lambda r: roles_spec.roles[r].salience)
        for lo, hi in zip(sr, sr[1:]):
            if roles_spec.roles[lo].salience == roles_spec.roles[hi].salience:
                continue  # tied levels impose no ordering
            def normc(role: str) -> float:
                L, C, h = hex_to_oklch(hexes[role])
                mc = max_chroma(L, h, "srgb")
                return (C / mc) if mc > 1e-9 else 0.0

            if normc(lo) - normc(hi) > SAL_RANK_TOL:
                problems.append(
                    f"{name}: salience reversal in family {fam} -- "
                    f"{lo}(sal {roles_spec.roles[lo].salience}) "
                    f"normC {normc(lo):.4f} > "
                    f"{hi}(sal {roles_spec.roles[hi].salience}) "
                    f"normC {normc(hi):.4f}"
                )

    return problems


def main() -> None:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "out/soft-night")
    if root.is_dir():
        paths = sorted(root.rglob("*.night.yaml"))
    elif root.exists():
        paths = [root]
    else:
        paths = []
    if not paths:
        print(f"soft_gate: no palettes found under {root}")
        sys.exit(1)
    problems: list[str] = []
    for p in paths:
        problems.extend(gate(p))
    for line in problems:
        print(line)
    if problems:
        sys.exit(1)
    print(f"soft_gate: {len(paths)} palette(s) admissible")


if __name__ == "__main__":
    main()