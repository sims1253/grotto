"""Author Grotto's summer-memory generation; repair readability without a beauty score.

Run from the repository root: uv run python scripts/memory_palette.py
"""
from __future__ import annotations

from grotto.color import hex_to_oklch
from grotto.spec import Palette

import next_palette as ng

OUT = ng.ROOT / 'out/summer-memories'
PROFILES = {
    'pergola': {'canvas_hue': 150, 'canvas_chroma': .016,
                'description': 'Green shade, herb-colored syntax, small amber accents.'},
    'stone': {'canvas_hue': 285, 'canvas_chroma': .004,
              'description': 'Mineral grey, softer foliage, small amber accents.'},
}
INTRO = ('Two interpretations of summers beneath kiwi vines and evenings at stone tables. '
         'Pergola brings foliage into the canvas. Stone keeps the canvas closer to grey. '
         'Both use related cool syntax colors and small amber accents, in Day and Night.')
# L(day), L(night), C, hue. Related roles intentionally share colors.
# Amber is assigned to numbers/constants rather than frequent keywords or strings.
SYNTAX = {
    'keyword': (.46, .77, .050, 110),
    'function': (.46, .79, .045, 215),
    'string': (.45, .75, .055, 150),
    'number': (.45, .80, .085, 75),
    'type': (.46, .77, .035, 290),
}


# Day needs more chroma and clearer hue differences against pale stone.
# Author it separately so changes here do not alter the Night composition.
DAY_SYNTAX = {
    'keyword': (.48, .130, 115),
    'function': (.49, .170, 250),
    'string': (.48, .150, 150),
    'number': (.49, .160, 55),
    'type': (.49, .180, 305),
}


def build_palette(profile, variant):
    dark = variant == 'night'
    p = PROFILES[profile]
    h = p['canvas_hue'] if dark else (110 if profile == 'pergola' else 85)
    c = p['canvas_chroma'] if dark else (.012 if profile == 'pergola' else .006)
    # Retain established non-syntax roles and override the composition below.
    raw = {r: hex_to_oklch(hx) for r, hx in ng.seed_colors('cove', variant).items()}
    raw.update({
        'bg': (.245 if dark else .970, c, h),
        'bg_elevated': (.267 if dark else .984, c * .8, h),
        'bg_overlay': (.285 if dark else .994, c * .5, h),
        'active_line': (.266 if dark else .947, c, h),
        'selection': (.315 if dark else .888, .019, 155),
        'search_match': (.277 if dark else .938, .021, 85),
        'search_match_current': (.325 if dark else .895, .037, 85),
        'diff_added': (.265 if dark else .941, .018, 150),
        'diff_removed': (.295 if dark else .914, .019, 30),
        'diff_changed': (.28 if dark else .931, .022, 85),
        'debug_current': (.31 if dark else .923, .025, 85),
    })
    for role in ('fg', 'parameter', 'property', 'line_number_active'):
        raw[role] = (.815 if dark else .405, .012, 85)
    for role in ('comment', 'docstring', 'fg_secondary', 'deprecated'):
        raw[role] = (.66 if dark else .48, .014, 125)
    for role in ('punctuation', 'operator'):
        raw[role] = (.72 if dark else .455, .008, 95)
    for role in ('fg_muted', 'line_number', 'ui_inactive'):
        raw[role] = (.59 if dark else .54, .010, h)
    for group, members in ng.GROUPS.items():
        day_L, night_L, chroma, hue = SYNTAX[group]
        # Stone's foliage is a little less colored; amber stays the same.
        if dark and profile == 'stone' and group in ('keyword', 'string'):
            chroma *= .8
        for role in members:
            raw[role] = (night_L, chroma, hue) if dark else DAY_SYNTAX[group]
    for role, hue, chroma in [('error', 28, .115), ('warning', 80, .09),
                              ('success', 150, .065), ('info', 215, .055),
                              ('focus', 80, .08), ('breakpoint', 28, .115)]:
        raw[role] = (.78 if dark else .45, chroma, hue)
    if not dark:
        # Color a few recurring identifiers; ordinary variables stay neutral.
        raw['parameter'] = (.47, .075, 195)
        raw['property'] = (.47, .075, 195)
    syntax_roles = {r for members in ng.GROUPS.values() for r in members} | {'parameter', 'property'}
    # Day syntax may use nearly the full sRGB gamut; the old 75% cap muted it.
    fractions = {r: .98 if not dark and r in syntax_roles else .75 for r in raw}
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
    metrics['authored_syntax'] = {r: {'requested': list(raw[r]), 'shipped': list(hex_to_oklch(colors[r]))}
                                  for r in (*ng.GROUPS, 'parameter', 'property')}
    metrics['amber_ink_share'] = {
        lang: round(sum(counts[r] for r in ng.GROUPS['number']) / sum(counts.values()), 4)
        for lang, counts in ng.COUNTS.items()
    }
    return palette, metrics


if __name__ == '__main__':
    ng.main(OUT, PROFILES, build_palette, 'summer-memories',
            'Grotto Summer Memories Preview', INTRO,
            'Authored from the Grotto summer-memory brief; lightness repaired for contrast. No aesthetic optimization.',
            extra_inputs=('scripts/memory_palette.py',))
