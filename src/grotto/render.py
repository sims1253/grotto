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


def on_text_threshold(hex_color: str) -> bool:
    """Whether DARK ink reads on ``hex_color`` -- the one shared chip-text cutoff.

    Returns True when WCAG relative luminance exceeds 0.42.  That constant is
    an arbitrary but serviceable midpoint, NOT a WCAG criterion (WCAG defines
    contrast ratios between two colours, not a background-luminance split).
    Only the DECISION is shared project-wide so renderers cannot disagree
    about which chips count as "light"; each caller keeps its own ink PALETTE
    (#000/#fff, or chrome-tinted near-black/near-white) -- see ``_on_text``
    here, ``family_report._variant_strip`` and ``candidate_report._on_svg``.
    """
    return relative_luminance(hex_to_srgb(hex_color)) > 0.42


def _on_text(hex_color: str) -> str:
    """Black or white, whichever reads on ``hex_color`` (see on_text_threshold)."""
    return "#000" if on_text_threshold(hex_color) else "#fff"


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
        # Bands deliberately overlap (comfortable 60-78 vs high 75-90), so
        # agreement is membership in the TARGET band, not band-name equality
        # with ``band_for_lc``'s first-match classification (cf. report.py,
        # model._contrast_block).
        target_ok = (target is None) or (
            env.contrast_bands[target].contains(abs(rep.apca))
        )
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
        # the ONLY change handler is the script listener at the bottom of the
        # page (an inline onchange here would set body.className a second time)
        '<select id="cvd">'
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


def _salience_budget_section(palette: Palette, roles: RoleSpec, env: Environments) -> str:
    """The DESIGN.md section-6 budget, measured from the declared coverage
    plan.  Fractions are of non-background pixels; violations are flagged,
    never tuned away."""
    from .spec import salience_coverage

    try:
        sc = salience_coverage(palette, roles, "code")
    except ValueError:
        return "<p class='meta'>No coverage model (missing bg).</p>"
    budget = env.salience_budget or {}
    rows = []
    ok = True
    for level, label, key in (
        ("at_or_above_3", "&ge; 3", "max_fraction_at_or_above_3"),
        ("at_or_above_5", "&ge; 5", "max_fraction_at_or_above_5"),
    ):
        frac = sc[level]
        limit = budget.get(key)
        cls = "flag-ok"
        note = "&ndash;"
        if limit is not None:
            note = f"{limit * 100:.0f}%"
            if frac > limit + 1e-9:
                cls = "flag-bad"
                ok = False
        rows.append(
            f"<tr><td>salience {label}</td><td>{frac * 100:.1f}%</td>"
            f"<td>{note}</td><td class='{cls}'>"
            f"{'within' if (limit is None or frac <= limit + 1e-9) else 'OVER'}</td></tr>"
        )
    return (
        "<table><tr><th>level</th><th>declared share of non-bg pixels</th>"
        "<th>budget</th><th>status</th></tr>" + "".join(rows) + "</table>"
        "<p class='meta'>Declared coverage estimate (spec.py COVERAGE_MODELS), "
        "not a screenshot measurement. The budget makes \"too busy\" a number "
        "(DESIGN.md section 6); an OVER row is a design signal, not an error "
        "to be tuned away.</p>"
    )


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
        ("Salience budget (declared estimate)", _salience_budget_section(palette, roles, env)),
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

    # per-role drift table (chromatic roles only); one column per variant,
    # built from the report itself -- the body must not assume three variants
    # just because the header below iterates them.
    role_rows = ""
    for role in sorted(report.roles):
        r = report.roles[role]
        if not r.hue_meaningful:
            continue
        drift = r.max_hue_drift if r.max_hue_drift is not None else float("nan")
        over = "bad" if (r.max_hue_drift or 0) > report.max_hue_drift_threshold else "ok"
        hue_cells = "".join(
            f"<td>{r.hue[v]:.1f}</td>"
            for v in report.variants
            if v in r.hue
        )
        role_rows += (
            f"<tr><td>{_esc(role)}</td><td>{_esc(r.family)}</td>"
            f"{hue_cells}"
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
        f"<p class='meta'>Salience rank check (spec coverage only; the rank "
        f"itself is constant by construction, so this verifies the roles exist "
        f"in the spec): "
        f"<b>{'yes' if report.salience_rank_preserved else 'no'}</b>. "
        "Achromatic/low-chroma roles are omitted (hue not meaningful below chroma floor).</p>"
        "</body></html>"
    )


# ===========================================================================
# Phase 3: reference-theme comparison rendering
# ===========================================================================
#
# These renderers take already-computed analysis/comparison dicts from
# ``grotto.reference_analysis`` (which holds all the numbers and caveats) and
# turn them into self-contained, deterministic HTML/SVG.  The page chrome is a
# neutral dark surface -- it cannot use one reference's palette, because the
# whole point is to compare six of them side by side.

_REF_CSS = """
* { box-sizing:border-box; }
body { margin:0; background:#15161c; color:#d7d9e2;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:13px; line-height:1.5; padding:20px; }
h1 { font-size:1.5rem; margin:0 0 .2em; }
h2 { font-size:1.1rem; margin:1.6em 0 .5em; border-bottom:1px solid #2a2c38; padding-bottom:.2em; }
.meta { color:#8b8ea0; font-size:.82rem; }
.banner { background:#1f212b; padding:.7em .9em; border-radius:6px; margin:.8em 0; border-left:3px solid #4a5d8a; }
.warn { border-left-color:#a35; }
table { border-collapse:collapse; width:100%; background:#1b1d26; border-radius:6px; overflow:hidden; }
th,td { text-align:left; padding:6px 9px; border-bottom:1px solid #2a2c38; vertical-align:top; }
th { color:#8b8ea0; font-weight:normal; font-size:.76rem; text-transform:uppercase; letter-spacing:.04em; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
td.miss { color:#766; }
.sw { display:inline-block; width:13px; height:13px; border-radius:2px;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.12); vertical-align:middle; margin-right:5px; }
.sw-row { display:flex; gap:0; border-radius:3px; overflow:hidden; height:18px; box-shadow:inset 0 0 0 1px rgba(255,255,255,.08); }
.sw-row span { flex:1; }
.pos { color:#9ad; } .neg { color:#dab; }
.bar-track { width:80px; display:inline-block; background:#2a2c38; border-radius:2px; height:9px; vertical-align:middle; overflow:hidden; }
.bar-fill { height:100%; background:#6a86c8; }
.foot { color:#8b8ea0; font-size:.75rem; margin-top:2em; border-top:1px solid #2a2c38; padding-top:.6em; }
ul.caveats { margin:.3em 0; padding-left:1.2em; } ul.caveats li { margin:.25em 0; }
"""


def _ref_doc(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_REF_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


def _sw(hex_color: str | None, label: str = "") -> str:
    if not hex_color:
        return f'<span class="meta">-</span>'
    return f'<span class="sw" style="background:{hex_color}" title="{_esc(label)}"></span>{_esc(label)}'


def _fmt_v(v) -> str:
    if v is None:
        return '<span class="meta">-</span>'
    if isinstance(v, float):
        s = f"{v:.3f}".rstrip("0").rstrip(".") or "0"
        return _esc(s)
    return _esc(str(v))


def _warm_cool_cell(score) -> str:
    if score is None:
        return '<span class="meta">-</span>'
    # map [-1,1] to a bar width and colour sign
    pct = abs(score) * 100
    cls = "pos" if score >= 0 else "neg"
    return (
        f'<span class="{cls}">{score:+.2f}</span> '
        f'<span class="bar-track"><span class="bar-fill" style="width:{pct:.0f}%"></span></span>'
    )


def reference_comparison_html(c: dict, analyses: dict[str, dict]) -> str:
    """Side-by-side comparison page.  Fixed order, NOT a ranking."""
    stems = c["references"]
    title = "Reference theme comparison -- grotto (Phase 3)"
    head = (
        "<h1>Reference theme comparison</h1>"
        f"<div class='meta'>{_esc(c['ordering_note'])}</div>"
        f"<div class='meta'>{_esc(c['comparison_basis'])}</div>"
        '<div class="banner">Descriptive only. No ranking, scoring, or winner is declared '
        "(DESIGN.md section 1).</div>"
    )

    # --- main metrics table -------------------------------------------------
    head_cells = "<th class='num'>metric</th>" + "".join(f"<th>{_esc(s)}</th>" for s in stems)
    rows_html = []
    for r in c["table"]:
        cells = f"<td>{_esc(r['label'])}</td>"
        for s in stems:
            v = r.get(s)
            if r["key"] in ("warm_cool",):
                cells += f"<td class='num'>{_warm_cool_cell(v)}</td>"
            elif r["key"] in ("bg_class", "bg_h", "roles_present"):
                cells += f"<td>{_fmt_v(v)}</td>"
            else:
                cells += f"<td class='num'>{_fmt_v(v)}</td>"
        rows_html.append(f"<tr>{cells}</tr>")
    table = (
        "<table><tr>" + head_cells + "</tr>" + "".join(rows_html) + "</table>"
        + "<p class='meta'>Warm/cool score: +warm / -cool (chroma-weighted, OKLCH hue convention; "
        "see reference_analysis.warm_cool_balance). Spectral columns are nominal-display, "
        "within-model, exploratory (R-4, R-5, R-13). APCA is experimental (R-11).</p>"
    )

    # --- swatch comparison: bg/fg + key chromatic roles ---------------------
    key_roles = ("bg", "fg", "keyword", "string", "type", "function",
                 "error", "warning", "diff_added", "diff_removed")
    sw_head = "<th>reference</th><th>bg</th><th>fg</th>" + "".join(
        f"<th>{_esc(r)}</th>" for r in key_roles[2:]
    )
    sw_rows = []
    for s in stems:
        pal = analyses[s]
        bg_hex = (pal["background"].get("bg") or {}).get("hex")
        fg_hex = (pal.get("reading_contrast") or {}).get("fg_hex")
        cells = f"<td><b>{_esc(s)}</b></td>"
        cells += f"<td>{_sw(bg_hex)}</td><td>{_sw(fg_hex)}</td>"
        for role in key_roles[2:]:
            # find the role's hex from the per-role warm/cool map, else skip
            hx = pal["warm_cool_balance"]["per_role"].get(role, {}).get("hex")
            cells += f"<td>{_sw(hx) if hx else '<span class=meta>-</span>'}</td>"
        sw_rows.append(f"<tr>{cells}</tr>")
    swatch_table = (
        "<h2>Swatch comparison (dark variant)</h2>"
        "<table><tr>" + sw_head + "</tr>" + "".join(sw_rows) + "</table>"
        "<p class='meta'>Swatches use the reference's own hex for each role that is "
        "both mapped and chromatic (hue lookup comes from the warm/cool per-role map, "
        "which excludes near-achromatic colours); a role that is unmapped OR mapped "
        "but achromatic shows '-'. Selection/diff alpha hexes are base-stripped.</p>"
    )

    # --- mapping completeness ----------------------------------------------
    map_rows = []
    for s in stems:
        m = c["mapping_completeness"][s]
        miss = m["roles_missing"]
        shown = ", ".join(miss[:12])
        more = f" <span class='meta'>(+{len(miss)-12} more)</span>" if len(miss) > 12 else ""
        norm = ", ".join(m["normalized_alpha_roles"]) or '<span class="meta">none</span>'
        map_rows.append(
            f"<tr><td><b>{_esc(s)}</b></td>"
            f"<td class='num'>{m['present']}/{m['total_spec_roles']}</td>"
            f"<td class='num'>{(m['fraction'] or 0)*100:.0f}%</td>"
            f"<td class='miss'>{_esc(shown) if shown else '-'}{more}</td>"
            f"<td>{norm}</td></tr>"
        )
    mapping_table = (
        "<h2>Mapping completeness (spec has "
        f"{c['n_spec_roles']} roles)</h2>"
        "<table><tr><th>reference</th><th class='num'>mapped</th><th class='num'>coverage</th>"
        "<th>missing roles (sample)</th><th>alpha-normalised</th></tr>"
        + "".join(map_rows) + "</table>"
        "<p class='meta'>Coverage reflects how many spec roles the reference maps, not theme "
        "quality. References predate this spec and use their own role vocabularies; low coverage "
        "is mapping incompleteness. 'alpha-normalised' lists roles whose 8-digit hex was "
        "base-stripped to 6-digit on load (canonical files are unchanged).</p>"
    )

    # --- variant / source ambiguity ----------------------------------------
    amb_rows = []
    for s in stems:
        amb = c["variant_ambiguity"][s]
        extras = ", ".join(amb["extra_variant_labels"]) or "none"
        amb_rows.append(
            f"<tr><td><b>{_esc(s)}</b></td><td>{_esc(extras)}</td>"
            f"<td class='num'>{_esc(amb['source_url'])}</td></tr>"
        )
    amb_table = (
        "<h2>Variant / source ambiguity</h2>"
        "<table><tr><th>reference</th><th>extra variants in file</th><th>source URL</th></tr>"
        + "".join(amb_rows) + "</table>"
        "<p class='meta'>Some files carry a light variant (Solarized roles_light; Rose Pine dawn). "
        "Only the dark block every file shares is compared here; light variants are recorded but "
        "excluded (mixing polarities would be a category error).</p>"
    )

    caveats = "<h2>Caveats</h2><ul class='caveats'>" + "".join(
        f"<li>{_esc(cv)}</li>" for cv in c["caveats"]
    ) + "</ul>"

    foot = (
        '<div class="foot">Generated by grotto Phase 3 reference analysis. '
        "Reproducible: identical inputs produce byte-identical output. "
        "Reference themes are inputs only; none is a candidate palette.</div>"
    )
    return _ref_doc(title, head + table + swatch_table + mapping_table + amb_table + caveats + foot)


def reference_analysis_html(a: dict) -> str:
    """A single self-contained HTML page for one reference's analysis."""
    ref = a["reference"]
    bg = a["background"]
    rc = a.get("reading_contrast") or {}
    title = f"{ref['name']} ({ref['label']}) -- reference analysis"
    amb = ""
    if ref["source_ambiguous"]:
        amb = f"<div class='meta'>file also carries: {_esc(', '.join(ref['extra_variant_labels']))}</div>"
    head = (
        f"<h1>{_esc(ref['name'])} <span class='meta'>({_esc(ref['label'])})</span></h1>"
        f"<div class='meta'>{_esc(ref['source_url'])}</div>{amb}"
        f"<div class='meta'>mapping {_esc(ref['roles_present_count'])}/"
        f"{_esc(ref['mapping_completeness']['total_spec_roles'])} spec roles "
        f"({(ref['mapping_completeness']['fraction'] or 0)*100:.0f}%)</div>"
        '<div class="banner">Reference theme -- NOT a candidate palette. Descriptive analysis '
        "only; no ranking (DESIGN.md section 1).</div>"
    )

    sec = []
    # background
    bg_rows = []
    for role in ("bg", "bg_elevated", "bg_overlay"):
        b = bg.get(role)
        if not b:
            continue
        h = f"{b['h']:.0f}&deg;" if b["h_meaningful"] else "achromatic"
        bg_rows.append(
            f"<tr><td>{_esc(role)}</td><td>{_sw(b['hex'])}</td>"
            f"<td class='num'>{b['L']:.3f}</td><td class='num'>{b['C']:.3f}</td>"
            f"<td>{h}</td><td>{_esc(b['classification'])}</td></tr>"
        )
    sec.append("<h2>Background (OKLCH)</h2>" + "<table><tr><th>role</th><th>hex</th>"
               "<th class='num'>L</th><th class='num'>C</th><th>hue</th><th>class</th></tr>"
               + "".join(bg_rows) + "</table>"
               + f"<p class='meta'>{_esc(bg['note'])}</p>")

    # reading contrast
    if rc:
        sec.append("<h2>Reading contrast (fg vs bg)</h2>"
                   f"<table>"
                   f"<tr><th>WCAG</th><th>AA body</th><th>AA large</th>"
                   f"<th class='num'>|APCA Lc|</th><th>APCA band</th><th class='num'>OKLab dL</th></tr>"
                   f"<tr><td class='num'>{rc['wcag_ratio']:.2f}</td>"
                   f"<td>{'yes' if rc['wcag_aa_body'] else 'no'}</td>"
                   f"<td>{'yes' if rc['wcag_aa_large'] else 'no'}</td>"
                   f"<td class='num'>{abs(rc['apca_lc']):.0f}</td>"
                   f"<td>{_esc(rc.get('apca_measured_band'))}</td>"
                   f"<td class='num'>{rc['oklab_dl']:+.3f}</td></tr></table>"
                   f"<p class='meta'>{_esc(rc['apca_note'])}</p>")

    # distributions
    dist = a["distributions"]
    drows = ""
    for scope in ("all_roles", "excluding_backgrounds"):
        d = dist[scope]
        ll, cc = d["lightness"], d["chroma"]
        drows += (
            f"<tr><td>{_esc(scope)}</td>"
            f"<td class='num'>{ll['min']:.3f}</td><td class='num'>{ll['median']:.3f}</td>"
            f"<td class='num'>{ll['max']:.3f}</td>"
            f"<td class='num'>{cc['min']:.3f}</td><td class='num'>{cc['median']:.3f}</td>"
            f"<td class='num'>{cc['max']:.3f}</td></tr>"
        )
    sec.append("<h2>Lightness / chroma distributions</h2>"
               "<table><tr><th>scope</th><th class='num'>L min</th><th class='num'>L med</th>"
               "<th class='num'>L max</th><th class='num'>C min</th><th class='num'>C med</th>"
               "<th class='num'>C max</th></tr>" + drows + "</table>"
               f"<p class='meta'>{_esc(dist['sample_note'])}</p>")

    # warm/cool
    wc = a["warm_cool_balance"]
    sec.append("<h2>Warm/cool balance</h2>"
               f"<p>chroma-weighted score: {_warm_cool_cell(wc['chroma_weighted_score'])}</p>"
               f"<p class='meta'>warm ({wc['n_warm_roles']}): {_esc(', '.join(wc['warm_roles']) or '-')}"
               f"<br>cool ({wc['n_cool_roles']}): {_esc(', '.join(wc['cool_roles']) or '-')}"
               f"<br>neutral ({wc['n_neutral_roles']}): {_esc(', '.join(wc['neutral_roles']) or '-')}"
               " &larr; hue exactly on the 150/330&deg; boundary</p>"
               f"<p class='meta'>{_esc(wc['definition'])}</p>")

    # constraint coverage
    cs = a["constraints"]
    crows = "".join(
        f"<tr><td>{_esc(kind)}</td><td class='num'>{cs[kind]['present_pairs']}/"
        f"{cs[kind]['declared_pairs']}</td><td class='num'>"
        f"{(cs[kind]['coverage_fraction'] or 0)*100:.0f}%</td></tr>"
        for kind in ("must_distinguish", "should_distinguish", "same_family",
                     "differentiated_by", "redundant_encoding")
    )
    sec.append("<h2>Declared-constraint coverage</h2>"
               "<table><tr><th>kind</th><th class='num'>present/declared</th>"
               "<th class='num'>coverage</th></tr>" + crows + "</table>"
               f"<p class='meta'>{_esc(cs['note'])}</p>")

    # spectral
    sp = a.get("spectral") or {}
    if sp and "melanopic_ratio" in sp:
        sec.append("<h2>Spectral (nominal display, exploratory)</h2>"
                   f"<table><tr><th class='num'>mel ratio</th><th class='num'>bg share</th>"
                   f"<th class='num'>fg share</th><th class='num'>token share</th></tr>"
                   f"<tr><td class='num'>{sp['melanopic_ratio']:.3f}</td>"
                   f"<td class='num'>{sp['background_share']*100:.1f}%</td>"
                   f"<td class='num'>{sp['foreground_share']*100:.1f}%</td>"
                   f"<td class='num'>{sp['token_share']*100:.1f}%</td></tr></table>"
                   f"<p class='meta'>{_esc(sp['caveat'])}</p>")

    # cvd
    cvd = a["cvd"]
    cvd_rows = "".join(
        f"<tr><td>{_esc(pr['a'])} / {_esc(pr['b'])}</td>"
        f"<td class='num'>{pr['normal_de']:.3f}</td>"
        f"<td class='num'>{pr['cvd_dichromat_de']['protan']:.3f}</td>"
        f"<td class='num'>{pr['cvd_dichromat_de']['deutan']:.3f}</td>"
        f"<td class='num'>{pr['cvd_dichromat_de']['tritan']:.3f}</td>"
        f"<td>{'collapses' if pr['collapses_below_floor'] else '-'}</td></tr>"
        for pr in cvd["pairs"]
    )
    sec.append("<h2>CVD (must_distinguish pairs present)</h2>"
               "<table><tr><th>pair</th><th class='num'>normal dE</th>"
               "<th class='num'>protan</th><th class='num'>deutan</th><th class='num'>tritan</th>"
               "<th>below floor</th></tr>" + cvd_rows + "</table>"
               f"<p class='meta'>{_esc(cvd['note'])}</p>")

    caveats = "<h2>Caveats</h2><ul class='caveats'>" + "".join(
        f"<li>{_esc(cv)}</li>" for cv in a["caveats"]) + "</ul>"
    foot = (
        '<div class="foot">Generated by grotto Phase 3 reference analysis. '
        "Reproducible: identical inputs produce byte-identical output.</div>"
    )
    return _ref_doc(title, head + "".join(sec) + caveats + foot)


def reference_comparison_svg(analyses: dict[str, dict], order: list[str]) -> str:
    """A self-contained SVG strip comparing every reference's key colours.

    One row per reference (in the fixed ``order``); each row shows the bg
    swatch, fg swatch, and the syntax/diagnostic roles that are both mapped
    and chromatic in that reference. A role that is unmapped OR mapped but
    achromatic shows '-' (its hex never enters the chromatic per-role map).
    Deterministic; no external resources.
    """
    key_roles = ("keyword", "string", "type", "function", "number",
                 "constant", "error", "warning", "diff_added", "diff_removed")
    n = len(order)
    row_h = 46
    pad = 10
    label_w = 110
    chip_w = 42
    # each row: bg + fg + up to len(key_roles) chips
    cols = 2 + len(key_roles)
    total_w = label_w + cols * (chip_w + pad) + pad
    total_h = 2 * row_h + n * row_h + pad
    bg_chrome = "#15161c"
    fg_chrome = "#d7d9e2"
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{total_w}" height="{total_h}" '
        f'font-family="ui-monospace,monospace" font-size="11">'
        f'<rect width="100%" height="100%" fill="{bg_chrome}"/>'
    ]
    # column headers
    parts.append(f'<text x="{pad}" y="20" fill="{fg_chrome}">reference</text>')
    x = label_w + pad
    for i, role in enumerate(("bg", "fg") + key_roles):
        parts.append(
            f'<text x="{x + i*(chip_w+pad) + 3}" y="20" fill="#8b8ea0">{_esc(role)}</text>'
        )
    # rows
    for ri, stem in enumerate(order):
        a = analyses[stem]
        y = 2 * row_h + ri * row_h
        parts.append(f'<text x="{pad}" y="{y + row_h//2 + 4}" fill="{fg_chrome}">{_esc(stem)}</text>')
        bg_hex = (a["background"].get("bg") or {}).get("hex")
        fg_hex = (a.get("reading_contrast") or {}).get("fg_hex")
        chips = [bg_hex, fg_hex] + [
            a["warm_cool_balance"]["per_role"].get(r, {}).get("hex") for r in key_roles
        ]
        for ci, hx in enumerate(chips):
            cx = label_w + pad + ci * (chip_w + pad)
            if hx:
                parts.append(
                    f'<rect x="{cx}" y="{y + 8}" width="{chip_w}" height="{row_h - 16}" '
                    f'fill="{hx}" rx="2" />'
                )
                parts.append(
                    f'<text x="{cx + 3}" y="{y + row_h - 12}" fill="#8b8ea0" font-size="8">{_esc(hx)}</text>'
                )
            else:
                parts.append(
                    f'<text x="{cx + chip_w//2 - 2}" y="{y + row_h//2 + 3}" fill="#555">-</text>'
                )
    parts.append("</svg>")
    return "".join(parts)
