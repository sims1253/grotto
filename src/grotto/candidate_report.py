"""Phase 6 cross-candidate comparison: matrix, drift, disagreement log.

This module sits ABOVE the Phase 5 generation layer and the Phase 4 deep module.
It takes the built candidate families and produces a **comparative evaluation**
across the 3 x 3 outputs -- WITHOUT selecting, scoring, ranking, or recommending
a winner (DESIGN.md section 1).  Every metric is reported alongside its limits;
soft misses stay visible and thresholds are not massaged.

What it computes
----------------
* a compact candidate *matrix* (one row per candidate): mean realized chroma,
  nominal area-weighted melanopic ratio under BOTH display models, distance /
  CVD / legibility issue counts, max cross-variant hue drift, min WCAG.  These
  are descriptive columns, NOT a score.
* per candidate x variant: nominal area-weighted spectral for led-lcd AND oled,
  lightness/chroma distributions + realized-chroma ordering, distance-matrix and
  CVD summaries.
* cross-variant (within candidate) and cross-candidate (between candidates)
  per-role hue/chroma/lightness/dE drift.
* a declared pixel-area estimate (NOT a screenshot measurement) grouped into the
  required categories, propagated into the spectral comparison.
* a metrics-vs-visual-judgment disagreement log/template and flagged tradeoffs.

Honest framing is mandatory and repeated near the numbers: WCAG is the hard
floor; APCA is experimental; CVD models are population-average collapse
detectors; spectral numbers are nominal within-model only and are NOT retinal
exposure or a medical/circadian claim.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from typing import Iterable

from .color import hex_to_oklch
from .contrast import wcag_contrast
from .cvd import CVD_TYPES, simulate
from .distance import breakdown, delta_e_ok
from .model import FamilyBuild, ModelSpec
from .candidates import DISPLAY_MODELS
from .spec import Palette, RoleSpec, check
from .spectral import DISPLAYS, led_lcd, screen_melanopic

#: Declared estimate of each role's share of visible pixels in a typical code
#: view.  This is a DESIGN ESTIMATE, not a measurement: no pixels were
#: rasterized or counted.  It exists only to weight the nominal spectral
#: comparison honestly and to state coverage by category.  Weights are
#: normalized to sum to 1.0 before use.
DECLARED_AREA: dict[str, float] = {
    # background (dominates area; in dark variants also the largest emitter)
    "bg": 0.780, "bg_elevated": 0.040, "bg_overlay": 0.005,
    # normal foreground / structure
    "fg": 0.055, "fg_secondary": 0.008, "fg_muted": 0.004,
    "parameter": 0.004, "punctuation": 0.012, "operator": 0.003,
    # comments / prose
    "comment": 0.025, "docstring": 0.012,
    # syntax accents
    "keyword": 0.008, "string": 0.012, "number": 0.002, "constant": 0.002,
    "type": 0.004, "function": 0.006, "builtin": 0.002, "decorator": 0.001,
    "namespace": 0.002, "tag": 0.010,
    # UI chrome
    "line_number": 0.006, "line_number_active": 0.0005, "ui_inactive": 0.004,
    "focus": 0.0003, "breakpoint": 0.0002, "deprecated": 0.0002,
    # selection / highlights / diagnostics-state surfaces
    "selection": 0.004, "search_match": 0.003, "search_match_current": 0.0005,
    "active_line": 0.015, "diff_added": 0.004, "diff_removed": 0.004,
    "diff_changed": 0.001, "debug_current": 0.001,
    "info": 0.0003, "warning": 0.0003, "error": 0.0003, "success": 0.0003,
}

#: Pixel-area categories the brief requires, mapped to their member roles.
AREA_CATEGORIES: dict[str, tuple[str, ...]] = {
    "background": ("bg", "bg_elevated", "bg_overlay"),
    "normal_foreground": (
        "fg", "fg_secondary", "fg_muted", "parameter", "punctuation", "operator",
    ),
    "comments": ("comment", "docstring"),
    "syntax_accents": (
        "keyword", "string", "number", "constant", "type", "function",
        "builtin", "decorator", "namespace", "tag", "property",
    ),
    "ui_chrome": (
        "line_number", "line_number_active", "ui_inactive", "focus",
        "breakpoint", "deprecated",
    ),
    "selection_highlights": (
        "selection", "search_match", "search_match_current", "active_line",
        "diff_added", "diff_removed", "diff_changed", "debug_current",
    ),
    "diagnostics": ("error", "warning", "info", "success"),
}

#: Diagnostic / state roles shown with redundant markers in the visuals.  Every
#: one declares a redundant channel in roles.yaml (hue is never the sole carrier
#: of critical meaning).
CRITICAL_STATES = (
    "error", "warning", "info", "success",
    "diff_added", "diff_removed", "diff_changed",
    "selection", "search_match_current", "focus", "debug_current", "breakpoint",
)

#: roles whose realized chroma is too small for hue/ordering to be meaningful.
_CHROMA_FLOOR = 0.02

SPECTRAL_CAVEAT = (
    "Nominal within-model ranking ONLY. An sRGB triple does not determine a "
    "spectral power distribution; two displays at the same hex emit different "
    "spectra. This never claims actual retinal exposure or a circadian/medical "
    "effect (RESEARCH.md R-4, R-5). Coverage is a DECLARED estimate, not a "
    "screenshot measurement."
)


# ===========================================================================
# area-weighted coverage + spectral (both display models)
# ===========================================================================


def area_coverage(palette: Palette) -> dict[str, float]:
    """hex -> normalized pixel fraction from the DECLARED area estimate.

    Roles absent from the palette fold their weight into bg (the honest
    fallback), exactly like ``spec.coverage_model``.  The result sums to 1.0.
    """
    cov: dict[str, float] = {}
    orphaned = 0.0
    for role, w in DECLARED_AREA.items():
        hx = palette.get(role)
        if hx:
            cov[hx] = cov.get(hx, 0.0) + w
        else:
            orphaned += w
    bg = palette.bg
    cov[bg] = cov.get(bg, 0.0) + orphaned
    total = sum(cov.values())
    return {k: v / total for k, v in cov.items()}


def area_category_weights(palette: Palette) -> dict[str, dict]:
    """Per-category declared coverage, normalized within the palette."""
    by_cat: dict[str, float] = {}
    for cat, roles in AREA_CATEGORIES.items():
        s = 0.0
        for r in roles:
            if r in palette:
                s += DECLARED_AREA.get(r, 0.0)
        by_cat[cat] = s
    total = sum(by_cat.values()) or 1.0
    return {
        cat: {
            "declared_fraction": round(by_cat[cat], 6),
            "normalized_fraction": round(by_cat[cat] / total, 6),
            "roles_present": sorted(r for r in roles if r in palette),
            "measurement": "declared estimate; not a screenshot pixel count",
        }
        for cat, roles in AREA_CATEGORIES.items()
    }


def spectral_both_displays(palette: Palette) -> dict:
    """Area-weighted nominal spectral under BOTH display archetypes."""
    cov = area_coverage(palette)
    out: dict[str, dict] = {}
    for name in DISPLAY_MODELS:
        disp = DISPLAYS[name]()
        res = screen_melanopic(cov, disp)
        out[name] = {
            "melanopic_ratio": round(res.mel_ratio, 6),
            "photopic_relative": round(res.photopic, 6),
            "melanopic_relative": round(res.melanopic, 6),
            "top_contributors": [
                {"hex": hx, "share": round(s, 6)}
                for hx, s in res.top_contributors(6)
            ],
        }
    out["coverage_model"] = "declared area estimate (see area_category_weights)"
    out["caveat"] = SPECTRAL_CAVEAT
    return out


# ===========================================================================
# distributions + ordering
# ===========================================================================


def _percentile(xs: list[float], p: float) -> float:
    if not xs:
        return 0.0
    xs = sorted(xs)
    if len(xs) == 1:
        return xs[0]
    k = (len(xs) - 1) * p
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def _dist(xs: list[float]) -> dict:
    if not xs:
        return {"min": None, "p25": None, "median": None, "p75": None, "max": None}
    return {
        "min": round(min(xs), 6),
        "p25": round(_percentile(xs, 0.25), 6),
        "median": round(statistics.median(xs), 6),
        "p75": round(_percentile(xs, 0.75), 6),
        "max": round(max(xs), 6),
    }


def chroma_ordering(palette: Palette, roles: RoleSpec) -> list[dict]:
    """Realized-chroma rank of chromatic roles (most-coloured first)."""
    rows = []
    for r in roles:
        if r.name not in palette:
            continue
        L, C, h = hex_to_oklch(palette[r.name])
        if C >= _CHROMA_FLOOR:
            rows.append({"role": r.name, "family": r.family, "C": round(C, 6)})
    rows.sort(key=lambda x: (-x["C"], x["role"]))
    return rows


def distributions(palette: Palette, roles: RoleSpec) -> dict:
    """Lightness/chroma distributions for all roles and chromatic-only roles."""
    Ls, Cs = [], []
    Lc, Cc = [], []
    for r in roles:
        if r.name not in palette:
            continue
        L, C, h = hex_to_oklch(palette[r.name])
        Ls.append(L); Cs.append(C)
        if C >= _CHROMA_FLOOR:
            Lc.append(L); Cc.append(C)
    return {
        "all_roles": {"lightness": _dist(Ls), "chroma": _dist(Cs)},
        "chromatic_only": {"lightness": _dist(Lc), "chroma": _dist(Cc)},
        "chroma_floor": _CHROMA_FLOOR,
        "chroma_ordering": chroma_ordering(palette, roles),
    }


# ===========================================================================
# distance + CVD summaries
# ===========================================================================


def distance_summary(palette: Palette, roles: RoleSpec, spec: ModelSpec) -> dict:
    viols = check(palette, roles, spec.distances)
    errors = [v for v in viols if v.severity == "error"]
    warnings = [v for v in viols if v.severity == "warning"]
    return {
        "n_errors": len(errors),
        "n_warnings": len(warnings),
        "n_total": len(viols),
        "errors": [
            {"constraint": str(v.constraint), "condition": v.condition,
             "measured_de": round(v.measured, 6), "threshold_de": round(v.threshold, 6)}
            for v in errors
        ],
        "warnings_count_by_constraint": _tally(warnings),
    }


def _tally(viols) -> dict[str, int]:
    out: dict[str, int] = {}
    for v in viols:
        key = v.constraint.kind
        out[key] = out.get(key, 0) + 1
    return {k: out[k] for k in sorted(out)}


def cvd_summary(palette: Palette, roles: RoleSpec, spec: ModelSpec) -> dict:
    """For each must_distinguish pair present, the worst CVD retention.

    Retention = cvd_dE / normal_dE.  A pair with redundant channels is noted so
    a low retention is read as "compensated", not "failing".
    """
    pairs = []
    worst_retention = 1.0
    for c in spec.distances.of_kind("must_distinguish"):
        a, b = palette.get(c.a), palette.get(c.b)
        if not a or not b:
            continue
        normal = delta_e_ok(a, b)
        per_kind = {}
        for kind in CVD_TYPES:
            cde = delta_e_ok(simulate(a, kind, 1.0), simulate(b, kind, 1.0))
            ret = (cde / normal) if normal > 1e-9 else 1.0
            per_kind[kind] = {"dichromat_de_1.0": round(cde, 6),
                              "retention": round(ret, 6)}
            worst_retention = min(worst_retention, ret)
        redundant = bool(
            c.channel
            or any(roles[n].redundant_channels for n in (c.a, c.b) if n in roles)
        )
        pairs.append({"a": c.a, "b": c.b, "normal_de": round(normal, 6),
                      "cvd": per_kind, "redundant_channel": redundant})
    return {
        "n_pairs": len(pairs),
        "worst_retention": round(worst_retention, 6),
        "pairs": pairs,
        "note": (
            "Population-average dichromat (Brettel) models at severity 1.0. They "
            "detect collapse; they do not reproduce an individual's experience "
            "(RESEARCH.md R-9). Low retention on a pair WITH a redundant channel "
            "is compensated, not a failure."
        ),
    }


# ===========================================================================
# drift: cross-variant (within candidate) and cross-candidate (between)
# ===========================================================================


def _role_drift(hex_a: str, hex_b: str) -> dict:
    La, Ca, ha = hex_to_oklch(hex_a)
    Lb, Cb, hb = hex_to_oklch(hex_b)
    dh = abs(((ha - hb + 180.0) % 360.0) - 180.0)
    return {
        "dE": round(delta_e_ok(hex_a, hex_b), 6),
        "dL": round(La - Lb, 6),
        "dC": round(Ca - Cb, 6),
        "dH_deg": round(dh, 4),
    }


def cross_variant_drift(family: FamilyBuild, spec: ModelSpec) -> dict:
    """Per-role day<->night drift WITHIN one candidate (lightness inverts by
    design, so dE/dL are informational; hue/chroma drift are the stability
    signals)."""
    day = family.variants["day"].palette
    night = family.variants["night"].palette
    out: dict[str, dict] = {}
    for r in spec.roles:
        if r.name in day and r.name in night:
            out[r.name] = _role_drift(day[r.name], night[r.name])
    return {
        "variants": ["day", "night"],
        "note": (
            "Day<->Night inverts lightness by DESIGN, so dE/dL are informational "
            "only; the stability signal is hue/chroma drift (DESIGN.md D-5)."
        ),
        "per_role": out,
    }


def cross_candidate_drift(families: list[FamilyBuild], spec: ModelSpec,
                          variant: str = "night") -> dict:
    """Per-role drift BETWEEN candidates (pairwise A<->B<->C) at one variant.
    This is what makes the strategies' identity differences visible and is the
    place a "did candidate X change role Y's identity?" question is answered."""
    names = [f.binding.name for f in families]
    pals = {f.binding.name: f.variants[variant].palette for f in families}
    out: dict[str, dict] = {}
    for r in spec.roles:
        present = [n for n in names if r.name in pals[n]]
        if len(present) < 2:
            continue
        row: dict[str, dict] = {}
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a, b = present[i], present[j]
                row[f"{a}|{b}"] = _role_drift(pals[a][r.name], pals[b][r.name])
        out[r.name] = row
    return {"variant": variant, "candidate_pairs": [f"{names[i]}|{names[j]}"
            for i in range(len(names)) for j in range(i + 1, len(names))],
            "per_role": out}


# ===========================================================================
# candidate matrix (descriptive columns, NOT a score)
# ===========================================================================


def _mean_realized_chroma(palette: Palette, roles: RoleSpec) -> float:
    cs = [hex_to_oklch(palette[r.name])[1] for r in roles if r.name in palette]
    return statistics.mean(cs) if cs else 0.0


def _min_wcag(palette: Palette, roles: RoleSpec, spec: ModelSpec) -> float:
    """Minimum WCAG over body-text roles (the 4.5 reading baseline).  Non-text
    roles (line numbers, muted chrome) legitimately sit near the 3.0 floor, so
    they are excluded from this headline to avoid a false 'below 4.5' reading."""
    bg = palette.bg
    vals = []
    for r in roles:
        if r.name in palette and r.accessibility_floor == "body_text":
            vals.append(wcag_contrast(palette[r.name], bg))
    return min(vals) if vals else 0.0


def candidate_matrix(families: list[FamilyBuild], spec: ModelSpec) -> list[dict]:
    rows = []
    for f in families:
        night = f.variants["night"].palette
        day = f.variants["day"].palette
        spec_n = spectral_both_displays(night)
        spec_d = spectral_both_displays(day)
        n_d = distance_summary(night, spec.roles, spec)
        n_cvd = cvd_summary(night, spec.roles, spec)
        rows.append({
            "candidate": f.binding.name,
            "strategy": f.binding.meta.get("strategy"),
            "input_hash": f.input_hash,
            "ok": f.ok,
            "mean_realized_chroma_night": round(_mean_realized_chroma(night, spec.roles), 6),
            "mean_realized_chroma_day": round(_mean_realized_chroma(day, spec.roles), 6),
            "mel_ratio_led_night": spec_n["led-lcd"]["melanopic_ratio"],
            "mel_ratio_oled_night": spec_n["oled"]["melanopic_ratio"],
            "mel_ratio_led_day": spec_d["led-lcd"]["melanopic_ratio"],
            "distance_errors_night": n_d["n_errors"],
            "distance_warnings_night": n_d["n_warnings"],
            "cvd_worst_retention_night": n_cvd["worst_retention"],
            "max_hue_drift_deg": (f.stability or {}).get("max_hue_drift_deg"),
            "stability_ok": (f.stability or {}).get("ok"),
            "min_wcag_body_text_night": round(_min_wcag(night, spec.roles, spec), 4),
            "n_issues": len(f.issues),
        })
    return rows


# ===========================================================================
# disagreement log template + flagged tradeoffs
# ===========================================================================


def disagreement_log_template(families: list[FamilyBuild], spec: ModelSpec) -> dict:
    """A structured metrics-vs-visual-judgment log.  Pre-seeded with the
    EXPECTED disagreements each candidate's tradeoffs predict; the visual fields
    are left OPEN for a human reviewer (this is Phase 6 evaluation material for
    Phase 7, not a verdict)."""
    seeded = [
        {
            "id": "A-chroma-vs-flatness",
            "candidate": "candidate-a-restrained",
            "metric_signal": "lowest mean realized chroma; fewest distance errors expected near floors",
            "metric_prediction": "metrics say A is 'safe' (low attention cost)",
            "visual_question": "does A read as comfortably scannable, or as flat/indistinguishable?",
            "visual_judgment": None,
            "resolution": None,
            "status": "open",
        },
        {
            "id": "C-busyness-vs-acuity",
            "candidate": "candidate-c-expressive",
            "metric_signal": "highest mean realized chroma; higher spectral budget",
            "metric_prediction": "metrics say C is 'loudest' (highest attention cost)",
            "visual_question": "does C's accent strength aid navigation, or read as busy in call/config-dense files?",
            "visual_judgment": None,
            "resolution": None,
            "status": "open",
        },
        {
            "id": "tag-azure-vs-violet",
            "candidate": "candidate-c-expressive vs a/b",
            "metric_signal": "C moves tag to violet (dH large vs A/B's azure/neutral)",
            "metric_prediction": "cross-candidate dH on tag is large by design",
            "visual_question": "does violet tag help or hurt key-scanning in YAML/JSON?",
            "visual_judgment": None,
            "resolution": None,
            "status": "open",
        },
        {
            "id": "cvd-retention-vs-redundancy",
            "candidate": "all",
            "metric_signal": "some must_distinguish pairs show low CVD retention",
            "metric_prediction": "low retention is compensated by declared redundant channels",
            "visual_question": "do the redundant markers (underline/icon/gutter sign) actually carry the meaning under CVD?",
            "visual_judgment": None,
            "resolution": None,
            "status": "open",
        },
    ]
    return {
        "purpose": (
            "Metrics and visual judgment WILL disagree. That disagreement is a "
            "finding, not a failure. Record it here; do not resolve it by "
            "massaging a threshold (DESIGN.md section 1)."
        ),
        "entries": seeded,
        "how_to_use": (
            "For each entry, a Phase 7 reviewer fills visual_judgment and "
            "resolution. status moves open -> confirmed -> resolved."
        ),
    }


def flagged_tradeoffs(families: list[FamilyBuild], spec: ModelSpec) -> list[dict]:
    """Per-candidate tradeoffs, sourced from the binding's own meta plus the
    observed issue counts.  Flagged, not resolved."""
    out = []
    for f in families:
        n_leg = sum(1 for i in f.issues if "over " in i or "ink-on-surface" in i)
        out.append({
            "candidate": f.binding.name,
            "strategy": f.binding.meta.get("strategy"),
            "declared_tradeoffs": f.binding.meta.get("tradeoffs"),
            "declared_purpose": f.binding.meta.get("purpose"),
            "n_total_issues": len(f.issues),
            "n_legibility_issues": n_leg,
            "stability_ok": (f.stability or {}).get("ok"),
            "max_hue_drift_deg": (f.stability or {}).get("max_hue_drift_deg"),
        })
    return out


# ===========================================================================
# top-level comparison
# ===========================================================================


def compare_candidates(families: list[FamilyBuild], spec: ModelSpec) -> dict:
    """The cross-candidate comparative evaluation (Phase 6).  No score, rank, or
    recommendation is produced; candidates are listed in binding-file order."""
    per_candidate: dict[str, dict] = {}
    for f in families:
        name = f.binding.name
        per_candidate[name] = {
            "input_hash": f.input_hash,
            "ok": f.ok,
            "strategy": f.binding.meta.get("strategy"),
            "stability": f.stability,
            "cross_variant_drift": cross_variant_drift(f, spec),
            "variants": {},
        }
        for v in ("day", "evening", "night"):
            pal = f.variants[v].palette
            per_candidate[name]["variants"][v] = {
                "colors_count": len(pal),
                "distributions": distributions(pal, spec.roles),
                "distance_summary": distance_summary(pal, spec.roles, spec),
                "cvd_summary": cvd_summary(pal, spec.roles, spec),
                "spectral_both_displays": spectral_both_displays(pal),
                "area_category_weights": area_category_weights(pal),
            }
    return {
        "schema": "grotto.candidate-comparison",
        "schema_version": "phase6",
        "n_candidates": len(families),
        "candidates": [f.binding.name for f in families],
        "ordering_note": (
            "Candidates are listed in binding-file (alphabetical) order: "
            "Restrained, Balanced, Expressive. This is NOT a ranking or a "
            "recommendation (DESIGN.md section 1)."
        ),
        "area_model": {
            "categories": {c: list(r) for c, r in AREA_CATEGORIES.items()},
            "declared_weights": dict(sorted(DECLARED_AREA.items())),
            "measurement": (
                "DECLARED ESTIMATE. No pixels were rasterized or counted. "
                "Weights are normalized to 1.0 and propagated into the nominal "
                "spectral comparison; this is not a screenshot measurement."
            ),
        },
        "matrix": candidate_matrix(families, spec),
        "per_candidate": per_candidate,
        "cross_candidate_drift_night": cross_candidate_drift(families, spec, "night"),
        "disagreement_log": disagreement_log_template(families, spec),
        "tradeoffs": flagged_tradeoffs(families, spec),
        "caveats": [
            "WCAG 2.x ratios are the hard compliance floor; all candidates pass "
            "or generation fails (ok=True).",
            "APCA is independent work in progress, not a W3C Recommendation or "
            "current WCAG criterion (R-11).",
            "CVD models are population-average dichromat simulations; they detect "
            "collapse, they do not certify accessibility or reproduce an "
            "individual's experience (R-9).",
            SPECTRAL_CAVEAT,
            "Semantic-identity / distance metrics are reported as diagnostics, "
            "not as universal pass/fail thresholds; thresholds are not massaged.",
            "No aggregate score, ranking, winner, or recommendation is produced. "
            "Phase 7 (human evaluation) is the only part that tests preference.",
        ],
    }


__all__ = [
    "DECLARED_AREA",
    "AREA_CATEGORIES",
    "CRITICAL_STATES",
    "DISPLAY_MODELS",
    "SPECTRAL_CAVEAT",
    "area_coverage",
    "area_category_weights",
    "spectral_both_displays",
    "distributions",
    "chroma_ordering",
    "distance_summary",
    "cvd_summary",
    "cross_variant_drift",
    "cross_candidate_drift",
    "candidate_matrix",
    "disagreement_log_template",
    "flagged_tradeoffs",
    "compare_candidates",
    "candidate_comparison_text",
    "candidate_comparison_html",
    "candidate_family_specimens_html",
    "candidate_comparison_svg",
]


# ===========================================================================
# Renderers (self-contained HTML / SVG / text).  Data lives above; these only
# format it.  Neutral dark chrome -- a comparison page cannot adopt one
# candidate's palette because the point is to compare them.
# ===========================================================================

from html import escape as _hesc
from . import specimens as SPEC


def _esc(s) -> str:
    return _hesc(str(s), quote=True)


_VIEWS = (("normal", "Normal"), ("protan", "Protan"), ("deutan", "Deutan"), ("tritan", "Tritan"))

#: compact glyph for each declared redundant channel (critical-state markers)
_MARKER = {
    "underline_wavy": "~", "underline_dotted": ".", "gutter_icon": "\u2691",
    "gutter_sign": "\u00b1", "gutter_shape": "\u25c6", "gutter_arrow": "\u25b6",
    "lightness_offset": "L", "lightness_and_icon": "L\u2691",
    "lightness_and_gutter_sign": "L\u00b1", "border": "\u25a4",
    "strikethrough": "S\u0338", "italic": "i", "chroma_trace": "c",
}

_CSS = """
* { box-sizing:border-box; }
body { margin:0; background:#15161c; color:#d7d9e2;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:13px; line-height:1.5; padding:18px; }
h1 { font-size:1.45rem; margin:0 0 .2em; }
h2 { font-size:1.08rem; margin:1.5em 0 .5em; border-bottom:1px solid #2a2c38; padding-bottom:.2em; }
h3 { font-size:.95rem; margin:1.1em 0 .35em; color:#aeb2c6; }
.meta { color:#8b8ea0; font-size:.82rem; }
.banner { background:#1f212b; padding:.6em .8em; border-radius:6px; margin:.7em 0; border-left:3px solid #4a5d8a; }
.warn { border-left-color:#a35; }
.controls { position:sticky; top:0; background:#15161c; padding:8px 0; z-index:3; }
.controls select { background:#1f212b; color:#d7d9e2; border:1px solid #3a3c48; border-radius:4px; padding:3px 7px; }
table { border-collapse:collapse; width:100%; background:#1b1d26; border-radius:6px; overflow:hidden; margin:.4em 0; }
th,td { text-align:left; padding:5px 8px; border-bottom:1px solid #2a2c38; vertical-align:top; }
th { color:#8b8ea0; font-weight:normal; font-size:.74rem; text-transform:uppercase; letter-spacing:.04em; }
td.num,th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.specimen { background:var(--vbg,#111); color:var(--vfg,#eee); padding:8px 10px; border-radius:5px;
  margin:0; white-space:pre; overflow:auto; tab-size:2; font-size:11.5px; line-height:1.45; }
.specwrap { margin:0; }
.cap { color:#8b8ea0; font-size:.72rem; margin:2px 0 1px; }
.vhead { color:#aeb2c6; font-weight:bold; font-size:.8rem; margin:0 0 4px; }
.grid3 { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:10px; }
.diag { display:flex; flex-wrap:wrap; gap:4px; margin:4px 0; }
.chip { display:inline-flex; align-items:center; gap:3px; border-radius:3px; padding:1px 5px;
  font-size:.72rem; box-shadow:inset 0 0 0 1px rgba(255,255,255,.12); }
.mark { color:#15161c; font-weight:bold; font-size:.7rem; opacity:.85; }
.sw { display:inline-block; width:11px; height:11px; border-radius:2px;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.14); vertical-align:middle; margin-right:4px; }
.bad { color:#f88; } .ok { color:#9ad; } .flag { color:#dc8; }
.foot { color:#8b8ea0; font-size:.75rem; margin-top:2em; border-top:1px solid #2a2c38; padding-top:.6em; }
ul.caveats { margin:.3em 0; padding-left:1.2em; } ul.caveats li { margin:.25em 0; }
pre.mono { background:#1b1d26; padding:8px 10px; border-radius:5px; overflow:auto; white-space:pre-wrap; }
"""


def _doc(title: str, body: str, extra_css: str = "") -> str:
    js = ("<script>document.body.className='view-normal';"
          "function setview(v){document.body.className='view-'+v;}"
          "document.addEventListener('DOMContentLoaded',function(){"
          "var s=document.getElementById('cvd'); if(s) s.addEventListener('change',"
          "function(e){setview(e.target.value);});});</script>")
    return ("<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{_esc(title)}</title><style>{_CSS}\n{extra_css}</style></head>"
            f"<body class='view-normal'>{body}{js}</body></html>")


def _cvd_control() -> str:
    return ('<div class="controls"><label for="cvd">CVD view: </label>'
            '<select id="cvd">'
            + "".join(f'<option value="{v}">{l}</option>' for v, l in _VIEWS)
            + "</select> <span class=\"meta\">(specimens + diagnostic chips re-render "
              "under Brettel dichromacy @1.0; population-average collapse detection, "
              "not individual experience)</span></div>")


def _scoped_css(scopes: dict[str, "Palette"]) -> str:
    """Emit per-scope role colours + bg/fg vars for normal + 3 CVD views.

    Each scope is a (candidate x) variant palette; a ``body.view-X`` class swaps
    the whole view so every specimen AND every diagnostic chip re-render under
    the same simulation.  This is a coherent extension of render.py's single-
    palette CVD toggle to many palettes on one page.
    """
    parts = []
    for scope_id, pal in scopes.items():
        for view, sim_kind in _VIEWS:
            sel = f"body.view-{view} .scope-{scope_id}"
            if view != "normal":
                cols = {r: simulate(hx, view, 1.0) for r, hx in pal.colors.items()}
            else:
                cols = dict(pal.colors)
            bg = cols.get("bg", "#111")
            fg = cols.get("fg", "#eee")
            parts.append(f"{sel}{{--vbg:{bg};--vfg:{fg};}}")
            for r, hx in cols.items():
                parts.append(f"{sel} .r-{r}{{color:{hx}}}")
                parts.append(f"{sel} .surface-{r}{{background-color:{hx}}}")
    return "\n".join(parts)


def _specimen_cell(specimen, scope_id: str, palette) -> str:
    lines = []
    for line in specimen.lines:
        parts = []
        for role, text in line:
            cls = f"r-{role}" if role in palette else "r-fg"
            parts.append(f'<span class="{cls}">{_esc(text)}</span>')
        lines.append("".join(parts))
    return (f'<div class="specwrap"><pre class="specimen">'
            + "\n".join(lines) + "</pre></div>")


def _diagnostic_chips(scope_id: str, palette, roles) -> str:
    """Critical-state chips with redundant-channel markers; re-render under CVD."""
    chips = []
    for role in CRITICAL_STATES:
        hx = palette.get(role)
        if not hx:
            continue
        spec = roles.roles.get(role)
        chans = spec.redundant_channels if spec else ()
        marks = "".join(
            f'<span class="mark" title="{_esc(c)}">{_esc(_MARKER.get(c, c[0:1]))}</span>'
            for c in chans
        )
        on = "#000" if _luma(hx) > 0.42 else "#fff"
        chips.append(
            f'<span class="chip surface-{role}" style="color:{on}">{_esc(role)}{marks}</span>'
        )
    return f'<div class="diag">{"".join(chips)}</div>'


def _luma(hx: str) -> float:
    from .color import hex_to_srgb, relative_luminance
    return relative_luminance(hex_to_srgb(hx))


def _disclaimer_banner() -> str:
    return ('<div class="banner warn">CANDIDATE comparison (Phase 6). No aggregate score, '
            "ranking, winner, or recommendation is produced. Phase 7 (human evaluation) "
            "decides. WCAG floors are hard; APCA is experimental; CVD models are "
            "population-average; spectral numbers are nominal within-model only "
            "(DESIGN.md section 1, RESEARCH.md).</div>")


def candidate_family_specimens_html(family, spec) -> str:
    """Per-candidate family page: day/evening/night side by side, EVERY language
    specimen under each, plus critical-state diagnostics with redundant markers.
    CVD-toggleable (normal + protan/deutan/tritan)."""
    scopes = {v: family.variants[v].palette for v in ("day", "evening", "night")}
    css = _scoped_css(scopes)
    head = (
        f"<h1>{_esc(family.name)} &mdash; family specimens</h1>"
        f"<div class=\"meta\">strategy <b>{_esc(family.binding.meta.get('strategy'))}</b> "
        f"&middot; input_hash <b>{family.input_hash}</b> &middot; ok <b>{family.ok}</b></div>"
        + _disclaimer_banner()
        + _cvd_control()
    )
    # diagnostics across variants
    diag_rows = "".join(
        f'<div class="scope-{v}"><div class="vhead">{_esc(v)}</div>'
        f'{_diagnostic_chips(v, family.variants[v].palette, spec.roles)}</div>'
        for v in ("day", "evening", "night")
    )
    diag = ("<h2>Critical-state diagnostics (redundant markers)</h2>"
            '<div class="grid3">' + diag_rows + "</div>"
            "<p class='meta'>Each chip uses the role colour as its background and re-renders "
            "under the selected CVD view. Glyphs mark the DECLARED redundant channel(s) so a "
            "critical state never relies on hue alone (D-3).</p>")
    # every language specimen, rows=language, columns=variant
    rows = []
    for lang in SPEC.REQUIRED_LANGUAGES:
        sp = SPEC.specimen(lang)
        cells = "".join(
            f'<div class="scope-{v}"><div class="cap">{_esc(v)}</div>'
            f'{_specimen_cell(sp, v, family.variants[v].palette)}</div>'
            for v in ("day", "evening", "night")
        )
        rows.append(
            f'<h3>{_esc(sp.label)} &middot; {_esc(sp.filename)}</h3>'
            f'<div class="grid3">{cells}</div>'
        )
    body = head + diag + "<h2>Specimens (day | evening | night)</h2>" + "".join(rows)
    foot = ('<div class="foot">Generated by grotto Phase 6. Reproducible: identical '
            "inputs produce byte-identical output. Identical specimens across variants; "
            "only the palette differs.</div>")
    return _doc(f"{family.name} -- family specimens", body + foot, extra_css=css)


def _matrix_table(matrix: list[dict]) -> str:
    head = ("<tr><th>candidate</th><th>strategy</th><th class='num'>mean C night</th>"
            "<th class='num'>mean C day</th><th class='num'>mel ratio LED night</th>"
            "<th class='num'>mel ratio OLED night</th><th class='num'>dist err/warn</th>"
            "<th class='num'>CVD worst ret.</th><th class='num'>max drift&deg;</th>"
            "<th class='num'>min WCAG body</th><th class='num'>issues</th></tr>")
    rows = []
    for m in matrix:
        rows.append(
            "<tr>"
            f'<td><b>{_esc(m["candidate"])}</b></td><td>{_esc(m["strategy"])}</td>'
            f'<td class="num">{m["mean_realized_chroma_night"]:.4f}</td>'
            f'<td class="num">{m["mean_realized_chroma_day"]:.4f}</td>'
            f'<td class="num">{m["mel_ratio_led_night"]:.3f}</td>'
            f'<td class="num">{m["mel_ratio_oled_night"]:.3f}</td>'
            f'<td class="num">{m["distance_errors_night"]}/{m["distance_warnings_night"]}</td>'
            f'<td class="num">{m["cvd_worst_retention_night"]:.2f}</td>'
            f'<td class="num">{_fmt(m["max_hue_drift_deg"])}</td>'
            f'<td class="num {"ok" if m["min_wcag_body_text_night"]>=4.5 else "bad"}">{m["min_wcag_body_text_night"]:.2f}</td>'
            f'<td class="num">{m["n_issues"]}</td>'
            "</tr>"
        )
    return ("<table>" + head + "".join(rows) + "</table>"
            "<p class='meta'>Descriptive columns, NOT a score. Mean C = mean realized OKLCH chroma. "
            "Mel ratio = nominal area-weighted melanopic/photopic (display white=1.0). "
            "Dist err/warn = must/should distance-matrix violations. CVD worst ret. = smallest "
            "dE retention across must_distinguish pairs under dichromacy (low = a pair collapses; "
            "check its redundant channel). min WCAG body = lowest body-text ratio (&ge;4.5 hard).</p>")


def _fmt(v):
    return "-" if v is None else f"{v:.2f}"


def _drift_table(drift: dict, title: str, focus_roles) -> str:
    pairs = drift.get("candidate_pairs") or ["day", "night"]
    head = f"<tr><th>role</th>" + "".join(f"<th class='num'>{_esc(p)}</th>" for p in pairs) + "</tr>"
    rows = []
    for role in focus_roles:
        if role not in drift.get("per_role", {}):
            continue
        cells = ""
        for p in pairs:
            d = drift["per_role"][role].get(p)
            if not d:
                cells += '<td class="num meta">-</td>'
            else:
                cells += (f'<td class="num">dE {d["dE"]:.3f}<br>'
                          f'<span class="meta">dH {d["dH_deg"]:.0f}&deg; dC {d["dC"]:+.3f} '
                          f'dL {d["dL"]:+.3f}</span></td>')
        rows.append(f"<tr><td>{_esc(role)}</td>{cells}</tr>")
    return f"<h2>{_esc(title)}</h2><table>" + head + "".join(rows) + "</table>"


def _disagreement_block(log: dict) -> str:
    rows = []
    for e in log["entries"]:
        rows.append(
            "<tr>"
            f'<td><b>{_esc(e["id"])}</b></td><td>{_esc(e["candidate"])}</td>'
            f'<td>{_esc(e["metric_signal"])}</td>'
            f'<td class="flag">{_esc(e["visual_question"])}</td>'
            f'<td class="meta">{_esc(e["status"])}</td></tr>'
        )
    return ("<h2>Metrics-vs-visual-judgment disagreement log</h2>"
            f"<p class='meta'>{_esc(log['purpose'])}</p>"
            "<table><tr><th>id</th><th>candidate</th><th>metric signal</th>"
            "<th>open visual question (Phase 7)</th><th>status</th></tr>"
            + "".join(rows) + "</table>")


def _tradeoff_block(tradeoffs: list[dict]) -> str:
    rows = []
    for t in tradeoffs:
        rows.append(
            "<tr>"
            f'<td><b>{_esc(t["candidate"])}</b></td>'
            f'<td>{_esc(t["declared_purpose"] or "-")}</td>'
            f'<td>{_esc(t["declared_tradeoffs"] or "-")}</td>'
            f'<td class="num">{t["n_total_issues"]}</td>'
            f'<td class="num">{t["n_legibility_issues"]}</td>'
            f'<td class="num {_fmt_cls(t["stability_ok"])}">{_fmt(t["max_hue_drift_deg"])}</td></tr>'
        )
    return ("<h2>Flagged tradeoffs</h2>"
            "<table><tr><th>candidate</th><th>purpose</th><th>declared tradeoffs</th>"
            "<th class='num'>issues</th><th class='num'>legibility</th>"
            "<th class='num'>max drift&deg;</th></tr>" + "".join(rows) + "</table>")


def _fmt_cls(ok):
    return "ok" if ok else "bad"


def candidate_comparison_html(comparison: dict, families, spec) -> str:
    """Cross-candidate comparison page: matrix, drift, disagreement log,
    tradeoffs, and a side-by-side specimen strip (one language across all
    candidate x variant combos) + diagnostics comparison.  CVD-toggleable."""
    # scopes for the side-by-side strip: candidate x variant (night chosen as the
    # hardest case; day/evening are on the per-candidate family pages)
    variant = "night"
    scopes = {f"{f.binding.name}-{variant}": f.variants[variant].palette for f in families}
    css = _scoped_css(scopes)
    head = (
        "<h1>Candidate comparison (Phase 6)</h1>"
        f"<div class='meta'>{_esc(comparison['ordering_note'])}</div>"
        + _disclaimer_banner()
        + _cvd_control()
    )
    matrix = "<h2>Candidate matrix (descriptive, not a score)</h2>" + _matrix_table(comparison["matrix"])
    # cross-candidate drift on a few identity-bearing roles
    focus = [r for r in ("keyword", "function", "string", "type", "tag", "error",
                         "warning", "selection", "diff_added", "diff_removed")
             if r in comparison["cross_candidate_drift_night"].get("per_role", {})]
    xdrift = _drift_table(comparison["cross_candidate_drift_night"],
                          "Cross-candidate per-role drift (night)", focus)
    disagree = _disagreement_block(comparison["disagreement_log"])
    tradeoffs = _tradeoff_block(comparison["tradeoffs"])
    # side-by-side specimen: Python under each candidate (night)
    sp = SPEC.specimen("python")
    strip = []
    for f in families:
        sid = f"{f.binding.name}-{variant}"
        strip.append(
            f'<div class="scope-{sid}"><div class="vhead">{_esc(f.binding.meta.get("strategy"))}<br>'
            f'<span class="meta">{_esc(f.binding.name)}</span></div>'
            f'<div class="cap">{_esc(sp.label)} &middot; {_esc(variant)}</div>'
            f'{_specimen_cell(sp, sid, f.variants[variant].palette)}</div>'
        )
    specimens = ("<h2>Side-by-side specimen (Python, night) &mdash; same code, three strategies</h2>"
                 '<div class="grid3">' + "".join(strip) + "</div>")
    # diagnostics comparison (night)
    dcells = "".join(
        f'<div class="scope-{f.binding.name}-{variant}"><div class="vhead">'
        f'{_esc(f.binding.meta.get("strategy"))}</div>'
        f'{_diagnostic_chips(f"{f.binding.name}-{variant}", f.variants[variant].palette, spec.roles)}</div>'
        for f in families
    )
    diag = ("<h2>Critical-state diagnostics (night, redundant markers)</h2>"
            '<div class="grid3">' + dcells + "</div>")
    caveats = "<h2>Caveats</h2><ul class='caveats'>" + "".join(
        f"<li>{_esc(c)}</li>" for c in comparison["caveats"]) + "</ul>"
    foot = ('<div class="foot">Generated by grotto Phase 6. Reproducible: identical '
            "inputs produce byte-identical output.</div>")
    return _doc("candidate comparison -- grotto (Phase 6)",
                head + matrix + xdrift + specimens + diag + disagree + tradeoffs + caveats + foot,
                extra_css=css)


def candidate_comparison_svg(families, spec) -> str:
    """Self-contained SVG: night-variant key roles, one row per role, three
    candidate chips per row.  Deterministic; no external resources."""
    key = ("bg", "fg", "comment", "keyword", "string", "number", "type", "function",
           "tag", "error", "warning", "diff_added", "diff_removed", "selection", "focus")
    n = len(families)
    chip_w, chip_h, pad, label_w = 64, 26, 6, 130
    row_h = chip_h + pad + 6
    total_w = label_w + n * (chip_w + pad) + pad
    total_h = (len(key) + 1) * row_h + pad
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
             f'font-family="ui-monospace,monospace" font-size="10">'
             f'<rect width="100%" height="100%" fill="#15161c"/>']
    for ci, f in enumerate(families):
        cx = label_w + ci * (chip_w + pad)
        parts.append(f'<text x="{cx}" y="16" fill="#aeb2c6">{_esc(f.binding.name)}</text>')
    for ri, role in enumerate(key):
        y = (ri + 1) * row_h
        parts.append(f'<text x="{pad}" y="{y + chip_h//2 + 3}" fill="#8b8ea0">{_esc(role)}</text>')
        for ci, f in enumerate(families):
            hx = f.variants["night"].palette.get(role)
            if not hx:
                continue
            cx = label_w + ci * (chip_w + pad)
            parts.append(f'<rect x="{cx}" y="{y}" width="{chip_w}" height="{chip_h}" fill="{hx}" rx="3"/>')
            parts.append(f'<text x="{cx+3}" y="{y+chip_h-4}" fill="{_on_svg(hx)}">{_esc(hx)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _on_svg(hx: str) -> str:
    return "#15161c" if _luma(hx) > 0.42 else "#fff"


def candidate_comparison_text(comparison: dict) -> str:
    """Human-readable compact comparison summary (no ranking)."""
    lines = ["# Candidate comparison (Phase 6)", comparison["ordering_note"], ""]
    lines.append("## matrix (descriptive, not a score)")
    lines.append(f"{'candidate':26s} {'meanC_n':>8s} {'meanC_d':>8s} {'melLED':>7s} "
                 f"{'melOLED':>7s} {'dErr':>5s} {'cvdRet':>7s} {'drift':>6s} {'wcag':>6s} {'iss':>5s}")
    for m in comparison["matrix"]:
        lines.append(
            f"{m['candidate']:26s} {m['mean_realized_chroma_night']:8.4f} "
            f"{m['mean_realized_chroma_day']:8.4f} {m['mel_ratio_led_night']:7.3f} "
            f"{m['mel_ratio_oled_night']:7.3f} {m['distance_errors_night']:5d} "
            f"{m['cvd_worst_retention_night']:7.2f} {_fmt(m['max_hue_drift_deg']):>6s} "
            f"{m['min_wcag_body_text_night']:6.2f} {m['n_issues']:5d}"
        )
    lines.append("")
    lines.append("## flagged tradeoffs")
    for t in comparison["tradeoffs"]:
        lines.append(f"  {t['candidate']}: {(t['declared_tradeoffs'] or '').strip()[:90]}")
    lines.append("")
    lines.append("## disagreement log (open for Phase 7)")
    for e in comparison["disagreement_log"]["entries"]:
        lines.append(f"  [{e['id']}] {e['visual_question']}")
    lines.append("")
    for c in comparison["caveats"]:
        lines.append(f"  - {c}")
    return "\n".join(lines) + "\n"
