"""Report: structure, determinism, and JSON/YAML/text validity."""

import json
from pathlib import Path

import pytest
import yaml

from grotto.environments import Environments
from grotto.report import _input_hash, palette_report_dict, to_json, to_text, to_yaml, write_report
from grotto.spec import DistanceSpec, RoleSpec, load

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def report():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    pal = load(REPO / "themes/fixtures/eval-night-full.yaml")
    return palette_report_dict(pal, roles, dists, env)


def test_report_has_expected_top_level_keys(report):
    assert report["schema"] == "grotto.palette-report"
    for k in ("palette", "provenance", "colors", "contrast_vs_bg",
              "distance_matrix", "cvd", "salience_budget", "spectral"):
        assert k in report


def test_report_colors_carry_full_audit(report):
    c = report["colors"]["focus"]
    assert c["gamut"]["in_srgb"] is False
    assert c["gamut"]["in_p3"] is False
    assert c["chroma_lost"] > 0  # focus was gamut-mapped
    assert c["source"] == "oklch"


def test_report_contrast_has_band_match_flag(report):
    cr = report["contrast_vs_bg"]["fg"]
    assert set(cr) >= {"wcag_ratio", "apca_lc", "oklab_dl", "wcag_aa_body",
                       "target_band", "measured_band", "band_match"}


def test_report_cvd_covers_all_three_types_at_both_severities(report):
    pair = report["cvd"]["must_distinguish_pairs"][0]
    for kind in ("protan", "deutan", "tritan"):
        assert "dichromat_de_1.0" in pair["cvd"][kind]
        assert "anomaly_de_0.6" in pair["cvd"][kind]


def test_redundant_channel_flag_reflects_spec_not_warning_severity(report):
    violations = report["distance_matrix"]["violations"]
    ordinary = next(v for v in violations if "should_distinguish(string, type)" in v["constraint"])
    encoded = next(v for v in violations if "must_distinguish(diff_added, diff_removed)" in v["constraint"])
    assert ordinary["has_redundant_channel"] is False
    assert encoded["has_redundant_channel"] is True


def test_report_spectral_is_labelled_exploratory(report):
    s = report["spectral"]
    assert "caveat" in s
    assert "retinal" in s["caveat"] or "exposure" in s["caveat"]
    assert 0 < s["melanopic_ratio"] < 2


def test_json_yaml_text_roundtrip(report, tmp_path):
    j = to_json(report)
    y = to_yaml(report)
    t = to_text(report)
    assert json.loads(j)["palette"]["name"] == report["palette"]["name"]
    assert yaml.safe_load(y)["palette"]["name"] == report["palette"]["name"]
    assert report["palette"]["name"] in t
    assert "APCA is independent work in progress" in t  # caveat surfaces in text


def test_write_report_creates_three_files(report, tmp_path):
    paths = write_report(report, tmp_path, "stem")
    assert {k for k in paths} == {"json", "yaml", "text"}
    for p in paths.values():
        assert p.exists() and p.stat().st_size > 0


def test_report_is_deterministic(report):
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    pal = load(REPO / "themes/fixtures/eval-night-full.yaml")
    again = palette_report_dict(pal, roles, dists, env)
    # input hash stable
    assert report["provenance"]["input_hash"] == again["provenance"]["input_hash"]
    # full JSON byte-identical
    assert to_json(report) == to_json(again)


def test_input_hash_changes_when_palette_changes():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    p1 = load(REPO / "themes/fixtures/eval-night-full.yaml")
    p2 = load(REPO / "themes/fixtures/eval-night.yaml")  # different role set
    h1 = _input_hash(p1, roles, dists, env)
    h2 = _input_hash(p2, roles, dists, env)
    assert h1 != h2


def test_input_hash_covers_the_whole_effective_spec():
    """Provenance means an unchanged hash implies unchanged inputs.  The hash
    must therefore react to fields the OLD version ignored: distance
    thresholds and the environments spec (band edges, floors)."""
    from dataclasses import replace

    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    pal = load(REPO / "themes/fixtures/eval-night-full.yaml")
    base = _input_hash(pal, roles, dists, env)

    stricter = replace(
        dists,
        thresholds={
            **dists.thresholds,
            "must_distinguish": {**dists.thresholds["must_distinguish"], "normal_vision": 0.2},
        },
    )
    assert _input_hash(pal, roles, stricter, env) != base

    # a shifted contrast band edge is a different effective spec
    from grotto.environments import ContrastBand
    moved = replace(
        env,
        contrast_bands={
            **env.contrast_bands,
            "high": ContrastBand("high", 74.0, env.contrast_bands["high"].max,
                                 env.contrast_bands["high"].centre),
        },
    )
    assert _input_hash(pal, roles, dists, moved) != base
