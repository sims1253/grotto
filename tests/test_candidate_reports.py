"""Phase 5 generated candidate palettes + family reports (commit 2).

The committed artifacts under themes/candidates/ and out/candidates/ must be
reproducible from source: a fresh build must equal the committed files
byte-for-byte.  These tests also pin the provenance contract (OKLCH-first,
candidate=true, generated=true, input hash present) and the round-trip
property (reloading a generated palette reproduces the same sRGB hex).
"""

from __future__ import annotations

import glob
from pathlib import Path

import pytest

from grotto.candidates import (
    build_candidates,
    candidate_family_report,
    candidate_index,
    candidate_palette_yaml,
    write_candidate_palettes,
)
from grotto.environments import Environments
from grotto.model import ModelSpec
from grotto.report import to_json
from grotto.spec import DistanceSpec, Palette, RoleSpec

REPO = Path(__file__).resolve().parents[1]
STRATEGIES = ("a-restrained", "b-balanced", "c-expressive")
VARIANTS = ("day", "evening", "night")


@pytest.fixture(scope="module")
def spec() -> ModelSpec:
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    return ModelSpec(roles, env, dists)


@pytest.fixture(scope="module")
def families(spec):
    return build_candidates(spec)


# ===========================================================================
# generated palettes: provenance + round-trip + reproducibility
# ===========================================================================


def test_exactly_nine_generated_palettes():
    paths = sorted(glob.glob(str(REPO / "themes/candidates/candidate-*.yaml")))
    # 3 candidates x 3 variants
    assert len(paths) == 9
    for s in STRATEGIES:
        for v in VARIANTS:
            assert (REPO / "themes/candidates" / f"candidate-{s}.{v}.yaml").exists()


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_generated_palette_provenance(strategy, families):
    fb = next(f for f in families if f.binding.name == f"candidate-{strategy}")
    pal = fb.variants["night"].palette
    import yaml

    d = yaml.safe_load(
        (REPO / "themes/candidates" / f"candidate-{strategy}.night.yaml").read_text()
    )
    assert d["format"] == "oklch"            # OKLCH-first
    assert d["candidate"] is True
    assert d["source"] == "generated"
    assert d["meta"]["generated"] is True
    assert d["meta"]["candidate"] is True
    assert d["meta"]["binding"] == fb.binding.name
    assert d["meta"]["input_hash"] == fb.input_hash
    assert d["meta"]["shared_environments"] == "spec/environments.yaml"
    assert d["meta"]["srgb_primary"] is True
    # every spec role is present
    for role in fb.spec.roles:
        assert role.name in d["colors"]


@pytest.mark.parametrize("strategy", STRATEGIES)
@pytest.mark.parametrize("variant", VARIANTS)
def test_generated_palette_round_trips_to_same_hex(strategy, variant, families):
    """Reloading a generated OKLCH-first palette reproduces the build's hex."""
    fb = next(f for f in families if f.binding.name == f"candidate-{strategy}")
    path = REPO / "themes/candidates" / f"candidate-{strategy}.{variant}.yaml"
    loaded = Palette.from_yaml(path)
    orig = fb.variants[variant].palette
    for role in orig.colors:
        assert loaded[role] == orig[role], f"{strategy}.{variant}.{role}"


def test_committed_palettes_match_fresh_build(families):
    """Every committed generated palette equals a freshly generated one."""
    for fb in families:
        for v in VARIANTS:
            fresh = candidate_palette_yaml(fb, v)
            committed = (
                REPO / "themes/candidates" / f"{fb.binding.name}.{v}.yaml"
            ).read_text()
            assert fresh == committed, f"{fb.binding.name}.{v} palette drifted"


def test_palette_generation_is_deterministic(families):
    fb = families[0]
    assert candidate_palette_yaml(fb, "night") == candidate_palette_yaml(fb, "night")


# ===========================================================================
# per-candidate family reports: structure + reproducibility
# ===========================================================================


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_candidate_family_report_structure(strategy, families, spec):
    fb = next(f for f in families if f.binding.name == f"candidate-{strategy}")
    report = candidate_family_report(fb, spec)
    assert report["is_candidate"] is True
    assert report["ok"] is True
    assert report["input_hash"] == fb.input_hash
    assert set(report["variants"]) == set(VARIANTS)
    # each variant carries the full audit blocks the Phase 6 report needs
    for v in VARIANTS:
        vr = report["variants"][v]
        for key in ("colors", "contrast_vs_bg", "distance_matrix", "cvd", "spectral"):
            assert key in vr, f"{strategy}.{v} missing {key}"
        # bg + every ink role audited
        assert "bg" in vr["colors"]
        assert "fg" in vr["colors"]


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_committed_eval_reports_match_fresh(strategy, families, spec):
    fb = next(f for f in families if f.binding.name == f"candidate-{strategy}")
    fresh = to_json(candidate_family_report(fb, spec))
    committed = (
        REPO / "out/candidates" / f"candidate-{strategy}"
        / f"candidate-{strategy}.eval.json"
    ).read_text()
    assert fresh == committed


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_committed_build_reports_match_fresh(strategy, families):
    fb = next(f for f in families if f.binding.name == f"candidate-{strategy}")
    fresh = to_json(fb.to_dict())
    committed = (
        REPO / "out/candidates" / f"candidate-{strategy}"
        / f"candidate-{strategy}.build.json"
    ).read_text()
    assert fresh == committed


def test_candidate_index_matches_fresh(families, spec):
    fresh = to_json(candidate_index(families, spec))
    committed = (REPO / "out/candidates/index.json").read_text()
    assert fresh == committed


def test_index_lists_three_candidates_no_ranking(families, spec):
    idx = candidate_index(families, spec)
    assert idx["n_candidates"] == 3
    assert len(idx["candidates"]) == 3
    # no aggregate score / winner / rank KEYS anywhere in the index (the
    # disclaimer TEXT says "no winner"; that must not be confused with a field).
    forbidden_keys = {"score", "rank", "winner", "recommendation", "best"}
    assert not (forbidden_keys & set(idx))
    for c in idx["candidates"]:
        assert not (forbidden_keys & set(c))
