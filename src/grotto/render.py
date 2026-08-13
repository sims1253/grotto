"""Self-contained visual rendering: HTML reports and SVG swatch strips.

Everything emitted here is a single file with inline CSS/JS and no external
resources, so a report can be archived or shared and still render identically.
Output is deterministic in its inputs (no wall-clock timestamps), which is what
"reproducible report output" requires.

The HTML is itself a live demo of the palette: the page chrome uses the
palette's own ``bg``/``fg``/``bg_elevated``, and the code specimens are coloured
with the palette under normal vision and under each CVD simulation, toggled by
a control that swaps a body class.
"""

from __future__ import annotations

from html import escape

from .color import hex_to_srgb, relative_luminance
from .contrast import contrast_report
from .cvd import CVD_TYPES, simulate
from .distance import delta_e_ok
from .environments import Environments
from .spectral import led_lcd, melanopic, screen_melanopic
from .spec import Palette, RoleSpec, audit_palette, check, coverage_model
from .spec import DistanceSpec
from . import specimens as SPEC

_CVD_VIEWS = (("normal", "Normal"), ("protan", "Protan"), ("deutan", "Deutan"), ("tritan", "Tritan"))


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------


def _esc(s) -> str:
    return escape(str(s), quote=True)


def _on_text(hex_color: str) -> str:
    """Black or white, whichever reads on ``hex_color``."""
    return "#000" if relative_luminance(hex_to_srgb(hex_color)) > 0.42 else "#fff"


def _chip(hex_color: str, label: str, *, w: int = 84, h: int = 34) -> str:
    return (
        f'<span class="chip" style="background:{hex_color};color:{_on_text(hex_color)};'
        f'min-width:{w}px;height:{h}px">{_esc(label)}</span>'
    )


def _gamut_badges(audit) -> str:
    s = "sRGB&#10003;" if audit.in_srgb else "sRGB&#10007;"
    p = "P3&#10003;" if audit.in_p3 else "P3&#10007;"
    lost = (
        f' <span class="lost">gamut-mapped &minus;{audit.chroma_lost:.3f} C</span>'
        if audit.chroma_lost > 1e-6
        else ""
    )
    return f'<span class="badge">{s}</span> <span class="badge">{p}</span>{lost}'


def _classify_band(env: Environments, lc_abs: float) -> str:
    b = env.band_for_lc(lc_abs)
    return b.name if b else "out-of-band"


# --------------------------------------------------------------------------
# CSS
# --------------------------------------------------------------------------


def _role_css(palette: Palette, selector_prefix: str = "") -> str:
    rules = []
    for role, hx in palette.items():
        rules.append(f"{selector_prefix}.r-{role}{{color:{hx}}}")
    return "\n".join(rules)


def _cvd_role_css(palette: Palette) -> str:
    """Four CSS scopes (normal + 3 CVD) so a body class swaps the specimen view."""
    parts = [_role_css(palette, "body.view-normal .specimen ")]
    for kind, _label in _CVD_VIEWS[1:]:
        sim = {r: simulate(hx, kind, 1.0) for r, hx in palette.items()}
        rules = [
            f"body.view-{kind} .specimen .r-{role}{{color:{hx}}}"
            for role, hx in sim.items()
        ]
        parts.append("\n".join(rules))
    return "\n".join(parts)


def _page_css(palette: Palette) -> str:
    bg = palette.get("bg", "#111")
    fg = palette.get("fg", "#eee")
    elev = palette.get("bg_elevated", bg)
    fg2 = palette.get("fg_secondary", fg)
    err = palette.get("error", "#f00")
    return f"""
:root {{--bg:{bg};--fg:{fg};--elev:{elev};--fg2:{fg2};--err:{err};}}
* {{ box-sizing:border-box; }}
body {{ margin:0; background:var(--bg); color:var(--fg);
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:13px; line-height:1.5; padding:18px; }}
h1 {{ font-size:1.5rem; margin:0 0 .2em; }}
h2 {{ font-size:1.1rem; margin:1.6em 0 .5em; border-bottom:1px solid var(--elev); padding-bottom:.2em; }}
p,li {{ margin:.3em 0; }}
.banner {{ background:var(--elev); padding:.6em .8em; border-radius:6px; margin:.8em 0; }}
.warn {{ color:var(--err); font-weight:bold; }}
.meta {{ color:var(--fg2); font-size:.85rem; }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(210px,1fr)); gap:8px; }}
.card {{ background:var(--elev); border-radius:6px; padding:8px 10px; }}
.card .name {{ font-weight:bold; }}
.card .vals {{ color:var(--fg2); font-size:.8rem; margin-top:2px; word-break:break-all; }}
.chip {{ display:inline-flex; align-items:center; justify-content:center;
  border-radius:4px; padding:0 6px; font-size:.78rem; font-weight:bold;
  letter-spacing:.02em; box-shadow:inset 0 0 0 1px rgba(128,128,128,.25); }}
.badge {{ font-size:.7rem; background:rgba(128,128,128,.25); padding:1px 5px; border-radius:8px; }}
.badge-ok {{ color:#7ec; }}
.badge-bad {{ color:var(--err); }}
.lost {{ color:var(--err); font-size:.72rem; }}
table {{ border-collapse:collapse; width:100%; background:var(--elev); border-radius:6px; overflow:hidden; }}
th,td {{ text-align:left; padding:5px 8px; border-bottom:1px solid rgba(128,128,128,.18); white-space:nowrap; }}
th {{ color:var(--fg2); font-weight:normal; font-size:.78rem; text-transform:uppercase; letter-spacing:.04em; }}
.flag-bad {{ color:var(--err); font-weight:bold; }}
.flag-ok {{ opacity:.65; }}
.specimen {{ background:var(--bg); color:var(--fg); padding:10px 12px; border-radius:6px;
  margin:6px 0; white-space:pre; overflow:auto; tab-size:2; font-size:12.5px; }}
.specimen .caption {{ color:var(--fg2); font-size:.75rem; margin-bottom:4px; }}
.bar-row {{ display:flex; align-items:center; gap:8px; margin:3px 0; }}
.bar-track {{ flex:1; background:rgba(128,128,128,.2); border-radius:3px; height:14px; overflow:hidden; }}
.bar-fill {{ height:100%; }}
.bar-label {{ width:150px; font-size:.78rem; color:var(--fg2); }}
.bar-val {{ width:64px; font-size:.78rem; text-align:right; }}
.controls {{ position:sticky; top:0; background:var(--bg); padding:8px 0; z-index:2; }}
select {{ background:var(--elev); color:var(--fg); border:1px solid var(--fg2); border-radius:4px; padding:2px 6px; }}
.footer {{ color:var(--fg2); font-size:.75rem; margin-top:2em; border-top:1px solid var(--elev); padding-top:.6em; }}
"""


# --------------------------------------------------------------------------
# sections
# --------------------------------------------------------------------------


def _swatch_grid(palette: Palette, roles: RoleSpec) -> str:
    au = audit_palette(palette, roles)
    cards = []
    for role in au:
        a = au[role]
        spec = roles.roles.get(role)
        desc = f"{spec.family} · sal {spec.salience}" if spec else "(not in spec)"
        cards.append(
            f'<div class="card"><div class="name">{_chip(a.hex, role)} '
            f'<span style="color:var(--fg2);font-size:.78rem">{_esc(desc)}</span></div>'
            f'<div class="vals">{_gamut_badges(a)}<br>'
            f"oklch {a.oklch[0]:.3f} {a.oklch[1]:.3f} {a.oklch[2]:.0f}&deg;</div></div>"
        )
    return f'<div class="grid">{"".join(cards)}</div>'


def _contrast_table(palette: Palette, roles: RoleSpec, env: Environments) -> str:
    bg = palette.bg
    rows = []
    for role, hx in palette.items():
        if role == "bg":
            continue
        rep = contrast_report(hx, bg)
        spec = roles.roles.get(role)
        target = spec.contrast_target if spec else None
        band = _classify_band(env, abs(rep.apca))
        target_ok = (target is None) or (band == target)
        wcag_body = rep.wcag_aa_body
        rows.append(
            "<tr>"
            f"<td>{_chip(hx, role, w=60, h=20)}</td>"
            f'<td>{"&ndash;" if target is None else _esc(target)}</td>'
            f"<td>{abs(rep.apca):.0f} <span class='meta'>({_esc(band)})</span></td>"
            f'<td class="{"flag-ok" if target_ok else "flag-bad"}">{_esc(band if target_ok else "MISMATCH")}</td>'
            f"<td>{rep.wcag:.2f}</td>"
            f'<td class="{"flag-ok" if wcag_body else "flag-bad"}">{"AA" if wcag_body else "below AA"}</td>'
            f"<td>{rep.dl:+.3f}</td>"
            "</tr>"
        )
    return (
        "<table><tr><th>role</th><th>target band</th><th>|APCA Lc|</th>"
        "<th>measured</th><th>WCAG</th><th>WCAG AA body</th><th>&Delta;L (OKLab)</th></tr>"
        + "".join(rows)
        + "</table>"
        + "<p class='meta'>Target band is the role's design band (environments.yaml); "
        "measured is the APCA band the pair actually lands in. APCA is independent "
        "work in progress, not a W3C Recommendation or current WCAG criterion "
        "(DESIGN.md section 7).</p>"
    )


def _distance_section(violations) -> str:
    if not violations:
        return "<p>No distance-matrix violations for the roles present.</p>"
    rows = []
    for v in violations:
        rows.append(
            "<tr>"
            f'<td class="{"flag-bad" if v.severity=="error" else ""}">{_esc(v.severity)}</td>'
            f"<td>{_esc(str(v.constraint))}</td>"
            f"<td>{_esc(v.condition)}</td>"
            f"<td>{v.measured:.3f}</td><td>{v.threshold:.3f}</td></tr>"
        )
    return (
        "<table><tr><th>severity</th><th>constraint</th><th>condition</th>"
        "<th>dE</th><th>threshold</th></tr>" + "".join(rows) + "</table>"
    )


def _diagnostics_panel(palette: Palette, roles: RoleSpec) -> str:
    diag = ("error", "warning", "info", "success", "diff_added", "diff_removed", "search_match_current")
    rows = []
    for role in diag:
        hx = palette.get(role)
        if not hx:
            continue
        spec = roles.roles.get(role)
        chans = ", ".join(spec.redundant_channels) if spec and spec.redundant_channels else "(none)"
        rows.append(
            f"<div class='card'><div class='name'>{_chip(hx, role)}</div>"
            f"<div class='vals'>cvd_priority {_esc(spec.cvd_priority if spec else '?')}<br>"
            f"redundant channels: {_esc(chans)}</div></div>"
        )
    return (
        '<div class="grid">' + "".join(rows) + "</div>"
        + "<p class='meta'>D-3: every critical role must carry a non-hue channel; "
        "hue is never the sole carrier of critical meaning.</p>"
    )


def _cvd_pairs_section(palette: Palette, dists: DistanceSpec) -> str:
    pairs = [c for c in dists.of_kind("must_distinguish") if c.a in palette and c.b in palette]
    if not pairs:
        return "<p>No must_distinguish pairs present in this palette.</p>"
    head = "<tr><th>pair</th><th>normal dE</th>" + "".join(
        f"<th>{k}@1.0</th>" for k in CVD_TYPES
    ) + "</tr>"
    rows = []
    for c in pairs:
        a, b = palette[c.a], palette[c.b]
        normal = delta_e_ok(a, b)
        cells = "".join(
            f"<td>{delta_e_ok(simulate(a, k, 1.0), simulate(b, k, 1.0)):.3f}</td>"
            for k in CVD_TYPES
        )
        rows.append(
            f"<tr><td>{_chip(a, c.a, w=46, h=18)}{_chip(b, c.b, w=46, h=18)}</td>"
            f"<td>{normal:.3f}</td>{cells}</tr>"
        )
    return "<table>" + head + "".join(rows) + "</table>"


def _spectral_section(palette: Palette) -> str:
    if "bg" not in palette:
        return "<p class='meta'>No bg role; cannot build coverage model.</p>"
    cov = coverage_model(palette, "code")
    res = screen_melanopic(cov, led_lcd())
    items = sorted(res.contributions.items(), key=lambda kv: -kv[1])[:8]
    scale = max((frac for _, frac in items), default=1.0) or 1.0
    bars = []
    for hx, frac in items:
        bar = (
            f'<div class="bar-row"><span class="bar-label">{_chip(hx, hx, w=70, h=16)}</span>'
            f'<span class="bar-track"><span class="bar-fill" style="width:{frac/scale*100:.1f}%;'
            f'background:{hx}"></span></span>'
            f'<span class="bar-val">{frac*100:.1f}%</span></div>'
        )
        bars.append(bar)
    return (
        f"<p class='meta'>Nominal {res.display} model, 'code' coverage estimate. "
        f"Screen melanopic/photopic ratio <b>{res.mel_ratio:.3f}</b> relative to display white = 1.0. "
        "Bars are each colour's share of total melanopic output. "
        "<b>Exploratory, within-model ranking only</b> -- an sRGB triple does not determine a "
        "spectral power distribution; this never claims actual retinal exposure (RESEARCH.md R-4, R-5).</p>"
        + "".join(bars)
    )


def _specimens_section(palette: Palette) -> str:
    blocks = []
    for lang in SPEC.REQUIRED_LANGUAGES:
        sp = SPEC.specimen(lang)
        missing = sorted(sp.roles_used() - set(palette.roles()))
        warn = (
            f'<div class="warn">missing roles: {", ".join(missing)} (rendered as fg)</div>'
            if missing
            else ""
        )
        body = []
        for line in sp.lines:
            parts = []
            for role, text in line:
                cls = f"r-{role}" if role in palette else "r-fg"
                parts.append(f'<span class="{cls}">{_esc(text)}</span>')
            body.append("".join(parts))
        blocks.append(
            f'<div><div class="caption">{_esc(sp.label)} &middot; {_esc(sp.filename)}</div>'
            f'{warn}<pre class="specimen">' + "\n".join(body) + "</pre></div>"
        )
    control = (
        '<div class="controls"><label for="cvd">CVD view: </label>'
        '<select id="cvd" onchange="document.body.className=\'view-\'+this.value">'
        + "".join(f'<option value="{v}">{l}</option>' for v, l in _CVD_VIEWS)
        + "</select></div>"
    )
    return (
        control
        + "".join(blocks)
        + "<p class='meta'>Specimens coloured by role under the selected CVD simulation "
        "(Brettel dichromacy at severity 1.0; Machado for anomaly). Missing roles fall back to fg.</p>"
    )


# --------------------------------------------------------------------------
# top-level reports
# --------------------------------------------------------------------------


def palette_html_report(
    palette: Palette, roles: RoleSpec, dists: DistanceSpec, env: Environments
) -> str:
    """A single self-contained HTML page auditing one palette."""
    missing = sorted(r for r in roles.roles if r not in palette)
    violations = check(palette, roles, dists)
    errs = sum(1 for v in violations if v.severity == "error")
    warns = sum(1 for v in violations if v.severity == "warning")

    candidate_note = (
        '<div class="banner warn">EVALUATION FIXTURE / REFERENCE -- NOT A CANDIDATE PALETTE. '
        "No palette is finalised in Phase 2 (DESIGN.md).</div>"
        if not palette.is_candidate
        else ""
    )
    header = (
        f"<h1>{_esc(palette.name)}</h1>"
        f"<div class='meta'>variant <b>{_esc(palette.variant)}</b> &middot; "
        f"source <b>{_esc(palette.source)}</b> &middot; {len(palette)} roles &middot; "
        f"{len(missing)} spec roles not defined</div>"
        f"<div class='meta'>{_esc(palette.note)}</div>"
    )
    summary = (
        f'<div class="banner">Distance-matrix check: <b>{errs}</b> error(s), '
        f"<b>{warns}</b> warning(s) across the {len(violations)} enforced constraint(s) "
        "for roles present.</div>"
    )
    sections = [
        ("Swatches &amp; gamut", _swatch_grid(palette, roles)),
        ("Contrast (vs bg)", _contrast_table(palette, roles, env)),
        ("Distance-matrix violations", _distance_section(violations)),
        ("Diagnostics &amp; redundant channels", _diagnostics_panel(palette, roles)),
        ("CVD: must_distinguish pairs", _cvd_pairs_section(palette, dists)),
        ("Spectral (nominal display, exploratory)", _spectral_section(palette)),
        ("Specimens (CVD-toggleable)", _specimens_section(palette)),
    ]
    body = header + candidate_note + summary + "".join(
        f"<h2>{title}</h2>{html}" for title, html in sections
    )
    footer = (
        '<div class="footer">Generated by grotto Phase 2 evaluation tooling. '
        "Reproducible: identical inputs produce identical output. "
        "Inputs are evaluation fixtures / reference themes, not candidate palettes.</div>"
    )
    js = (
        "<script>document.body.className='view-normal';"
        "document.getElementById('cvd').addEventListener('change',function(e){"
        "document.body.className='view-'+e.target.value;});</script>"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(palette.name)} -- grotto report</title>"
        f"<style>{_page_css(palette)}\n{_cvd_role_css(palette)}</style></head>"
        f"<body class='view-normal'>{body}{footer}{js}</body></html>"
    )


def palette_svg_strip(palette: Palette, roles: RoleSpec) -> str:
    """A self-contained SVG swatch strip, one rect per role in spec order."""
    au = audit_palette(palette, roles)
    items = list(au.values())
    n = len(items)
    w, h, pad = 120, 56, 2
    total_w = n * (w + pad) + pad
    rects = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{h+22}" '
             f'font-family="monospace" font-size="10">']
    rects.append(f'<rect width="100%" height="100%" fill="{palette.get("bg","#111")}"/>')
    for i, a in enumerate(items):
        x = pad + i * (w + pad)
        rects.append(
            f'<rect x="{x}" y="2" width="{w}" height="{h-6}" fill="{a.hex}" '
            f'rx="3" />'
        )
        txt_color = _on_text(a.hex)
        label = f"{a.role}  {a.hex}"
        rects.append(
            f'<text x="{x+6}" y="18" fill="{txt_color}">{_esc(a.role)}</text>'
            f'<text x="{x+6}" y="{h-8}" fill="{txt_color}">{a.hex}</text>'
        )
        flag = "" if a.in_srgb else " &#9888;"  # warning sign if OOG
        rects.append(
            f'<text x="{x+6}" y="{h+12}" fill="{palette.get("fg_secondary","#888")}">'
            f"L{a.oklch[0]:.2f} C{a.oklch[1]:.2f} h{a.oklch[2]:.0f}{flag}</text>"
        )
    rects.append("</svg>")
    return "".join(rects)


def stability_html_report(report, roles: RoleSpec) -> str:
    """Self-contained HTML for a cross-variant StabilityReport."""
    bg = "#111"
    fg = "#eee"
    elev = "#1c1c22"
    css = f"""
body {{ background:{bg}; color:{fg}; font-family:ui-monospace,monospace; padding:18px; font-size:13px;}}
h1{{font-size:1.4rem;}} h2{{font-size:1.05rem;border-bottom:1px solid {elev};}}
table{{border-collapse:collapse;width:100%;background:{elev};border-radius:6px;}}
th,td{{text-align:left;padding:5px 8px;border-bottom:1px solid rgba(128,128,128,.2);white-space:nowrap;}}
th{{color:#9aa;font-weight:normal;font-size:.78rem;text-transform:uppercase;}}
.ok{{color:#7ec;}} .bad{{color:#f88;font-weight:bold;}}
.banner{{background:{elev};padding:.6em .8em;border-radius:6px;margin:.6em 0;}}
.meta{{color:#9aa;font-size:.8rem;}}
"""
    var_list = ", ".join(report.variants)
    status = (
        f'<span class="ok">PASS</span>' if report.ok
        else f'<span class="bad">ATTENTION</span>'
    )
    drift_rows = "".join(
        f"<tr><td>{_esc(r)}</td><td>{d:.2f}</td>"
        f"<td>{report.max_hue_drift_threshold:.1f}</td>"
        f'<td class="bad">over</td></tr>'
        for r, d in report.drift_violations
    ) or '<tr><td colspan="4" class="meta">none</td></tr>'
    inv_rows = "".join(
        f"<tr><td>{_esc(i.kind)}</td><td>{_esc(i.role_a)} / {_esc(i.role_b)}</td>"
        f"<td>{_esc(i.variant_a)} &rarr; {_esc(i.variant_b)}</td><td>{_esc(i.detail)}</td></tr>"
        for i in (report.hue_order_inversions + report.chroma_rank_inversions)
    ) or '<tr><td colspan="4" class="meta">none</td></tr>'

    # per-role drift table (chromatic roles only)
    role_rows = ""
    for role in sorted(report.roles):
        r = report.roles[role]
        if not r.hue_meaningful:
            continue
        drift = r.max_hue_drift if r.max_hue_drift is not None else float("nan")
        over = "bad" if (r.max_hue_drift or 0) > report.max_hue_drift_threshold else "ok"
        role_rows += (
            f"<tr><td>{_esc(role)}</td><td>{_esc(r.family)}</td>"
            f"<td>{r.hue[report.variants[0]]:.1f}</td><td>{r.hue[report.variants[1]]:.1f}</td>"
            f"<td>{r.hue[report.variants[2]]:.1f}</td>"
            f'<td class="{over}">{drift:.2f}</td></tr>'
        )

    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>cross-variant stability -- grotto</title><style>{css}</style></head><body>"
        f"<h1>Cross-variant stability</h1>"
        f"<div class='meta'>variants: {var_list} &middot; status: {status}</div>"
        f"<div class='banner'>{_esc(report.caveat)}</div>"
        f"<h2>Drift violations (hue drift &gt; {report.max_hue_drift_threshold:.0f}&deg;)</h2>"
        "<table><tr><th>role</th><th>max drift&deg;</th><th>threshold</th><th></th></tr>"
        f"{drift_rows}</table>"
        "<h2>Rank / order inversions</h2>"
        "<table><tr><th>kind</th><th>roles</th><th>variants</th><th>detail</th></tr>"
        f"{inv_rows}</table>"
        f"<h2>Per-role hue drift (variants: {' / '.join(report.variants)})</h2>"
        "<table><tr><th>role</th><th>family</th>"
        + "".join(f"<th>{_esc(v)} h&deg;</th>" for v in report.variants)
        + "<th>max drift&deg;</th></tr>" + role_rows + "</table>"
        f"<p class='meta'>Salience rank preserved by construction: "
        f"<b>{'yes' if report.salience_rank_preserved else 'no'}</b>. "
        "Achromatic/low-chroma roles are omitted (hue not meaningful below chroma floor).</p>"
        "</body></html>"
    )
