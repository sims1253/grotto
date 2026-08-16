"""huerd-driven night palettes: fixed semantic anchors + CVD-safe optimization.

The middle/numeric frontier experiments (scripts/middle_palette.py,
scripts/numeric_palette.py, NUMERIC.md) established the tradeoff curve.  This
pipeline answers the owner's next question: what does the NEW huerd (>=0.6.2)
produce when we pin the non-negotiable semantic anchors (canvas, error red,
warning amber -- "we can keep red for errors") and let its CVD-safe optimizer
place the free categorical roles?

Pipeline: R generation (huerd sann, cvd_safe, include_colors=pins) ->
convention-window assignment of free colors to roles -> WCAG repair ->
chroma-capped variant -> grotto-instrument evaluation -> themes.

NON-CANDIDATE exploration; nothing here is selected or ranked as a winner.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "src"))
sys.path.insert(0, str(REPO / "scripts"))

from grotto.color import hex_to_oklch, max_chroma, oklch_to_hex  # noqa: E402
from grotto.contrast import wcag_contrast  # noqa: E402
from grotto.cvd import simulate  # noqa: E402
from grotto.distance import delta_e_ok  # noqa: E402
from grotto.spec import DistanceSpec, Palette, RoleSpec, load  # noqa: E402

#: free categorical roles; assignment windows keep the learned conventions
#: (owner rejected the convention-free numeric frontier: "magenta in-your-face")
FREE_ROLES = {
    "keyword":   (275.0, 335.0),
    "string":    (95.0, 165.0),
    "function":  (180.0, 265.0),
    "type":      (160.0, 215.0),
    "namespace": (160.0, 215.0),
    "number":    (40.0, 110.0),
    "constant":  (40.0, 110.0),
    "decorator": (40.0, 110.0),
    "builtin":   (0.0, 50.0),
    "tag":       (180.0, 265.0),
}

#: roles whose colors huerd must NOT move (pinned at the committed values).
#: Two modes: "diagnostics" pins only canvas+error+warning; "anchors" also
#: pins the four syntax family anchors (keyword/string/function/type), so
#: huerd optimizes the literal/config cluster around fixed conventions --
#: a pure set-optimizer spreads hues evenly and does not guarantee coverage
#: of grotto's convention windows (verified: 10-role runs left 3-5 windows
#: empty every time).
PIN_MODES = {
    "diagnostics": ("bg", "error", "warning"),
    "anchors": ("bg", "error", "warning", "keyword", "string", "function", "type"),
}

SCAFFOLD = "themes/candidates/candidate-b-balanced.night.yaml"
SYNTAX_CAP = 0.12  # the loudness ceiling the owner's magenta feedback imposed


def _circ(a: float, b: float) -> float:
    return abs(((a - b + 180.0) % 360.0) - 180.0)


def generate(pins: list[str], n_free: int, runs: int, seed: int, iters: int) -> list[dict]:
    with tempfile.TemporaryDirectory() as td:
        pins_file = Path(td) / "pins.csv"
        pins_file.write_text("\n".join(pins) + "\n")
        out_csv = Path(td) / "gen.csv"
        subprocess.run(
            ["Rscript", str(REPO / "scripts/huerd_generate.R"), str(pins_file),
             str(n_free), str(runs), str(seed), str(iters), str(out_csv)],
            check=True, capture_output=True, text=True, cwd=REPO,
        )
        import csv

        runs_data: dict[int, list[dict]] = {}
        with open(out_csv) as fh:
            for row in csv.DictReader(fh):
                runs_data.setdefault(int(row["run"]), []).append(row)
    return [
        {
            "hexes": [r["hex"].lower() for r in rows],
            "min_dist": float(rows[0]["min_dist"]),
            "min_cvd": float(rows[0]["min_cvd_safe"]),
        }
        for _, rows in sorted(runs_data.items())
    ]


def assign(free_hexes: list[str], committed: Palette) -> tuple[dict[str, str], list[str]]:
    """Match generated colors to roles inside their convention windows.

    Greedy over hue distance to the committed role hue (windows gate
    feasibility), improved by pairwise swaps; unconstrained-color problems
    are reported rather than silently reassigned."""
    colors = [hex_to_oklch(hx) for hx in free_hexes]
    roles = list(FREE_ROLES)
    # candidate (role, color) pairs legal under the windows
    pairs = []
    for ri, role in enumerate(roles):
        target = committed.oklch(role)[2]
        for ci, (L, C, h) in enumerate(colors):
            if FREE_ROLES[role][0] <= h <= FREE_ROLES[role][1]:
                pairs.append((_circ(h, target), ri, ci))
    pairs.sort()
    role_of: dict[int, int] = {}
    color_of: dict[int, int] = {}
    for cost, ri, ci in pairs:
        if ri not in role_of and ci not in color_of:
            role_of[ri] = ci
            color_of[ci] = ri
    issues: list[str] = []
    if len(role_of) < len(roles):
        unassigned = [roles[i] for i in range(len(roles)) if i not in role_of]
        issues.append(f"unassigned roles (no in-window color): {unassigned}")

    def swap_gain():
        best = None
        for ri in role_of:
            for rj in role_of:
                if ri >= rj:
                    continue
                ci, cj = role_of[ri], role_of[rj]
                cur = _cost(ri, ci) + _cost(rj, cj)
                alt = _cost(ri, cj) + _cost(rj, ci)
                if alt < cur - 1e-9:
                    if best is None or (cur - alt) > best[0]:
                        best = (cur - alt, ri, rj)
        return best

    def _cost(ri, ci):
        role = roles[ri]
        L, C, h = colors[ci]
        target = committed.oklch(role)[2]
        if not (FREE_ROLES[role][0] <= h <= FREE_ROLES[role][1]):
            return 1e6
        return _circ(h, target)

    while True:
        g = swap_gain()
        if not g:
            break
        _, ri, rj = g
        role_of[ri], role_of[rj] = role_of[rj], role_of[ri]

    out = {roles[ri]: free_hexes[ci] for ri, ci in role_of.items()}
    # fallback: leftover roles take the nearest-hue leftover color; the
    # convention break is FLAGGED, never silently treated as in-window
    leftovers_r = [i for i in range(len(roles)) if i not in role_of]
    leftovers_c = [i for i in range(len(colors)) if i not in color_of]
    for ri in leftovers_r:
        if not leftovers_c:
            break
        target = committed.oklch(roles[ri])[2]
        best = min(leftovers_c, key=lambda ci: _circ(colors[ci][2], target))
        out[roles[ri]] = free_hexes[best]
        issues.append(f"convention break: {roles[ri]} assigned h={colors[best][2]:.0f} "
                      f"(window {FREE_ROLES[roles[ri]]})")
        leftovers_c.remove(best)
    return out, issues


def wcag_repair(assignment: dict[str, str], bg: str, roles: RoleSpec) -> dict[str, str]:
    """Raise L (hue kept, chroma re-projected) until every body-text role
    clears 4.5:1 vs the canvas; every adjustment is recorded in the hex."""
    out = dict(assignment)
    for role, hx in assignment.items():
        floor = 4.5 if roles.roles[role].accessibility_floor == "body_text" else 3.0
        if wcag_contrast(hx, bg) >= floor:
            continue
        L, C, h = hex_to_oklch(hx)
        lo, hi = L, 1.0
        for _ in range(24):
            mid = (lo + hi) / 2
            c = min(C, max_chroma(mid, h))
            if wcag_contrast(oklch_to_hex((mid, c, h)), bg) >= floor:
                hi = mid
            else:
                lo = mid
        out[role] = oklch_to_hex((hi, min(C, max_chroma(hi, h)), h))
    return out


def cap_chroma(assignment: dict[str, str], cap: float) -> dict[str, str]:
    return {
        role: oklch_to_hex((L, min(C, cap, max_chroma(L, h)), h))
        for role, hx in assignment.items()
        for (L, C, h) in [hex_to_oklch(hx)]
    }


def compose(scaffold: Palette, assignment: dict[str, str]) -> Palette:
    colors = dict(scaffold.colors)
    colors.update(assignment)
    return Palette(f"huerd-night", "night", colors, source="hex",
                   note="NON-CANDIDATE huerd-driven exploration (see NUMERIC.md)")


def evaluate(pal: Palette, roles: RoleSpec, dists: DistanceSpec) -> dict:
    from anchor_search import PAIRS  # grotto's co-occurring pair list

    th = dists.thresholds
    must_n, must_cvd, should = [], [], []
    for c in dists.constraints:
        a, b = pal.get(c.a), pal.get(c.b)
        if not a or not b:
            continue
        de = delta_e_ok(a, b)
        if c.kind == "must_distinguish":
            must_n.append(de / th["must_distinguish"]["normal_vision"])
            for kind in ("protan", "deutan", "tritan"):
                cde = delta_e_ok(simulate(a, kind, 1.0), simulate(b, kind, 1.0))
                must_cvd.append(cde / th["must_distinguish"]["cvd_dichromat"])
        elif c.kind == "should_distinguish":
            should.append(de / th["should_distinguish"]["normal_vision"])
    same = [
        delta_e_ok(pal[c.a], pal[c.b]) / th["same_family"]["min_distance"]
        for c in dists.of_kind("same_family")
        if pal.get(c.a) and pal.get(c.b)
    ]
    cats = ["keyword", "string", "function", "type", "number",
            "constant", "builtin", "decorator", "namespace", "tag"]
    chroma = [hex_to_oklch(pal[r])[1] for r in cats if pal.get(r)]
    worst_surface = min(
        (delta_e_ok(simulate(pal["diff_added"], k, 1.0),
                    simulate(pal["diff_removed"], k, 1.0)) for k in ("protan", "deutan", "tritan")),
        default=0.0,
    )
    return {
        "worst_margin": round(min(must_n + must_cvd), 3),
        "must_normal": round(min(must_n), 3),
        "must_cvd": round(min(must_cvd), 3),
        "should": round(min(should), 3) if should else None,
        "same_family_min": round(min(same), 3) if same else None,
        "diff_cvd_worst": round(worst_surface, 3),
        "num_const_dE": round(delta_e_ok(pal["number"], pal["constant"]), 3),
        "mean_cat_chroma": round(sum(chroma) / len(chroma), 3),
        "max_cat_chroma": round(max(chroma), 3),
        "min_wcag": round(min(
            wcag_contrast(pal[r.name], pal["bg"]) for r in roles
            if r.name in pal and r.accessibility_floor != "none"
        ), 2),
    }


def main() -> None:
    import yaml

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mode", choices=sorted(PIN_MODES), default="anchors")
    ap.add_argument("--runs", type=int, default=4)
    ap.add_argument("--seed", type=int, default=20260816)
    ap.add_argument("--iterations", type=int, default=2000)
    ap.add_argument("--out", default="out/huerd-night")
    ap.add_argument("--vscode-preview", type=int, default=3)
    args = ap.parse_args()

    global FREE_ROLES
    FREE_ROLES = {r: w for r, w in FREE_ROLES.items() if r not in PIN_MODES[args.mode]}
    out = REPO / args.out
    out.mkdir(parents=True, exist_ok=True)
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    scaffold = load(REPO / SCAFFOLD)
    pin_roles = PIN_MODES[args.mode]
    pins = [scaffold[r] for r in pin_roles]

    gens = generate(pins, len(FREE_ROLES), args.runs, args.seed, args.iterations)
    results = []
    for gi, g in enumerate(gens, 1):
        free = [hx for hx in g["hexes"] if hx not in pins]
        assignment, issues = assign(free, scaffold)
        for msg in issues:
            print(f"[run {gi}] {msg}")
        repaired = wcag_repair(assignment, scaffold["bg"], roles)
        capped = cap_chroma(repaired, SYNTAX_CAP)
        for label, asg in (("raw", repaired), ("capped", capped)):
            pal = compose(scaffold, asg)
            results.append({
                "id": f"h{gi:02d}-{label}",
                "huerd_min_dist": round(g["min_dist"], 3),
                "huerd_min_cvd": round(g["min_cvd"], 3),
                "assignment": asg,
                "metrics": evaluate(pal, roles, dists),
            })

    baselines = {}
    for name, path in (("candidate-b", "themes/candidates/candidate-b-balanced.night.yaml"),
                       ("middle-m01", "out/middle-night/middle-m01.night.yaml"),
                       ("numeric-n01", "out/numeric-night/numeric-n01.night.yaml")):
        p = REPO / path
        if p.exists():
            baselines[name] = evaluate(load(p), roles, dists)

    payload = {
        "schema": "grotto.huerd-night",
        "huerd_version": "0.6.2 (local ../huerd, sann optimizer, cvd_safe=TRUE)",
        "mode": args.mode,
        "pins": {r: scaffold[r] for r in pin_roles},
        "free_roles": {k: list(v) for k, v in FREE_ROLES.items()},
        "syntax_cap": SYNTAX_CAP,
        "baselines": baselines,
        "results": results,
        "note": "NON-CANDIDATE exploration; assignment keeps learned hue "
                "conventions, huerd places the free colors.",
    }
    (out / "results.json").write_text(json.dumps(payload, indent=2) + "\n")
    (out / "results.yaml").write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=True, width=100))

    lines = ["# huerd-driven night palettes (NON-CANDIDATE)", ""]
    lines.append(f"huerd >= 0.6.2, optimizer sann, cvd_safe=TRUE; pins: {payload['pins']}")
    lines.append(f"free roles assigned within convention windows; chroma cap {SYNTAX_CAP} for 'capped'")
    lines.append("")
    header = f"{'palette':16s} {'worstM':>7s} {'mustN':>6s} {'mustCVD':>8s} {'same':>6s} {'diffCVD':>8s} {'n/c dE':>7s} {'meanC':>6s} {'maxC':>6s} {'wcag':>5s}"
    lines.append(header)
    for name, m in baselines.items():
        lines.append(f"{name:16s} {m['worst_margin']:7.3f} {m['must_normal']:6.3f} {m['must_cvd']:8.3f} "
                     f"{m['same_family_min']:6.3f} {m['diff_cvd_worst']:8.3f} {m['num_const_dE']:7.3f} "
                     f"{m['mean_cat_chroma']:6.3f} {m['max_cat_chroma']:6.3f} {m['min_wcag']:5.2f}")
    for r in results:
        m = r["metrics"]
        lines.append(f"{r['id']:16s} {m['worst_margin']:7.3f} {m['must_normal']:6.3f} {m['must_cvd']:8.3f} "
                     f"{m['same_family_min']:6.3f} {m['diff_cvd_worst']:8.3f} {m['num_const_dE']:7.3f} "
                     f"{m['mean_cat_chroma']:6.3f} {m['max_cat_chroma']:6.3f} {m['min_wcag']:5.2f}")
    (out / "results.txt").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))

    # side-by-side HTML on the R specimen
    from anchor_search import render_specimen_html
    from grotto.specimens import specimen

    r_spec = specimen("r")
    picks = [("candidate-b (base)", scaffold)] + [
        (r["id"], compose(scaffold, r["assignment"])) for r in results[:6]
    ]
    cells = []
    for label, pal in picks:
        sw = "".join(
            f'<span title="{r}" style="background:{pal[r]};color:{pal["bg"]};padding:1px 7px;'
            f'margin-right:3px;border-radius:3px">{r}</span>'
            for r in ("keyword", "string", "function", "type", "number", "constant", "error", "warning"))
        cells.append(
            f'<div class="cell"><h3>{label}</h3>'
            f'<div style="background:{pal["bg"]};padding:6px 8px;margin:6px 0;border-radius:4px">{sw}</div>'
            f'<pre style="background:{pal["bg"]};color:{pal["fg"]};padding:10px;margin:0;'
            f'border-radius:6px;overflow:auto">{render_specimen_html(pal, r_spec)}</pre></div>')
    css = ("body{margin:0;background:#141414;color:#d8d8d8;font-family:ui-monospace,Menlo,Consolas,monospace;"
           "font-size:13px;padding:18px} h1{font-size:1.3rem} h3{margin:.2em 0 .1em}"
           ".cell{margin:0 0 26px} pre{line-height:1.5;font-size:12px} .banner{background:#1f212b;"
           "padding:.6em .8em;border-radius:6px;margin:.8em 0;border-left:3px solid #4a5d8a}")
    html = ("<!doctype html><html><head><meta charset='utf-8'><title>huerd night</title>"
            f"<style>{css}</style></head><body><h1>huerd-driven night palettes</h1>"
            "<div class='banner'>NON-CANDIDATE: huerd 0.6.2 sann cvd_safe, pins = canvas/error/warning; "
            "free roles assigned within convention windows. 'raw' vs 'capped' = chroma 0.12 fence.</div>"
            + "".join(cells) + "</body></html>")
    (out / "variants.html").write_text(html)

    # VS Code preview: base + capped picks preferred for eyeballing
    if args.vscode_preview:
        from grotto import vscode as gv

        mapping = gv._load_mapping(REPO / "spec/mappings/vscode.yaml", roles)
        ext = out / "vscode-preview"
        (ext / "themes").mkdir(parents=True, exist_ok=True)
        themes = []
        shown = [("h01-raw", results[0])] if results else []
        shown += [(r["id"], r) for r in results if r["id"].endswith("capped")][: args.vscode_preview - 1]
        for i, (label, r) in enumerate(shown, 1):
            pal = compose(scaffold, r["assignment"])
            theme = gv._build_theme(pal, f"Grotto H-Explore {i:02d} Night", "night", mapping,
                                    source_name=f"huerd-{label}", source_sha256="exploration")
            theme["grotto"]["note"] = f"NON-CANDIDATE huerd-driven variant ({label})"
            path = f"themes/huerd-{i:02d}-night.json"
            (ext / path).write_text(gv._dump(theme), encoding="utf-8", newline="\n")
            themes.append({"label": f"Grotto H-Explore {i:02d} Night", "uiTheme": "vs-dark", "path": path})
        pkg = {
            "name": "grotto-huerd-exploration",
            "displayName": "Grotto huerd Exploration (NON-CANDIDATE)",
            "description": "Night themes from huerd 0.6.2 CVD-safe generation with pinned anchors.",
            "version": "0.0.1", "publisher": "grotto-exploration",
            "engines": {"vscode": "^1.70.0"}, "categories": ["Themes"],
            "contributes": {"themes": themes},
        }
        (ext / "package.json").write_text(json.dumps(pkg, indent=2) + "\n")
        print(f"[vscode] exploration extension at {ext}")


if __name__ == "__main__":
    main()
