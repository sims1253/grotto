"""Rebuild the bounded design review using the existing report renderer.

Run from the repository root: uv run python docs/review/build.py
"""
from pathlib import Path
import hashlib
import json
from html import escape

from grotto.candidate_report import _scoped_css, _specimen_cell
from grotto.spec import Palette
from grotto.specimens import specimen
from grotto.contrast import wcag_contrast

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent


def main():
    palettes = {}
    sources = {}
    labels = {}
    for letter, family in [('a', 'restrained'), ('b', 'balanced'), ('c', 'expressive')]:
        for variant in ['night', 'day', 'evening']:
            key = f'{family}-{variant}'
            path = ROOT / f'themes/candidates/candidate-{letter}-{family}.{variant}.yaml'
            palettes[key] = Palette.from_yaml(path)
            sources[key] = path
            labels[key] = f'{family.title()} {variant.title()}'
    for key, path, label in [
        ('middle', 'out/middle-night/middle-m01.night.yaml', 'Middle M01'),
        ('numeric', 'out/numeric-night/numeric-n01.night.yaml', 'Numeric N01'),
    ]:
        sources[key] = ROOT / path
        palettes[key] = Palette.from_yaml(sources[key])
        labels[key] = label
    sources['huerd'] = ROOT / 'out/huerd-night/results.json'
    result = next(r for r in json.loads(sources['huerd'].read_text())['results'] if r['id'] == 'h01-capped')
    palettes['huerd'] = Palette('h01-capped', 'night', {**palettes['balanced-night'].colors, **result['assignment']})
    labels['huerd'] = 'Huerd H01 capped'

    def card(key, language):
        pal = palettes[key]
        states = ''.join(
            f'<div class="state surface-{role}"><span class="r-fg">{escape(text)}</span></div>'
            for role, text in [('selection', 'Selected: result = rolling_mean(values)'),
                               ('search_match_current', 'Find: rolling_mean'),
                               ('diff_added', '+ result = rolling_mean(values)'),
                               ('diff_removed', '- result = mean(values)')]
        )
        return (f'<article class="scope-{key}"><h3>{labels[key]}</h3>'
                + _specimen_cell(specimen(language), pal)
                + '<div class="states">' + states
                + '<div class="state"><span class="r-error">× Error: missing argument</span>'
                + '<br><span class="r-warning">! Warning: unused value</span></div></div></article>')

    css = '''body{margin:24px;background:#e8e8e8;color:#222;font:16px/1.5 system-ui,sans-serif}
    h1{font-size:28px}h2{font-size:22px}h3{font-size:16px;margin:0;padding:10px 14px;background:#ddd;color:#222}
    p{max-width:85ch}select{font:inherit;padding:6px}a{color:inherit}.grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}
    article{background:var(--vbg);color:var(--vfg)}pre{font:13px/1.65 'DejaVu Sans Mono',monospace;margin:0;padding:14px;overflow:auto}
    .states{padding:0 14px 14px;font:13px/1.65 'DejaVu Sans Mono',monospace}.state{padding:5px 8px}.r-parameter{font-style:italic}
    section{margin:28px 0}.language[hidden]{display:none}@media(max-width:850px){.grid{grid-template-columns:minmax(0,1fr)}}
    '''
    groups = [
        ('canonical', 'Current Night families', ['restrained-night', 'balanced-night', 'expressive-night']),
        ('alternatives', 'Existing Night experiments', ['middle', 'numeric', 'huerd']),
        ('day', 'Current Day families', ['restrained-day', 'balanced-day', 'expressive-day']),
        ('evening', 'Current Evening families', ['restrained-evening', 'balanced-evening', 'expressive-evening']),
    ]
    body = '<h1>Grotto: choose a design direction</h1><p>Same code, type size, and state examples in every palette. These are browser specimens, not editor screenshots. State fills are opaque palette colors; editor alpha overlays and grammar assignments can differ.</p>'
    body += '<p>Start with the pictures, then read <a href="README.md">the design review</a>. The experiments cover Night only.</p>'
    body += '<label>Language <select id="language"><option value="r">R</option><option value="typescript">TypeScript</option></select></label> <label>View <select id="view"><option value="normal">Normal</option><option value="protan">Protan simulation</option><option value="deutan">Deutan simulation</option><option value="tritan">Tritan simulation</option></select></label>'
    body += '<p>Simulations expose potential color confusion; they do not reproduce individual vision. Text labels and +/− signs remain visible.</p>'
    for language in ['r', 'typescript']:
        body += f'<div class="language" data-language="{language}"' + (' hidden' if language != 'r' else '') + '>'
        for key, title, keys in groups:
            body += f'<section id="{key}-{language}"><h2>{title}</h2><div class="grid">' + ''.join(card(k, language) for k in keys) + '</div></section>'
        body += '</div>'
    js = '''document.getElementById('language').onchange=e=>document.querySelectorAll('.language').forEach(x=>x.hidden=x.dataset.language!==e.target.value);
    document.getElementById('view').onchange=e=>document.body.className='view-'+e.target.value;'''
    (OUT / 'comparison.html').write_text('<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Grotto design review</title><style>' + css + _scoped_css(palettes) + '</style><body class="view-normal">' + body + '<script>' + js + '</script></body></html>')
    evidence = {}
    for key, pal in palettes.items():
        evidence[key] = {
            'source': str(sources[key].relative_to(ROOT)),
            'sha256': hashlib.sha256(sources[key].read_bytes()).hexdigest(),
            'fg_on_bg': round(wcag_contrast(pal['fg'], pal['bg']), 2),
            'fg_on_selection': round(wcag_contrast(pal['fg'], pal['selection']), 2),
            'comment_on_bg': round(wcag_contrast(pal['comment'], pal['bg']), 2),
            'specimen_ink_min_on_bg': round(min(wcag_contrast(pal[r], pal['bg']) for lang in ['r', 'typescript'] for r in specimen(lang).roles_used()), 2),
        }
    evidence['huerd']['construction'] = 'Balanced Night plus h01-capped assignment; both source hashes are recorded above.'
    (OUT / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n')


if __name__ == '__main__':
    main()
