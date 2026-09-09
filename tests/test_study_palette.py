"""Rebuild the eight studies and check the shipped editor colors."""
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from grotto.spec import Palette

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
spec = importlib.util.spec_from_file_location('study_palette', ROOT / 'scripts/study_palette.py')
study = importlib.util.module_from_spec(spec)
spec.loader.exec_module(study)
sys.path.pop(0)


@pytest.mark.parametrize('profile', study.PROFILES)
@pytest.mark.parametrize('variant', ('day', 'night'))
def test_studies_rebuild_and_shipped_editor_contrast(profile, variant):
    key = f'{profile}-{variant}'
    palette, audit = study.build_palette(profile, variant)
    assert palette.colors == Palette.from_yaml(study.OUT / f'{key}.yaml').colors
    assert not audit['contrast_failures']
    vs = json.loads((study.OUT / f'vscode-preview/themes/{key}.json').read_text())
    zs = json.loads((study.OUT / 'zed-preview/themes/grotto.json').read_text())['themes']
    z = next(t for t in zs if t['name'] == vs['name'])
    assert vs['colors']['editor.background'] == palette['bg']
    assert z['style']['editor.background'] == palette['bg'] + 'ff'
    assert not study.ng.editor_audit(palette, vs, z)['failures']


def test_studies_have_a_separate_extension_identity_and_distinct_palettes():
    package = json.loads((study.OUT / 'vscode-preview/package.json').read_text())
    assert len(package['contributes']['themes']) == 8
    for folder in ('summer-memories', 'next-generation'):
        old = json.loads((ROOT / 'out' / folder / 'vscode-preview/package.json').read_text())
        assert package['name'] != old['name']
        assert not ({t['label'] for t in package['contributes']['themes']} &
                    {t['label'] for t in old['contributes']['themes']})
    for variant in ('day', 'night'):
        signatures = {tuple(Palette.from_yaml(study.OUT / f'{p}-{variant}.yaml')[r]
                            for r in study.ng.GROUPS) for p in study.PROFILES}
        assert len(signatures) == 4
