"""Anchor-hue search: explore the binding anchor space numerically.

Motivation (first Phase-7-style install feedback): at night the co-occurring
syntax pairs -- especially function (azure) vs string (sage) vs type (teal) --
are separated mostly by LIGHTNESS, because the sRGB gamut offers little chroma
in the blue sector at high lightness and the hue channel's contribution is
bounded by realized chroma (dH ~= radians(dh) * mean_C).  The anchors are the
free semantic parameters (lightness is contrast-solved, chroma is budget-
capped), so THIS is the space to search.

What this script does
---------------------
1. Sample anchor hues for the four movable syntax families (sage/teal/azure/
   violet; sand+rose stay fixed because they anchor the diagnostics/literals
   semantics) around a committed base binding (B or C).
2. Build the full three-variant family for every sample through the REAL
   transform (build_family) -- no shortcuts.
3. Gate on the hard instruments: D-5 stability ok, WCAG ok (automatic), and
   the distance-matrix error count no worse than the base binding.
4. Score survivors on three DECLARED objectives (weights recorded in output):
   A. min hue-channel dE across the co-occurring syntax pairs x variants
      (the max-min objective huerd uses, restricted to the pairs that
      actually sit next to each other in code);
   B. mean realized chroma of the categorical roles at night (visibility
      after dark);
   C. min full dE of those pairs under protan/deutan at night (CVD safety,
      huerd's min CVD-safe distance analogue).
5. Emit deterministic artifacts: results.{json,yaml,txt}, a side-by-side HTML
   comparison page (swatches + the R specimen at night per variant), and an
   optional VS Code exploration extension with the top-K night themes.

NON-CANDIDATE: everything this script writes is exploration material.  It does
not modify the committed candidate bindings; promoting a variant is a human
decision (copy the anchor values into a binding, then regenerate).

Usage:
    uv run python scripts/anchor_search.py --base candidate-b-balanced \
        --n 360 --out out/anchor-search --top 8 --vscode-preview 3
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from dataclasses import replace
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))

from grotto.cvd import simulate  # noqa: E402
from grotto.distance import breakdown, delta_e_ok  # noqa: E402
from grotto.environments import Environments  # noqa: E402
from grotto.model import CandidateBinding, ModelSpec, build_family  # noqa: E402
from grotto.spec import DistanceSpec, RoleSpec  # noqa: E402

#: The four movable families and their sampled hue ranges.  Ordered along the
#: hue circle (sage < teal < azure < violet); sand/rose/neutral anchors stay
#: at the base binding's values (diagnostics + literal semantics are pinned).
MOVABLE = {
    "sage": (105.0, 150.0),
    "teal": (160.0, 205.0),
    "azure": (205.0, 255.0),
    "violet": (295.0, 335.0),
}

#: Co-occurring syntax pairs (they sit next to each other in real code; the
#: R specimen makes function/string/function-number adjacency ubiquitous).
PAIRS = (
    ("function", "string"),
    ("function", "type"),
    ("function", "number"),
    ("keyword", "string"),
    ("keyword", "function"),
    ("string", "number"),
    ("type", "string"),
    ("type", "number"),
)

#: Categorical roles whose night chroma feeds objective B.
CHROMATIC_ROLES = ("keyword", "string", "function", "type", "number")

#: Composite weights (declared, recorded in the output; design judgement).
WEIGHTS = {"min_hue": 0.5, "night_chroma": 0.2, "cvd_safe": 0.3}

VARIANTS = ("day", "evening", "night")


def load_spec() -> ModelSpec:
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    env = Environments.load(REPO / "spec/environments.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    return ModelSpec(roles, env, dists)


def n_errors(fb) -> int:
    return sum(1 for i in fb.issues if i.startswith("[error]"))


def score_family(fb) -> dict:
    """The three declared objectives for one built family."""
    hue_vals: dict[str, float] = {}
    for a, b in PAIRS:
        for v in VARIANTS:
            pal = fb.variants[v].palette
            hue_vals[f"{a}|{b}@{v}"] = breakdown(pal[a], pal[b]).d_hue
    night = fb.variants["night"].palette
    cvd_vals = {}
    for a, b in PAIRS:
        for kind in ("protan", "deutan"):
            ca, cb = simulate(night[a], kind, 1.0), simulate(night[b], kind, 1.0)
            cvd_vals[f"{a}|{b}@{kind}"] = delta_e_ok(ca, cb)
    return {
        "min_hue": min(hue_vals.values()),
        "mean_hue": statistics.mean(hue_vals.values()),
        "night_chroma": statistics.mean(night.oklch(r)[1] for r in CHROMATIC_ROLES),
        "cvd_safe": min(cvd_vals.values()),
        "_hue": hue_vals,
        "_cvd": cvd_vals,
    }


def anchors_of(binding: CandidateBinding, hues: dict[str, float]) -> dict:
    return {
        fam: replace(a, h=round(hues.get(fam, a.h), 2))
        for fam, a in binding.anchors.items()
    }


def search(base_name: str, n: int, seed: int) -> list[dict]:
    spec = load_spec()
    base_binding = CandidateBinding.load(REPO / "spec/bindings" / f"{base_name}.yaml")
    base_fb = build_family(base_binding, spec)
    base_errors = n_errors(base_fb)
    base_score = score_family(base_fb)
    rng = random.Random(seed)

    results = [{
        "id": "base",
        "hues": {f: base_binding.anchors[f].h for f in MOVABLE},
        **{k: base_score[k] for k in ("min_hue", "mean_hue", "night_chroma", "cvd_safe")},
        "errors": base_errors,
        "stability_ok": base_fb.stability["ok"],
        "is_base": True,
    }]

    tried = 0
    accepted = 0
    while accepted < n and tried < n * 6:
        tried += 1
        hues = {f: round(rng.uniform(lo, hi), 1) for f, (lo, hi) in MOVABLE.items()}
        # preserve the circular family order the stability checker relies on
        if not (hues["sage"] < hues["teal"] < hues["azure"] < hues["violet"]):
            continue
        try:
            fb = build_family(replace(base_binding, anchors=anchors_of(base_binding, hues)), spec)
        except Exception:
            continue
        if not fb.ok or not fb.stability["ok"]:
            continue
        if n_errors(fb) > base_errors:
            continue
        sc = score_family(fb)
        results.append({
            "id": f"v{accepted:03d}",
            "hues": hues,
            **{k: sc[k] for k in ("min_hue", "mean_hue", "night_chroma", "cvd_safe")},
            "errors": n_errors(fb),
            "stability_ok": True,
            "is_base": False,
        })
        accepted += 1

    # composite: min-max normalise each objective over accepted samples
    for key in WEIGHTS:
        lo = min(r[key] for r in results)
        hi = max(r[key] for r in results)
        for r in results:
            r[f"{key}_n"] = (r[key] - lo) / (hi - lo) if hi > lo else 0.5
    for r in results:
        r["score"] = round(sum(WEIGHTS[k] * r[f"{k}_n"] for k in WEIGHTS), 4)
    results.sort(key=lambda r: (-r["score"], r["id"]))
    return results, base_fb


def _l1(h1: dict, h2: dict) -> float:
    return sum(abs(h1[k] - h2[k]) for k in MOVABLE)


def diverse_selection(results: list[dict], k: int, min_l1: float = 25.0) -> list[dict]:
    """A comparison set, not a leaderboard: the score-sorted top of a search
    is one narrow peak (the first run shipped three variants 7 degrees apart
    in total -- 'exactly the same theme' to a human eye).  Seed with the
    per-objective champions (they sit in different regions by construction),
    then greedily add the best-scoring variant at least `min_l1` anchor
    degrees from everything already selected."""
    pool = [r for r in results if not r["is_base"]]
    selected: list[dict] = []
    champions = [
        max(pool, key=lambda r: r["min_hue"]),
        max(pool, key=lambda r: r["cvd_safe"]),
        max(pool, key=lambda r: r["night_chroma"]),
    ]
    for c in champions:
        if all(_l1(c["hues"], s_["hues"]) >= min_l1 for s_ in selected):
            selected.append(c)
    for r in sorted(pool, key=lambda r: -r["score"]):
        if len(selected) >= k:
            break
        if all(_l1(r["hues"], s_["hues"]) >= min_l1 for s_ in selected):
            selected.append(r)
    # fill remaining slots with the best available even if closer (a diverse
    # set of size 3 beats an unfilled one), then order by score for display
    if len(selected) < k:
        for r in sorted(pool, key=lambda r: -r["score"]):
            if r not in selected:
                selected.append(r)
            if len(selected) >= k:
                break
    return sorted(selected, key=lambda r: -r["score"])


def write_text(results, base_name, out: Path) -> None:
    lines = [f"# Anchor search -- base {base_name} (NON-CANDIDATE exploration)", ""]
    lines.append(f"accepted samples: {len(results) - 1} (+ base)   weights: {WEIGHTS}")
    lines.append("gates: stability ok, WCAG ok, distance errors <= base")
    lines.append("")
    lines.append(f"{'id':>5s} {'score':>6s} {'minHue':>7s} {'meanHue':>7s} {'nightC':>7s} {'cvdSafe':>7s} "
                 f"{'sage':>6s} {'teal':>6s} {'azure':>6s} {'violet':>6s}")
    for r in results[:16]:
        h = r["hues"]
        tag = " *" if r["is_base"] else ""
        lines.append(f"{r['id']:>5s} {r['score']:6.3f} {r['min_hue']:7.3f} {r['mean_hue']:7.3f} "
                     f"{r['night_chroma']:7.3f} {r['cvd_safe']:7.3f} "
                     f"{h['sage']:6.1f} {h['teal']:6.1f} {h['azure']:6.1f} {h['violet']:6.1f}{tag}")
    div = diverse_selection(results, 8)
    lines.append("")
    lines.append("## diverse comparison set (champions + min 25 deg anchor separation)")
    for r in div:
        h = r["hues"]
        lines.append(f"{r['id']:>5s} {r['score']:6.3f} {r['min_hue']:7.3f} {r['mean_hue']:7.3f} "
                     f"{r['night_chroma']:7.3f} {r['cvd_safe']:7.3f} "
                     f"{h['sage']:6.1f} {h['teal']:6.1f} {h['azure']:6.1f} {h['violet']:6.1f}")
    lines.append("")
    lines.append("* = the committed base binding. minHue = smallest hue-channel dE across")
    lines.append("  co-occurring syntax pairs x variants; nightC = mean realized chroma of")
    lines.append("  keyword/string/function/type/number at night; cvdSafe = smallest full")
    lines.append("  dE of those pairs under protan/deutan at night.")
    (out / "results.txt").write_text("\n".join(lines) + "\n")


def _esc(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))


def render_specimen_html(palette, specimen) -> str:
    out = []
    for line in specimen.lines:
        for role, text in line:
            hx = palette.get(role) or palette["fg"]
            out.append(f'<span style="color:{hx}">{_esc(text)}</span>')
        out.append("\n")
    return "".join(out)


def write_html(results, base_fb, base_name, top: int, out: Path) -> None:
    from grotto.specimens import specimen

    spec_obj = base_fb.spec
    r_spec = specimen("r")
    rows = []
    shown = diverse_selection(results, top - 1)
    # rebuild families for the entries we display
    base_binding = CandidateBinding.load(REPO / "spec/bindings" / f"{base_name}.yaml")
    cells = []
    for entry in ([r for r in results if r["is_base"]] + shown):
        if entry["is_base"]:
            fb = base_fb
        else:
            fb = build_family(replace(base_binding, anchors=anchors_of(base_binding, entry["hues"])), spec_obj)
        pal = fb.variants["night"].palette
        swatches = "".join(
            f'<span title="{r}" style="background:{pal[r]};color:{pal["bg"]};padding:1px 7px;'
            f'margin-right:3px;border-radius:3px">{r}</span>'
            for r in ("keyword", "string", "function", "type", "number")
        )
        cells.append(
            f'<div class="cell"><h3>{entry["id"]}{" (base)" if entry["is_base"] else ""}</h3>'
            f'<div class="meta">score {entry["score"]:.3f} &middot; minHue {entry["min_hue"]:.3f} &middot; '
            f'nightC {entry["night_chroma"]:.3f} &middot; cvdSafe {entry["cvd_safe"]:.3f}<br>'
            f'sage {entry["hues"]["sage"]:.0f}&deg; teal {entry["hues"]["teal"]:.0f}&deg; '
            f'azure {entry["hues"]["azure"]:.0f}&deg; violet {entry["hues"]["violet"]:.0f}&deg;</div>'
            f'<div style="background:{pal["bg"]};padding:6px 8px;margin:6px 0;border-radius:4px">{swatches}</div>'
            f'<pre style="background:{pal["bg"]};color:{pal["fg"]};padding:10px;margin:0;'
            f'border-radius:6px;overflow:auto">{render_specimen_html(pal, r_spec)}</pre></div>'
        )
    css = ("body{margin:0;background:#141414;color:#d8d8d8;font-family:ui-monospace,Menlo,Consolas,monospace;"
           "font-size:13px;padding:18px} h1{font-size:1.3rem} h3{margin:.2em 0 .1em} .meta{color:#999;font-size:.78rem}"
           ".cell{margin:0 0 26px} pre{line-height:1.5;font-size:12px} .banner{background:#1f212b;"
           "padding:.6em .8em;border-radius:6px;margin:.8em 0;border-left:3px solid #4a5d8a}")
    html = (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>anchor search -- {base_name}</title><style>{css}</style></head><body>"
        f"<h1>Anchor search &middot; base {base_name} &middot; night</h1>"
        "<div class='banner'>NON-CANDIDATE exploration of the anchor-hue space. Each panel is the "
        "R specimen under that variant's NIGHT palette; nothing here is selected or ranked as a "
        "winner beyond the declared composite (see results.txt).</div>"
        + "".join(cells) + "</body></html>"
    )
    (out / "variants.html").write_text(html)


def write_vscode_preview(results, base_fb, base_name, k: int, out: Path) -> Path:
    """A standalone extension dir with the top-K night themes for eyeballing."""
    from grotto import vscode as gv

    base_binding = CandidateBinding.load(REPO / "spec/bindings" / f"{base_name}.yaml")
    mapping = gv._load_mapping(REPO / "spec/mappings/vscode.yaml", base_fb.spec.roles)
    ext_dir = out / "vscode-preview"
    (ext_dir / "themes").mkdir(parents=True, exist_ok=True)
    prefix = "B" if "balanced" in base_name else "C"
    shown = diverse_selection(results, k)
    themes = []
    for i, entry in enumerate(shown, 1):
        fb = build_family(replace(base_binding, anchors=anchors_of(base_binding, entry["hues"])), base_fb.spec)
        theme = gv._build_theme(
            fb.variants["night"].palette, f"Grotto {prefix}-Explore {i:02d} Night", "night", mapping,
            source_name=f"anchor-search-{entry['id']}", source_sha256="exploration",
        )
        theme["grotto"]["note"] = (
            f"NON-CANDIDATE anchor-search variant {entry['id']} "
            f"(sage {entry['hues']['sage']:.0f} teal {entry['hues']['teal']:.0f} "
            f"azure {entry['hues']['azure']:.0f} violet {entry['hues']['violet']:.0f})"
        )
        path = f"themes/explore-{i:02d}-night.json"
        (ext_dir / path).write_text(gv._dump(theme), encoding="utf-8", newline="\n")
        themes.append({"label": f"Grotto {prefix}-Explore {i:02d} Night", "uiTheme": "vs-dark", "path": path})
    pkg = {
        "name": f"grotto-anchor-exploration-{prefix.lower()}",
        "displayName": f"Grotto Anchor Exploration {prefix} (NON-CANDIDATE)",
        "description": "Night themes from the anchor-hue search; exploration only, no winner.",
        "version": "0.0.1",
        "publisher": "grotto-exploration",
        "engines": {"vscode": "^1.70.0"},
        "categories": ["Themes"],
        "contributes": {"themes": themes},
    }
    (ext_dir / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")
    return ext_dir


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="candidate-b-balanced",
                    choices=["candidate-b-balanced", "candidate-c-expressive"])
    ap.add_argument("--n", type=int, default=360, help="accepted samples")
    ap.add_argument("--seed", type=int, default=20260815)
    ap.add_argument("--top", type=int, default=8, help="variants on the HTML page")
    ap.add_argument("--vscode-preview", type=int, default=0, help="write top-K night themes")
    ap.add_argument("--out", default="out/anchor-search")
    args = ap.parse_args()

    out = REPO / args.out / args.base
    out.mkdir(parents=True, exist_ok=True)
    print(f"[search] base={args.base} n={args.n} seed={args.seed}")
    results, base_fb = search(args.base, args.n, args.seed)
    payload = {
        "schema": "grotto.anchor-search",
        "base": args.base,
        "seed": args.seed,
        "n_accepted": len(results) - 1,
        "weights": WEIGHTS,
        "pairs": [list(p) for p in PAIRS],
        "movable_ranges": {k: list(v) for k, v in MOVABLE.items()},
        "gates": ["ok", "stability ok", "distance errors <= base"],
        "note": "NON-CANDIDATE exploration; promotion is a human decision.",
        "results": [{k: v for k, v in r.items()} for r in results],
    }
    (out / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    import yaml

    (out / "results.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100)
    )
    write_text(results, args.base, out)
    write_html(results, base_fb, args.base, args.top, out)
    print(f"[search] accepted {len(results) - 1}; best score {results[0]['score'] if results[0]['id'] != 'base' else results[1]['score']}")
    if args.vscode_preview:
        ext = write_vscode_preview(results, base_fb, args.base, args.vscode_preview, out)
        print(f"[vscode] exploration extension written to {ext}")


if __name__ == "__main__":
    main()
