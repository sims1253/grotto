"""Deterministic Phase 4 family-build + comparison reports (text / HTML).

All output is reproducible: identical inputs produce byte-identical files (no
wall-clock timestamp).  The HTML is a single self-contained page with inline
CSS and no external resources, using a neutral dark chrome (it cannot adopt one
variant's palette because the point is to compare three side by side).

These renderers only FORMAT the dicts produced by ``grotto.model``; all the
numbers and caveats live there.  JSON/YAML reuse ``grotto.report.to_json`` /
``to_yaml``.
"""

from __future__ import annotations

from html import escape

from .render import on_text_threshold

# --------------------------------------------------------------------------
# small helpers (formatting stays local; the on-text ink DECISION is imported
# from render.py so chip text cannot disagree across report modules)
# --------------------------------------------------------------------------


def _esc(s) -> str:
    return escape(str(s), quote=True)


def _sw(hx: str | None, label: str = "") -> str:
    if not hx:
        return f'<span class="meta">-</span>'
    return f'<span class="sw" style="background:{hx}" title="{_esc(label)}"></span>{_esc(label)}'


_CSS = """
* { box-sizing:border-box; }
body { margin:0; background:#15161c; color:#d7d9e2;
  font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  font-size:13px; line-height:1.5; padding:20px; }
h1 { font-size:1.5rem; margin:0 0 .2em; }
h2 { font-size:1.1rem; margin:1.6em 0 .5em; border-bottom:1px solid #2a2c38; padding-bottom:.2em; }
h3 { font-size:.95rem; margin:1.2em 0 .4em; color:#aeb2c6; }
.meta { color:#8b8ea0; font-size:.82rem; }
.banner { background:#1f212b; padding:.7em .9em; border-radius:6px; margin:.8em 0; border-left:3px solid #4a5d8a; }
.warn { border-left-color:#a35; }
table { border-collapse:collapse; width:100%; background:#1b1d26; border-radius:6px; overflow:hidden; }
th,td { text-align:left; padding:5px 8px; border-bottom:1px solid #2a2c38; vertical-align:top; }
th { color:#8b8ea0; font-weight:normal; font-size:.76rem; text-transform:uppercase; letter-spacing:.04em; }
td.num, th.num { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
.sw { display:inline-block; width:13px; height:13px; border-radius:2px;
  box-shadow:inset 0 0 0 1px rgba(255,255,255,.12); vertical-align:middle; margin-right:5px; }
.strip { display:flex; flex-wrap:wrap; gap:2px; }
.strip span { display:flex; flex-direction:column; align-items:flex-start; justify-content:flex-end;
  width:78px; height:40px; padding:3px 5px; border-radius:3px; font-size:.7rem; }
.bad { color:#f88; } .ok { color:#9ad; } .flag { color:#dc8; }
.foot { color:#8b8ea0; font-size:.75rem; margin-top:2em; border-top:1px solid #2a2c38; padding-top:.6em; }
ul.caveats { margin:.3em 0; padding-left:1.2em; } ul.caveats li { margin:.25em 0; }
"""


def _doc(title: str, body: str) -> str:
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head>"
        f"<body>{body}</body></html>"
    )


# --------------------------------------------------------------------------
# text renderers
# --------------------------------------------------------------------------


def family_build_text(build) -> str:
    """Human-readable derivation summary for a FamilyBuild."""
    b = build.to_dict()
    lines = []
    cand = "CANDIDATE" if b["is_candidate"] else "NON-CANDIDATE"
    lines.append(f"# {b['name']}  ({cand})  ok={b['ok']}  input_hash={b['input_hash']}")
    if build.binding.meta.get("note"):
        lines.append(f"  note: {str(build.binding.meta['note']).strip()}")
    st = b.get("stability") or {}
    if st:
        lines.append(
            f"  stability: ok={st.get('ok')}  max_hue_drift={st.get('max_hue_drift_deg')}deg "
            f"(cap {st.get('drift_threshold_deg')})  cyclic_seq_preserved={st.get('cyclic_family_sequence_preserved')}  "
            f"normC_inversions={len(st.get('normalized_chroma_inversions', []))}  "
            f"salience_reversals={len(st.get('salience_proxy_reversals', []))}"
        )
    n_issues = len(b["issues"])
    lines.append(f"  issues: {n_issues} (aesthetic/distance/legibility misses; informational)")
    for v in ("day", "evening", "night"):
        if v not in b["variants"]:
            continue
        lines.append("")
        lines.append(f"## variant {v}")
        lines.append(f"{'role':16s} {'paint':7s} {'winning':13s} hex      "
                     f"{'L':>6s} {'C':>6s} {'h':>5s}  reqC   capC   realC  capL   gamL   frac")
        for role, t in b["variants"][v]["traces"].items():
            L, C, h = t["realized"]
            cl = t["chroma_losses"]
            lines.append(
                f"{role:16s} {t['paint']:7s} {t['winning_constraint']:13s} {t['final_hex']} "
                f"{L:6.3f} {C:6.3f} {h:5.0f}  {cl['requested']:.4f} {cl['capped']:.4f} "
                f"{cl['realized']:.4f} {cl['cap_loss']:.4f} {cl['gamut_loss']:.4f} {cl['realized_fraction']:.2f}"
                + (f"  conflicts={t['conflicts']}" if t["conflicts"] else "")
            )
    lines.append("")
    lines.append("ok = built without TransformError AND every ink/border final hex meets its WCAG floor.")
    lines.append("NON-CANDIDATE: no palette here is final (DESIGN.md section 1).")
    return "\n".join(lines) + "\n"


def comparison_text(cmp: dict) -> str:
    """Human-readable systematic-vs-hand-tuned comparison."""
    s = cmp["summary"]
    lines = [
        f"# systematic '{cmp['systematic']}' vs hand-tuned '{cmp['hand_tuned']}'",
        f"  roles compared : {s['n_roles_compared']} across {s['n_variants']} variants",
        f"  dE_OK mean/med/max : {s['de_mean']} / {s['de_median']} / {s['de_max']}",
        f"  threshold      : {s['threshold_de']}",
        f"  needing adjust : {s['n_needing_adjustment']} role(s)",
        f"  >> systematic needed hand adjustment: {s['systematic_needed_hand_adjustment']}",
    ]
    needing = cmp["needing_adjustment"]
    if needing:
        lines.append("")
        lines.append("## roles where a human corrected the systematic output (dE > threshold)")
        for r in sorted(needing, key=lambda x: -x["de"])[:25]:
            lines.append(
                f"  {r['variant']:8s} {r['role']:16s} dE={r['de']:.4f} "
                f"dL={r['dL']:+.3f} dC={r['dC']:+.3f} dh={r['dh']:+.1f}  "
                f"{r['systematic_hex']} -> {r['hand_hex']}"
            )
    lines.append("")
    lines.append(cmp["note"])
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------
# HTML renderer (self-contained comparison + derivation page)
# --------------------------------------------------------------------------


def _variant_strip(build, variant: str) -> str:
    pal = build.variants[variant].palette
    chips = []
    for role in sorted(pal.colors):
        hx = pal[role]
        # light/dark decision is the shared luminance threshold (formerly a
        # local OKLCH-L>0.55 rule that disagreed with the other renderers in
        # a mid-lightness band); the ink colours stay #000/#fff as before
        chips.append(
            f'<span style="background:{hx};color:{("#000" if on_text_threshold(hx) else "#fff")}">'
            f'{_esc(role)}</span>'
        )
    return f'<div class="strip">{"".join(chips)}</div>'


def _derivation_table(build, variant: str) -> str:
    rows = []
    for role, t in sorted(build.variants[variant].traces.items()):
        cl = t.chroma_losses
        L, C, h = t.realized
        conf = ", ".join(t.conflicts) if t.conflicts else ""
        rows.append(
            "<tr>"
            f'<td>{_sw(t.final_hex)}{_esc(role)}</td>'
            f"<td>{_esc(t.paint)}</td><td class='flag'>{_esc(t.winning_constraint)}</td>"
            f"<td class='num'>{cl['requested']:.4f}</td>"
            f"<td class='num'>{cl['capped']:.4f}</td>"
            f"<td class='num'>{cl['realized']:.4f}</td>"
            f"<td class='num'>{cl['cap_loss']:.4f}</td>"
            f"<td class='num'>{cl['gamut_loss']:.4f}</td>"
            f"<td class='num'>{cl['realized_fraction']:.2f}</td>"
            f"<td class='{'bad' if conf else 'meta'}'>{_esc(conf)}</td>"
            "</tr>"
        )
    return (
        "<table><tr><th>role</th><th>paint</th><th>winning constraint</th>"
        "<th class='num'>req C</th><th class='num'>capped C</th><th class='num'>realized C</th>"
        "<th class='num'>cap loss</th><th class='num'>gamut loss</th><th class='num'>frac</th>"
        "<th>conflicts</th></tr>" + "".join(rows) + "</table>"
    )


def _stability_block(st: dict) -> str:
    if not st:
        return ""
    cls = "ok" if st.get("ok") else "bad"
    return (
        f"<p>status: <b class='{cls}'>{'PASS' if st.get('ok') else 'ATTENTION'}</b> &middot; "
        f"max hue drift <b>{st.get('max_hue_drift_deg')}deg</b> (cap {st.get('drift_threshold_deg')}) &middot; "
        f"cyclic family sequence preserved: <b>{st.get('cyclic_family_sequence_preserved')}</b> &middot; "
        f"normalized-chroma inversions: <b>{len(st.get('normalized_chroma_inversions', []))}</b> &middot; "
        f"salience-proxy reversals: <b>{len(st.get('salience_proxy_reversals', []))}</b></p>"
        "<p class='meta'>Corrected checks (senior-review): normalized C/max_chroma ordering, "
        "cyclic family sequence, non-vacuous realized salience proxy, total hue drift including "
        "adjustments. Cross-variant dE is NOT a gate (Day/Night invert lightness by design).</p>"
    )


def family_build_html(build) -> str:
    b = build.to_dict()
    cand_banner = (
        '<div class="banner warn">NON-CANDIDATE Phase 4 experiment. No palette here is final '
        "(DESIGN.md section 1).</div>"
        if not b["is_candidate"]
        else ""
    )
    head = (
        f"<h1>{_esc(b['name'])} &mdash; environmental transform</h1>"
        f"<div class='meta'>input_hash <b>{b['input_hash']}</b> &middot; ok <b>{b['ok']}</b> "
        f"&middot; {len(b['issues'])} issue(s)</div>"
        + cand_banner
    )
    stab = f"<h2>Cross-variant stability</h2>{_stability_block(b.get('stability') or {})}"

    sections = [head, stab]
    for v in ("day", "evening", "night"):
        if v not in build.variants:
            continue
        sections.append(f"<h2>Variant: {v}</h2>")
        sections.append(f"<h3>palette</h3>{_variant_strip(build, v)}")
        sections.append(f"<h3>derivation provenance</h3>{_derivation_table(build, v)}")

    sections.append(
        "<h2>Caveats</h2><ul class='caveats'>"
        "<li>APCA is independent work in progress, not a W3C Recommendation or current WCAG criterion.</li>"
        "<li>WCAG overrides the Night foreground ceiling and the APCA preference; each override is recorded.</li>"
        "<li>Cap/gamut losses are reported independently; silent clipping is prohibited (DESIGN.md section 5).</li>"
        "<li>Ink-on-surface legibility is evaluated as issues, never raised.</li>"
        "</ul>"
    )
    foot = (
        '<div class="foot">Generated by grotto Phase 4 environmental transform. '
        "Reproducible: identical inputs produce byte-identical output.</div>"
    )
    return _doc(f"{b['name']} -- family build", "".join(sections) + foot)


def comparison_html(build, cmp: dict) -> str:
    s = cmp["summary"]
    verdict = (
        '<span class="ok">did NOT need hand adjustment</span>'
        if not s["systematic_needed_hand_adjustment"]
        else '<span class="bad">NEEDED hand adjustment</span>'
    )
    head = (
        f"<h1>Systematic vs hand-tuned</h1>"
        f"<div class='meta'>systematic <b>{_esc(cmp['systematic'])}</b> vs hand-tuned "
        f"<b>{_esc(cmp['hand_tuned'])}</b></div>"
        f"<div class='banner'>Verdict: the systematic transform {verdict}. "
        f"{s['n_needing_adjustment']} role(s) differ by more than dE {s['threshold_de']}; "
        f"dE mean {s['de_mean']} / median {s['de_median']} / max {s['de_max']}.</div>"
    )
    needing = sorted(cmp["needing_adjustment"], key=lambda x: -x["de"])
    rows = "".join(
        "<tr>"
        f"<td>{_esc(r['variant'])}</td><td>{_sw(r['systematic_hex'])}{_sw(r['hand_hex'])}{_esc(r['role'])}</td>"
        f"<td class='num'>{r['de']:.4f}</td><td class='num'>{r['dL']:+.3f}</td>"
        f"<td class='num'>{r['dC']:+.3f}</td><td class='num'>{r['dh']:+.1f}</td>"
        f"<td><span class='meta'>{r['systematic_hex']}</span> &rarr; {r['hand_hex']}</td></tr>"
        for r in needing[:60]
    ) or '<tr><td colspan="7" class="meta">no role exceeded the threshold</td></tr>'
    table = (
        "<h2>Roles needing hand adjustment (dE &gt; threshold)</h2>"
        "<table><tr><th>variant</th><th>role</th><th class='num'>dE_OK</th>"
        "<th class='num'>dL</th><th class='num'>dC</th><th class='num'>dh deg</th>"
        "<th>systematic &rarr; hand</th></tr>" + rows + "</table>"
    )
    # side-by-side night swatches for a quick visual check
    night_sys = build.variants.get("night")
    night_hand_rows = ""
    if night_sys:
        # the comparison carries per_role hand hex; build a quick lookup
        hand_hex = {(r["variant"], r["role"]): r["hand_hex"] for r in cmp["per_role"]}
        cells = ""
        for role in sorted(night_sys.palette.colors):
            sys_hx = night_sys.palette[role]
            h_hx = hand_hex.get(("night", role))
            cells += (
                f"<td>{_sw(sys_hx)}<br><span class='meta'>{_esc(role)}</span></td>"
                f"<td>{_sw(h_hx) if h_hx else '-'}</td>"
            )
        night_hand_rows = (
            "<h2>Night variant: systematic vs hand-tuned swatches</h2>"
            "<table><tr>" + cells + "</tr></table>"
        )
    note = f"<p class='meta'>{_esc(cmp['note'])}</p>"
    foot = (
        '<div class="foot">Generated by grotto Phase 4. Reproducible: identical inputs '
        "produce byte-identical output. NON-CANDIDATE experiment.</div>"
    )
    return _doc("systematic vs hand-tuned", head + table + night_hand_rows + note + foot)
