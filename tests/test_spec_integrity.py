"""Spec integrity: roles/distance/environments load and obey their own rules."""

from pathlib import Path

import pytest

from grotto.environments import Environments
from grotto.spec import CONSTRAINT_KINDS, DistanceSpec, RoleSpec

REPO = Path(__file__).resolve().parents[1]


def test_role_spec_loads_and_has_all_groups():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    for group in ("neutrals", "syntax", "diagnostics"):
        assert roles.by_group(group), f"group {group} empty"
    assert len(roles) >= 30


def test_every_critical_role_declares_redundant_channels():
    """D-3 invariant, enforced by the loader -- guard it at the spec level too."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    for r in roles:
        if r.cvd_priority == "critical":
            assert r.redundant_channels, (
                f"{r.name} is critical but has no redundant_channels (D-3)"
            )


def test_distance_spec_constraints_reference_real_roles():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    assert set(dists.thresholds).issuperset(
        {"must_distinguish", "should_distinguish", "same_family", "differentiated_by"}
    )
    for c in dists.constraints:
        assert c.kind in CONSTRAINT_KINDS
        assert c.a in roles and c.b in roles, f"constraint {c} references unknown role"


def test_distance_relationships_do_not_impose_conflicting_bounds():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    must = {frozenset((c.a, c.b)) for c in dists.of_kind("must_distinguish")}
    near = {frozenset((c.a, c.b)) for c in dists.of_kind("differentiated_by")}
    assert must.isdisjoint(near), "a pair cannot be both far-apart and near-identical"
    assert {frozenset((c.a, c.b)) for c in dists.of_kind("redundant_encoding")} <= must


def test_environments_loads_bands_and_floors():
    env = Environments.load(REPO / "spec/environments.yaml")
    for band in ("minimal", "low", "comfortable", "high", "maximal"):
        b = env.band(band)
        assert b.min < b.centre < b.max, f"band {band} not monotonic"
    assert env.accessibility_floors["body_text_wcag"] == pytest.approx(4.5)
    for v in ("day", "evening", "night"):
        assert v in env.environments
    assert env.stability["max_hue_drift_deg"] == pytest.approx(12.0)


def test_band_for_lc_classification():
    env = Environments.load(REPO / "spec/environments.yaml")
    assert env.band_for_lc(82).name == "high"
    assert env.band_for_lc(24).name == "minimal"
    assert env.band_for_lc(200) is None  # out of band
