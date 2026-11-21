"""Permutation + rotation search: is the family->role assignment privileged?

Motivation: the anchor ANGLES were searched (anchor_search.py), but two larger
design choices were never tested:
  1. the family->role assignment -- which of {violet, sage, teal, azure} serves
     keyword / string / function / type.  roles.yaml gives weak reasons
     (keyword violet "rather than red" to avoid diagnostics), but the specific
     mapping is design judgement -- "vibed".
  2. the angular POSITION of the whole layout -- including whether an even
     spread (the classic categorical-palette seed) works better than the
     hand-chosen angles.

What stays PINNED, deliberately (learned conventions with relearning cost the
instruments cannot measure): rose -> error/breakpoint/diff_removed/builtin,
sand -> warning/number/constant/decorator, comments warm-neutral, variables
neutral.  namespace follows type (same_family(type, namespace) in the distance
matrix); tag and info follow azure (binding-level associations).

Combos explored, per base binding:
  * the 24 permutations of the four movable families over the four shape
    roles, at the base anchors;
  * each permutation under an EVEN-SPREAD seed (four families at 90-degree
    spacing) rotated by offsets 0..324 in 36-degree steps -- "different seed
    colors" and "rotate the colors", literally.
All combos pass the same hard gates as anchor_search (stability ok, WCAG ok,
distance errors <= base) and are scored on the same three objectives.  Each
result also carries LEARNED-CONVENTION flags (string-green? function-blue?
keyword-purple?) -- objective score and familiarity are reported side by side,
never merged.

NON-CANDIDATE exploration.  Usage:
    uv run python scripts/permute_search.py --base candidate-b-balanced \
        --out out/permute-search --refine 6 --refine-n 60 --vscode-preview 3
"""

from __future__ import annotations

import argparse
import itertools
import json
import random
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from anchor_search import (  # noqa: E402
    CHROMATIC_ROLES,
    PAIRS,
    VARIANTS,
    WEIGHTS,
    load_spec,
    n_errors,
    render_specimen_html,
    score_family,
    write_vscode_preview,
)
from grotto.model import CandidateBinding, build_family  # noqa: E402

SHAPE_ROLES = ("keyword", "string", "function", "type")
MOVABLE_FAMILIES = ("violet", "sage", "teal", "azure")

#: learned conventions worth flagging (hue windows in OKLCH degrees).  These
#: are NOT scored -- they are reported so a human can weigh familiarity
#: against the objective metrics.
CONVENTIONS = {
    "string_green": ("string", 95, 165),
    "function_blue_cyan": ("function", 180, 265),
    "keyword_purple": ("keyword", 275, 335),
}


def even_spread(offset: float) -> dict[str, float]:
    """Four families 90 degrees apart -- the classic categorical seed."""
    order = ("violet", "teal", "azure", "sage")
    return {fam: round((offset + i * 90.0) % 360.0, 1) for i, fam in enumerate(order)}


def permuted_binding(base: CandidateBinding, perm: dict[str, str],
                     angles: dict[str, float]) -> CandidateBinding:
    """A binding copy where the four shape roles read the permuted families at
    the given angles.  namespace follows type (same_family constraint); the
    binding's own role_overrides (comment/property/tag in B and C) stand."""
    overrides = dict(base.role_overrides)
    for role, fam in perm.items():
        overrides[role] = {"family": fam}
    overrides["namespace"] = {"family": perm["type"]}
    anchors = {
        fam: replace(a, h=round(angles.get(fam, a.h), 1))
        for fam, a in base.anchors.items()
    }
    return replace(base, anchors=anchors, role_overrides=overrides)


def convention_flags(fb) -> list[str]:
    """Which learned syntax conventions this family build keeps."""
    kept = []
    night = fb.variants["night"].palette
    for name, (role, lo, hi) in CONVENTIONS.items():
        L, C, h = night.oklch(role)
        kept.append(f"{name}={'yes' if lo <= h <= hi else 'NO'}")
    return kept


def run(base_name: str, refine: int, refine_n: int, seed: int) -> dict:
    spec = load_spec()
    base_binding = CandidateBinding.load(REPO / "spec/bindings" / f"{base_name}.yaml")
    base_fb = build_family(base_binding, spec)
    base_errors = n_errors(base_fb)
    base_score = score_family(base_fb)

    combos = []
    # (a) all permutations at the base anchors
    for perm_tuple in itertools.permutations(MOVABLE_FAMILIES):
        perm = dict(zip(SHAPE_ROLES, perm_tuple))
        combos.append((perm, {f: base_binding.anchors[f].h for f in MOVABLE_FAMILIES},
                       "base-angles"))
    # (b) all permutations under rotated even-spread seeds
    for perm_tuple in itertools.permutations(MOVABLE_FAMILIES):
        perm = dict(zip(SHAPE_ROLES, perm_tuple))
        for off in range(0, 360, 36):
            combos.append((perm, even_spread(float(off)), f"even+{off:03d}"))

    results = [{
        "id": "base",
        "perm": {r: r if r in ("keyword", "string", "function", "type") else r for r in SHAPE_ROLES},
        "angles": {f: base_binding.anchors[f].h for f in MOVABLE_FAMILIES},
        "seed": "committed",
        **{k: base_score[k] for k in ("min_hue", "mean_hue", "night_chroma", "cvd_safe")},
        "errors": base_errors,
        "conventions": convention_flags(base_fb),
        "is_base": True,
    }]

    built = 0
    for perm, angles, seed_name in combos:
        try:
            fb = build_family(permuted_binding(base_binding, perm, angles), spec)
        except Exception:
            continue
        built += 1
        if not fb.ok or not fb.stability["ok"]:
            continue
        if n_errors(fb) > base_errors:
            continue
        sc = score_family(fb)
        results.append({
            "id": f"p{len(results):03d}",
            "perm": dict(perm),
            "angles": {f: round(angles[f], 1) for f in MOVABLE_FAMILIES},
            "seed": seed_name,
            **{k: sc[k] for k in ("min_hue", "mean_hue", "night_chroma", "cvd_safe")},
            "errors": n_errors(fb),
            "conventions": convention_flags(fb),
            "is_base": False,
        })

    # local refinement around the best combos: perturb angles within +-18 deg
    rng = random.Random(seed)
    for key in WEIGHTS:
        lo = min(r[key] for r in results)
        hi = max(r[key] for r in results)
        for r in results:
            r[f"{key}_n"] = (r[key] - lo) / (hi - lo) if hi > lo else 0.5
    for r in results:
        r["score"] = round(sum(WEIGHTS[k] * r[f"{k}_n"] for k in WEIGHTS), 4)
    results.sort(key=lambda r: (-r["score"], r["id"]))

    refined = 0
    for entry in [r for r in results if not r["is_base"]][:refine]:
        best = entry
        for _ in range(refine_n):
            angles = {
                f: round((entry["angles"][f] + rng.uniform(-18, 18)) % 360.0, 1)
                for f in MOVABLE_FAMILIES
            }
            try:
                fb = build_family(permuted_binding(base_binding, entry["perm"], angles), spec)
            except Exception:
                continue
            if not fb.ok or not fb.stability["ok"] or n_errors(fb) > base_errors:
                continue
            sc = score_family(fb)
            # accept if better on the same composite (recompute norms lazily:
            # compare on raw min-max of the three keys among {entry, cand})
            better = (
                sc["min_hue"] > best["min_hue"] and sc["cvd_safe"] >= best["cvd_safe"] - 0.002
            ) or (
                sc["cvd_safe"] > best["cvd_safe"] + 0.002 and sc["min_hue"] >= best["min_hue"] - 0.002
            )
            if better:
                best = {**entry, "angles": angles,
                        **{k: sc[k] for k in ("min_hue", "mean_hue", "night_chroma", "cvd_safe")},
                        "conventions": convention_flags(fb), "seed": entry["seed"] + "+refined"}
        if best is not entry:
            entry.update(best)
            entry["refined"] = True
            refined += 1

    # final composite over the final values
    for key in WEIGHTS:
        lo = min(r[key] for r in results)
        hi = max(r[key] for r in results)
        for r in results:
            r[f"{key}_n"] = (r[key] - lo) / (hi - lo) if hi > lo else 0.5
    for r in results:
        r["score"] = round(sum(WEIGHTS[k] * r[f"{k}_n"] for k in WEIGHTS), 4)
    results.sort(key=lambda r: (-r["score"], r["id"]))
    return {"results": results, "built": built, "base_fb": base_fb,
            "base_binding": base_binding, "spec": spec, "refined": refined}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="candidate-b-balanced",
                    choices=["candidate-b-balanced", "candidate-c-expressive"])
    ap.add_argument("--refine", type=int, default=6)
    ap.add_argument("--refine-n", type=int, default=60)
    ap.add_argument("--seed", type=int, default=20260815)
    ap.add_argument("--vscode-preview", type=int, default=0)
    ap.add_argument("--out", default="out/permute-search")
    args = ap.parse_args()

    out = REPO / args.out / args.base
    out.mkdir(parents=True, exist_ok=True)
    print(f"[permute] base={args.base}")
    run_data = run(args.base, args.refine, args.refine_n, args.seed)
    results, base_fb = run_data["results"], run_data["base_fb"]
    payload = {
        "schema": "grotto.permute-search",
        "base": args.base,
        "seed": args.seed,
        "combos_built": run_data["built"],
        "refined": run_data["refined"],
        "weights": WEIGHTS,
        "pinned": ("rose->diagnostics, sand->literals+warning, comments warm-neutral, "
                   "variables neutral; namespace follows type, tag/info follow azure"),
        "conventions_flagged": {k: list(v) for k, v in CONVENTIONS.items()},
        "note": ("NON-CANDIDATE exploration. Objective score says nothing about "
                 "learned-convention cost; read the conventions flags beside it."),
        "results": results,
    }
    (out / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    import yaml

    (out / "results.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100))

    lines = [f"# Permutation + rotation search -- base {args.base} (NON-CANDIDATE)", ""]
    lines.append(f"combos built: {run_data['built']} (24 perms x base angles + 24 perms x 10 even-spread rotations)")
    lines.append(f"gates: stability ok, WCAG ok, distance errors <= base; refined top {args.refine} locally")
    lines.append("")
    lines.append(f"{'id':>5s} {'score':>6s} {'minHue':>7s} {'nightC':>7s} {'cvd':>6s}  "
                 f"kw/str/fn/typ families      conventions")
    for r in results[:14]:
        p = r["perm"]
        fams = "/".join(p[x][:3] for x in ("keyword", "string", "function", "type"))
        conv = " ".join(c.split("=")[1] for c in r["conventions"]).replace("NO", "!").replace("yes", ".")
        tag = " *" if r["is_base"] else ""
        lines.append(f"{r['id']:>5s} {r['score']:6.3f} {r['min_hue']:7.3f} {r['night_chroma']:7.3f} "
                     f"{r['cvd_safe']:6.3f}  {fams:26s} {conv}{tag}")
    lines.append("")
    lines.append("conventions column = string_green / function_blue_cyan / keyword_purple kept(.) or broken(!)")
    lines.append("* = committed base. Angles per result in results.json.")
    (out / "results.txt").write_text("\n".join(lines) + "\n")

    # HTML: base + top diverse entries on the R specimen (night)
    from grotto.specimens import specimen

    r_spec = specimen("r")
    shown = results[:7]
    cells = []
    for entry in shown:
        fb = build_family(
            permuted_binding(run_data["base_binding"], entry["perm"], entry["angles"]),
            run_data["spec"]) if not entry["is_base"] else base_fb
        pal = fb.variants["night"].palette
        p = entry["perm"]
        sw = "".join(
            f'<span title="{r}" style="background:{pal[r]};color:{pal["bg"]};padding:1px 7px;'
            f'margin-right:3px;border-radius:3px">{r}</span>'
            for r in ("keyword", "string", "function", "type", "number"))
        cells.append(
            f'<div class="cell"><h3>{entry["id"]}{" (base)" if entry["is_base"] else ""}</h3>'
            f'<div class="meta">score {entry["score"]:.3f} &middot; minHue {entry["min_hue"]:.3f} &middot; '
            f'cvd {entry["cvd_safe"]:.3f} &middot; seed {entry["seed"]}<br>'
            f'kw->{p["keyword"][:3]} str->{p["string"][:3]} fn->{p["function"][:3]} typ->{p["type"][:3]} &middot; '
            f'angles {entry["angles"]}<br>{", ".join(entry["conventions"])}</div>'
            f'<div style="background:{pal["bg"]};padding:6px 8px;margin:6px 0;border-radius:4px">{sw}</div>'
            f'<pre style="background:{pal["bg"]};color:{pal["fg"]};padding:10px;margin:0;'
            f'border-radius:6px;overflow:auto">{render_specimen_html(pal, r_spec)}</pre></div>')
    css = ("body{margin:0;background:#141414;color:#d8d8d8;font-family:ui-monospace,Menlo,Consolas,monospace;"
           "font-size:13px;padding:18px} h1{font-size:1.3rem} h3{margin:.2em 0 .1em} .meta{color:#999;font-size:.78rem}"
           ".cell{margin:0 0 26px} pre{line-height:1.5;font-size:12px} .banner{background:#1f212b;"
           "padding:.6em .8em;border-radius:6px;margin:.8em 0;border-left:3px solid #4a5d8a}")
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>permute search -- {args.base}</title><style>{css}</style></head><body>"
        f"<h1>Permutation + rotation search &middot; base {args.base} &middot; night</h1>"
        "<div class='banner'>NON-CANDIDATE exploration of the family->role assignment and angular "
        "position. Conventions flags show which learned associations each variant breaks; the "
        "score does NOT price familiarity.</div>" + "".join(cells) + "</body></html>")
    (out / "variants.html").write_text(html)

    print(f"[permute] built {run_data['built']}, kept {len(results)-1}, refined {run_data['refined']}")
    if args.vscode_preview:
        top = [r for r in results if not r["is_base"]][: args.vscode_preview]
        # write P-Explore themes directly (labels distinct from B/C explore sets)
        from grotto import vscode as gv

        mapping = gv._load_mapping(REPO / "spec/mappings/vscode.yaml", base_fb.spec.roles)
        ext_dir = out / "vscode-preview"
        (ext_dir / "themes").mkdir(parents=True, exist_ok=True)
        themes = []
        for i, entry in enumerate(top, 1):
            fb = build_family(
                permuted_binding(run_data["base_binding"], entry["perm"], entry["angles"]),
                run_data["spec"])
            theme = gv._build_theme(
                fb.variants["night"].palette, f"Grotto P-Explore {i:02d} Night", "night",
                mapping, source_name=f"permute-{entry['id']}", source_sha256="exploration")
            theme["grotto"]["note"] = (
                f"NON-CANDIDATE permute variant {entry['id']} "
                f"kw->{entry['perm']['keyword']} str->{entry['perm']['string']} "
                f"fn->{entry['perm']['function']} typ->{entry['perm']['type']}")
            path = f"themes/permute-{i:02d}-night.json"
            (ext_dir / path).write_text(gv._dump(theme), encoding="utf-8", newline="\n")
            themes.append({"label": f"Grotto P-Explore {i:02d} Night", "uiTheme": "vs-dark", "path": path})
        pkg = {
            "name": "grotto-permute-exploration",
            "displayName": "Grotto Permutation Exploration (NON-CANDIDATE)",
            "description": "Night themes from the permutation/rotation search; exploration only.",
            "version": "0.0.1", "publisher": "grotto-exploration",
            "engines": {"vscode": "^1.70.0"}, "categories": ["Themes"],
            "contributes": {"themes": themes},
        }
        (ext_dir / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")
        print(f"[vscode] permute extension written to {ext_dir}")


if __name__ == "__main__":
    main()
