"""Cross-variant semantic-distance reporting (DESIGN.md D-5).

Three variants of *one* system should be one design under a transform, not
three unrelated palettes.  This module reports how well a set of per-variant
palettes (day / evening / night) preserve the *semantic* identity of each role
across variants.

What "stability" means here -- and what it deliberately does NOT mean
---------------------------------------------------------------------
Stability lives in **hue, in family ordering, in salience rank and in chroma
rank**.  It does **not** live in colour distance: Day and Night necessarily
invert lightness, so the cross-variant dE of any foreground role is large by
construction, and calling that "instability" would be a methodological error
(DESIGN.md D-5, last row).  We still *compute* cross-variant dE and surface
it, but explicitly labelled as informational, never as a gate.

Hue drift is only meaningful for *chromatic* roles.  A neutral background with
chroma ~0.007 has a hue angle, but it is noise -- its hue can swing 100 degrees
between variants while the colour is perceptually identical.  We therefore
suppress hue-drift reporting for any role whose chroma is below a floor in
either variant (``chroma_floor``), which is the honest treatment of the
"achromatic -> hue undefined" case from ``color.oklab_to_oklch``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from .color import hex_to_oklch
from .distance import delta_e_ok
from .spec import Palette, RoleSpec

#: Hue drift below this chroma in *either* variant is treated as meaningless.
DEFAULT_CHROMA_FLOOR = 0.02

#: Pairs whose hue separation is below this in both variants are not checked
#: for ordering inversion -- their relative order is too close to call, and
#: flagging it would be noise rather than signal.
MIN_HUE_SEPARATION_DEG = 30.0

#: From spec/environments.yaml stability.max_hue_drift_deg.
DEFAULT_MAX_HUE_DRIFT = 12.0


def circular_drift(h1: float, h2: float) -> float:
    """Smallest absolute angular difference between two hues, in degrees."""
    return abs(((h1 - h2 + 180.0) % 360.0) - 180.0)


def _signed_shortest(h1: float, h2: float) -> float:
    """Signed shortest-arc difference h1 - h2, in (-180, 180]."""
    return ((h1 - h2 + 180.0) % 360.0) - 180.0


# --------------------------------------------------------------------------
# Per-role stability
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class RoleStability:
    role: str
    family: str | None
    salience: int | None
    present_in: tuple[str, ...]
    lightness: dict[str, float]
    chroma: dict[str, float]
    hue: dict[str, float]  # raw hue; meaningless when ``hue_meaningful`` is False
    hue_meaningful: bool
    max_hue_drift: float | None  # None when hue is not meaningful
    hue_drift_pairs: tuple[tuple[str, str, float], ...]
    cross_variant_de: tuple[tuple[str, str, float], ...]  # INFORMATIONAL only

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "family": self.family,
            "salience": self.salience,
            "present_in": list(self.present_in),
            "lightness": {k: round(v, 6) for k, v in self.lightness.items()},
            "chroma": {k: round(v, 6) for k, v in self.chroma.items()},
            "hue": {k: round(v, 6) for k, v in self.hue.items()},
            "hue_meaningful": self.hue_meaningful,
            "max_hue_drift_deg": (
                None if self.max_hue_drift is None else round(self.max_hue_drift, 4)
            ),
            "hue_drift_pairs": [
                {"a": a, "b": b, "drift_deg": round(d, 4)}
                for a, b, d in self.hue_drift_pairs
            ],
            "cross_variant_de_informational": [
                {"a": a, "b": b, "de": round(d, 6)}
                for a, b, d in self.cross_variant_de
            ],
        }


@dataclass(frozen=True)
class RankInversion:
    kind: str  # "hue_order" | "chroma_rank"
    role_a: str
    role_b: str
    variant_a: str
    variant_b: str
    detail: str

    def to_dict(self) -> dict:
        return {
            "kind": self.kind,
            "roles": [self.role_a, self.role_b],
            "variants": [self.variant_a, self.variant_b],
            "detail": self.detail,
        }


@dataclass(frozen=True)
class StabilityReport:
    variants: tuple[str, ...]
    roles: dict[str, RoleStability]
    hue_order_inversions: tuple[RankInversion, ...]
    chroma_rank_inversions: tuple[RankInversion, ...]
    salience_rank_preserved: bool
    max_hue_drift_threshold: float
    drift_violations: tuple[tuple[str, float], ...]  # (role, max_drift) over threshold
    caveat: str

    @property
    def ok(self) -> bool:
        return (
            not self.hue_order_inversions
            and not self.chroma_rank_inversions
            and not self.drift_violations
            and self.salience_rank_preserved
        )

    def to_dict(self) -> dict:
        return {
            "variants": list(self.variants),
            "max_hue_drift_threshold_deg": self.max_hue_drift_threshold,
            "salience_rank_preserved": self.salience_rank_preserved,
            "drift_violations": [
                {"role": r, "max_hue_drift_deg": round(d, 4)}
                for r, d in self.drift_violations
            ],
            "hue_order_inversions": [i.to_dict() for i in self.hue_order_inversions],
            "chroma_rank_inversions": [i.to_dict() for i in self.chroma_rank_inversions],
            "roles": {r: s.to_dict() for r, s in self.roles.items()},
            "caveat": self.caveat,
            "ok": self.ok,
        }


# --------------------------------------------------------------------------
# Report construction
# --------------------------------------------------------------------------

CAVEAT = (
    "Cross-variant dE is reported INFORMATIONALLY ONLY and is NOT a stability "
    "gate: Day<->Night necessarily inverts lightness, so a large cross-variant "
    "dE is expected and correct. Stability lives in hue drift, family ordering, "
    "salience rank and chroma rank (DESIGN.md D-5)."
)


def _role_oklch(palette: Palette, role: str) -> tuple[float, float, float]:
    return hex_to_oklch(palette[role])


def cross_variant_report(
    variants: dict[str, Palette],
    roles: RoleSpec,
    *,
    max_hue_drift_deg: float = DEFAULT_MAX_HUE_DRIFT,
    chroma_floor: float = DEFAULT_CHROMA_FLOOR,
) -> StabilityReport:
    """Report cross-variant semantic stability for a family of palettes.

    ``variants`` maps variant name -> Palette.  Roles are taken from ``roles``;
    a role present in two or more variants is reported.  Roles absent from the
    spec are flagged by ``salience_rank_preserved`` becoming False.
    """
    if len(variants) < 2:
        raise ValueError("cross-variant report needs at least 2 variants")
    var_names = tuple(variants.keys())

    # All roles that appear in >=2 variants.
    role_presence: dict[str, list[str]] = {}
    for vname, pal in variants.items():
        for role in pal.roles():
            role_presence.setdefault(role, []).append(vname)
    shared = sorted(r for r, vs in role_presence.items() if len(set(vs)) >= 2)

    role_reports: dict[str, RoleStability] = {}
    for role in shared:
        present = tuple(
            v for v in var_names if role in variants[v]
        )  # preserve variant order, dedup
        present = tuple(dict.fromkeys(present))
        lightness: dict[str, float] = {}
        chroma: dict[str, float] = {}
        hue: dict[str, float] = {}
        for v in present:
            L, C, h = _role_oklch(variants[v], role)
            lightness[v] = L
            chroma[v] = C
            hue[v] = h

        meaningful = all(chroma[v] >= chroma_floor for v in present)
        drift_pairs: list[tuple[str, str, float]] = []
        max_drift: float | None = None
        if meaningful:
            for a, b in combinations(present, 2):
                d = circular_drift(hue[a], hue[b])
                drift_pairs.append((a, b, d))
            max_drift = max(d for _, _, d in drift_pairs) if drift_pairs else 0.0

        # Informational cross-variant dE (NOT a gate).
        de_pairs: list[tuple[str, str, float]] = []
        for a, b in combinations(present, 2):
            de_pairs.append((a, b, delta_e_ok(variants[a][role], variants[b][role])))

        spec_role = roles.roles.get(role)
        role_reports[role] = RoleStability(
            role=role,
            family=spec_role.family if spec_role else None,
            salience=spec_role.salience if spec_role else None,
            present_in=present,
            lightness=lightness,
            chroma=chroma,
            hue=hue,
            hue_meaningful=meaningful,
            max_hue_drift=max_drift,
            hue_drift_pairs=tuple(drift_pairs),
            cross_variant_de=tuple(de_pairs),
        )

    # --- hue-order inversions across role pairs ----------------------------
    hue_inversions: list[RankInversion] = []
    chroma_inversions: list[RankInversion] = []
    chromatic_roles = [r for r in shared if role_reports[r].hue_meaningful]
    for ra, rb in combinations(chromatic_roles, 2):
        for va, vb in combinations(var_names, 2):
            if ra not in variants[va] or ra not in variants[vb]:
                continue
            if rb not in variants[va] or rb not in variants[vb]:
                continue
            ha_a = role_reports[ra].hue[va]
            hb_a = role_reports[rb].hue[va]
            ha_b = role_reports[ra].hue[vb]
            hb_b = role_reports[rb].hue[vb]
            # Hue ordering: only judge when both separations are unambiguous.
            if (
                circular_drift(ha_a, hb_a) >= MIN_HUE_SEPARATION_DEG
                and circular_drift(ha_b, hb_b) >= MIN_HUE_SEPARATION_DEG
            ):
                if (_signed_shortest(ha_a, hb_a) > 0) != (_signed_shortest(ha_b, hb_b) > 0):
                    hue_inversions.append(
                        RankInversion(
                            "hue_order", ra, rb, va, vb,
                            f"hue ordering of {ra}/{rb} flips between {va} and {vb}",
                        )
                    )
            # Chroma rank inversion: only when both diffs are non-trivial.
            ca_a, cb_a = role_reports[ra].chroma[va], role_reports[rb].chroma[va]
            ca_b, cb_b = role_reports[ra].chroma[vb], role_reports[rb].chroma[vb]
            eps = 0.005
            if (
                abs(ca_a - cb_a) > eps
                and abs(ca_b - cb_b) > eps
                and ((ca_a > cb_a) != (ca_b > cb_b))
            ):
                chroma_inversions.append(
                    RankInversion(
                        "chroma_rank", ra, rb, va, vb,
                        f"chroma rank of {ra}/{rb} inverts between {va} and {vb}",
                    )
                )

    # --- drift violations --------------------------------------------------
    drift_violations: list[tuple[str, float]] = []
    for role, rep in role_reports.items():
        if rep.hue_meaningful and rep.max_hue_drift is not None:
            if rep.max_hue_drift > max_hue_drift_deg:
                drift_violations.append((role, rep.max_hue_drift))

    # --- salience rank: constant by construction, but verify spec coverage --
    unknown = [r for r in shared if roles.roles.get(r) is None]
    salience_preserved = not unknown

    return StabilityReport(
        variants=var_names,
        roles=role_reports,
        hue_order_inversions=tuple(hue_inversions),
        chroma_rank_inversions=tuple(chroma_inversions),
        salience_rank_preserved=salience_preserved,
        max_hue_drift_threshold=max_hue_drift_deg,
        drift_violations=tuple(drift_violations),
        caveat=CAVEAT,
    )
