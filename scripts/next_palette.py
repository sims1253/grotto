"""Generate six restrained review palettes with a bounded, preference-led search.

Run from the repository root: uv run python scripts/next_palette.py
The authored directions and loss weights are design choices, not scientific constants.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from html import escape
import hashlib
import json
from pathlib import Path
import shutil

import yaml

from grotto import vscode, zed
from grotto.candidate_report import _scoped_css, _specimen_cell
from grotto.color import hex_to_oklch, max_chroma, oklch_to_hex
from grotto.contrast import wcag_contrast
from grotto.cvd import simulate
from grotto.distance import delta_e_ok
from grotto.model import CO_OCCURRING_SURFACES
from grotto.spec import Palette, RoleSpec
from grotto.specimens import specimen

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'out/next-generation'
ROLES = RoleSpec.load(ROOT / 'spec/roles.yaml')
FLOORS = yaml.safe_load((ROOT / 'spec/environments.yaml').read_text())['accessibility_floors']
GROUPS = {
    'keyword': ('keyword',),
    'function': ('function', 'builtin'),
    'string': ('string',),
    'number': ('number', 'constant', 'decorator'),
    'type': ('type', 'namespace', 'tag'),
}
PROFILES = {
    'cove': {'hues': (295, 225, 145, 80, 190), 'canvas_hue': 245,
             'description': 'Blue functions, green strings, lilac keywords.'},
    'grove': {'hues': (85, 155, 200, 45, 260), 'canvas_hue': 110,
              'description': 'Amber keywords, green functions, blue-green strings.'},
    'dusk': {'hues': (285, 335, 90, 40, 195), 'canvas_hue': 310,
             'description': 'Plum functions, purple keywords, gold strings.'},
}
PAIRS = (('keyword', 'function'), ('keyword', 'string'),
         ('function', 'string'), ('number', 'type'))
LANGUAGES = ('r', 'typescript', 'python')
# Visible non-whitespace character counts approximate ink area at a fixed monospace size.
# These are composition weights, not a model of attention or fatigue.
COUNTS = {lang: Counter() for lang in LANGUAGES}
for lang in LANGUAGES:
    for role, text in specimen(lang).spans():
        COUNTS[lang][role] += sum(not c.isspace() for c in text)


def floor_for(role):
    key = ROLES.roles[role].accessibility_floor
    return float(FLOORS.get({'body_text': 'body_text_wcag', 'non_text': 'non_text_wcag'}.get(key), 0))


def surfaces(colors):
    return ['bg', 'bg_elevated', 'bg_overlay', *CO_OCCURRING_SURFACES]


@lru_cache(maxsize=32768)
def color(L, C, h):
    return oklch_to_hex((L, min(C, max_chroma(L, h) * 0.75), h % 360))


def repair_ink(lch, variant, backgrounds, floor):
    """Move only lightness until the shipped hex passes, with 0.1 ratio headroom."""
    L, C, h = lch
    direction = 1 if variant == 'night' else -1
    for _ in range(201):
        hx = color(L, C, h)
        if all(wcag_contrast(hx, bg) >= floor + 0.1 for bg in backgrounds):
            return hx
        L += direction * 0.002
        if not 0 <= L <= 1:
            break
    raise ValueError(f'Cannot repair ink {lch} for {variant}')


def seed_colors(profile, variant):
    """Author surfaces and semantic colors directly, then repair foreground contrast."""
    p = PROFILES[profile]
    dark = variant == 'night'
    base = Palette.from_yaml(ROOT / f'themes/candidates/candidate-b-balanced.{variant}.yaml')
    raw = {r: hex_to_oklch(hx) for r, hx in base.items()}
    h = p['canvas_hue']
    raw.update({
        'bg': (0.225 if dark else 0.974, 0.006, h),
        'bg_elevated': (0.26 if dark else 0.987, 0.005, h),
        'bg_overlay': (0.29 if dark else 0.995, 0.002, h),
        'active_line': (0.25 if dark else 0.95, 0.006, h),
        'selection': (0.33 if dark else 0.89, 0.026, 245),
        'search_match': (0.285 if dark else 0.94, 0.02, 85),
        'search_match_current': (0.35 if dark else 0.89, 0.042, 85),
        'diff_added': (0.265 if dark else 0.94, 0.022, 145),
        'diff_removed': (0.30 if dark else 0.91, 0.022, 25),
        'diff_changed': (0.28 if dark else 0.93, 0.025, 85),
        'debug_current': (0.32 if dark else 0.92, 0.025, 85),
    })
    for role in ['fg', 'parameter', 'property', 'line_number_active']:
        raw[role] = (0.79 if dark else 0.43, 0.007, h)
    for role in ['comment', 'docstring', 'fg_secondary', 'deprecated']:
        raw[role] = (0.67 if dark else 0.49, 0.012, h)
    for role in ['punctuation', 'operator']:
        raw[role] = (0.72 if dark else 0.47, 0.006, h)
    for role in ['fg_muted', 'line_number', 'ui_inactive']:
        raw[role] = (0.59 if dark else 0.55, 0.008, h)
    for role, hue in [('error', 25), ('warning', 85), ('success', 145),
                      ('info', 235), ('focus', 235), ('breakpoint', 25)]:
        raw[role] = (0.78 if dark else 0.46, 0.105 if role == 'error' else 0.085, hue)
    colors = {r: color(*lch) for r, lch in raw.items()}
    bg = [colors[r] for r in surfaces(colors)]
    for r in ROLES:
        floor = floor_for(r.name)
        if floor:
            refs = bg if r.paint == 'ink' else [colors[r.contrast_reference or 'bg']]
            colors[r.name] = repair_ink(raw[r.name], variant, refs, floor)
    return colors


def shortfall(distance, target=0.07):
    return max(0.0, 1.0 - distance / target) ** 2


def loss(colors, anchors):
    # No reward for extra separation, including the tie-break. No number/constant floor.
    separation = sum(shortfall(delta_e_ok(colors[a], colors[b])) for a, b in PAIRS) / len(PAIRS)
    departure = sum((delta_e_ok(colors[g], anchors[g]) / 0.06) ** 2 for g in GROUPS) / len(GROUPS)
    emphasis = []
    for counts in COUNTS.values():
        total = sum(counts[r] for members in GROUPS.values() for r in members)
        penalty = sum(counts[r] * (max(0, hex_to_oklch(colors[r])[1] - 0.065) / 0.035) ** 2
                      for members in GROUPS.values() for r in members)
        emphasis.append(penalty / total)
    return separation + 0.25 * departure + 0.18 * max(emphasis)


def build_palette(profile, variant, passes=8):
    colors = seed_colors(profile, variant)
    bg = tuple(colors[r] for r in surfaces(colors))
    raw = {}
    for (g, members), hue in zip(GROUPS.items(), PROFILES[profile]['hues']):
        raw[g] = (0.78 if variant == 'night' else 0.48, 0.078 if variant == 'night' else 0.09, hue)
        hx = repair_ink(raw[g], variant, bg, max(floor_for(r) for r in members))
        colors.update({r: hx for r in members})
    anchors = dict(colors)
    score = loss(colors, anchors)
    initial_score = score
    for step in (1.0, 0.5):
        for _ in range(passes):
            changed = False
            for g, members in GROUPS.items():
                best = None
                for axis, amount in [(0, -.01), (0, .01), (1, -.008), (1, .008), (2, -4), (2, 4)]:
                    trial = list(raw[g]); trial[axis] += step * amount
                    seed_L, _, seed_h = (0.78 if variant == 'night' else 0.48, 0, PROFILES[profile]['hues'][list(GROUPS).index(g)])
                    if not (abs(trial[0] - seed_L) <= .04 and .035 <= trial[1] <= .10 and abs(trial[2] - seed_h) <= 16):
                        continue
                    hx = repair_ink(tuple(trial), variant, bg, max(floor_for(r) for r in members))
                    candidate = {**colors, **{r: hx for r in members}}
                    candidate_score = loss(candidate, anchors)
                    if candidate_score < score - 1e-10 and (best is None or candidate_score < best[0]):
                        best = candidate_score, tuple(trial), candidate
                if best:
                    score, raw[g], colors = best
                    changed = True
            if not changed:
                break
    palette = Palette(f'{profile}-{variant}', variant, colors, meta={'candidate': False})
    metrics = audit(palette)
    if metrics['contrast_failures']:
        raise ValueError(metrics['contrast_failures'])
    metrics.update(initial_loss=round(initial_score, 6), final_loss=round(score, 6))
    return palette, metrics


def audit(palette):
    pairs = []
    for role in ROLES:
        floor = floor_for(role.name)
        if not floor:
            continue
        refs = surfaces(palette.colors) if role.paint == 'ink' else [role.contrast_reference or 'bg']
        for ref in refs:
            ratio = wcag_contrast(palette[role.name], palette[ref])
            pairs.append({'ink': role.name, 'surface': ref, 'ratio': round(ratio, 4), 'floor': floor})
    return {
        'contrast_failures': [p for p in pairs if p['ratio'] < p['floor']],
        'contrast_pairs_checked': len(pairs),
        'minimum_body_text_contrast': min(p['ratio'] for p in pairs if p['floor'] == FLOORS['body_text_wcag']),
        'fg_on_selection': round(wcag_contrast(palette['fg'], palette['selection']), 4),
        'max_syntax_chroma': round(max(hex_to_oklch(palette[r])[1] for members in GROUPS.values() for r in members), 5),
        'diagnostic_distances': {view: round(delta_e_ok(simulate(palette['error'], view, 1), simulate(palette['warning'], view, 1)), 4)
                                 for view in ('protan', 'deutan', 'tritan')},
        'lowest_body_text_pairs': sorted((p for p in pairs if p['floor'] == FLOORS['body_text_wcag']), key=lambda p: p['ratio'])[:5],
    }


def composite(foreground, background):
    """Resolve a theme RGBA overlay over an opaque sRGB canvas."""
    alpha = int(foreground[7:9], 16) / 255 if len(foreground) == 9 else 1.0
    channels = [round(alpha * int(foreground[i:i + 2], 16) + (1 - alpha) * int(background[i:i + 2], 16)) for i in (1, 3, 5)]
    return '#' + ''.join(f'{c:02x}' for c in channels)


def editor_audit(palette, vs_theme, zed_theme):
    """Check ordinary editor text backgrounds, including nested VS Code diff washes.

    This models sRGB background composition, not screenshot antialiasing or every
    possible editor state. Low-opacity inactive text and collaboration cursors
    are outside this bounded check.
    """
    backgrounds = {}
    for key, hx in vs_theme['colors'].items():
        if (key.startswith(('editor.', 'diffEditor.')) and key.lower().endswith('background')) or key == 'editorBracketMatch.background':
            backgrounds['vscode:' + key] = composite(hx, palette['bg'])
    for mode in ('inserted', 'removed'):
        line = vs_theme['colors'][f'diffEditor.{mode}LineBackground']
        word = vs_theme['colors'][f'diffEditor.{mode}TextBackground']
        backgrounds[f'vscode:{mode}-nested'] = composite(word, composite(line, palette['bg']))
    for key, hx in zed_theme['style'].items():
        if isinstance(hx, str) and ((key.startswith('editor.') and key.endswith('background')) or key in ('search.match_background', 'created.background', 'deleted.background', 'modified.background')):
            backgrounds['zed:' + key] = composite(hx, palette['bg'])
    failures = []
    minimum = float('inf')
    for role in ROLES:
        if role.paint != 'ink' or not floor_for(role.name):
            continue
        for key, bg in backgrounds.items():
            ratio = wcag_contrast(palette[role.name], bg)
            if floor_for(role.name) == FLOORS['body_text_wcag']:
                minimum = min(minimum, ratio)
            if ratio < floor_for(role.name):
                failures.append(f'{role.name} on {key}: {ratio:.3f}')
    return {'backgrounds_checked': len(backgrounds), 'minimum_body_text_contrast': round(minimum, 4), 'failures': failures}


def write_preview(palettes, out=OUT, profiles=PROFILES, intro=None, title="Grotto next generation"):
    OUT = out
    PROFILES = profiles
    css = '''body{margin:24px;background:#e8e8e8;color:#222;font:16px/1.5 system-ui,sans-serif}p{max-width:85ch}
    .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}h1{font-size:28px}h3{margin:0;padding:10px 14px;background:#ddd;color:#222;font-size:17px}
    article{background:var(--vbg);color:var(--vfg)}pre{font:13px/1.65 'DejaVu Sans Mono',monospace;margin:0;padding:14px;overflow:auto}
    .states{padding:0 14px 14px;font:13px/1.65 'DejaVu Sans Mono',monospace}.state{padding:6px 8px}.r-parameter{font-style:italic}select{font:inherit;padding:6px}
    .language[hidden]{display:none}@media(max-width:850px){.grid{grid-template-columns:minmax(0,1fr)}}'''
    body = '<h1>Grotto: next-generation palettes</h1><p>Three directions, each with Day and Night. Functions and builtins share a color. Numbers and constants share a color. These are code specimens, not editor screenshots.</p><p>Selection, search, and diff rows use opaque palette fills; editor overlays can differ. Every authored text/surface pair passes its configured contrast floor. Color-vision simulations remain checks, not certification.</p>'
    if intro is not None:
        body = '<h1>' + escape(title) + '</h1><p>' + escape(intro) + '</p><p>Browser code specimens, not editor screenshots. State rows use opaque fills; editor overlays can differ. Color-vision simulations are checks, not certification.</p><p><a href="../next-generation/comparison.html">Compare Cove, Grove and Dusk</a></p>'
        css += '.grid{grid-template-columns:repeat(' + str(len(PROFILES)) + ',minmax(0,1fr))}@media(max-width:850px){.grid{grid-template-columns:minmax(0,1fr)}}'
    body += '<label>Language <select id="language">' + ''.join(f'<option value="{x}">{x.title()}</option>' for x in LANGUAGES) + '</select></label> <label>View <select id="view">' + ''.join(f'<option value="{x}">{x.title()}</option>' for x in ['normal', 'protan', 'deutan', 'tritan']) + '</select></label>'
    for lang in LANGUAGES:
        body += f'<div class="language" data-language="{lang}"' + (' hidden' if lang != 'r' else '') + '>'
        for variant in ('night', 'day'):
            body += f'<section id="{variant}-{lang}"><h2>{variant.title()}</h2><div class="grid">'
            for profile in PROFILES:
                key = f'{profile}-{variant}'; pal = palettes[key]
                body += f'<article class="scope-{key}"><h3>Grotto {profile.title()} {variant.title()}</h3>' + _specimen_cell(specimen(lang), pal) + '<div class="states">'
                for role, text in [('selection', 'Selected: result = rolling_mean(values)'), ('search_match_current', 'Find: rolling_mean'), ('diff_added', '+ result = rolling_mean(values)'), ('diff_removed', '- result = mean(values)')]:
                    body += f'<div class="state surface-{role}"><span class="r-fg">{escape(text)}</span></div>'
                body += '<div class="state"><span class="r-error">× Error: missing argument</span><br><span class="r-warning">! Warning: unused value</span></div></div></article>'
            body += '</div></section>'
        body += '</div>'
    js = "document.getElementById('language').onchange=e=>document.querySelectorAll('.language').forEach(x=>x.hidden=x.dataset.language!==e.target.value);document.getElementById('view').onchange=e=>document.body.className='view-'+e.target.value;"
    (OUT / 'comparison.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>' + escape(title) + '</title><style>' + css + _scoped_css(palettes) + '</style><body class="view-normal">' + body + '<script>' + js + '</script></body></html>')


def main(out=OUT, profiles=PROFILES, builder=build_palette, generation='next-generation',
         title='Grotto Next Generation Preview', intro=None,
         note='Generated review palette; authored direction plus bounded shortfall/emphasis search.',
         extra_inputs=()):
    OUT = out
    PROFILES = profiles
    OUT.mkdir(parents=True, exist_ok=True)
    palettes = {}; evidence = {}; contributions = []; zthemes = []
    vm = vscode._load_mapping(ROOT / 'spec/mappings/vscode.yaml', ROLES)
    zm = zed._load_mapping(ROOT / 'spec/mappings/zed.yaml', ROLES)
    # A gutter marker needs an ink color, not the quiet fill used behind code.
    for name, role in [('added', 'success'), ('modified', 'warning'), ('deleted', 'error')]:
        vm.workbench[f'editorGutter.{name}Background'] = role
    for name, role in [('created', 'success'), ('modified', 'warning'), ('deleted', 'error')]:
        zm.style[name] = role
        zm.style[f'{name}.border'] = role
    zm.style['editor.document_highlight.write_background'] = {'role': 'selection', 'alpha': '4d'}
    vdir = OUT / 'vscode-preview'; (vdir / 'themes').mkdir(parents=True, exist_ok=True)
    zdir = OUT / 'zed-preview'; (zdir / 'themes').mkdir(parents=True, exist_ok=True)
    for profile in PROFILES:
        for variant in ('day', 'night'):
            pal, metrics = builder(profile, variant)
            key = pal.name; palettes[key] = pal
            data = {'name': key, 'variant': variant, 'format': 'oklch', 'candidate': False,
                    'note': note,
                    'colors': {r: dict(zip(('L', 'C', 'h'), hex_to_oklch(hx))) for r, hx in pal.items()}}
            path = OUT / f'{key}.yaml'; path.write_text(yaml.safe_dump(data, sort_keys=False))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            assert Palette.from_yaml(path).colors == pal.colors
            label = f'Grotto {profile.title()} {variant.title()}'
            theme = vscode._build_theme(pal, label, variant, vm, source_name=path.name, source_sha256=digest)
            theme['grotto'].update(candidate=False, note=data['note'])
            rel = f'themes/{key}.json'; (vdir / rel).write_text(vscode._dump(theme))
            contributions.append({'label': label, 'uiTheme': 'vs' if variant == 'day' else 'vs-dark', 'path': rel})
            ztheme = zed._build_theme(pal, {'label': label, 'variant': variant}, zm)
            zthemes.append(ztheme)
            metrics['editor_composites'] = editor_audit(pal, theme, ztheme)
            if metrics['editor_composites']['failures']:
                raise ValueError(metrics['editor_composites']['failures'])
            evidence[key] = {'source_sha256': digest, **metrics}
            print(key, 'min body contrast', metrics['minimum_body_text_contrast'], flush=True)
    (vdir / 'package.json').write_text(json.dumps({
        'name': 'grotto-' + generation, 'displayName': title,
        'description': intro or 'Cove, Grove, and Dusk in Day and Night. Experimental review themes.',
        'version': '0.1.0', 'publisher': 'grotto-local', 'license': 'MIT',
        'repository': {'type': 'git', 'url': 'https://github.com/sims1253/grotto.git'},
        'engines': {'vscode': '^1.80.0'}, 'categories': ['Themes'],
        'files': ['themes/*.json', 'README.md', 'LICENSE'], 'contributes': {'themes': contributions},
    }, indent=2) + '\n')
    shutil.copyfile(ROOT / 'LICENSE', vdir / 'LICENSE')
    (vdir / 'README.md').write_text('# Grotto next-generation preview\n\nChoose Grotto Cove, Grove, or Dusk from Preferences: Color Theme. Each has Day\nand Night versions. These are experimental palettes with manual switching.\n\nCove uses blue functions and green strings. Grove uses green functions and\namber keywords. Dusk uses plum functions and gold strings.\n\nReport readability problems with the theme name, language, font, and UI state.\n')
    (zdir / 'extension.toml').write_text(f'id = "grotto-{generation}"\nname = "{title}"\nversion = "0.1.0"\nschema_version = 1\nauthors = ["Maximilian Scholz"]\nrepository = "https://github.com/sims1253/grotto"\n')
    if intro is not None:
        (vdir / 'README.md').write_text(f'# {title}\n\n{intro}\n\nChoose a theme from Preferences: Color Theme. Each has Day and Night versions. Switching is manual. These are review themes.\n')
    (zdir / 'themes/grotto.json').write_text(zed._dump({'$schema': zed.SCHEMA, 'name': title.removesuffix(' Preview'), 'author': 'Maximilian Scholz', 'themes': zthemes}))
    (zdir / 'provenance.json').write_text(json.dumps({k: v['source_sha256'] for k, v in evidence.items()}, indent=2) + '\n')
    (OUT / 'metrics.json').write_text(json.dumps(evidence, indent=2) + '\n')
    inputs = ['scripts/next_palette.py', 'spec/roles.yaml', 'spec/environments.yaml', 'spec/mappings/vscode.yaml', 'spec/mappings/zed.yaml', 'src/grotto/specimens.py', 'themes/candidates/candidate-b-balanced.day.yaml', 'themes/candidates/candidate-b-balanced.night.yaml']
    (OUT / 'inputs.json').write_text(json.dumps({p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in [*inputs, *extra_inputs]}, indent=2) + '\n')
    write_preview(palettes, OUT, PROFILES, intro, title if intro else "Grotto next generation")


if __name__ == '__main__':
    main()
