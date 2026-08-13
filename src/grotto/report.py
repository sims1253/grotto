"""Reproducible data reports (JSON / YAML / plain text).

A report is the machine- and human-readable audit of one palette: every role's
OKLCH/OKLab/hex/gamut, every role's contrast vs the background, the
distance-matrix violations, the CVD behaviour of every must_distinguish pair,
and the nominal spectral output.  Output is deterministic in its inputs -- no
wall-clock timestamp -- so two runs over the same palette and spec produce
byte-identical files.  A content hash of the inputs is included so a consumer
can verify provenance without trusting a timestamp.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import yaml

from .contrast import contrast_report
from .cvd import CVD_TYPES, simulate
from .distance import delta_e_ok
from .environments import Environments
from .spectral import DISPLAYS, led_lcd, screen_melanopic
from .spec import (
    DistanceSpec,
    Palette,
    RoleSpec,
    audit_palette,
    check,
    coverage_model,
    missing_roles,
)

VERSION = "phase2"


# --------------------------------------------------------------------------
# input hashing (provenance, not a timestamp)
# --------------------------------------------------------------------------


def _input_hash(palette: Palette, roles: RoleSpec, dists: DistanceSpec) -> str:
    h = hashlib.sha256()
    h.update(palette.name.encode())
    for role in sorted(palette.colors):
        h.update(f"{role}={palette.colors[role]};".encode())
    for role in sorted(roles.roles):
        r = roles.roles[role]
        h.update(f"{role}:{r.salience}:{r.family}:{r.contrast_target}:{r.cvd_priority};".encode())
    for c in dists.constraints:
        h.update(f"{c.kind}:{c.a}:{c.b};".encode())
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------
# report body
# --------------------------------------------------------------------------


def palette_report_dict(
    palette: Palette,
    roles: RoleSpec,
    dists: DistanceSpec,
    env: Environments,
    *,
    coverage_kind: str = "code",
    display: str = "led-lcd",
) -> dict:
    """Build the full audit dictionary for one palette."""
    audit = audit_palette(palette, roles)
    bg = palette.get("bg")

    # --- contrast per role ---
    contrast = {}
    if bg:
        for role, hx in palette.items():
            if role == "bg":
                continue
            rep = contrast_report(hx, bg)
            spec = roles.roles.get(role)
            target = spec.contrast_target if spec else None
            measured_band = env.band_for_lc(abs(rep.apca))
            contrast[role] = {
                "target_band": target,
                "measured_band": measured_band.name if measured_band else None,
                "band_match": (target is None) or (measured_band is not None and measured_band.name == target),
                "wcag_ratio": round(rep.wcag, 4),
                "wcag_aa_body": rep.wcag_aa_body,
                "wcag_aa_large": rep.wcag_aa_large,
                "apca_lc": round(rep.apca, 4),
                "apca_note": "independent work in progress; not a W3C Recommendation or current WCAG criterion",
                "oklab_dl": round(rep.dl, 6),
            }

    # --- distance-matrix violations ---
    violations = [
        {
            "severity": v.severity,
            "constraint": str(v.constraint),
            "condition": v.condition,
            "measured_de": round(v.measured, 6),
            "threshold_de": round(v.threshold, 6),
            "has_redundant_channel": bool(
                v.constraint.channel
                or any(
                    roles.roles.get(name)
                    and roles.roles[name].redundant_channels
                    for name in (v.constraint.a, v.constraint.b)
                )
            ),
        }
        for v in check(palette, roles, dists)
    ]

    # --- CVD on must_distinguish pairs ---
    cvd_pairs = []
    for c in dists.of_kind("must_distinguish"):
        a, b = palette.get(c.a), palette.get(c.b)
        if not a or not b:
            continue
        normal = delta_e_ok(a, b)
        per_kind = {}
        for kind in CVD_TYPES:
            per_kind[kind] = {
                "dichromat_de_1.0": round(delta_e_ok(simulate(a, kind, 1.0), simulate(b, kind, 1.0)), 6),
                "anomaly_de_0.6": round(delta_e_ok(simulate(a, kind, 0.6), simulate(b, kind, 0.6)), 6),
            }
        cvd_pairs.append({"a": c.a, "b": c.b, "normal_de": round(normal, 6), "cvd": per_kind})

    # --- spectral (exploratory) ---
    spectral = None
    if bg:
        try:
            cov = coverage_model(palette, coverage_kind)
            disp = DISPLAYS[display]() if display in DISPLAYS else led_lcd()
            res = screen_melanopic(cov, disp)
            spectral = {
                "display": display,
                "coverage_kind": coverage_kind,
                "coverage": {k: round(v, 6) for k, v in cov.items()},
                "photopic_relative": round(res.photopic, 6),
                "melanopic_relative": round(res.melanopic, 6),
                "melanopic_ratio": round(res.mel_ratio, 6),
                "top_melanopic_contributors": [
                    {"hex": hx, "share": round(s, 6)}
                    for hx, s in res.top_contributors(8)
                ],
                "caveat": (
                    "Exploratory nominal-display model; within-model ranking only. "
                    "An sRGB triple does not determine a spectral power distribution; "
                    "this never claims actual retinal exposure (RESEARCH.md R-4, R-5)."
                ),
            }
        except ValueError:
            spectral = {"error": "coverage model could not be built"}

    missing = missing_roles(palette, roles)

    return {
        "schema": "grotto.palette-report",
        "schema_version": VERSION,
        "palette": {
            "name": palette.name,
            "variant": palette.variant,
            "source": palette.source,
            "is_candidate": palette.is_candidate,
            "note": palette.note,
            "n_roles": len(palette),
        },
        "provenance": {
            "input_hash": _input_hash(palette, roles, dists),
            "roles_spec_version": roles.version,
            "distance_spec_version": dists.version,
            "environments_version": env.version,
            "missing_spec_roles": missing,
        },
        "colors": {role: audit[role].as_dict() for role in audit},
        "contrast_vs_bg": contrast,
        "distance_matrix": {
            "thresholds": dists.thresholds,
            "violations": violations,
            "n_errors": sum(1 for v in violations if v["severity"] == "error"),
            "n_warnings": sum(1 for v in violations if v["severity"] == "warning"),
            "non_goals": list(dists.non_goals),
        },
        "cvd": {
            "note": (
                "dichromacy (severity 1.0) via Brettel 1997; anomaly (severity 0.6) via "
                "Machado 2009; tritan always Brettel. Population-average dichromat models; "
                "they detect collapse, they do not reproduce an individual's experience "
                "(RESEARCH.md R-9)."
            ),
            "must_distinguish_pairs": cvd_pairs,
        },
        "spectral": spectral,
    }


# --------------------------------------------------------------------------
# serialisation
# --------------------------------------------------------------------------


def to_json(report: dict, *, indent: int = 2) -> str:
    return json.dumps(report, indent=indent, ensure_ascii=False, sort_keys=False) + "\n"


def to_yaml(report: dict) -> str:
    return yaml.safe_dump(report, sort_keys=False, allow_unicode=True, width=100)


def to_text(report: dict) -> str:
    """Human-readable plain-text summary."""
    p = report["palette"]
    prov = report["provenance"]
    dm = report["distance_matrix"]
    lines = []
    lines.append(f"# {p['name']}  ({p['variant']}, source={p['source']}, "
                 f"{'candidate' if p['is_candidate'] else 'NON-candidate'})")
    if p["note"]:
        lines.append(f"  note: {p['note'].strip()}")
    lines.append(f"  roles: {p['n_roles']} defined, {len(prov['missing_spec_roles'])} spec roles missing")
    lines.append(f"  input_hash: {prov['input_hash']}")
    lines.append("")
    lines.append("## colors (role: hex  oklch L C h  gamut)")
    for role, c in report["colors"].items():
        g = c["gamut"]
        flag = "" if g["in_srgb"] else "  <-- OUT of sRGB"
        lost = f"  (chroma_lost {c['chroma_lost']:.3f})" if c["chroma_lost"] > 1e-6 else ""
        lines.append(f"  {role:18s} {c['hex']}  L{c['oklch']['L']:.3f} C{c['oklch']['C']:.3f} "
                     f"h{c['oklch']['h']:.0f}  sRGB={'Y' if g['in_srgb'] else 'N'} P3={'Y' if g['in_p3'] else 'N'}"
                     f"{flag}{lost}")
    lines.append("")
    lines.append("## contrast vs bg (role: |Lc| WCAG DL band)")
    for role, cr in report["contrast_vs_bg"].items():
        match = "" if cr["band_match"] else "  <-- band MISMATCH"
        lines.append(f"  {role:18s} |Lc|={abs(cr['apca_lc']):5.0f}  WCAG={cr['wcag_ratio']:5.2f}  "
                     f"DL={cr['oklab_dl']:+.3f}  band={cr['measured_band']} (target {cr['target_band']})"
                     f"{'  AA-ok' if cr['wcag_aa_body'] else '  BELOW-AA'}{match}")
    lines.append("")
    lines.append(f"## distance matrix: {dm['n_errors']} error(s), {dm['n_warnings']} warning(s)")
    for v in dm["violations"]:
        lines.append(f"  [{v['severity']}] {v['constraint']} under {v['condition']}: "
                     f"dE {v['measured_de']:.3f} vs {v['threshold_de']:.3f}")
    lines.append("")
    lines.append("## CVD must_distinguish pairs (normal dE | protan deutan tritan @1.0)")
    for pair in report["cvd"]["must_distinguish_pairs"]:
        cv = pair["cvd"]
        line = (f"  {pair['a']}/{pair['b']}: {pair['normal_de']:.3f} | "
                f"{cv['protan']['dichromat_de_1.0']:.3f} "
                f"{cv['deutan']['dichromat_de_1.0']:.3f} "
                f"{cv['tritan']['dichromat_de_1.0']:.3f}")
        lines.append(line)
    if report.get("spectral") and "melanopic_ratio" in report.get("spectral", {}):
        s = report["spectral"]
        lines.append("")
        lines.append(f"## spectral (nominal {s['display']}, {s['coverage_kind']} coverage) -- exploratory")
        lines.append(f"  melanopic/photopic ratio: {s['melanopic_ratio']:.3f} (display white = 1.0)")
        for c in s["top_melanopic_contributors"][:5]:
            lines.append(f"    {c['hex']}: {c['share']*100:.1f}% of melanopic output")
        lines.append("  " + s["caveat"])
    lines.append("")
    lines.append("APCA is independent work in progress, not a W3C Recommendation or current WCAG criterion. "
                 "CVD models are population-average dichromat models (RESEARCH.md R-9).")
    return "\n".join(lines) + "\n"


def write_report(report: dict, outdir: str | Path, stem: str) -> dict[str, Path]:
    """Write JSON, YAML and text variants of a report under ``outdir``.

    Returns the map of format -> path written.
    """
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    paths = {
        "json": out / f"{stem}.json",
        "yaml": out / f"{stem}.yaml",
        "text": out / f"{stem}.txt",
    }
    paths["json"].write_text(to_json(report), encoding="utf-8")
    paths["yaml"].write_text(to_yaml(report), encoding="utf-8")
    paths["text"].write_text(to_text(report), encoding="utf-8")
    return paths
