"""Four authored Grotto studies, each in Day and Night.

Run: uv run python scripts/study_palette.py
These are aesthetic experiments, not optimizer winners.
"""
from __future__ import annotations

import json

from grotto.color import hex_to_oklch
from grotto.spec import Palette
from grotto.specimens import specimen

import memory_palette as memory
import next_palette as ng

OUT = ng.ROOT / 'out/grotto-studies'
# Hue order: keyword, function, string, number, type. Separate Day/Night chroma.
PROFILES = {
    'tansy': {
        'hues': (85, 300, 165, 250, 45),
        'day_chroma': (.13, .17, .12, .15, .12),
        'night_chroma': (.12, .11, .095, .095, .10),
        'canvas': (110, .011), 'parameter_hue': 165, 'operator_hue': 300,
        'description': 'Golden keywords, violet functions, herb-green strings.',
    },
    'fig': {
        'hues': (325, 150, 85, 250, 205),
        'day_chroma': (.17, .14, .12, .15, .12),
        'night_chroma': (.12, .10, .115, .09, .085),
        'canvas': (310, .009), 'parameter_hue': 250, 'operator_hue': 150,
        'description': 'Plum keywords, green functions, golden strings.',
    },
    'rainstone': {
        'hues': (265, 50, 190, 320, 120),
        'day_chroma': (.18, .15, .12, .16, .12),
        'night_chroma': (.12, .12, .095, .105, .095),
        'canvas': (250, .008), 'parameter_hue': 265, 'operator_hue': 190,
        'description': 'Blue keywords, copper functions, teal strings.',
    },
    'lantern': {
        'hues': (195, 75, 125, 295, 250),
        'day_chroma': (.12, .14, .12, .17, .12),
        'night_chroma': (.10, .13, .10, .105, .085),
        'canvas': (75, .008), 'parameter_hue': 195, 'operator_hue': 125,
        'description': 'Teal keywords, amber functions, olive strings.',
    },
}
LANGUAGES = ('typescript', 'python', 'r', 'json', 'css')
INTRO = ('Four different uses of color from the Grotto setting. Tansy, Fig, '
         'Rainstone and Lantern each have Day and Night versions.')


def build_palette(profile, variant):
    p = PROFILES[profile]
    dark = variant == 'night'
    base, _ = memory.build_palette('stone', variant)
    raw = {r: hex_to_oklch(hx) for r, hx in base.items()}
    hue, chroma = p['canvas']
    for role, lightness in {
        'bg': .25 if dark else .975,
        'bg_elevated': .275 if dark else .987,
        'bg_overlay': .29 if dark else .995,
        'active_line': .27 if dark else .948,
    }.items():
        raw[role] = (lightness, chroma if dark else chroma * .7, hue)
    for role in ('fg', 'line_number_active'):
        raw[role] = (.825 if dark else .405, .016 if profile == 'fig' else .01, hue)
    for (group, members), h, c in zip(ng.GROUPS.items(), p['hues'], p['night_chroma' if dark else 'day_chroma']):
        for role in members:
            raw[role] = (.79 if dark else .49, c, h)
    for role in ('parameter', 'property'):
        raw[role] = (.77 if dark else .46, .055 if dark else .075, p['parameter_hue'])
    raw['operator'] = (.74 if dark else .455, .035 if dark else .05, p['operator_hue'])
    syntax_roles = {r for members in ng.GROUPS.values() for r in members} | {'parameter', 'property', 'operator'}
    fractions = {r: (.92 if dark else .98) if r in syntax_roles else .75 for r in raw}
    colors = {r: ng.color(*lch, fractions[r]) for r, lch in raw.items()}
    backgrounds = [colors[r] for r in ng.surfaces(colors)]
    for role in ng.ROLES:
        floor = ng.floor_for(role.name)
        if floor:
            refs = backgrounds if role.paint == 'ink' else [colors[role.contrast_reference or 'bg']]
            colors[role.name] = ng.repair_ink(raw[role.name], variant, refs, floor, fractions[role.name])
    palette = Palette(f'{profile}-{variant}', variant, colors, meta={'candidate': False})
    metrics = ng.audit(palette)
    if metrics['contrast_failures']:
        raise ValueError(metrics['contrast_failures'])
    metrics['authored_syntax'] = {
        r: {'requested': list(raw[r]), 'shipped': list(hex_to_oklch(colors[r]))}
        for r in sorted(syntax_roles)
    }
    return palette, metrics


def main():
    ng.main(OUT, PROFILES, build_palette, 'studies', 'Grotto Studies Preview', INTRO,
            'Authored Grotto study; contrast repaired after color assignment. No aesthetic score.',
            extra_inputs=('scripts/memory_palette.py', 'scripts/study_palette.py',
                          'src/grotto/color.py', 'src/grotto/contrast.py',
                          'src/grotto/vscode.py', 'src/grotto/zed.py'))
    role_preview = OUT / 'comparison.html'
    role_preview.write_text(role_preview.read_text().replace('repeat(4,minmax', 'repeat(2,minmax'))
    role_preview.replace(OUT / 'role-specimens.html')
    # CSS specimen is authored here because the toolkit does not include one.
    samples = {lang: specimen(lang).plaintext() for lang in LANGUAGES if lang != 'css'}
    samples['css'] = '''/* Shade beneath the vines */
:root {
  --leaf: #277647;
  --stone: #f4f5ec;
  --gap: 1.5rem;
}

.balcony {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--gap);
  color: var(--leaf);
  background: var(--stone);
}

.balcony a:hover {
  text-decoration: underline;
  text-underline-offset: 0.2em;
}

@media (max-width: 48rem) {
  .balcony { grid-template-columns: 1fr; }
}
'''
    (OUT / 'samples.json').write_text(json.dumps(samples, indent=2) + '\n')
    (OUT / 'profiles.json').write_text(json.dumps({k: p['description'] for k, p in PROFILES.items()}, indent=2) + '\n')


if __name__ == '__main__':
    main()
