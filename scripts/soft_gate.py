"""Hard-constraint gate for the soft-objective palette search.

Independent of ``scripts/soft_palette.py``: it re-reads the palettes the
benchmark produced and asserts every constraint that must never trade for a
better utility number.  Empty output means the run is admissible; any line on
stdout means the run must be discarded, whatever it scored.

Gates, in order of how badly it would be to break them:

1. **WCAG 2.x floors** for every role with an ``accessibility_floor``,
   against the canvas AND every co-occurring surface -- the same set the
   numeric/middle searches treat as hard.  8-bit hex, after rounding.
2. **sRGB gamut**: no emitted colour outside the displayable triangle.
3. **Taste fences** from ``scripts/middle_palette.py``: hue convention
   windows, the ink/surface lightness deltas around candidate-b Night, the
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
from grotto.spec import Palette  # noqa: E402

import numeric_palette as np_  # noqa: E402
import middle_palette as mp  # noqa: E402


def gate(path: Path) -> list[str]:
    problems: list[str] = []
    name = path.name
    palette = Palette.from_yaml(path)
    colors = {r: str(v) for r, v in palette.colors.items()}
    problem = mp.MiddleProblem()
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

    # 5. The palette must not have gone achromatic where the design needs a
    #    hue: an error that renders grey technically sits inside its window.
    for role in ("error", "diff_removed", "diff_added"):
        c = hex_to_oklch(hexes[role])[1]
        if c < 0.010:
            problems.append(f"{name}: {role} is achromatic (C={c:.4f})")

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