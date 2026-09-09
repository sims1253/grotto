"""Release-relevant checks for the bounded next-generation experiment."""
import importlib.util
import json
from pathlib import Path

import pytest

from grotto.color import hex_to_oklch
from grotto.contrast import wcag_contrast
from grotto.spec import Palette

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('next_palette', ROOT / 'scripts/next_palette.py')
ng = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ng)
KEYS = [f'{p}-{v}' for p in ng.PROFILES for v in ('day', 'night')]


def test_separation_reward_stops_at_target():
    assert ng.shortfall(0.035) == pytest.approx(0.25)
    assert ng.shortfall(0.07) == 0
    assert ng.shortfall(0.35) == 0


def test_overlay_composition_endpoints_and_midpoint():
    assert ng.composite('#ffffff00', '#123456') == '#123456'
    assert ng.composite('#ffffff', '#123456') == '#ffffff'
    assert ng.composite('#ffffff80', '#000000') == '#808080'


@pytest.mark.parametrize('key', KEYS)
def test_palette_rebuild_and_contrast_on_all_declared_surfaces(key):
    profile, variant = key.split('-')
    palette = Palette.from_yaml(ng.OUT / f'{key}.yaml')
    rebuilt, metrics = ng.build_palette(profile, variant)
    assert rebuilt.colors == palette.colors
    assert metrics['final_loss'] < metrics['initial_loss']
    assert not metrics['contrast_failures']
    # Check the unrounded ratios, including the old Day selection failure.
    for role in ng.ROLES:
        floor = ng.floor_for(role.name)
        if not floor:
            continue
        refs = ng.surfaces(palette.colors) if role.paint == 'ink' else [role.contrast_reference or 'bg']
        for ref in refs:
            assert wcag_contrast(palette[role.name], palette[ref]) >= floor, (key, role.name, ref)
    for members in ng.GROUPS.values():
        assert len({palette[r] for r in members}) == 1
        assert hex_to_oklch(palette[members[0]])[1] <= .101  # shipped hex rounding
    assert not palette.is_candidate


@pytest.mark.parametrize('key', KEYS)
def test_exports_and_composited_backgrounds(key):
    palette = Palette.from_yaml(ng.OUT / f'{key}.yaml')
    vs = json.loads((ng.OUT / f'vscode-preview/themes/{key}.json').read_text())
    zs = json.loads((ng.OUT / 'zed-preview/themes/grotto.json').read_text())['themes']
    z = next(t for t in zs if t['name'] == vs['name'])
    assert vs['colors']['editor.background'] == palette['bg']
    assert vs['colors']['editor.foreground'] == palette['fg']
    assert z['style']['editor.background'] == palette['bg'] + 'ff'
    assert not ng.editor_audit(palette, vs, z)['failures']
    assert vs['grotto']['candidate'] is False
    # Gutter markers must remain visible even when diff fills are quiet.
    for key in ('added', 'modified', 'deleted'):
        marker = vs['colors'][f'editorGutter.{key}Background']
        assert wcag_contrast(marker, palette['bg']) >= 3
    # Confirm the editor check catches a broken opaque selection export.
    vs['colors']['editor.selectionBackground'] = palette['fg']
    assert ng.editor_audit(palette, vs, z)['failures']


def test_family_hue_identity_survives_day_night_switch():
    for profile in ng.PROFILES:
        day = Palette.from_yaml(ng.OUT / f'{profile}-day.yaml')
        night = Palette.from_yaml(ng.OUT / f'{profile}-night.yaml')
        for role in ng.GROUPS:
            dh = abs(hex_to_oklch(day[role])[2] - hex_to_oklch(night[role])[2])
            assert min(dh, 360 - dh) <= 33, (profile, role, dh)
