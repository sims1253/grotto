#!/usr/bin/env python3
"""Generate the NON-CANDIDATE hand-tuned Phase 4 comparison fixture.

This is NOT a candidate palette generator.  It builds the systematic family
from spec/bindings/calibration.yaml, then applies a small set of *curated
designer corrections* -- the kind a human would make where DESIGN.md section 9
predicts the systematic transform to be weakest (backgrounds / near-background
surfaces, the blue/violet region) -- and writes the result as three
hand-authored OKLCH palettes under themes/experiments/.

The point is to give compare_families an honest target: the deltas it reports
are exactly the corrections a designer made over the systematic output, which
answers the Phase 4 question "did the systematic transform need hand
adjustment, and where?".

Re-running this script over the same inputs produces byte-identical output
(no wall-clock), so the committed YAML is reproducible.
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from grotto.environments import Environments  # noqa: E402
from grotto.model import (  # noqa: E402
    CandidateBinding,
    ModelSpec,
    build_family,
)
from grotto.spec import DistanceSpec, RoleSpec  # noqa: E402

# Curated designer corrections over the systematic output, per variant.
# Values are OKLCH (L, C, h) overrides for specific roles; roles not listed
# inherit the systematic value.  These are deliberate, NON-CANDIDATE design
# judgements documented inline.
CORRECTIONS = {
    "day": {
        # backgrounds: a touch warmer/lighter canvas, cooler elevated (Q-2 probe)
        "bg":          (0.970, 0.010, 90),
        "bg_elevated": (0.990, 0.006, 90),
        "keyword":     (0.48, 0.130, 296),   # cleaner violet reading (R-8)
        "selection":   (0.905, 0.070, 250),  # stronger, bluer selection tint
        "comment":     (0.55, 0.020, 75),
    },
    "evening": {
        "bg":          (0.240, 0.012, 260),
        "bg_elevated": (0.280, 0.013, 260),
        "keyword":     (0.69, 0.128, 298),
        "string":      (0.77, 0.085, 145),
        "selection":   (0.300, 0.065, 250),
    },
    "night": {
        # the Night variant is where the transform is most exercised
        "bg":          (0.210, 0.008, 65),    # marginally warmer floor
        "bg_elevated": (0.245, 0.009, 65),
        "bg_overlay":  (0.275, 0.010, 65),
        "keyword":     (0.705, 0.122, 298),   # violet curvature correction
        "function":    (0.80, 0.095, 248),    # azure held slightly cooler
        "error":       (0.665, 0.165, 25),    # error pinned, near-zero adapt
        "selection":   (0.265, 0.060, 250),
        "active_line": (0.235, 0.006, 65),    # subtler active line
        "comment":     (0.595, 0.018, 70),
    },
}

OUTDIR = REPO / "themes" / "experiments"


def main() -> int:
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    spec = ModelSpec(roles, env, dists)
    binding = CandidateBinding.load(REPO / "spec" / "bindings" / "calibration.yaml")

    fb = build_family(binding, spec)

    OUTDIR.mkdir(parents=True, exist_ok=True)
    for variant in ("day", "evening", "night"):
        sys_pal = fb.variants[variant].palette
        colors = {}
        for role in roles:
            # start from the systematic realized OKLCH (pre-quantization hue/L),
            # then apply any curated correction
            L, C, h = sys_pal.perceptual[role.name]
            if role.name in CORRECTIONS[variant]:
                L, C, h = CORRECTIONS[variant][role.name]
            colors[role.name] = {"L": round(L, 4), "C": round(C, 4), "h": round(h, 2)}

        doc = {
            "name": f"handtuned-{variant}",
            "variant": variant,
            "format": "oklch",
            "candidate": False,
            "kind": "phase4-handtuned-experiment",
            "note": (
                "NON-CANDIDATE Phase 4 hand-tuned comparison target. Curated "
                "designer corrections over the systematic transform output "
                "(spec/bindings/calibration.yaml). Not a finished theme "
                "(DESIGN.md section 1)."
            ),
            "colors": colors,
        }
        out = OUTDIR / f"handtuned-{variant}.yaml"
        out.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=100))
        print(f"[handtuned] {out.relative_to(REPO)}  ({len(colors)} roles)")
    print(
        "[handtuned] NON-CANDIDATE. These exist only so compare_families can "
        "quantify where a designer corrected the systematic output."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
