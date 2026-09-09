"""Check the shipped memory palettes and preservation of the previous generation."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

from grotto.contrast import wcag_contrast
from grotto.spec import Palette

ROOT = Path(__file__).resolve().parents[1]
# Scripts are also executable directly, where Python supplies this path.
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('memory_palette', ROOT / 'scripts/memory_palette.py')
mem = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mem)
sys.path.pop(0)


@pytest.mark.parametrize('profile', mem.PROFILES)
@pytest.mark.parametrize('variant', ('day', 'night'))
def test_shipped_palette_rebuild_and_editor_readability(profile, variant):
    key = f'{profile}-{variant}'
    palette = Palette.from_yaml(mem.OUT / f'{key}.yaml')
    rebuilt, metrics = mem.build_palette(profile, variant)
    assert rebuilt.colors == palette.colors
    assert not metrics['contrast_failures']
    for role in mem.ng.ROLES:
        floor = mem.ng.floor_for(role.name)
        if floor:
            refs = mem.ng.surfaces(palette.colors) if role.paint == 'ink' else [role.contrast_reference or 'bg']
            assert all(wcag_contrast(palette[role.name], palette[r]) >= floor for r in refs)
    vs = json.loads((mem.OUT / f'vscode-preview/themes/{key}.json').read_text())
    zs = json.loads((mem.OUT / 'zed-preview/themes/grotto.json').read_text())['themes']
    z = next(t for t in zs if t['name'] == vs['name'])
    assert vs['colors']['editor.background'] == palette['bg']
    assert z['style']['editor.background'] == palette['bg'] + 'ff'
    assert not mem.ng.editor_audit(palette, vs, z)['failures']


def test_new_extension_can_coexist_with_previous_generation():
    previous = json.loads((mem.ng.OUT / 'vscode-preview/package.json').read_text())
    current = json.loads((mem.OUT / 'vscode-preview/package.json').read_text())
    assert current['name'] != previous['name']
    assert len(current['contributes']['themes']) == 4
    assert len(previous['contributes']['themes']) == 6
    assert not ({t['label'] for t in current['contributes']['themes']} &
                {t['label'] for t in previous['contributes']['themes']})
