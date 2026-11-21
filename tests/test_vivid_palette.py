"""Vivid exports keep readable colors and explicitly color ordinary variables."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest
from grotto.spec import Palette

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('vivid_palette', ROOT / 'scripts/vivid_palette.py')
vivid = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vivid)
sys.path.pop(0)


@pytest.mark.parametrize('profile', vivid.PROFILES)
@pytest.mark.parametrize('variant', ('day', 'night'))
def test_vivid_palette_exports_contrast_and_variable_mapping(profile, variant):
    key = f'{profile}-{variant}'
    palette, audit = vivid.build_palette(profile, variant)
    assert palette.colors == Palette.from_yaml(vivid.OUT / f'{key}.yaml').colors
    assert not audit['contrast_failures']
    vs = json.loads((vivid.OUT / f'vscode-preview/themes/{key}.json').read_text())
    zs = json.loads((vivid.OUT / 'zed-preview/themes/grotto.json').read_text())['themes']
    z = next(t for t in zs if t['name'] == vs['name'])
    assert not vivid.ng.editor_audit(palette, vs, z)['failures']
    assert vs['semanticTokenColors']['variable']['foreground'] == palette['property']
    assert vs['colors']['editor.foreground'] == palette['fg'] != palette['property']
    assert z['style']['syntax']['variable']['color'] == palette['property'] + 'ff'
    assert vs['semanticTokenColors']['function']['foreground'] == palette['function']
    assert vs['semanticTokenColors']['variable.readonly']['foreground'] == palette['constant']


def test_vivid_extension_has_its_own_identity():
    new = json.loads((vivid.OUT / 'vscode-preview/package.json').read_text())
    old = json.loads((vivid.studies.OUT / 'vscode-preview/package.json').read_text())
    assert new['name'] != old['name']
    assert len(new['contributes']['themes']) == 4
