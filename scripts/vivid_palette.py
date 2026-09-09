"""Bolder Fig and Rainstone studies, including colored ordinary variables."""
from __future__ import annotations

import shutil
from grotto.color import hex_to_oklch
from grotto.spec import Palette
import next_palette as ng
import study_palette as studies

OUT = ng.ROOT / 'out/vivid-studies'
PROFILES = {'fig-vivid': {}, 'rainstone-vivid': {}}


def adjust_mapping(vs, zs):
    # Python TextMate leaves some plain identifiers unclassified, so its root
    # receives the same fallback. Deeper punctuation/comment/etc. rules win.
    # Share the property color with ordinary variables. Keep specific function,
    # constant, parameter and builtin scopes more specific than this fallback.
    vs.textmate.insert(0, {'role': 'property', 'scopes': ['variable', 'entity.name.variable', 'meta.definition.variable.name', 'source.python']})
    for rule in vs.textmate:
        if rule['role'] == 'fg':
            rule['role'] = 'property'
    for rule in vs.semantic:
        if rule.get('selector') == 'variable':
            rule['role'] = 'property'
    for key in ('variable', 'variable.member'):
        if key in zs.syntax:
            zs.syntax[key]['role'] = 'property'


def build_palette(profile, variant):
    name = profile.removesuffix('-vivid')
    dark = variant == 'night'
    base, _ = studies.build_palette(name, variant)
    raw = {r: hex_to_oklch(hx) for r, hx in base.items()}
    if not dark:
        # Lighter state fills allow stronger, lighter inks while preserving
        # the same text-contrast floor in selection, search and diff states.
        for role in ng.surfaces(base.colors):
            if role not in ('bg', 'bg_elevated', 'bg_overlay'):
                L, C, h = raw[role]
                raw[role] = (max(.932, L), C, h)
    day_L = (.55, .54, .525, .55, .525)
    day_C = (.24, .20, .17, .23, .17)
    night_L = (.79, .82, .79, .80, .79)
    night_C = (.18, .16, .16, .17, .15)
    for i, ((group, members), hue) in enumerate(zip(ng.GROUPS.items(), studies.PROFILES[name]['hues'])):
        for role in members:
            raw[role] = ((night_L if dark else day_L)[i], (night_C if dark else day_C)[i], hue)
    # Stronger color across common tokens, rather than just rare accents.
    raw['property'] = (.78 if dark else .48, .10 if dark else .12, 250)
    raw['parameter'] = (.79 if dark else .51, .10 if dark else .14, 50)
    raw['operator'] = (.77 if dark else .50, .10, studies.PROFILES[name]['hues'][0])
    for role in ('comment', 'docstring'):
        raw[role] = (.71 if dark else .49, .065 if dark else .09, 150)
    inks = {r for members in ng.GROUPS.values() for r in members} | {'property', 'parameter', 'operator', 'comment', 'docstring'}
    colors = {r: ng.color(*lch, .99 if r in inks else .75) for r, lch in raw.items()}
    backgrounds = [colors[r] for r in ng.surfaces(colors)]
    for role in ng.ROLES:
        floor = ng.floor_for(role.name)
        if floor:
            refs = backgrounds if role.paint == 'ink' else [colors[role.contrast_reference or 'bg']]
            colors[role.name] = ng.repair_ink(raw[role.name], variant, refs, floor, .99 if role.name in inks else .75)
    palette = Palette(f'{profile}-{variant}', variant, colors, meta={'candidate': False})
    metrics = ng.audit(palette)
    if metrics['contrast_failures']:
        raise ValueError(metrics['contrast_failures'])
    return palette, metrics


if __name__ == '__main__':
    ng.main(OUT, PROFILES, build_palette, 'vivid-studies', 'Grotto Vivid Studies Preview',
            'Bolder Fig and Rainstone: colored variables, green comments and stronger accents.',
            'Authored vivid study with colored variables; all configured text contrast floors retained.',
            extra_inputs=('scripts/memory_palette.py', 'scripts/study_palette.py', 'scripts/vivid_palette.py'),
            mapping_adjuster=adjust_mapping)
    (OUT / 'comparison.html').replace(OUT / 'role-specimens.html')
    shutil.copyfile(studies.OUT / 'samples.json', OUT / 'samples.json')
