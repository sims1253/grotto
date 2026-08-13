"""Phase 4 experiment reports: determinism + CLI smoke (commit 4)."""

import json
from pathlib import Path

import pytest

from grotto.cli import main
from grotto.model import (
    CandidateBinding,
    ModelSpec,
    build_family,
    compare_families,
    hand_tuned_build,
)
from grotto.report import to_json
from grotto.spec import DistanceSpec, RoleSpec, load

REPO = Path(__file__).resolve().parents[1]
FH = {"neutral": 0, "warm-neutral": 70, "sand": 80, "rose": 25,
      "violet": 300, "azure": 245, "sage": 145, "teal": 195}


def _spec():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    from grotto.environments import Environments
    env = Environments.load(REPO / "spec/environments.yaml")
    return ModelSpec(roles, env, dists)


def _binding():
    from grotto.model import FamilyAnchor
    anchors = {f: FamilyAnchor(f, h, 1.0) for f, h in FH.items()}
    return CandidateBinding("det", 1.0, anchors)


# ===========================================================================
# deterministic reports (JSON/YAML/text/HTML are byte-identical across runs)
# ===========================================================================


def test_build_dict_is_deterministic():
    spec = _spec()
    d1 = build_family(_binding(), spec).to_dict()
    d2 = build_family(_binding(), spec).to_dict()
    assert to_json(d1) == to_json(d2)


def test_comparison_dict_is_deterministic():
    spec = _spec()
    fb = build_family(_binding(), spec)
    hand = {v: load(REPO / f"themes/experiments/handtuned-{v}.yaml")
            for v in ("day", "evening", "night")}
    ht = hand_tuned_build(hand, spec)
    c1 = compare_families(fb, ht, spec)
    c2 = compare_families(fb, ht, spec)
    assert to_json(c1) == to_json(c2)


def test_text_and_html_renderers_run():
    from grotto.family_report import (
        comparison_html, comparison_text, family_build_html, family_build_text,
    )
    spec = _spec()
    fb = build_family(_binding(), spec)
    hand = {v: load(REPO / f"themes/experiments/handtuned-{v}.yaml")
            for v in ("day", "evening", "night")}
    ht = hand_tuned_build(hand, spec)
    cmp = compare_families(fb, ht, spec)
    txt_b = family_build_text(fb)
    html_b = family_build_html(fb)
    txt_c = comparison_text(cmp)
    html_c = comparison_html(fb, cmp)
    for s in (txt_b, html_b, txt_c, html_c):
        assert isinstance(s, str) and len(s) > 0
    # HTML is self-contained: no external resource references
    for html in (html_b, html_c):
        assert "<style>" in html
        assert "src=" not in html and 'href="' not in html


def test_calibration_binding_loads_and_builds():
    spec = _spec()
    b = CandidateBinding.load(REPO / "spec/bindings/calibration.yaml")
    fb = build_family(b, spec)
    assert fb.ok is True
    assert fb.binding.is_candidate is False  # NON-CANDIDATE
    assert set(fb.variants) == {"day", "evening", "night"}


# ===========================================================================
# committed experiment reports are reproducible from source
# ===========================================================================


def test_committed_reports_match_fresh_build():
    """The committed out/model-calibration JSON must equal a fresh build."""
    spec = _spec()
    b = CandidateBinding.load(REPO / "spec/bindings/calibration.yaml")
    fresh = to_json(build_family(b, spec).to_dict())
    committed = (REPO / "out/model-calibration/calibration.build.json").read_text()
    assert fresh == committed


def test_committed_comparison_matches_fresh_build():
    spec = _spec()
    b = CandidateBinding.load(REPO / "spec/bindings/calibration.yaml")
    fb = build_family(b, spec)
    hand = {v: load(REPO / f"themes/experiments/handtuned-{v}.yaml")
            for v in ("day", "evening", "night")}
    ht = hand_tuned_build(hand, spec)
    fresh = to_json(compare_families(fb, ht, spec))
    committed = (REPO / "out/model-calibration/calibration.compare.json").read_text()
    assert fresh == committed


# ===========================================================================
# CLI smoke
# ===========================================================================


def _common():
    return ["--roles", str(REPO / "spec/roles.yaml"),
            "--distances", str(REPO / "spec/distance-matrix.yaml"),
            "--environments", str(REPO / "spec/environments.yaml")]


def test_cli_family(tmp_path):
    rc = main(_common() + ["family", str(REPO / "spec/bindings/calibration.yaml"),
                           "--out", str(tmp_path)])
    assert rc == 0
    files = {p.name for p in tmp_path.iterdir()}
    assert {"calibration.build.json", "calibration.build.yaml",
            "calibration.build.txt", "calibration.build.html"} <= files
    d = json.loads((tmp_path / "calibration.build.json").read_text())
    assert d["is_candidate"] is False  # NON-CANDIDATE


def test_cli_compare_families(tmp_path):
    rc = main(_common() + [
        "compare-families", str(REPO / "spec/bindings/calibration.yaml"),
        str(REPO / "themes/experiments/handtuned-day.yaml"),
        str(REPO / "themes/experiments/handtuned-evening.yaml"),
        str(REPO / "themes/experiments/handtuned-night.yaml"),
        "--out", str(tmp_path),
    ])
    assert rc == 0
    files = {p.name for p in tmp_path.iterdir()}
    assert {"calibration.compare.json", "calibration.compare.html"} <= files
    d = json.loads((tmp_path / "calibration.compare.json").read_text())
    assert "systematic_needed_hand_adjustment" in d["summary"]


def test_systematic_vs_hand_headline_finding():
    """The Phase 4 question: did the systematic transform need hand adjustment?"""
    spec = _spec()
    b = CandidateBinding.load(REPO / "spec/bindings/calibration.yaml")
    fb = build_family(b, spec)
    hand = {v: load(REPO / f"themes/experiments/handtuned-{v}.yaml")
            for v in ("day", "evening", "night")}
    ht = hand_tuned_build(hand, spec)
    cmp = compare_families(fb, ht, spec)
    s = cmp["summary"]
    # the hand-tuned fixture is curated corrections over systematic, so the
    # finding is that hand adjustment WAS needed, in a bounded set of roles
    assert s["systematic_needed_hand_adjustment"] is True
    assert s["n_needing_adjustment"] > 0
    # ... but the mean dE is small: systematic is close to the designer's intent
    assert s["de_mean"] < 0.05
