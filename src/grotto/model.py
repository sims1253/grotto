"""Phase 4 environmental transform: ``build_family`` / ``compare_families``.

This is the deep, pure Layer-2 transform that turns an abstract semantic spec
plus a *candidate binding* (semantic hue anchors + scales + bounded
rationale-bearing adjustments) into three concrete per-variant palettes
(day / evening / night) with full per-role derivation provenance.

It implements the **senior-architecture review** of DESIGN.md section 9, not a
blind copy of those equations.  The differences from the section-9 sketch are
deliberate and load-bearing; they are called out inline.  In summary:

* **paint types** (canvas | ink | surface | border) drive *distinct* derivation
  paths.  The transform does NOT run every role through one formula.
  - canvas    : authored verbatim from the environment (the contrast reference).
  - ink       : lightness and chroma JOINTLY solved in sRGB under a lexicographic
                stack (gamut/polarity > WCAG floor > Night fg ceiling > APCA band
                centre > minimal adjustment).
  - surface   : perceptual lightness STEPS from the canvas (never contrast-solved
                -- solving a surface for contrast would silently destroy the
                legibility of the ink that sits on it).
  - border    : non-text 3:1 floor against its adjacent surface.

* **chroma** is an explicit multiplicative chain (class fraction * candidate *
  family * role * environment * night term), then absolute cap, then gamut map,
  with the three losses (cap / gamut / total) reported INDEPENDENTLY plus a
  normalized realized fraction.

* **hue** attracts along the SHORTEST CIRCULAR ARC toward a configurable warm
  anchor, bounded by the environment's rotation cap and gated by the role's
  night_adaptation and the per-hue weight.  A plain signed rotation is WRONG
  here: it moves violet (h~300) toward blue (cooler).  Warm attraction moves
  violet toward magenta/red (warmer) and azure toward green (warmer).

* **stability** (see ``family_stability``) uses the corrected checks: normalized
  C/max_chroma ordering, a cyclic family hue sequence rather than pairwise
  signed hue ordering, non-vacuous realized salience proxies, and total hue
  drift that *includes* the adjustment component.

Error policy: :class:`BindingError` for a malformed binding/spec (caller's
fault, fix the input); :class:`TransformError` only for an *infeasible hard
constraint* (gamut/polarity or an unreachable WCAG floor).  Aesthetic, distance
and legibility misses are never raised -- they are recorded as ``issues``.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass, field, replace
from itertools import combinations

from .color import gamut_map, max_chroma, oklch_to_hex
from .contrast import apca_lc, contrast_report, wcag_contrast
from .environments import Environments, hue_weight
from .spec import (
    CONTRAST_TARGETS,
    FAMILIES,
    CHROMA_CLASSES,
    ACCESSIBILITY_FLOORS,
    DistanceSpec,
    Palette,
    Role,
    RoleSpec,
)

# ===========================================================================
# Errors
# ===========================================================================


class BindingError(Exception):
    """The candidate binding or model spec is malformed.

    Raised for unknown/missing anchors, out-of-range numbers, duplicate or
    conflicting declarations, or dangling role references.  This is a
    caller/input fault: fix the binding, do not catch it as a palette problem.
    """


class TransformError(Exception):
    """A hard constraint of the transform is infeasible.

    Raised only when gamut/polarity or an applicable WCAG floor cannot be
    satisfied at all (e.g. the canvas is so close to the ink extreme that even
    the extreme lightness cannot reach the floor).  Aesthetic, distance and
    legibility misses are NOT this -- those become ``issues``.
    """


# ===========================================================================
# Tunables (design judgement, deliberately exposed and documented)
# ===========================================================================

#: Bounded per-role adjustment limits.  A binding may nudge a role's solved
#: lightness/chroma/hue by at most this much; anything larger is a BindingError.
#: These exist so a "candidate" cannot quietly re-author a role's identity --
#: the systematic solution stays primary, adjustments are bounded corrections.
ADJUSTMENT_LIMITS = {"L": 0.06, "C": 0.03, "h": 8.0}

#: Scale ranges considered well-formed for candidate/family/role scales.
SCALE_RANGE = (0.0, 5.0)

#: Perceptual lightness STEP (OKLCH L) for derived surface roles, keyed by the
#: role's contrast_target.  Surfaces step away from the canvas: lighter in dark
#: variants, darker in light variants (matching how diff/search highlights read
#: in reference themes).  The elevated/overlay backgrounds are NOT derived --
#: they are authored verbatim from the environment.
SURFACE_STEPS = {
    "minimal": 0.030,
    "low": 0.055,
    "comfortable": 0.080,
    "high": 0.110,
    "maximal": 0.140,
}

#: Lightness search tolerance (OKLCH L).  8-bit quantization is ~1e-3, so solving
#: tighter than 1e-4 is false precision.
SOLVE_TOL = 1e-4

#: Co-occurring surfaces an ink role may land on; the transform evaluates ink
#: legibility over each of these regardless of the ink's primary reference,
#: because text can appear on any of them (DESIGN.md / roles.yaml notes).
CO_OCCURRING_SURFACES = (
    "selection",
    "search_match",
    "search_match_current",
    "active_line",
    "diff_added",
    "diff_removed",
    "diff_changed",
    "debug_current",
)

#: OKLCH lightness clamps to keep derived colours inside a sane realised range.
_L_FLOOR, _L_CEIL = 0.0, 1.0


# ===========================================================================
# Bindings and the model spec bundle
# ===========================================================================


@dataclass(frozen=True)
class FamilyAnchor:
    """One family's semantic hue anchor + family chroma scale."""

    family: str
    h: float
    family_scale: float = 1.0


@dataclass(frozen=True)
class RoleAdjustment:
    """A bounded, rationale-bearing per-role nudge applied after the solve."""

    role: str
    L: float = 0.0
    C: float = 0.0
    h: float = 0.0
    rationale: str = ""


@dataclass(frozen=True)
class CandidateBinding:
    """Semantic anchors for a hue family, NOT a per-variant hex palette.

    A binding says: "family *violet* lives at hue 300, scaled to 0.9 of its
    chroma budget; the *error* role gets 1.1x chroma and a -0.02 lightness nudge
    because ...".  It is the same kind of object across all three variants; the
    environment transform does the rest.  Per-variant hex palettes are the
    OUTPUT of :func:`build_family`, never the input.
    """

    name: str
    candidate_scale: float
    anchors: dict[str, FamilyAnchor]
    role_scales: dict[str, float] = field(default_factory=dict)
    role_overrides: dict[str, dict] = field(default_factory=dict)
    adjustments: dict[str, RoleAdjustment] = field(default_factory=dict)
    warm_anchor_override: float | None = None
    meta: dict = field(default_factory=dict)

    @property
    def is_candidate(self) -> bool:
        return bool(self.meta.get("candidate", False))

    @classmethod
    def load(cls, path) -> "CandidateBinding":
        import yaml
        from pathlib import Path

        d = yaml.safe_load(Path(path).read_text())
        return cls.from_dict(d)

    @classmethod
    def from_dict(cls, d: dict) -> "CandidateBinding":
        if not isinstance(d, dict):
            raise BindingError("binding: top level must be a mapping")
        name = str(d.get("name", "unnamed"))
        candidate_scale = float(d.get("candidate_scale", 1.0))
        warm = d.get("warm_anchor")
        warm = float(warm) if warm is not None else None

        anchors: dict[str, FamilyAnchor] = {}
        for fam, a in (d.get("anchors") or {}).items():
            if not isinstance(a, dict):
                raise BindingError(f"anchor {fam!r}: expected a mapping with h/family_scale")
            anchors[fam] = FamilyAnchor(
                family=fam,
                h=float(a["h"]),
                family_scale=float(a.get("family_scale", 1.0)),
            )

        role_scales = {k: float(v) for k, v in (d.get("role_scales") or {}).items()}
        role_overrides = {k: dict(v) for k, v in (d.get("role_overrides") or {}).items()}

        adjustments: dict[str, RoleAdjustment] = {}
        for role, a in (d.get("adjustments") or {}).items():
            if not isinstance(a, dict):
                raise BindingError(f"adjustment {role!r}: expected a mapping")
            adjustments[role] = RoleAdjustment(
                role=role,
                L=float(a.get("L", 0.0)),
                C=float(a.get("C", 0.0)),
                h=float(a.get("h", 0.0)),
                rationale=str(a.get("rationale", "") or ""),
            )

        return cls(
            name=name,
            candidate_scale=candidate_scale,
            anchors=anchors,
            role_scales=role_scales,
            role_overrides=role_overrides,
            adjustments=adjustments,
            warm_anchor_override=warm,
            meta=dict(d.get("meta") or {}),
        )

    def canonical(self) -> dict:
        """Deterministic, hashable view (sorted; floats rounded)."""
        return {
            "name": self.name,
            "candidate_scale": round(self.candidate_scale, 6),
            "warm_anchor": None if self.warm_anchor_override is None
            else round(self.warm_anchor_override, 4),
            "anchors": {
                f: {"h": round(a.h, 4), "family_scale": round(a.family_scale, 6)}
                for f, a in sorted(self.anchors.items())
            },
            "role_scales": {k: round(v, 6) for k, v in sorted(self.role_scales.items())},
            "role_overrides": {
                role: {
                    key: round(value, 6) if isinstance(value, float) else value
                    for key, value in sorted(overrides.items())
                }
                for role, overrides in sorted(self.role_overrides.items())
            },
            "adjustments": {
                r: {
                    "L": round(a.L, 5), "C": round(a.C, 5), "h": round(a.h, 4),
                    "rationale": a.rationale,
                }
                for r, a in sorted(self.adjustments.items())
            },
            "meta": _canonical_value(self.meta),
        }


def _canonical_value(value):
    """Return a stable JSON-compatible representation of nested YAML values."""
    if isinstance(value, dict):
        return {str(k): _canonical_value(v) for k, v in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(v) for v in value]
    if isinstance(value, float):
        return round(value, 6)
    return value


@dataclass(frozen=True)
class ModelSpec:
    """Bundle of the Layer-1/Layer-2 specs the transform reads.

    Keeping these together in one object makes :func:`build_family` a pure
    function of ``(binding, spec)`` and lets reports pin provenance.
    """

    roles: RoleSpec
    environments: Environments
    distances: DistanceSpec


def _effective_role(role: Role, binding: CandidateBinding) -> Role:
    """Apply a binding's per-role overrides to produce the role the solve sees.

    Overrides are bounded experimental tweaks (e.g. drop a role's contrast_target
    to probe a WCAG-vs-APCA conflict).  Identity properties (name/family/paint)
    are never overridden, so a role cannot be silently moved between derivation
    paths.
    """
    ov = binding.role_overrides.get(role.name)
    if not ov:
        return role
    return replace(
        role,
        contrast_target=ov.get("contrast_target", role.contrast_target),
        chroma_class=ov.get("chroma_class", role.chroma_class),
        accessibility_floor=ov.get("accessibility_floor", role.accessibility_floor),
        night_adaptation=float(ov.get("night_adaptation", role.night_adaptation)),
    )


# ===========================================================================
# Geometry helpers (circular hue)
# ===========================================================================


def signed_shortest_arc(a: float, b: float) -> float:
    """Signed shortest circular difference a->b, in (-180, 180]."""
    return ((b - a + 180.0) % 360.0) - 180.0


def circular_drift(a: float, b: float) -> float:
    """Absolute shortest circular distance between two hues, in degrees."""
    return abs(signed_shortest_arc(a, b))


# ===========================================================================
# Validation
# ===========================================================================


def validate_binding(binding: CandidateBinding, spec: ModelSpec) -> None:
    """Raise :class:`BindingError` if the binding is malformed for this spec.

    Checks: numeric ranges; anchors cover every family a role uses and name no
    unknown family; no duplicate anchors; role scales/adjustments reference real
    roles; adjustments within bounds; deterministic ordering is enforced by the
    construction (dicts are sorted in :meth:`canonical`).
    """
    lo, hi = SCALE_RANGE
    if not (lo < binding.candidate_scale <= hi):
        raise BindingError(f"candidate_scale {binding.candidate_scale} not in ({lo}, {hi}]")

    # families actually referenced by roles in this spec
    used_families = {r.family for r in spec.roles}
    anchor_families = set(binding.anchors)

    unknown = sorted(anchor_families - set(FAMILIES))
    if unknown:
        raise BindingError(f"anchors name unknown families: {unknown}")

    missing = sorted(used_families - anchor_families)
    if missing:
        raise BindingError(
            f"binding is missing hue anchors for families used by roles: {missing}"
        )

    for fam, a in sorted(binding.anchors.items()):
        if not (lo < a.family_scale <= hi):
            raise BindingError(f"anchor {fam}: family_scale {a.family_scale} not in ({lo}, {hi}]")
        if not (0.0 <= a.h < 360.0 or a.h == 0.0):
            if not (0.0 <= a.h % 360.0 < 360.0):
                raise BindingError(f"anchor {fam}: hue {a.h} not in [0, 360)")

    bad_roles = sorted(
        set(binding.role_scales) | set(binding.adjustments) | set(binding.role_overrides)
    )
    unknown_roles = sorted(r for r in bad_roles if r not in spec.roles)
    if unknown_roles:
        raise BindingError(f"binding references unknown roles: {unknown_roles}")

    for role, s in sorted(binding.role_scales.items()):
        if not (lo < s <= hi):
            raise BindingError(f"role_scale {role}: {s} not in ({lo}, {hi}]")

    # role overrides: per-role experimental tweaks to the semantic properties
    # the solve branches on.  Validated strictly so a typo cannot silently flip
    # a role into the wrong derivation path.
    _override_vocab = {
        "contrast_target": (None, CONTRAST_TARGETS),
        "chroma_class": (None, CHROMA_CLASSES),
        "accessibility_floor": (None, ACCESSIBILITY_FLOORS),
        "night_adaptation": (0.0, 1.0),
    }
    for role, ov in sorted(binding.role_overrides.items()):
        for key, val in ov.items():
            if key not in _override_vocab:
                raise BindingError(f"role_override {role}: unknown key {key!r}")
            lo_v, hi_v = _override_vocab[key]
            if key == "night_adaptation":
                if not (lo_v <= float(val) <= hi_v):
                    raise BindingError(f"role_override {role}.night_adaptation out of range")
            elif hi_v is not None and val not in hi_v:
                raise BindingError(f"role_override {role}.{key}={val!r} not in {hi_v}")

    for role, adj in sorted(binding.adjustments.items()):
        for key, val in (("L", adj.L), ("C", adj.C), ("h", adj.h)):
            if abs(val) > ADJUSTMENT_LIMITS[key] + 1e-9:
                raise BindingError(
                    f"adjustment {role}.{key}={val} exceeds bound "
                    f"{ADJUSTMENT_LIMITS[key]} (rationale: {adj.rationale!r})"
                )

    if binding.warm_anchor_override is not None and not (0.0 <= binding.warm_anchor_override < 360.0):
        raise BindingError(
            f"warm_anchor {binding.warm_anchor_override} not in [0, 360)"
        )


# ===========================================================================
# Per-role derivation trace
# ===========================================================================


@dataclass
class RoleTrace:
    """Full derivation provenance for one role in one variant.

    Every downstream claim (contrast, distance, stability) is derived from the
    ``final_hex``; this trace pins down HOW that hex was reached, so a number
    that looks wrong can be traced to its cause (a cap loss, a gamut loss, a
    WCAG override, an adjustment) rather than guessed at.
    """

    role: str
    paint: str
    variant: str
    family: str
    base_oklch: tuple  # (L0, C0, h0): identity before the transform
    requested: tuple   # (L, C, h): after transform, before absolute cap
    capped: tuple      # after absolute chroma cap, before gamut map
    realized: tuple    # after gamut map (the coordinate the hex quantises)
    final_hex: str
    max_chroma_at_L: float
    chroma_losses: dict  # {"requested", "capped", "realized", "cap_loss",
    #                      "gamut_loss", "total_loss", "realized_fraction"}
    adjustments_applied: dict  # {"L", "C", "h"} actually applied (bounded)
    contrast: dict  # contrast vs reference + co-occurring surfaces
    conflicts: list  # e.g. "wcag_apca_conflict", "foreground_ceiling_overridden"
    winning_constraint: str | None
    derivation: list  # human-readable ordered steps
    issues: list  # soft issues for THIS role (severity-tagged strings)

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "paint": self.paint,
            "variant": self.variant,
            "family": self.family,
            "base_oklch": _round3(self.base_oklch),
            "requested": _round3(self.requested),
            "capped": _round3(self.capped),
            "realized": _round3(self.realized),
            "final_hex": self.final_hex,
            "max_chroma_at_L": round(self.max_chroma_at_L, 6),
            "chroma_losses": {k: round(v, 6) for k, v in self.chroma_losses.items()},
            "adjustments_applied": {k: round(v, 5) for k, v in self.adjustments_applied.items()},
            "contrast": self.contrast,
            "conflicts": self.conflicts,
            "winning_constraint": self.winning_constraint,
            "derivation": self.derivation,
            "issues": self.issues,
        }


def _round3(t):
    return tuple(round(float(x), 4) for x in t)


# ===========================================================================
# Core colour maths: chroma formula, hue adaptation, solving
# ===========================================================================


def chroma_components(
    spec: ModelSpec, binding: CandidateBinding, role: Role, L: float, h: float, env_name: str
) -> dict:
    """The multiplicative chroma chain, returned factorised for provenance.

    ``requested = max_chroma(L,h) * class_frac * candidate * family * role
                  * env_gain * (1 - attenuation*night_adaptation)``
    """
    env = spec.environments.environments[env_name]
    cmax = max_chroma(L, h, "srgb")
    class_frac = spec.environments.chroma_classes.get(role.chroma_class, 0.0)
    candidate = binding.candidate_scale
    family = binding.anchors[role.family].family_scale
    role_scale = binding.role_scales.get(role.name, 1.0)
    env_gain = env.chroma_gain
    night_term = 1.0 - env.chroma_attenuation * role.night_adaptation
    requested = (
        cmax * class_frac * candidate * family * role_scale * env_gain * night_term
    )
    return {
        "max_chroma": cmax,
        "class_fraction": class_frac,
        "candidate_scale": candidate,
        "family_scale": family,
        "role_scale": role_scale,
        "environment_gain": env_gain,
        "night_term": night_term,
        "requested": max(0.0, requested),
    }


def adapt_hue(
    spec: ModelSpec,
    env_name: str,
    role: Role,
    h0: float,
    warm_anchor_override: float | None = None,
) -> tuple[float, dict]:
    """Attract ``h0`` along the shortest arc toward the warm anchor.

    Returns (h_adapted, components).  Direction is the SIGN of the shortest arc
    to the anchor (so violet 300 -> toward magenta/red, warmer; a plain negative
    rotation would move it toward blue, cooler -- the bug this corrects).
    Magnitude is bounded by the environment's rotation cap and gated by the
    role's night_adaptation and the per-hue weight.
    """
    env = spec.environments.environments[env_name]
    warm = (
        spec.environments.warm_anchor
        if warm_anchor_override is None
        else warm_anchor_override
    )
    cap = env.rotation_cap_deg
    weight = spec.environments.hue_weight(h0)
    delta = signed_shortest_arc(h0, warm)  # signed direction toward warm
    direction = 0.0 if abs(delta) < 1e-9 else math.copysign(1.0, delta)
    magnitude = cap * role.night_adaptation * weight
    h_adapted = (h0 + direction * magnitude) % 360.0
    return h_adapted, {
        "base_hue": h0,
        "warm_anchor": warm,
        "rotation_cap": cap,
        "night_adaptation": role.night_adaptation,
        "weight": weight,
        "direction": direction,
        "magnitude": magnitude,
        "adapted_hue": h_adapted,
    }


def _realize_chroma(L: float, h: float, components: dict, ceiling: float):
    """Apply the absolute cap then the gamut map; return losses + coordinates."""
    requested = components["requested"]
    capped_C = min(requested, ceiling)
    cap_loss = max(0.0, requested - capped_C)
    capped = (L, capped_C, h)
    realized, gamut_loss = gamut_map(capped, "srgb")
    realized_C = realized[1]
    total_loss = cap_loss + gamut_loss
    realized_fraction = (realized_C / requested) if requested > 1e-9 else 1.0
    return {
        "capped": capped,
        "realized": realized,
        "cap_loss": cap_loss,
        "gamut_loss": gamut_loss,
        "total_loss": total_loss,
        "realized_fraction": realized_fraction,
        "requested_C": requested,
    }


# -- contrast solving (ink & border share this; params differ) --------------


def _accessibility_wcag_floor(role: Role, spec: ModelSpec) -> float:
    """Resolve a semantic floor name to the configured WCAG threshold."""
    floors = spec.environments.accessibility_floors
    if role.accessibility_floor == "body_text":
        return float(floors["body_text_wcag"])
    if role.accessibility_floor == "non_text":
        return float(floors["non_text_wcag"])
    return 0.0


def _wcag_of(L: float, h: float, role, binding, spec, env_name, ref_hex, components, ceiling):
    out = _realize_chroma(L, h, components, ceiling)
    ink_hex = oklch_to_hex(out["realized"])
    return wcag_contrast(ink_hex, ref_hex), out


def _apca_abs_of(L: float, h: float, role, binding, spec, env_name, ref_hex, components, ceiling):
    out = _realize_chroma(L, h, components, ceiling)
    ink_hex = oklch_to_hex(out["realized"])
    return abs(apca_lc(ink_hex, ref_hex)), out


def _solve_contrast_role(
    role: Role,
    h: float,
    ref_hex: str,
    ref_L: float,
    env_name: str,
    spec: ModelSpec,
    binding: CandidateBinding,
) -> tuple[float, dict]:
    """Lexicographic lightness solve for an ink/border role.

    Priorities: (1) gamut/polarity, (2) WCAG floor, (3) Night fg ceiling,
    (4) APCA band centre, (5) minimal adjustment.  Returns (L, details).
    """
    env = spec.environments.environments[env_name]
    dark = env.polarity == "dark"
    ceiling = env.foreground_ceiling if role.paint == "ink" else None
    wcag_floor = _accessibility_wcag_floor(role, spec)
    band = spec.environments.contrast_bands[role.contrast_target]
    apca_centre = band.centre
    abs_ceiling = spec.environments.chroma_absolute_ceiling

    def comp(L):
        return chroma_components(spec, binding, role, L, h, env_name)

    def wcag_at(L):
        return _wcag_of(L, h, role, binding, spec, env_name, ref_hex, comp(L), abs_ceiling)[0]

    def apca_at(L):
        return _apca_abs_of(L, h, role, binding, spec, env_name, ref_hex, comp(L), abs_ceiling)[0]

    details: dict = {
        "polarity": env.polarity,
        "wcag_floor": wcag_floor,
        "apca_centre": apca_centre,
        "ceiling": ceiling,
        "ref_L": ref_L,
    }

    # --- priority 1+2: feasible WCAG lightness ---------------------------
    if dark:
        lo, hi = ref_L, 1.0
    else:
        lo, hi = 0.0, ref_L
    # feasibility: the extreme (most separation) must meet the floor
    extreme = hi if dark else lo
    if wcag_floor > 0.0 and wcag_at(extreme) + 1e-6 < wcag_floor:
        raise TransformError(
            f"{role.name}@{env_name}: WCAG floor {wcag_floor} unreachable "
            f"(max contrast {wcag_at(extreme):.3f} at L={extreme:.3f} vs ref L={ref_L:.3f})"
        )

    # L_wcag: minimal-separation lightness that meets the floor
    if wcag_floor > 0.0:
        if dark:
            a, b = ref_L, 1.0
            while b - a > SOLVE_TOL:
                m = (a + b) / 2
                if wcag_at(m) >= wcag_floor:
                    b = m
                else:
                    a = m
            L_wcag = b
        else:
            a, b = 0.0, ref_L
            while b - a > SOLVE_TOL:
                m = (a + b) / 2
                if wcag_at(m) >= wcag_floor:
                    a = m
                else:
                    b = m
            L_wcag = a
    else:
        L_wcag = ref_L  # no floor -> defer entirely to APCA preference

    # --- priority 4: APCA band centre -------------------------------------
    if dark:
        a, b = ref_L, 1.0
        if apca_at(b) + 1e-6 < apca_centre:
            L_apca = b  # cannot reach centre; clamp, record miss below
            apca_reachable = False
        else:
            while b - a > SOLVE_TOL:
                m = (a + b) / 2
                if apca_at(m) >= apca_centre:
                    b = m
                else:
                    a = m
            L_apca = b
            apca_reachable = True
    else:
        a, b = 0.0, ref_L
        if apca_at(a) + 1e-6 < apca_centre:
            L_apca = a
            apca_reachable = False
        else:
            while b - a > SOLVE_TOL:
                m = (a + b) / 2
                if apca_at(m) >= apca_centre:
                    a = m
                else:
                    b = m
            L_apca = a
            apca_reachable = True

    # --- resolve WCAG (2) vs APCA (4) -------------------------------------
    conflict = False
    if wcag_floor > 0.0:
        meets_at_apca = wcag_at(L_apca) >= wcag_floor - 1e-6
        if meets_at_apca:
            L_pref = L_apca
        else:
            L_pref = L_wcag  # WCAG forces beyond APCA centre
            conflict = True
    else:
        L_pref = L_apca

    # --- priority 3: Night foreground ceiling -----------------------------
    overridden = False
    winning: str
    if ceiling is not None and dark and wcag_floor > 0.0:
        if ceiling >= L_wcag:
            L_final = min(L_pref, ceiling)
            if L_final < L_pref - 1e-9:
                winning = "night_ceiling"
            elif conflict:
                winning = "wcag_floor"
            else:
                winning = "apca_centre"
        else:
            # meeting WCAG requires exceeding the ceiling -> WCAG overrides
            L_final = L_wcag
            overridden = True
            winning = "wcag_floor"
    else:
        L_final = L_pref
        winning = "wcag_floor" if conflict else "apca_centre"

    details.update(
        L_wcag=L_wcag,
        L_apca=L_apca,
        L_pref=L_pref,
        L_final=L_final,
        apca_reachable=apca_reachable,
        wcag_apca_conflict=conflict,
        foreground_ceiling_overridden=overridden,
        winning_constraint=winning,
    )
    return L_final, details


# ===========================================================================
# Per-paint derivation
# ===========================================================================


def _base_identity(role: Role, binding: CandidateBinding) -> tuple[float, float, float]:
    """The role's pre-transform identity: anchor hue, zero chroma, mid lightness.

    Lightness is solved/stepped per paint type; chroma comes from the formula.
    Only the family hue is an identity here, which is the point: a role's
    identity is its contrast relationship (ink) or its perceptual step (surface),
    not an absolute lightness value (DESIGN.md section 9).
    """
    h0 = binding.anchors[role.family].h % 360.0
    return (0.5, 0.0, h0)


def _trace_common(
    role: Role, env_name: str, L: float, h: float, components: dict, spec: ModelSpec
) -> dict:
    abs_ceiling = spec.environments.chroma_absolute_ceiling
    out = _realize_chroma(L, h, components, abs_ceiling)
    losses = {
        "requested": out["requested_C"],
        "capped": out["capped"][1],
        "realized": out["realized"][1],
        "cap_loss": out["cap_loss"],
        "gamut_loss": out["gamut_loss"],
        "total_loss": out["total_loss"],
        "realized_fraction": out["realized_fraction"],
    }
    return {"L": L, "h": h, "components": components, "losses": losses,
            "capped": out["capped"], "realized": out["realized"]}


def _build_canvas(role, env, env_name):
    """Authored verbatim from the environment (the contrast reference)."""
    bg = env.background
    return (bg.L, bg.C, bg.h)


def _build_elevated(env, key):
    """bg_elevated / bg_overlay are authored backgrounds, emitted verbatim."""
    src = getattr(env, key)
    return (src.L, src.C, src.h)


def _derive_surface(role, env_name, spec, binding, canvas_L):
    """Perceptual lightness STEP from the canvas; never contrast-solved."""
    env = spec.environments.environments[env_name]
    dark = env.polarity == "dark"
    step = SURFACE_STEPS.get(role.contrast_target, SURFACE_STEPS["low"])
    direction = 1.0 if dark else -1.0
    L = max(_L_FLOOR, min(_L_CEIL, canvas_L + direction * step))
    h0 = binding.anchors[role.family].h % 360.0
    h, hue_info = adapt_hue(
        spec, env_name, role, h0, binding.warm_anchor_override
    )
    components = chroma_components(spec, binding, role, L, h, env_name)
    return L, h, components, hue_info


def _derive_ink_or_border(role, env_name, spec, binding, ref_hex, ref_L):
    """Contrast-solve lightness (lexicographic); chroma follows from the formula."""
    h0 = binding.anchors[role.family].h % 360.0
    h, hue_info = adapt_hue(
        spec, env_name, role, h0, binding.warm_anchor_override
    )
    L, solve_info = _solve_contrast_role(
        role, h, ref_hex, ref_L, env_name, spec, binding
    )
    components = chroma_components(spec, binding, role, L, h, env_name)
    return L, h, components, hue_info, solve_info


# ===========================================================================
# Variant + family build
# ===========================================================================


@dataclass
class VariantBuild:
    variant: str
    palette: Palette
    traces: dict[str, RoleTrace]


def _apply_adjustment(role, L, h, components, binding, spec, env_name):
    """Apply a bounded adjustment; clamp so hard constraints stay satisfied.

    Returns (dL, dC, dh actually applied).  Lightness/chroma/hue are nudged; if
    a lightness nudge would drop an ink/border below its WCAG floor it is
    rejected (recorded).  Hue adjustments always count toward cross-variant
    drift (see family_stability).
    """
    adj = binding.adjustments.get(role.name)
    if adj is None:
        return {"L": 0.0, "C": 0.0, "h": 0.0}, L, h, components
    env = spec.environments.environments[env_name]
    dL = max(-ADJUSTMENT_LIMITS["L"], min(ADJUSTMENT_LIMITS["L"], adj.L))
    dC = max(-ADJUSTMENT_LIMITS["C"], min(ADJUSTMENT_LIMITS["C"], adj.C))
    dh = max(-ADJUSTMENT_LIMITS["h"], min(ADJUSTMENT_LIMITS["h"], adj.h))
    # apply chroma + hue adjustments directly to the requested chroma / hue
    components = dict(components)
    components["requested"] = max(0.0, components["requested"] + dC)
    new_h = (h + dh) % 360.0
    # lightness nudge, clamped to range.  Hard floors are re-validated by the
    # caller's final-quantized-hex WCAG check -- priority 5 (minimal adjustment)
    # never overrides priority 2 (WCAG floor); an adjustment that would break
    # the floor surfaces there as an issue, not a silent violation.
    new_L = max(_L_FLOOR, min(_L_CEIL, L + dL))
    return {"L": new_L - L, "C": dC, "h": dh}, new_L, new_h, components


def _build_variant(
    binding: CandidateBinding, spec: ModelSpec, env_name: str
) -> VariantBuild:
    env = spec.environments.environments[env_name]
    roles = spec.roles
    abs_ceiling = spec.environments.chroma_absolute_ceiling
    palette_colors: dict[str, str] = {}
    palette_perceptual: dict[str, tuple[float, float, float]] = {}
    palette_losses: dict[str, float] = {}
    traces: dict[str, RoleTrace] = {}
    issues: list[str] = []

    # 1. canvas + authored elevated/overlay backgrounds (the direct references)
    canvas_role = next(r for r in roles if r.paint == "canvas")
    bg_lch = _build_canvas(canvas_role, env, env_name)
    bg_hex = oklch_to_hex(gamut_map(bg_lch, "srgb")[0])
    elevated_lch = _build_elevated(env, "background_elevated")
    overlay_lch = _build_elevated(env, "background_overlay")

    authored = {
        canvas_role.name: ("canvas", bg_lch),
        "bg_elevated": ("surface", elevated_lch),
        "bg_overlay": ("surface", overlay_lch),
    }
    for role_name, (paint, lch) in authored.items():
        role = roles.roles[role_name]
        mapped, gloss = gamut_map(lch, "srgb")
        hx = oklch_to_hex(mapped)
        palette_colors[role_name] = hx
        palette_perceptual[role_name] = mapped
        palette_losses[role_name] = gloss
        base = _base_identity(role, binding)
        traces[role_name] = RoleTrace(
            role=role_name, paint=paint, variant=env_name, family=role.family,
            base_oklch=base, requested=tuple(lch), capped=tuple(lch),
            realized=tuple(mapped), final_hex=hx,
            max_chroma_at_L=max_chroma(mapped[0], mapped[2], "srgb"),
            chroma_losses={"requested": lch[1], "capped": lch[1], "realized": mapped[1],
                           "cap_loss": 0.0, "gamut_loss": gloss, "total_loss": gloss,
                           "realized_fraction": 1.0 if lch[1] <= 1e-9 else mapped[1] / lch[1]},
            adjustments_applied={"L": 0.0, "C": 0.0, "h": 0.0},
            contrast={}, conflicts=[], winning_constraint="authored",
            derivation=[f"{paint}: authored verbatim from environment.{env_name}.background*"],
            issues=[],
        )

    ref_L = bg_lch[0]

    # 2. derived surfaces (perceptual steps)
    # 3. ink + border (contrast-solved)
    for role in roles:
        if role.name in authored:
            continue
        r = _effective_role(role, binding)
        base = _base_identity(r, binding)
        try:
            if r.paint == "surface":
                L, h, components, hue_info = _derive_surface(
                    r, env_name, spec, binding, ref_L
                )
                solve_info = {"winning_constraint": "perceptual_step"}
            elif r.paint in ("ink", "border"):
                L, h, components, hue_info, solve_info = _derive_ink_or_border(
                    r, env_name, spec, binding, bg_hex, ref_L
                )
            else:
                raise BindingError(f"{r.name}: unknown paint {r.paint!r}")
        except TransformError:
            raise

        # bounded adjustment (priority 5: minimal adjustment)
        unadjusted = (L, h, components)
        applied, L, h, components = _apply_adjustment(
            r, L, h, components, binding, spec, env_name
        )
        common = _trace_common(r, env_name, L, h, components, spec)
        realized = common["realized"]
        losses = common["losses"]
        hx = oklch_to_hex(realized)
        adjustment_rejected = False
        floor_v = _accessibility_wcag_floor(r, spec)
        if (
            r.paint in ("ink", "border")
            and floor_v > 0.0
            and any(applied.values())
            and wcag_contrast(hx, bg_hex) + 1e-6 < floor_v
        ):
            # Adjustments are the lowest-priority preference. If their combined
            # L/C/h change breaches a hard floor, reject the whole nudge and
            # retain the systematic solution rather than emitting a known-bad
            # colour with ``ok=False``.
            L, h, components = unadjusted
            applied = {"L": 0.0, "C": 0.0, "h": 0.0}
            common = _trace_common(r, env_name, L, h, components, spec)
            realized = common["realized"]
            losses = common["losses"]
            hx = oklch_to_hex(realized)
            adjustment_rejected = True
        palette_colors[role.name] = hx
        palette_perceptual[role.name] = realized
        palette_losses[role.name] = losses["gamut_loss"]

        # contrast vs reference + final-hex WCAG validation
        contrast = _contrast_block(r, hx, bg_hex, spec, env_name)
        conflicts = []
        derivation = []
        winning = solve_info.get("winning_constraint", "perceptual_step")
        if r.paint in ("ink", "border"):
            if solve_info.get("wcag_apca_conflict"):
                conflicts.append("wcag_apca_conflict")
            if solve_info.get("foreground_ceiling_overridden"):
                conflicts.append("foreground_ceiling_overridden")
            if adjustment_rejected:
                conflicts.append("adjustment_rejected_wcag")
            derivation.append(
                f"solved L={L:.4f} to {winning} "
                f"(wcag_floor={solve_info['wcag_floor']}, "
                f"apca_centre={solve_info['apca_centre']}, "
                f"L_wcag={solve_info['L_wcag']:.4f}, L_apca={solve_info['L_apca']:.4f})"
            )
            # final quantized hex must still meet the floor
            if floor_v > 0.0:
                if contrast["wcag"] + 1e-6 < floor_v:
                    issues.append(
                        f"[error] {r.name}@{env_name}: final hex {hx} WCAG "
                        f"{contrast['wcag']:.3f} < floor {floor_v} after quantization"
                    )
        else:
            derivation.append(
                f"surface step: L={L:.4f} (canvas {ref_L:.4f} "
                f"{'+.' if L>=ref_L else '-.'}{abs(L-ref_L):.4f})"
            )

        derivation.append(
            f"chroma: requested {losses['requested']:.4f} -> capped "
            f"{losses['capped']:.4f} (cap -{losses['cap_loss']:.4f}) -> "
            f"realized {losses['realized']:.4f} (gamut -{losses['gamut_loss']:.4f}), "
            f"fraction {losses['realized_fraction']:.3f}"
        )
        if any(applied.values()):
            derivation.append(
                f"adjustment applied L{applied['L']:+.4f} C{applied['C']:+.4f} "
                f"h{applied['h']:+.3f}"
            )
        elif adjustment_rejected:
            derivation.append("adjustment rejected: combined nudge breached WCAG floor")

        role_issues: list[str] = []
        if losses["total_loss"] > 1e-6 and losses["realized_fraction"] < 0.85:
            role_issues.append(
                f"[warning] {r.name}@{env_name}: large chroma loss "
                f"({losses['total_loss']:.4f}, fraction {losses['realized_fraction']:.3f})"
            )

        traces[r.name] = RoleTrace(
            role=r.name, paint=r.paint, variant=env_name, family=r.family,
            base_oklch=base, requested=(L, components["requested"], h),
            capped=common["capped"], realized=realized, final_hex=hx,
            max_chroma_at_L=components["max_chroma"],
            chroma_losses=losses, adjustments_applied=applied, contrast=contrast,
            conflicts=conflicts, winning_constraint=winning, derivation=derivation,
            issues=role_issues,
        )

    palette = Palette(
        binding.name, env_name, palette_colors, source="oklch",
        perceptual=palette_perceptual, gamut_losses=palette_losses,
        note=f"Phase 4 transform; candidate={binding.is_candidate}",
        meta={"candidate": binding.is_candidate, "transform": "phase4"},
    )
    return VariantBuild(env_name, palette, traces)


def _contrast_block(role, hx, bg_hex, spec, env_name):
    rep = contrast_report(hx, bg_hex)
    measured_band = spec.environments.band_for_lc(abs(rep.apca))
    target = role.contrast_target
    # ``measured_band`` remains a convenient single label for reports. Target
    # membership must be checked directly because the declared bands overlap.
    in_target = (
        target is not None
        and spec.environments.contrast_bands[target].contains(abs(rep.apca))
    )
    return {
        "reference": "bg",
        "target_band": target,
        "measured_band": measured_band.name if measured_band else None,
        "in_target_band": in_target,
        "wcag": round(rep.wcag, 4),
        "apca_lc": round(rep.apca, 4),
        "oklab_dl": round(rep.dl, 6),
    }


def _evaluate_legibility(colors, roles, spec, env_name):
    """Ink-over-co-occurring-surface WCAG evaluation -> issue strings.

    Text can land on selection/search/active-line/diff/debug surfaces; the ink's
    primary reference is bg, but it must also remain legible over these.  A miss
    is an issue, not a TransformError (DESIGN.md roles.yaml: "text on selection
    must stay readable").
    """
    out = []
    surfaces = [s for s in CO_OCCURRING_SURFACES if s in colors]
    for role in roles:
        if role.paint != "ink" or role.accessibility_floor == "none":
            continue
        hx = colors.get(role.name)
        if not hx:
            continue
        floor = _accessibility_wcag_floor(role, spec)
        for surf in surfaces:
            wcag = wcag_contrast(hx, colors[surf])
            if wcag + 1e-6 < floor:
                out.append(
                    f"[warning] {role.name}@{env_name} over {surf}: WCAG {wcag:.3f} "
                    f"< {floor} (ink-on-surface legibility)"
                )
    return out


# ===========================================================================
# Public seam: build_family
# ===========================================================================


@dataclass
class FamilyBuild:
    """Result of :func:`build_family`: three palettes + full provenance."""

    name: str
    binding: CandidateBinding
    spec: ModelSpec
    variants: dict[str, VariantBuild]
    input_hash: str
    issues: list[str]
    ok: bool
    stability: dict | None = None

    @property
    def palettes(self) -> dict[str, Palette]:
        return {v: vb.palette for v, vb in self.variants.items()}

    def variant(self, name: str) -> VariantBuild:
        return self.variants[name]

    def trace(self, variant: str, role: str) -> RoleTrace:
        return self.variants[variant].traces[role]

    def to_dict(self) -> dict:
        return {
            "schema": "grotto.family-build",
            "schema_version": "phase4",
            "name": self.name,
            "is_candidate": self.binding.is_candidate,
            "input_hash": self.input_hash,
            "ok": self.ok,
            "binding": self.binding.canonical(),
            "issues": self.issues,
            "stability": self.stability,
            "variants": {
                v: {
                    "palette": {
                        "name": vb.palette.name, "variant": vb.palette.variant,
                        "n_roles": len(vb.palette),
                        "colors": dict(vb.palette.colors),
                    },
                    "traces": {r: t.to_dict() for r, t in sorted(vb.traces.items())},
                }
                for v, vb in sorted(self.variants.items())
            },
        }


def _input_hash(binding: CandidateBinding, spec: ModelSpec) -> str:
    h = hashlib.sha256()
    payload = {
        "binding": binding.canonical(),
        # Hash the effective inputs, not only their version labels. Two working
        # specs can legitimately share a schema version while containing
        # different thresholds or environment coordinates.
        "roles": asdict(spec.roles),
        "environments": asdict(spec.environments),
        "distances": asdict(spec.distances),
    }
    h.update(json.dumps(_canonical_value(payload), sort_keys=True).encode())
    return h.hexdigest()[:16]


def build_family(binding: CandidateBinding, spec: ModelSpec) -> FamilyBuild:
    """Build the day/evening/night family for a binding under a model spec.

    Pure function of ``(binding, spec)``.  Raises :class:`BindingError` for a
    malformed binding and :class:`TransformError` for an infeasible hard
    constraint; aesthetic/distance/legibility misses are returned as ``issues``.
    """
    validate_binding(binding, spec)
    if not spec.environments.environments:
        raise BindingError("model spec has no environments")

    variants: dict[str, VariantBuild] = {}
    all_issues: list[str] = []
    for env_name in ("day", "evening", "night"):
        if env_name not in spec.environments.environments:
            raise BindingError(f"spec missing environment {env_name!r}")
        vb = _build_variant(binding, spec, env_name)
        variants[env_name] = vb

    for vb in variants.values():
        for t in vb.traces.values():
            all_issues.extend(t.issues)

    # distance-matrix issues (aesthetic/semantic misses; never raised)
    dm_issues = _distance_issues(variants, spec)
    all_issues.extend(dm_issues)

    # legibility issues already embedded per-variant; collect from a re-scan
    for env_name, vb in variants.items():
        leg = _evaluate_legibility(vb.palette.colors, spec.roles, spec, env_name)
        all_issues.extend(leg)

    # ok: built without TransformError AND every ink/border final hex meets floor
    ok = True
    for env_name, vb in variants.items():
        bg_hex = vb.palette["bg"]
        for role in spec.roles:
            if role.paint in ("ink", "border") and role.accessibility_floor != "none":
                hx = vb.palette.colors.get(role.name)
                if hx and role.name in vb.palette:
                    effective = _effective_role(role, binding)
                    floor = _accessibility_wcag_floor(effective, spec)
                    if wcag_contrast(hx, bg_hex) + 1e-6 < floor:
                        ok = False

    h = _input_hash(binding, spec)
    stability = family_stability_build(variants, spec)
    return FamilyBuild(
        name=binding.name, binding=binding, spec=spec, variants=variants,
        input_hash=h, issues=sorted(set(all_issues)), ok=ok, stability=stability,
    )


def _distance_issues(variants: dict[str, VariantBuild], spec: ModelSpec) -> list[str]:
    """Distance-matrix violations as issues (informational, never raised)."""
    from .distance import delta_e_ok
    from .spec import check as spec_check

    out: list[str] = []
    for env_name, vb in variants.items():
        viols = spec_check(vb.palette, spec.roles, spec.distances)
        for v in viols:
            out.append(
                f"[{v.severity}] {env_name}: {v.constraint} under {v.condition}: "
                f"dE {v.measured:.3f} vs {v.threshold:.3f}"
            )
    return out


# ===========================================================================
# Corrected cross-variant stability (senior-review fixes to DESIGN.md D-5)
# ===========================================================================
#
# Phase 2's ``cross_variant_report`` works on bare hex palettes and uses raw
# chroma rank + pairwise signed hue ordering.  Both are wrong for a transform
# that inverts lightness between Day and Night and rotates hue via warm
# attraction across the 0/360 wrap:
#   * raw chroma is NOT comparable across lightness-inverted variants; the
#     invariant quantity is the realized fraction of available chroma,
#     C / max_chroma(L, h).
#   * pairwise signed shortest-arc hue is unstable near the wrap and near
#     antipodal hues; the robust check is the cyclic SEQUENCE of families.
#   * salience rank was "preserved by construction" (vacuous).  A non-vacuous
#     proxy checks that realized chroma actually tracks the declared hierarchy.
#   * total hue drift must include the per-role adjustment component, which the
#     realized (post-adjustment) hue already encodes.
#
# These corrected checks need the transform's provenance (max_chroma per role),
# so they live here rather than in the Phase 2 stability module.


def _circular_mean(hues):
    if not hues:
        return None
    xs = sum(math.cos(math.radians(h)) for h in hues)
    ys = sum(math.sin(math.radians(h)) for h in hues)
    return math.degrees(math.atan2(ys, xs)) % 360.0


def family_stability_build(variants: dict[str, VariantBuild], spec: ModelSpec) -> dict:
    """Corrected cross-variant stability for a built family.

    Takes the per-variant traces (which carry max_chroma and post-adjustment
    realized hues) and applies the four corrected checks.  Returns a report
    dict; never raises -- stability misses are reported, not thrown.
    """
    var_names = tuple(sorted(variants))
    roles = spec.roles
    floor = 0.02  # chroma below this -> hue/normalized-chroma meaningless
    thresh = spec.environments.stability.get("max_hue_drift_deg", 12.0)

    # only roles present in every variant can be compared across variants;
    # hand-tuned inputs are often partial, so missing roles are skipped
    # (never raise) rather than treated as instability.
    present_roles = [r.name for r in roles
                     if all(r.name in variants[v].traces for v in var_names)]
    role_by_name = {r.name: r for r in roles}

    # normalized realized chroma C / max_chroma(L, h)
    normC: dict[tuple[str, str], float] = {}
    for v in var_names:
        for name in present_roles:
            t = variants[v].traces[name]
            mc = t.max_chroma_at_L
            normC[(name, v)] = (t.realized[1] / mc) if mc and mc > 1e-9 else 0.0

    def is_chromatic(name):
        return all(variants[v].traces[name].realized[1] >= floor for v in var_names)

    chromatic = [name for name in present_roles if is_chromatic(name)]

    # (1) normalized C/max_chroma ordering preservation
    nc_inversions = []
    for a, b in combinations(chromatic, 2):
        for v1, v2 in combinations(var_names, 2):
            da = normC[(a, v1)] - normC[(b, v1)]
            db = normC[(a, v2)] - normC[(b, v2)]
            if abs(da) > 1e-3 and abs(db) > 1e-3 and (da > 0) != (db > 0):
                nc_inversions.append(
                    {"roles": [a, b], "variants": [v1, v2],
                     "d1": round(da, 4), "d2": round(db, 4)})

    # (2) cyclic family hue sequence preservation (not pairwise signed)
    families_used = sorted({role_by_name[n].family for n in chromatic})
    fam_hue: dict[tuple[str, str], float | None] = {}
    for fam in families_used:
        for v in var_names:
            hs = [variants[v].traces[n].realized[2]
                  for n in chromatic if role_by_name[n].family == fam]
            fam_hue[(fam, v)] = _circular_mean(hs)
    seq: dict[str, tuple] = {}
    for v in var_names:
        present = [f for f in families_used if fam_hue[(f, v)] is not None]
        ordered = sorted(present, key=lambda f: fam_hue[(f, v)])
        # canonicalize the cyclic order by rotating the smallest family name
        # to the front, so a global wrap rotation does not look like a swap.
        if ordered:
            k = ordered.index(min(ordered))
            ordered = ordered[k:] + ordered[:k]
        seq[v] = tuple(ordered)
    sequence_preserved = len(set(seq.values())) <= 1

    # (3) non-vacuous realized salience proxy: within a family, higher declared
    # salience should carry >= normalized chroma (DESIGN.md: chroma is a
    # salience channel).  A reversal is recorded; it is a soft signal.
    salience_reversals = []
    for fam in families_used:
        famroles = [role_by_name[n] for n in chromatic if role_by_name[n].family == fam]
        if len(famroles) < 2:
            continue
        for v in var_names:
            sr = sorted(famroles, key=lambda r: r.salience)
            for i in range(len(sr) - 1):
                if normC[(sr[i].name, v)] - normC[(sr[i + 1].name, v)] > 2e-3:
                    salience_reversals.append(
                        {"family": fam, "variant": v,
                         "lower_salience": sr[i].name, "higher_salience": sr[i + 1].name})

    # (4) total hue drift INCLUDING adjustments (realized hue is post-adjustment)
    drift_violations = []
    max_drift = 0.0
    for role in chromatic:
        for v1, v2 in combinations(var_names, 2):
            h1 = variants[v1].traces[role].realized[2]
            h2 = variants[v2].traces[role].realized[2]
            d = circular_drift(h1, h2)
            if d > max_drift:
                max_drift = d
            if d > thresh:
                drift_violations.append(
                    {"role": role, "variants": [v1, v2], "drift_deg": round(d, 3)})

    ok = (not nc_inversions and sequence_preserved and not drift_violations)
    return {
        "variants": list(var_names),
        "checks": [
            "normalized_chroma_ordering",
            "cyclic_family_sequence",
            "realized_salience_proxy",
            "total_hue_drift_including_adjustments",
        ],
        "normalized_chroma_inversions": nc_inversions,
        "cyclic_family_sequence_preserved": sequence_preserved,
        "cyclic_family_sequence": {v: list(s) for v, s in seq.items()},
        "salience_proxy_reversals": salience_reversals,
        "max_hue_drift_deg": round(max_drift, 4),
        "drift_threshold_deg": thresh,
        "drift_violations": drift_violations,
        "ok": ok,
    }


# ===========================================================================
# Systematic-vs-hand-tuned comparison
# ===========================================================================

#: dE_OK above which a role is counted as "needing hand adjustment" relative to
#: the systematic output.  ~0.05 is a side-by-side comfortable-difference step.
COMPARE_DE_THRESHOLD = 0.05


def _stub_trace(role_name: str, variant: str, palette: Palette, spec: ModelSpec) -> RoleTrace:
    """A minimal trace for a hand-authored role (no derivation provenance)."""
    from .color import hex_to_oklch, max_chroma as _mc
    L, C, h = hex_to_oklch(palette[role_name])
    return RoleTrace(
        role=role_name, paint="hand", variant=variant, family="",
        base_oklch=(L, C, h), requested=(L, C, h), capped=(L, C, h),
        realized=(L, C, h), final_hex=palette[role_name],
        max_chroma_at_L=_mc(L, h, "srgb"),
        chroma_losses={"requested": C, "capped": C, "realized": C, "cap_loss": 0.0,
                       "gamut_loss": 0.0, "total_loss": 0.0,
                       "realized_fraction": 1.0},
        adjustments_applied={"L": 0.0, "C": 0.0, "h": 0.0},
        contrast={}, conflicts=[], winning_constraint="hand_authored",
        derivation=["hand-authored; no systematic derivation"], issues=[],
    )


def hand_tuned_build(
    palettes: dict[str, Palette], spec: ModelSpec, name: str = "hand-tuned"
) -> FamilyBuild:
    """Wrap hand-authored per-variant palettes as a FamilyBuild for comparison.

    The hand-tuned input carries no systematic derivation provenance; its traces
    are stubs that record the authored colour and its max_chroma so the
    corrected stability checks can still run on it.  Used by
    :func:`compare_families`.
    """
    variants: dict[str, VariantBuild] = {}
    for v, pal in palettes.items():
        traces = {r: _stub_trace(r, v, pal, spec) for r in pal.roles()}
        variants[v] = VariantBuild(v, pal, traces)
    h = hashlib.sha256()
    for v in sorted(variants):
        h.update(v.encode())
        for role in sorted(variants[v].palette.colors):
            h.update(f"{role}={variants[v].palette[role]};".encode())
    stability = family_stability_build(variants, spec)
    return FamilyBuild(
        name=name, binding=_neutral_binding(spec), spec=spec, variants=variants,
        input_hash=h.hexdigest()[:16], issues=[], ok=True, stability=stability,
    )


def _neutral_binding(spec: ModelSpec) -> CandidateBinding:
    anchors = {f: FamilyAnchor(f, 0.0, 1.0) for f in FAMILIES}
    return CandidateBinding("hand-tuned", 1.0, anchors, meta={"candidate": False})


@dataclass
class RoleComparison:
    variant: str
    role: str
    systematic_hex: str
    hand_hex: str
    de: float
    dL: float
    dC: float
    dh: float
    needs_adjustment: bool


def compare_families(systematic: FamilyBuild, hand_tuned: FamilyBuild, spec: ModelSpec) -> dict:
    """Compare a systematic :class:`FamilyBuild` against a hand-tuned one.

    Beside :func:`build_family`, not inside it: the comparison is an evaluation
    question ("did the systematic transform match the designer's intent, or did
    the designer have to correct it?"), separate from building either family.
    Returns per-role deltas plus the headline finding -- whether the systematic
    output needed hand adjustment, and where.
    """
    from .color import hex_to_oklch
    from .distance import delta_e_ok

    variants = sorted(set(systematic.variants) & set(hand_tuned.variants))
    per_role: list[dict] = []
    needing: list[dict] = []
    des: list[float] = []
    for v in variants:
        sp = systematic.variants[v].palette
        hp = hand_tuned.variants[v].palette
        for role in spec.roles:
            if role.name not in sp or role.name not in hp:
                continue
            de = delta_e_ok(sp[role.name], hp[role.name])
            sL, sC, sh = hex_to_oklch(sp[role.name])
            hL, hC, hh = hex_to_oklch(hp[role.name])
            dh = signed_shortest_arc(sh, hh)
            needs = de > COMPARE_DE_THRESHOLD
            row = {
                "variant": v, "role": role.name,
                "systematic_hex": sp[role.name], "hand_hex": hp[role.name],
                "de": round(de, 5), "dL": round(sL - hL, 5),
                "dC": round(sC - hC, 5), "dh": round(dh, 4),
                "needs_adjustment": needs,
            }
            per_role.append(row)
            des.append(de)
            if needs:
                needing.append(row)

    import statistics
    summary = {
        "n_roles_compared": len(per_role),
        "n_variants": len(variants),
        "de_mean": round(statistics.mean(des), 5) if des else 0.0,
        "de_median": round(statistics.median(des), 5) if des else 0.0,
        "de_max": round(max(des), 5) if des else 0.0,
        "n_needing_adjustment": len(needing),
        "threshold_de": COMPARE_DE_THRESHOLD,
        "systematic_needed_hand_adjustment": bool(needing),
    }
    return {
        "schema": "grotto.family-comparison",
        "schema_version": "phase4",
        "systematic": systematic.name,
        "hand_tuned": hand_tuned.name,
        "summary": summary,
        "needing_adjustment": needing,
        "per_role": per_role,
        "systematic_stability": systematic.stability,
        "hand_tuned_stability": hand_tuned.stability,
        "note": (
            "NON-CANDIDATE Phase 4 experiment. dE_OK between systematic and "
            "hand-tuned final hex; roles above the threshold are where a human "
            "corrected the systematic output. No palette is finalised here."
        ),
    }


__all__ = [
    "BindingError",
    "TransformError",
    "FamilyAnchor",
    "RoleAdjustment",
    "CandidateBinding",
    "ModelSpec",
    "RoleTrace",
    "VariantBuild",
    "FamilyBuild",
    "ADJUSTMENT_LIMITS",
    "SURFACE_STEPS",
    "CO_OCCURRING_SURFACES",
    "validate_binding",
    "chroma_components",
    "adapt_hue",
    "signed_shortest_arc",
    "circular_drift",
    "build_family",
    "family_stability_build",
    "hand_tuned_build",
    "compare_families",
    "COMPARE_DE_THRESHOLD",
]
