"""Phase 3: quantitative reference-theme analysis.

This module analyses the six curated reference themes
(``themes/references/*.yaml``) on a *consistent* set of axes and produces a
side-by-side comparison.  It is deliberately **descriptive only**: it measures,
it does not rank, score, or declare a winner (DESIGN.md section 1 -- there is
no evidence that any syntax palette outperforms another).

Why a separate module, instead of reusing the Phase 2 ``palette_report``?
------------------------------------------------------------------------
The Phase 2 report audits *one* candidate/fixture palette against the full
spec.  References are different in two ways that matter:

1. They are partial and authored in editor-native terms.  Many spec roles are
   unmapped (``null``), and two themes ship **8-digit alpha hex** for selection
   backgrounds -- a representation grotto's candidate model does not use.  We
   normalise that here (base-RGB, the convention already documented in those
   YAMLs' own notes) and surface every normalisation and every missing role,
   rather than silently dropping or inventing data.

2. Some reference files carry more than one variant (Solarized has a light
   ``roles_light`` block; Rose Pine has a nested ``dawn`` light block).  The
   consistent six-way comparison uses the **dark** variant every file shares;
   the extra variants are recorded as provenance/ambiguity, never silently
   mixed into a polarity-heterogeneous comparison.

The interface is intentionally small::

    load_reference_file(path)  -> list[ReferenceVariant]   # all variants found
    load_reference_dir(dir)    -> dict[stem, list[ReferenceVariant]]
    analyze_reference(variant, roles, dists, env) -> dict   # one quantitative report
    compare_references(analyses, roles, dists, env) -> dict # side-by-side
    reference_text(analysis) / comparison_text(comparison) -> str

JSON/YAML reuse ``grotto.report.to_json`` / ``to_yaml`` (generic dict
serialisers).  HTML/SVG live in ``grotto.render``.

Axes analysed (each applied identically to every reference)
------------------------------------------------------------
  background        OKLCH L/C/h of bg (+ elevated/overlay), with hue suppressed
                    when effectively achromatic (C < ACHROMATIC_CHROMA_FLOOR).
  reading contrast  fg-vs-bg WCAG 2.x ratio + experimental APCA Lc + OKLab dL.
  distributions     lightness & chroma descriptive stats over present roles,
                    with and without background surfaces.
  constraints       per-pair dE + channel breakdown for every declared
                    distance-matrix constraint whose two roles are both mapped;
                    plus *coverage* -- the fraction of declared constraints the
                    reference even maps.
  warm/cool balance an explicitly defined, chroma-weighted score in [-1, +1]
                    (see ``warm_cool_balance`` docstring).
  spectral          nominal area-weighted melanopic output (exploratory only),
                    decomposed into background / foreground / token shares.
  CVD               must_distinguish pairs under protan/deutan/tritan
                    dichromacy; references are NOT bound by D-3.

Every caveat (APCA experimental; CVD population-average; spectral nominal-only)
is carried into the output verbatim, because a number torn from its caveat is
misleading.
"""

from __future__ import annotations

import re
import statistics
from dataclasses import dataclass
from pathlib import Path

import yaml

from .contrast import contrast_report
from .cvd import CVD_TYPES, simulate
from .distance import breakdown, delta_e_ok
from .environments import Environments
from .spectral import DISPLAYS, led_lcd, screen_melanopic
from .spec import (
    CONSTRAINT_KINDS,
    DistanceSpec,
    Palette,
    RoleSpec,
    coverage_model,
)

VERSION = "phase3"

#: A role whose OKLCH chroma is below this is treated as *effectively
#: achromatic*: its hue angle is noise and is suppressed in the output.  Kept
#: equal to ``stability.DEFAULT_CHROMA_FLOOR`` so the project speaks with one
#: voice about when hue is meaningful.
ACHROMATIC_CHROMA_FLOOR = 0.02

#: Hue of peak "warmth" for the warm/cool score (amber/orange).
WARM_HUE_CENTER = 60.0

#: CVD dichromat dE floor, taken from spec/distance-matrix.yaml at analysis
#: time (kept here only as a documented fallback; the live value comes from
#: ``dists.thresholds``).
_DEFAULT_CVD_FLOOR = 0.09

#: grotto variant labels considered "dark" polarity for the consistent
#: comparison.  Reference files use ``dark``; we also accept common synonyms.
_DARK_VARIANT_LABELS = {"dark", "wave", "dragon"}

_HEX6 = re.compile(r"#[0-9a-fA-F]{6}\b")
_HEX8 = re.compile(r"#[0-9a-fA-F]{8}\b")


# ===========================================================================
# Loading: variant + alpha-hex handling
# ===========================================================================


@dataclass(frozen=True)
class ReferenceVariant:
    """One loadable variant (polarity block) of a reference theme file.

    A file may yield more than one (e.g. Solarized yields ``dark`` + ``light``);
    exactly one is ``is_primary`` -- the block used in the consistent six-way
    comparison.  ``source_ambiguous`` is True whenever a file carries more than
    one variant, so the report can say so out loud.
    """

    name: str
    label: str  # dark | light | dawn | ... -- the block this came from
    palette: Palette
    source_url: str
    source_note: str
    is_primary: bool
    source_ambiguous: bool
    normalized_alpha_roles: tuple[str, ...] = ()
    extra_variant_labels: tuple[str, ...] = ()


def _normalize_role_hex(value, role: str, normalized: list[str]) -> str | None:
    """Return a clean 6-digit ``#rrggbb`` for a reference role value.

    Reference themes are editor-native and may carry **8-digit alpha hex**
    (e.g. VS Code ``editor.selectionBackground``).  grotto's candidate model is
    opaque sRGB, so we strip alpha to the base RGB -- the convention those
    YAMLs already document internally ("alpha stripped to base color").  The
    canonical YAML values are never modified; any normalisation is recorded in
    ``normalized`` and surfaced in the report.
    """
    if value is None:
        return None
    v = str(value).strip()
    if _HEX8.match(v + " ") or (v.startswith("#") and len(v) == 9):
        normalized.append(role)
        return "#" + v[1:7].lower()
    if _HEX6.match(v + " ") or (v.startswith("#") and len(v) == 7):
        return v.lower()
    # tolerantly accept a bare 6/8-hex without '#'
    if len(v) in (6, 8) and re.fullmatch(r"[0-9a-fA-F]+", v):
        normalized.append(role) if len(v) == 8 else None
        return ("#" + (v[:6] if len(v) == 8 else v)).lower()
    # anything else: pass through unchanged; Palette validation will reject it
    return v.lower()


def _palette_from_roles(
    name: str, label: str, roles_map: dict, source_url: str, source_note: str
) -> tuple[Palette, tuple[str, ...]]:
    """Build a Palette from a ``{role: hex|null}`` map, normalising alpha hex.

    Returns the palette and the tuple of roles whose value was alpha-stripped.
    """
    normalized: list[str] = []
    colors: dict[str, str] = {}
    for role, val in (roles_map or {}).items():
        hx = _normalize_role_hex(val, role, normalized)
        if hx:
            colors[role] = hx
    pal = Palette(
        name=name,
        variant=label,
        colors=colors,
        source="hex",
        note=source_note,
        meta={
            "source_url": source_url,
            "reference_label": label,
            "candidate": False,
        },
    )
    return pal, tuple(normalized)


def load_reference_file(path: str | Path) -> list[ReferenceVariant]:
    """Load every variant block present in one reference YAML file.

    The dark ``roles:`` block is always primary.  Sibling ``roles_light:``
    blocks (Solarized) and nested light blocks such as ``dawn:`` (Rose Pine)
    are also loaded and marked non-primary, so their existence is visible --
    but they are NOT part of the consistent six-way comparison (mixing
    polarities would be a category error).
    """
    p = Path(path)
    data = yaml.safe_load(p.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")

    name = str(data.get("name", p.stem))
    source_url = str(data.get("source_url", "") or "")
    # the top-level fetched_note documents provenance/ambiguity
    source_note = str(data.get("fetched_note", "") or "").strip()
    primary_label = str(data.get("variant", "dark") or "dark").lower()

    variants: list[ReferenceVariant] = []
    extra_labels: list[str] = []

    # --- primary block: top-level `roles:` --------------------------------
    if isinstance(data.get("roles"), dict):
        pal, norm = _palette_from_roles(
            name, primary_label, data["roles"], source_url, source_note
        )
        variants.append(
            ReferenceVariant(
                name=name,
                label=primary_label,
                palette=pal,
                source_url=source_url,
                source_note=source_note,
                is_primary=True,
                source_ambiguous=False,  # finalised below
                normalized_alpha_roles=norm,
                extra_variant_labels=(),  # finalised below
            )
        )

    # --- sibling `roles_light:` (Solarized convention) --------------------
    if isinstance(data.get("roles_light"), dict):
        extra_labels.append("light")
        pal, norm = _palette_from_roles(
            name + "-light", "light", data["roles_light"], source_url, source_note
        )
        variants.append(
            ReferenceVariant(
                name=name + "-light",
                label="light",
                palette=pal,
                source_url=source_url,
                source_note=source_note,
                is_primary=False,
                source_ambiguous=False,
                normalized_alpha_roles=norm,
            )
        )

    # --- nested light blocks, e.g. rose-pine `dawn:` ----------------------
    for key, val in data.items():
        if key in ("roles", "roles_light", "palette", "accent"):
            continue
        if isinstance(val, dict) and isinstance(val.get("roles"), dict):
            sub_name = str(val.get("name", f"{name}-{key}"))
            sub_label = str(val.get("variant", key) or key).lower()
            sub_url = str(val.get("source_url", source_url) or source_url)
            sub_note = str(val.get("fetched_note", "") or source_note).strip()
            extra_labels.append(sub_label)
            pal, norm = _palette_from_roles(
                sub_name, sub_label, val["roles"], sub_url, sub_note
            )
            variants.append(
                ReferenceVariant(
                    name=sub_name,
                    label=sub_label,
                    palette=pal,
                    source_url=sub_url,
                    source_note=sub_note,
                    is_primary=False,
                    source_ambiguous=False,
                    normalized_alpha_roles=norm,
                )
            )

    if not variants:
        raise ValueError(f"{path}: no `roles:` block found")

    # finalise the ambiguity flags now that we know the full variant set
    ambiguous = len(variants) > 1
    out = []
    for v in variants:
        out.append(
            ReferenceVariant(
                name=v.name,
                label=v.label,
                palette=v.palette,
                source_url=v.source_url,
                source_note=v.source_note,
                is_primary=v.is_primary,
                source_ambiguous=ambiguous,
                normalized_alpha_roles=v.normalized_alpha_roles,
                extra_variant_labels=tuple(extra_labels),
            )
        )
    return out


def load_reference_dir(dirpath: str | Path = "themes/references") -> dict[str, list[ReferenceVariant]]:
    """Load every ``*.yaml`` in a directory, keyed by file stem.

    The key is the *file stem* (e.g. ``palenight``), not the theme's display
    ``name`` (``material-palenight``), because the stem is stable and unique
    while display names collide across theme families.
    """
    d = Path(dirpath)
    out: dict[str, list[ReferenceVariant]] = {}
    for p in sorted(d.glob("*.yaml")):
        out[p.stem] = load_reference_file(p)
    return out


def primary_variant(variants: list[ReferenceVariant]) -> ReferenceVariant:
    """The variant used for the consistent comparison (the dark block)."""
    for v in variants:
        if v.is_primary:
            return v
    # fall back to a dark-labelled variant, else the first
    for v in variants:
        if v.label in _DARK_VARIANT_LABELS:
            return v
    return variants[0]


# ===========================================================================
# Small numeric helpers
# ===========================================================================


def _r(x: float | None, n: int = 6) -> float | None:
    return None if x is None else round(float(x), n)


def _stats(values: list[float]) -> dict:
    """Deterministic descriptive stats; empty-input safe."""
    if not values:
        return {"n": 0, "min": None, "median": None, "mean": None, "max": None, "spread": None}
    vals = sorted(values)
    return {
        "n": len(vals),
        "min": _r(vals[0]),
        "median": _r(statistics.median(vals)),
        "mean": _r(statistics.fmean(vals)),
        "max": _r(vals[-1]),
        "spread": _r(vals[-1] - vals[0]),
    }


def _classify_hue(L: float, C: float, h: float) -> dict:
    """OKLCH of one colour with hue suppressed when effectively achromatic."""
    meaningful = C >= ACHROMATIC_CHROMA_FLOOR
    if meaningful:
        score = _warm_cool_score(C, h)
        classification = "warm" if score > 0 else ("cool" if score < 0 else "neutral")
    else:
        classification = "achromatic"
    return {
        "L": _r(L),
        "C": _r(C),
        "h": _r(h) if meaningful else None,
        "h_meaningful": meaningful,
        "classification": classification,
        "achromatic_floor": ACHROMATIC_CHROMA_FLOOR,
    }


def _warm_cool_score(C: float, h: float) -> float:
    """Per-colour warm-ward score in [-1, +1] (unweighted).

    +1 at the warm centre (amber, 60 deg), -1 at the cool centre (azure,
    240 deg), 0 at the intermediate boundaries (150 deg / 330 deg).  See
    ``warm_cool_balance`` for the palette-level aggregation and the full
    definition.
    """
    import math

    return math.cos(math.radians(h - WARM_HUE_CENTER))


# ===========================================================================
# Per-reference analysis
# ===========================================================================


def _background_section(palette: Palette) -> dict:
    bg_roles = ("bg", "bg_elevated", "bg_overlay")
    out: dict[str, dict | None] = {}
    for role in bg_roles:
        hx = palette.get(role)
        if not hx:
            out[role] = None
            continue
        from .color import hex_to_oklch

        L, C, h = hex_to_oklch(hx)
        out[role] = {"role": role, "hex": hx, **_classify_hue(L, C, h)}
    out["note"] = (
        "Hue is suppressed (reported null, classification 'achromatic') when "
        f"OKLCH chroma C < {ACHROMATIC_CHROMA_FLOOR}, because hue angle is noise "
        "near the achromatic axis (color.oklab_to_oklch). The warm/cool "
        "classification uses the same warm/cool convention documented under "
        "warm_cool_balance."
    )
    return out


def _reading_contrast(palette: Palette, env: Environments) -> dict | None:
    fg, bg = palette.get("fg"), palette.get("bg")
    if not fg or not bg:
        return None
    rep = contrast_report(fg, bg)
    band = env.band_for_lc(abs(rep.apca))
    return {
        "pair": ["fg", "bg"],
        "fg_hex": fg,
        "bg_hex": bg,
        "wcag_ratio": _r(rep.wcag),
        "wcag_aa_body": bool(rep.wcag_aa_body),
        "wcag_aa_large": bool(rep.wcag_aa_large),
        "apca_lc": _r(rep.apca),
        "oklab_dl": _r(rep.dl),
        "apca_measured_band": band.name if band else None,
        "apca_note": (
            "APCA is independent work in progress, not a W3C Recommendation or "
            "current WCAG criterion (DESIGN.md section 7, RESEARCH.md R-11)."
        ),
    }


def _distributions(palette: Palette) -> dict:
    bg_roles = {"bg", "bg_elevated", "bg_overlay"}
    from .color import hex_to_oklch

    def collect(exclude_bg: bool):
        Ls, Cs, L_argmin, L_argmax, C_argmin, C_argmax = [], [], "", "", "", ""
        for role, hx in palette.items():
            if exclude_bg and role in bg_roles:
                continue
            L, C, _h = hex_to_oklch(hx)
            Ls.append((role, L))
            Cs.append((role, C))
        L_sorted = sorted(Ls, key=lambda kv: kv[1])
        C_sorted = sorted(Cs, key=lambda kv: kv[1])
        return {
            "lightness": {
                **_stats([L for _, L in Ls]),
                "min_role": L_sorted[0][0] if L_sorted else None,
                "max_role": L_sorted[-1][0] if L_sorted else None,
            },
            "chroma": {
                **_stats([C for _, C in Cs]),
                "min_role": C_sorted[0][0] if C_sorted else None,
                "max_role": C_sorted[-1][0] if C_sorted else None,
            },
        }

    n_all = len(palette)
    return {
        "all_roles": collect(exclude_bg=False),
        "excluding_backgrounds": collect(exclude_bg=True),
        "sample_note": (
            f"Descriptive statistics over n={n_all} mapped roles (small sample; "
            "use the spread, not the mean, as the signal). 'excluding_backgrounds' "
            "omits bg/bg_elevated/bg_overlay so the syntax+foreground distribution "
            "is visible on its own."
        ),
    }


def _constraint_section(palette: Palette, roles: RoleSpec, dists: DistanceSpec) -> dict:
    """Per-pair dE + channel breakdown for present pairs, plus coverage.

    Coverage is the fraction of *declared* constraints of each kind whose two
    roles are both mapped in this reference -- i.e. how much of the spec's
    declared structure the reference even participates in.  References are not
    candidates and are NOT bound by these thresholds; the dE values are
    descriptive.
    """
    out: dict[str, dict] = {}
    for kind in CONSTRAINT_KINDS:
        declared = [c for c in dists.constraints if c.kind == kind]
        present: list[dict] = []
        for c in declared:
            a, b = palette.get(c.a), palette.get(c.b)
            if not a or not b:
                continue
            de = delta_e_ok(a, b)
            br = breakdown(a, b)
            present.append(
                {
                    "a": c.a,
                    "b": c.b,
                    "a_hex": a,
                    "b_hex": b,
                    "de": _r(de),
                    "d_lightness": _r(br.d_lightness),
                    "d_chroma": _r(br.d_chroma),
                    "d_hue": _r(br.d_hue),
                    "dominant_channel": br.dominant_channel(),
                    "channel": c.channel,
                }
            )
        total = len(declared)
        np_ = len(present)
        out[kind] = {
            "declared_pairs": total,
            "present_pairs": np_,
            "coverage_fraction": _r(np_ / total) if total else None,
            "pairs": present,
        }
    out["note"] = (
        "Coverage = fraction of declared constraints whose two roles are both "
        "mapped in this reference. References are NOT candidate palettes and are "
        "not bound by the distance thresholds; the dE values are descriptive. "
        "Low coverage reflects mapping incompleteness, not a theme defect."
    )
    return out


def warm_cool_balance(palette: Palette, roles: RoleSpec) -> dict:
    """Explicit, chroma-weighted warm/cool balance over the chromatic roles.

    Definition (a convention on OKLCH hue, not a perceptual law):

    * A role is **chromatic** if its OKLCH chroma ``C >= ACHROMATIC_CHROMA_FLOOR``
      (0.02).  Near-achromatic roles -- backgrounds, fg, punctuation -- are
      excluded so they cannot tilt the balance they barely participate in.
    * Each chromatic role gets a per-colour score ``cos(h - 60 deg)``: **+1** at
      the warm centre (amber, 60 deg), **-1** at the cool centre (azure,
      240 deg), **0** at the intermediate boundaries (150 deg / 330 deg).
      A role is 'warm' when its score > 0, 'cool' when < 0.
    * The palette score is the **chroma-weighted mean** of the per-role scores:
      ``sum(C_i * score_i) / sum(C_i)``.  Weighting by chroma means a faint
      role moves the needle less than a saturated one.  Range [-1, +1]:
      positive => warm-leaning palette, negative => cool-leaning.

    The 150 deg / 330 deg boundaries are genuinely intermediate hues
    (yellow-green / magenta); the choice of 60 deg as the warm centre follows
    the project's `sand`/`amber` family.  Treat the sign and magnitude as a
    coarse summary only.
    """
    from .color import hex_to_oklch

    warm, cool = [], []
    num = 0.0
    den = 0.0
    per_role = {}
    for role, hx in palette.items():
        L, C, h = hex_to_oklch(hx)
        if C < ACHROMATIC_CHROMA_FLOOR:
            continue
        s = _warm_cool_score(C, h)
        per_role[role] = {"hex": hx, "C": _r(C), "h": _r(h), "score": _r(s)}
        num += C * s
        den += C
        (warm if s > 0 else cool).append(role)
    score = num / den if den > 0 else 0.0
    return {
        "definition": (
            "Palette score = sum(C_i * cos(h_i - 60deg)) / sum(C_i) over chromatic "
            "roles (C >= 0.02). +1 warm (amber), -1 cool (azure), 0 at 150/330 deg. "
            "A convention on OKLCH hue, not a perceptual law."
        ),
        "warm_hue_center_deg": WARM_HUE_CENTER,
        "achromatic_floor": ACHROMATIC_CHROMA_FLOOR,
        "chroma_weighted_score": _r(score),
        "n_chromatic_roles": len(per_role),
        "n_warm_roles": len(warm),
        "n_cool_roles": len(cool),
        "warm_roles": sorted(warm),
        "cool_roles": sorted(cool),
        "per_role": {k: per_role[k] for k in sorted(per_role)},
        "note": (
            "Sign/magnitude are a coarse summary. Boundaries at 150/330 deg are "
            "genuinely intermediate. Roles below the chroma floor (most backgrounds "
            "and near-neutral foregrounds) are excluded; a barely-chromatic surface "
            "contributes negligibly because the score is chroma-weighted."
        ),
    }


def _spectral_section(palette: Palette, display: str = "led-lcd") -> dict | None:
    """Nominal area-weighted melanopic output, exploratory only.

    Decomposes the screen melanopic budget into background / foreground /
    other-token shares -- the 'background-vs-token contribution' axis.  The
    caveat that an sRGB triple does not determine a spectral power
    distribution is carried verbatim (RESEARCH.md R-4, R-5, R-13).
    """
    if "bg" not in palette:
        return None
    try:
        cov = coverage_model(palette, "code")
    except ValueError:
        return {"error": "coverage model could not be built (no bg or unknown kind)"}
    disp = DISPLAYS[display]() if display in DISPLAYS else led_lcd()
    res = screen_melanopic(cov, disp)

    bg_hexes = {
        palette.get(r) for r in ("bg", "bg_elevated", "bg_overlay") if palette.get(r)
    }
    fg_hex = palette.get("fg")
    bg_share = sum(res.contributions.get(h, 0.0) for h in bg_hexes)
    fg_share = res.contributions.get(fg_hex, 0.0) if fg_hex else 0.0
    token_share = max(0.0, 1.0 - bg_share - fg_share)

    return {
        "display": display,
        "coverage_kind": "code",
        "photopic_relative": _r(res.photopic),
        "melanopic_relative": _r(res.melanopic),
        "melanopic_ratio": _r(res.mel_ratio),
        "background_share": _r(bg_share),
        "foreground_share": _r(fg_share),
        "token_share": _r(token_share),
        "top_melanopic_contributors": [
            {"hex": hx, "share": _r(s)} for hx, s in res.top_contributors(8)
        ],
        "caveat": (
            "Exploratory nominal-display model; within-model ranking only. An sRGB "
            "triple does not determine a spectral power distribution; emitted "
            "contribution depends on linear channel drive and assumed primary "
            "spectra, not area alone. This never claims actual retinal exposure "
            "(RESEARCH.md R-4, R-5, R-13, M-1)."
        ),
    }


def _cvd_section(palette: Palette, dists: DistanceSpec) -> dict:
    floor = float(
        dists.thresholds.get("must_distinguish", {}).get("cvd_dichromat", _DEFAULT_CVD_FLOOR)
    )
    pairs_out: list[dict] = []
    n_collapse = 0
    for c in dists.of_kind("must_distinguish"):
        a, b = palette.get(c.a), palette.get(c.b)
        if not a or not b:
            continue
        normal = delta_e_ok(a, b)
        per_kind = {}
        below = False
        for kind in CVD_TYPES:
            de = delta_e_ok(simulate(a, kind, 1.0), simulate(b, kind, 1.0))
            per_kind[kind] = _r(de)
            if de < floor:
                below = True
        if below:
            n_collapse += 1
        pairs_out.append(
            {
                "a": c.a,
                "b": c.b,
                "normal_de": _r(normal),
                "cvd_dichromat_de": per_kind,
                "cvd_floor": _r(floor),
                "collapses_below_floor": below,
                "redundant_channel": False,  # references declare no redundant channels
            }
        )
    return {
        "n_must_distinguish_pairs_present": len(pairs_out),
        "n_pairs_collapsing_below_floor": n_collapse,
        "cvd_floor": _r(floor),
        "pairs": pairs_out,
        "note": (
            "Dichromacy via Brettel 1997 (population-average models); they detect "
            "collapse, they do not reproduce an individual's experience (R-9). "
            "References are NOT bound by D-3 and declare no redundant channels; a "
            "collapse here is informational, not a compliance failure."
        ),
    }


def analyze_reference(
    variant: ReferenceVariant,
    roles: RoleSpec,
    dists: DistanceSpec,
    env: Environments,
    *,
    display: str = "led-lcd",
) -> dict:
    """Build the full quantitative analysis dict for one reference variant.

    Deterministic in its inputs: no wall-clock, sorted iteration, fixed
    rounding.  The same (file, specs) always yields a byte-identical dict.
    """
    palette = variant.palette
    spec_names = set(roles.roles)
    present = [r for r in palette.roles() if r in spec_names]
    extra = [r for r in palette.roles() if r not in spec_names]
    missing = sorted(spec_names - set(palette.roles()))

    return {
        "schema": "grotto.reference-analysis",
        "schema_version": VERSION,
        "reference": {
            "name": variant.name,
            "label": variant.label,
            "file_stem": variant.palette.meta.get("source_path", ""),
            "source_url": variant.source_url,
            "source_note": variant.source_note,
            "is_primary": variant.is_primary,
            "source_ambiguous": variant.source_ambiguous,
            "extra_variant_labels": list(variant.extra_variant_labels),
            "normalized_alpha_roles": list(variant.normalized_alpha_roles),
            "roles_present_count": len(present),
            "roles_missing_count": len(missing),
            "roles_missing": missing,
            "roles_not_in_spec": sorted(extra),
            "mapping_completeness": {
                "present": len(present),
                "total_spec_roles": len(spec_names),
                "fraction": _r(len(present) / len(spec_names)) if spec_names else None,
            },
        },
        "background": _background_section(palette),
        "reading_contrast": _reading_contrast(palette, env),
        "distributions": _distributions(palette),
        "constraints": _constraint_section(palette, roles, dists),
        "warm_cool_balance": warm_cool_balance(palette, roles),
        "spectral": _spectral_section(palette, display=display),
        "cvd": _cvd_section(palette, dists),
        "caveats": [
            "Descriptive only. No ranking, scoring, or winner is declared "
            "(DESIGN.md section 1: no evidence selects one syntax palette over another).",
            "APCA is independent work in progress, not a W3C Recommendation or "
            "current WCAG criterion (R-11).",
            "CVD figures use population-average dichromat models (R-9).",
            "Spectral figures are nominal-display, within-model, exploratory; "
            "they never claim retinal exposure (R-4, R-5, R-13).",
        ],
    }


# ===========================================================================
# Cross-reference comparison (side by side, NOT a ranking)
# ===========================================================================

#: The scalar rows shown in the side-by-side comparison table.  Each is
#: (row_key, human label, extractor fn(analysis)->value).  Order is the column
#: order in the text/HTML table.  References are always listed in a fixed
#: (alphabetical-by-stem) order -- never ranked.


def _row(key: str, label: str, fn):
    return (key, label, fn)


def _comparison_rows():
    def bg_field(name):
        return lambda a: (a["background"].get("bg") or {}).get(name)

    rc = lambda a: a.get("reading_contrast") or {}
    dist_all = lambda a: a["distributions"]["all_roles"]
    cc = lambda a: a["constraints"]
    sp = lambda a: a.get("spectral") or {}
    wc = lambda a: a["warm_cool_balance"]
    cv = lambda a: a["cvd"]
    mc = lambda a: a["reference"]["mapping_completeness"]

    return [
        _row("bg_L", "background L", bg_field("L")),
        _row("bg_C", "background C", bg_field("C")),
        _row("bg_h", "background hue (deg, or achromatic)",
             lambda a: (lambda b: b.get("h") if b and b.get("h_meaningful") else "achromatic")(
                 a["background"].get("bg"))),
        _row("bg_class", "background classification", bg_field("classification")),
        _row("wcag_fg_bg", "fg/bg WCAG ratio", lambda a: rc(a).get("wcag_ratio")),
        _row("apca_fg_bg", "fg/bg |APCA Lc|", lambda a: _r(abs(rc(a).get("apca_lc") or 0))),
        _row("L_min", "lightness min (all roles)", lambda a: dist_all(a)["lightness"]["min"]),
        _row("L_median", "lightness median (all roles)", lambda a: dist_all(a)["lightness"]["median"]),
        _row("L_max", "lightness max (all roles)", lambda a: dist_all(a)["lightness"]["max"]),
        _row("C_min", "chroma min (all roles)", lambda a: dist_all(a)["chroma"]["min"]),
        _row("C_median", "chroma median (all roles)", lambda a: dist_all(a)["chroma"]["median"]),
        _row("C_max", "chroma max (all roles)", lambda a: dist_all(a)["chroma"]["max"]),
        _row("must_cov", "must_distinguish coverage",
             lambda a: cc(a)["must_distinguish"]["coverage_fraction"]),
        _row("should_cov", "should_distinguish coverage",
             lambda a: cc(a)["should_distinguish"]["coverage_fraction"]),
        _row("warm_cool", "warm/cool score (chroma-wtd)",
             lambda a: wc(a)["chroma_weighted_score"]),
        _row("warm_n", "warm role count", lambda a: wc(a)["n_warm_roles"]),
        _row("cool_n", "cool role count", lambda a: wc(a)["n_cool_roles"]),
        _row("mel_ratio", "melanopic ratio (nominal)",
             lambda a: sp(a).get("melanopic_ratio")),
        _row("bg_share", "bg melanopic share",
             lambda a: sp(a).get("background_share")),
        _row("fg_share", "fg melanopic share",
             lambda a: sp(a).get("foreground_share")),
        _row("token_share", "token melanopic share",
             lambda a: sp(a).get("token_share")),
        _row("cvd_collapse", "CVD must-pairs collapsing",
             lambda a: cv(a)["n_pairs_collapsing_below_floor"]),
        _row("roles_present", "roles mapped / spec",
             lambda a: f"{mc(a)['present']}/{mc(a)['total_spec_roles']}"),
    ]


def compare_references(
    analyses: dict[str, dict],
    roles: RoleSpec,
    dists: DistanceSpec,
    env: Environments,
) -> dict:
    """Side-by-side comparison dict.  ``analyses`` maps file stem -> analysis.

    References are listed in a **fixed order** (sorted by stem).  No ranking,
    no winner, no 'best'.  The comparison is a table of raw measured values
    plus explicit per-reference mapping-completeness and variant-ambiguity
    notes.
    """
    stems = sorted(analyses)
    rows = _comparison_rows()
    table = []
    for key, label, fn in rows:
        row = {"key": key, "label": label}
        for stem in stems:
            try:
                row[stem] = fn(analyses[stem])
            except (KeyError, TypeError):
                row[stem] = None
        table.append(row)

    mapping = {
        stem: {
            **analyses[stem]["reference"]["mapping_completeness"],
            "roles_missing": analyses[stem]["reference"]["roles_missing"],
            "roles_not_in_spec": analyses[stem]["reference"]["roles_not_in_spec"],
            "normalized_alpha_roles": analyses[stem]["reference"]["normalized_alpha_roles"],
        }
        for stem in stems
    }
    ambiguity = {
        stem: {
            "source_ambiguous": analyses[stem]["reference"]["source_ambiguous"],
            "extra_variant_labels": analyses[stem]["reference"]["extra_variant_labels"],
            "normalized_alpha_roles": analyses[stem]["reference"]["normalized_alpha_roles"],
            "source_url": analyses[stem]["reference"]["source_url"],
        }
        for stem in stems
    }

    return {
        "schema": "grotto.reference-comparison",
        "schema_version": VERSION,
        "references": stems,
        "ordering_note": (
            "References are listed in a fixed alphabetical-by-file-stem order. "
            "This is NOT a ranking; no winner or 'best' theme is declared "
            "(DESIGN.md section 1)."
        ),
        "comparison_basis": (
            "All metrics are computed on the dark (primary) variant of each "
            "reference, which is the only block all six share. Light/dawn "
            "variants present in some files are recorded under "
            "'variant_ambiguity' but are NOT part of this comparison (mixing "
            "polarities would be a category error)."
        ),
        "table": table,
        "mapping_completeness": mapping,
        "variant_ambiguity": ambiguity,
        "n_spec_roles": len(roles.roles),
        "caveats": [
            "Descriptive only; no ranking or winner (DESIGN.md section 1).",
            "Coverage fractions reflect mapping incompleteness, not theme quality.",
            "Spectral columns are nominal-display, within-model, exploratory (R-4, R-5, R-13).",
            "APCA is experimental (R-11); CVD uses population-average dichromat models (R-9).",
        ],
    }


# ===========================================================================
# Plain-text rendering
# ===========================================================================


def _fmt(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") or "0"
    return str(v)


def reference_text(a: dict) -> str:
    """Human-readable text report for one reference analysis."""
    ref = a["reference"]
    bg = a["background"]
    rc = a.get("reading_contrast") or {}
    dist = a["distributions"]
    wc = a["warm_cool_balance"]
    sp = a.get("spectral") or {}
    cvd = a["cvd"]
    L = []
    amb = " [file also carries: " + ", ".join(ref["extra_variant_labels"]) + "]" if ref["source_ambiguous"] else ""
    L.append(f"# {ref['name']}  ({ref['label']}){amb}")
    if ref["source_url"]:
        L.append(f"  source: {ref['source_url']}")
    L.append(
        f"  mapping: {ref['roles_present_count']}/{ref['mapping_completeness']['total_spec_roles']} "
        f"spec roles ({ref['mapping_completeness']['fraction']*100:.0f}%); "
        f"{ref['roles_missing_count']} missing"
    )
    if ref["normalized_alpha_roles"]:
        L.append(f"  alpha-normalised (8->6 hex): {', '.join(ref['normalized_alpha_roles'])}")
    L.append("")

    L.append("## background (OKLCH; hue suppressed when effectively achromatic)")
    for role in ("bg", "bg_elevated", "bg_overlay"):
        b = bg.get(role)
        if not b:
            continue
        h = f"h {b['h']:.0f}" if b["h_meaningful"] else "achromatic"
        L.append(f"  {role:12s} {b['hex']}  L{b['L']:.3f} C{b['C']:.3f} {h}  [{b['classification']}]")
    L.append("")

    if rc:
        L.append("## reading contrast (fg vs bg)")
        L.append(
            f"  WCAG {rc['wcag_ratio']:.2f} ({'AA-body' if rc['wcag_aa_body'] else 'below AA-body'} / "
            f"{'AA-large' if rc['wcag_aa_large'] else 'below AA-large'})  "
            f"|APCA Lc| {abs(rc['apca_lc']):.0f} (band {rc.get('apca_measured_band')})  "
            f"dL {rc['oklab_dl']:+.3f}"
        )
        L.append(f"  note: {rc['apca_note']}")
        L.append("")

    L.append("## lightness / chroma distributions")
    for scope in ("all_roles", "excluding_backgrounds"):
        d = dist[scope]
        ll, cc = d["lightness"], d["chroma"]
        L.append(f"  {scope}:")
        L.append(
            f"    L min {ll['min']:.3f} ({ll['min_role']})  med {ll['median']:.3f}  "
            f"max {ll['max']:.3f} ({ll['max_role']})"
        )
        L.append(
            f"    C min {cc['min']:.3f} ({cc['min_role']})  med {cc['median']:.3f}  "
            f"max {cc['max']:.3f} ({cc['max_role']})"
        )
    L.append("")

    L.append("## warm/cool balance (explicit definition)")
    L.append(f"  chroma-weighted score: {wc['chroma_weighted_score']:+.3f}  "
             f"(+ warm, - cool)")
    L.append(f"  warm roles ({wc['n_warm_roles']}): {', '.join(wc['warm_roles']) or '-'}")
    L.append(f"  cool roles ({wc['n_cool_roles']}): {', '.join(wc['cool_roles']) or '-'}")
    L.append(f"  definition: {wc['definition']}")
    L.append("")

    cs = a["constraints"]
    L.append("## declared-constraint coverage & distances")
    for kind in CONSTRAINT_KINDS:
        c = cs[kind]
        L.append(f"  {kind:20s} {c['present_pairs']}/{c['declared_pairs']} pairs "
                 f"({(c['coverage_fraction'] or 0)*100:.0f}% coverage)")
    L.append(f"  note: {cs['note']}")
    L.append("")

    if sp:
        L.append("## spectral (nominal display, exploratory)")
        L.append(f"  melanopic/photopic ratio: {sp['melanopic_ratio']:.3f}  (display white = 1.0)")
        L.append(f"  bg share {sp['background_share']*100:.1f}%  "
                 f"fg share {sp['foreground_share']*100:.1f}%  "
                 f"token share {sp['token_share']*100:.1f}%")
        L.append(f"  caveat: {sp['caveat']}")
        L.append("")

    L.append("## CVD behaviour (must_distinguish pairs present)")
    L.append(f"  {cvd['n_pairs_collapsing_below_floor']}/{cvd['n_must_distinguish_pairs_present']} "
             f"pairs collapse below dE {cvd['cvd_floor']} under some dichromacy")
    for pr in cvd["pairs"][:8]:
        flag = "  <-- collapses" if pr["collapses_below_floor"] else ""
        L.append(
            f"  {pr['a']}/{pr['b']}: normal {pr['normal_de']:.3f} | "
            f"protan {pr['cvd_dichromat_de']['protan']:.3f} "
            f"deutan {pr['cvd_dichromat_de']['deutan']:.3f} "
            f"tritan {pr['cvd_dichromat_de']['tritan']:.3f}{flag}"
        )
    L.append(f"  note: {cvd['note']}")
    L.append("")

    L.append("## caveats")
    for c in a["caveats"]:
        L.append(f"  - {c}")
    return "\n".join(L) + "\n"


def comparison_text(c: dict) -> str:
    """Human-readable side-by-side comparison (fixed order, NOT a ranking)."""
    stems = c["references"]
    rows = c["table"]
    L = ["# Reference theme comparison (descriptive; NOT a ranking)", ""]
    L.append(c["ordering_note"])
    L.append("")
    L.append(c["comparison_basis"])
    L.append("")

    # column width from the widest reference stem
    cw = max([len(s) for s in stems] + [6])
    label_w = max(len(r["label"]) for r in rows) + 2
    header = f"  {'metric'.ljust(label_w)}" + "".join(s.rjust(cw + 2) for s in stems)
    L.append(header)
    L.append("  " + "-" * (len(header) - 2))
    for r in rows:
        cells = "".join(_fmt(r.get(s)).rjust(cw + 2) for s in stems)
        L.append(f"  {r['label'].ljust(label_w)}{cells}")
    L.append("")

    L.append("## mapping completeness (roles mapped vs spec)")
    L.append(f"  spec declares {c['n_spec_roles']} roles")
    for s in stems:
        m = c["mapping_completeness"][s]
        miss = ", ".join(m["roles_missing"][:8])
        more = f", +{len(m['roles_missing'])-8} more" if len(m["roles_missing"]) > 8 else ""
        L.append(f"  {s:{cw}}  {m['present']}/{m['total_spec_roles']} mapped; "
                 f"missing: {miss}{more}")
    L.append("")

    L.append("## variant / source ambiguity")
    for s in stems:
        amb = c["variant_ambiguity"][s]
        extras = ", ".join(amb["extra_variant_labels"]) or "none"
        norm = ", ".join(amb["normalized_alpha_roles"]) or "none"
        L.append(f"  {s:{cw}}  extra variants: {extras}; alpha-normalised roles: {norm}")
    L.append("")

    L.append("## caveats")
    for cv in c["caveats"]:
        L.append(f"  - {cv}")
    return "\n".join(L) + "\n"


def esc(s) -> str:
    """HTML-escape helper (kept here so text renderers share one definition)."""
    from html import escape

    return escape(str(s), quote=True)
