"""Command-line interface for grotto Phase 2 evaluation tooling.

Examples
--------
  # Full audit of one palette as JSON/YAML/text + self-contained HTML/SVG
  grotto palette themes/fixtures/eval-night-full.yaml --out out/

  # Cross-variant stability report for a day/evening/night trio
  grotto stability themes/fixtures/eval-day.yaml \
      themes/fixtures/eval-evening.yaml themes/fixtures/eval-night.yaml --out out/

The CLI loads spec/roles.yaml, spec/distance-matrix.yaml and
spec/environments.yaml from the repo root (override with --roles / --distances
/ --environments).  All inputs may be evaluation fixtures or reference themes;
none are treated as candidate palettes.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .environments import Environments
from .reference_analysis import (
    VERSION as REFERENCE_VERSION,
    analyze_reference,
    compare_references,
    comparison_text,
    load_reference_dir,
    load_reference_file,
    primary_variant,
    reference_text,
)
from .report import palette_report_dict, write_report, to_json, to_yaml
from .render import (
    palette_html_report,
    palette_svg_strip,
    reference_comparison_svg,
    stability_html_report,
    reference_analysis_html,
    reference_comparison_html,
)
from .spec import DistanceSpec, Palette, RoleSpec, load
from .stability import DEFAULT_MAX_HUE_DRIFT, cross_variant_report


def _load_specs(args) -> tuple[RoleSpec, DistanceSpec, Environments]:
    roles = RoleSpec.load(args.roles)
    dists = DistanceSpec.load(args.distances, roles)
    env = Environments.load(args.environments)
    return roles, dists, env


def _stem(path: str) -> str:
    return Path(path).stem


def cmd_palette(args) -> int:
    roles, dists, env = _load_specs(args)
    palette = load(args.palette)
    report = palette_report_dict(palette, roles, dists, env, display=args.display)
    out = Path(args.out)
    stem = _stem(args.palette)
    paths = write_report(report, out, f"{stem}.report")
    # visual
    html = palette_html_report(palette, roles, dists, env)
    svg = palette_svg_strip(palette, roles)
    html_path = out / f"{stem}.html"
    svg_path = out / f"{stem}.svg"
    out.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    svg_path.write_text(svg, encoding="utf-8")
    print(f"[palette] {palette.name} ({palette.variant})")
    print(f"  colors audited : {len(palette)}")
    print(f"  distance check : {report['distance_matrix']['n_errors']} error(s), "
          f"{report['distance_matrix']['n_warnings']} warning(s)")
    if report.get("spectral") and "melanopic_ratio" in report.get("spectral", {}):
        print(f"  mel ratio      : {report['spectral']['melanopic_ratio']:.3f} "
              f"({args.display}, nominal, exploratory)")
    for kind, p in paths.items():
        print(f"  report {kind:5s}: {p}")
    print(f"  html           : {html_path}")
    print(f"  svg            : {svg_path}")
    return 0


def cmd_stability(args) -> int:
    roles, dists, env = _load_specs(args)
    variants: dict[str, Palette] = {}
    for vp in args.variants:
        pal = load(vp)
        if pal.variant not in variants:
            variants[pal.variant] = pal
        else:
            # allow explicit ordering by filename if variant names collide
            variants[_stem(vp)] = pal
    report = cross_variant_report(
        variants, roles, max_hue_drift_deg=args.max_hue_drift
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / "stability.report.json"
    html_path = out / "stability.html"
    json_path.write_text(to_json(report.to_dict()), encoding="utf-8")
    html_path.write_text(stability_html_report(report, roles), encoding="utf-8")
    print(f"[stability] variants: {', '.join(report.variants)}")
    print(f"  status               : {'PASS' if report.ok else 'ATTENTION'}")
    print(f"  drift violations     : {len(report.drift_violations)} "
          f"(threshold {report.max_hue_drift_threshold:.0f} deg)")
    print(f"  hue-order inversions : {len(report.hue_order_inversions)}")
    print(f"  chroma-rank inversions: {len(report.chroma_rank_inversions)}")
    print(f"  report json          : {json_path}")
    print(f"  html                 : {html_path}")
    return 0


def cmd_specimens(args) -> int:
    from . import specimens as S

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    for lang in S.REQUIRED_LANGUAGES:
        sp = S.specimen(lang)
        (out / sp.filename).write_text(sp.plaintext(), encoding="utf-8")
        print(f"[specimen] {sp.filename} ({sp.label}, {sp.line_count()} lines)")
    return 0


def cmd_references(args) -> int:
    """Phase 3: consistent quantitative analysis of all reference themes.

    Produces per-reference JSON/YAML/text reports and a side-by-side
    comparison (JSON/YAML/text + HTML/SVG) under ``out/references/``.
    Descriptive only; no ranking or winner is declared.
    """
    roles, dists, env = _load_specs(args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    # load every reference file; key by stem for stable ordering
    if args.references:
        loaded: dict[str, list] = {}
        for p in args.references:
            vs = load_reference_file(p)
            loaded[Path(p).stem] = vs
    else:
        loaded = load_reference_dir(args.references_dir)
    if not loaded:
        print("[references] no reference files found", file=sys.stderr)
        return 1

    analyses: dict[str, dict] = {}
    for stem in sorted(loaded):
        pv = primary_variant(loaded[stem])
        analyses[stem] = analyze_reference(pv, roles, dists, env, display=args.display)

    # --- per-reference machine + text reports ---
    for stem, a in analyses.items():
        (out / f"{stem}.json").write_text(to_json(a), encoding="utf-8")
        (out / f"{stem}.yaml").write_text(to_yaml(a), encoding="utf-8")
        (out / f"{stem}.txt").write_text(reference_text(a), encoding="utf-8")
        (out / f"{stem}.html").write_text(reference_analysis_html(a), encoding="utf-8")

    # --- side-by-side comparison ---
    comparison = compare_references(analyses, roles, dists, env)
    order = comparison["references"]
    (out / "comparison.json").write_text(to_json(comparison), encoding="utf-8")
    (out / "comparison.yaml").write_text(to_yaml(comparison), encoding="utf-8")
    (out / "comparison.txt").write_text(comparison_text(comparison), encoding="utf-8")
    (out / "comparison.html").write_text(
        reference_comparison_html(comparison, analyses), encoding="utf-8"
    )
    (out / "comparison.svg").write_text(
        reference_comparison_svg(analyses, order), encoding="utf-8"
    )

    # --- console summary (descriptive, not a ranking) ---
    print(f"[references] {len(analyses)} theme(s): {', '.join(order)}")
    print(f"  schema           : grotto.reference-analysis v{REFERENCE_VERSION}")
    for stem in order:
        a = analyses[stem]
        mc = a["reference"]["mapping_completeness"]
        bg = a["background"].get("bg") or {}
        bh = f"h{bg.get('h'):.0f}" if bg.get("h_meaningful") else "achromatic"
        wc = a["warm_cool_balance"]["chroma_weighted_score"]
        print(
            f"  {stem:11s} bg {bh} ({bg.get('classification')})  "
            f"mapped {mc['present']}/{mc['total_spec_roles']}  "
            f"warm/cool {wc:+.2f}"
        )
    print(f"  comparison (descriptive; NOT a ranking): {out / 'comparison.html'}")
    print("  outputs        : per-reference .json/.yaml/.txt/.html + "
          "comparison.{json,yaml,txt,html,svg}")
    print("  caveats        : APCA experimental; CVD population-average; "
          "spectral nominal-only (see reports).")
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="grotto", description="grotto Phase 2 evaluation tooling")
    ap.add_argument("--roles", default="spec/roles.yaml")
    ap.add_argument("--distances", default="spec/distance-matrix.yaml")
    ap.add_argument("--environments", default="spec/environments.yaml")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_pal = sub.add_parser("palette", help="audit one palette (JSON/YAML/text + HTML/SVG)")
    p_pal.add_argument("palette")
    p_pal.add_argument("--out", default="out")
    p_pal.add_argument("--display", default="led-lcd", choices=("led-lcd", "oled"))
    p_pal.set_defaults(func=cmd_palette)

    p_stab = sub.add_parser("stability", help="cross-variant stability for a variant trio")
    p_stab.add_argument("variants", nargs="+", help="day/evening/night palette files")
    p_stab.add_argument("--out", default="out")
    p_stab.add_argument("--max-hue-drift", type=float, default=DEFAULT_MAX_HUE_DRIFT)
    p_stab.set_defaults(func=cmd_stability)

    p_sp = sub.add_parser("specimens", help="write plaintext code specimens")
    p_sp.add_argument("--out", default="out/specimens")
    p_sp.set_defaults(func=cmd_specimens)

    p_ref = sub.add_parser(
        "references",
        help="consistent reference-theme analysis + comparison (Phase 3)",
    )
    p_ref.add_argument(
        "references",
        nargs="*",
        help="reference YAML files (default: all of themes/references/*.yaml)",
    )
    p_ref.add_argument("--references-dir", default="themes/references")
    p_ref.add_argument("--out", default="out/references")
    p_ref.add_argument("--display", default="led-lcd", choices=("led-lcd", "oled"))
    p_ref.set_defaults(func=cmd_references)

    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
