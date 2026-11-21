"""Phase 4 corrected cross-variant stability and systematic-vs-hand comparison.

These are the senior-review fixes to DESIGN.md D-5:
  * normalized C/max_chroma ordering (not raw chroma rank)
  * cyclic family hue sequence (not pairwise signed hue ordering)
  * non-vacuous realized salience proxies
  * total hue drift that includes the adjustment component
plus compare_families (beside build_family, not inside it).
"""

from pathlib import Path

import pytest

from grotto.color import hex_to_oklch, max_chroma
from grotto.model import (
    COMPARE_DE_THRESHOLD,
    CandidateBinding,
    FamilyAnchor,
    FamilyBuild,
    ModelSpec,
    RoleTrace,
    VariantBuild,
    build_family,
    compare_families,
    family_stability_build,
    hand_tuned_build,
)
from grotto.spec import DistanceSpec, Palette, RoleSpec

REPO = Path(__file__).resolve().parents[1]
FAMILY_HUES = {
    "neutral": 0, "warm-neutral": 70, "sand": 80, "rose": 25,
    "violet": 300, "azure": 245, "sage": 145, "teal": 195,
}


@pytest.fixture(scope="module")
def spec() -> ModelSpec:
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    from grotto.environments import Environments
    env = Environments.load(REPO / "spec/environments.yaml")
    return ModelSpec(roles, env, dists)


def _binding(name="t", candidate_scale=1.0, **kw):
    fs = kw.pop("family_scales", {})
    anchors = {f: FamilyAnchor(f, h, fs.get(f, 1.0)) for f, h in FAMILY_HUES.items()}
    return CandidateBinding(name, candidate_scale, anchors, **kw)


# -- minimal-spec helper for synthetic-trace unit tests ---------------------


def _role(name, family="azure", salience=3, paint="ink"):
    from grotto.spec import Role
    return Role(
        name=name, group="syntax", description="", salience=salience, family=family,
        chroma_class="medium", contrast_target="comfortable", cvd_priority="normal",
        night_adaptation=0.8, area_class="minor", paint=paint,
        accessibility_floor="body_text" if paint == "ink" else "none",
        contrast_reference="bg",
    )


def _mini_spec(roles):
    from grotto.environments import Environments
    env = Environments.load(REPO / "spec/environments.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", RoleSpec.load(REPO / "spec/roles.yaml"))
    return ModelSpec(RoleSpec(version=1, roles=roles), env, dists)


def _trace(role, variant, L, C, h, mc=None, salience_family=None):
    mc = mc if mc is not None else max(0.05, max_chroma(L, h, "srgb"))
    return RoleTrace(
        role=role, paint="ink", variant=variant, family=(salience_family or "x"),
        base_oklch=(0.5, 0.0, h), requested=(L, C, h), capped=(L, C, h),
        realized=(L, C, h), final_hex="#000000", max_chroma_at_L=mc,
        chroma_losses={"requested": C, "capped": C, "realized": C, "cap_loss": 0.0,
                       "gamut_loss": 0.0, "total_loss": 0.0, "realized_fraction": 1.0},
        adjustments_applied={"L": 0.0, "C": 0.0, "h": 0.0},
        contrast={}, conflicts=[], winning_constraint="apca_centre",
        derivation=[], issues=[],
    )


def _variant(name, traces):
    pal = Palette("synth", name, {r: "#000000" for r in traces})
    return VariantBuild(name, pal, traces)


# ===========================================================================
# (1) normalized C/max_chroma ordering
# ===========================================================================


def test_normalized_chroma_inversion_is_detected(spec):
    """Two roles whose NORMALIZED chroma (C/max_chroma) order swaps, even though
    raw chroma might not, must be flagged.  Raw chroma rank is the bug."""
    mini = _mini_spec({"a": _role("a", "azure"), "b": _role("b", "sage")})
    day = _variant("day", {
        "a": _trace("a", "day", 0.8, 0.10, 245, mc=0.11, salience_family="azure"),   # norm ~0.91
        "b": _trace("b", "day", 0.5, 0.05, 145, mc=0.20, salience_family="sage"),   # norm ~0.25
    })
    night = _variant("night", {
        "a": _trace("a", "night", 0.8, 0.02, 245, mc=0.11, salience_family="azure"),  # norm ~0.18
        "b": _trace("b", "night", 0.5, 0.18, 145, mc=0.20, salience_family="sage"),  # norm ~0.90
    })
    st = family_stability_build({"day": day, "night": night}, mini)
    assert st["normalized_chroma_inversions"], "expected a normalized-chroma inversion"
    inv = st["normalized_chroma_inversions"][0]
    assert set(inv["roles"]) == {"a", "b"}


def test_raw_chroma_would_misrank_but_normalized_does_not(spec):
    """Sanity: the check keys off normalized, not raw, chroma."""
    mini = _mini_spec({"a": _role("a", "azure"), "b": _role("b", "sage")})
    day = _variant("day", {
        "a": _trace("a", "day", 0.8, 0.10, 245, mc=0.11, salience_family="azure"),
        "b": _trace("b", "day", 0.5, 0.18, 145, mc=0.20, salience_family="sage"),
    })
    night = _variant("night", {
        "a": _trace("a", "night", 0.8, 0.10, 245, mc=0.11, salience_family="azure"),
        "b": _trace("b", "night", 0.5, 0.18, 145, mc=0.20, salience_family="sage"),
    })
    st = family_stability_build({"day": day, "night": night}, mini)
    assert st["normalized_chroma_inversions"] == []


# ===========================================================================
# (2) cyclic family hue sequence (not pairwise signed)
# ===========================================================================


def test_cyclic_family_sequence_detected_with_three_families(spec):
    """A re-ordering of three families around the hue circle is detected."""
    mini = _mini_spec({"a": _role("a", "rose"), "b": _role("b", "sand"), "c": _role("c", "sage")})
    day = _variant("day", {
        "a": _trace("a", "day", 0.7, 0.10, 25, salience_family="rose"),
        "b": _trace("b", "day", 0.7, 0.10, 80, salience_family="sand"),
        "c": _trace("c", "day", 0.7, 0.10, 145, salience_family="sage"),
    })
    # night: sage crossed past sand -> cyclic order changes
    night = _variant("night", {
        "a": _trace("a", "night", 0.7, 0.10, 25, salience_family="rose"),
        "b": _trace("b", "night", 0.7, 0.10, 90, salience_family="sand"),
        "c": _trace("c", "night", 0.7, 0.10, 70, salience_family="sage"),
    })
    st = family_stability_build({"day": day, "night": night}, mini)
    assert st["cyclic_family_sequence_preserved"] is False


def test_real_build_preserves_cyclic_family_sequence(spec):
    fb = build_family(_binding(), spec)
    assert fb.stability["cyclic_family_sequence_preserved"] is True
    # the sequence is the same canonical cycle in every variant
    seqs = fb.stability["cyclic_family_sequence"]
    assert len(set(tuple(v) for v in seqs.values())) == 1


# ===========================================================================
# (3) non-vacuous realized salience proxy
# ===========================================================================


def test_salience_proxy_is_non_vacuous_and_detects_reversal(spec):
    """Within one family, a higher-salience role with LESS normalized chroma
    than a lower-salience role is a realized-salience reversal."""
    mini = _mini_spec({"hi": _role("hi", "x", salience=5), "lo": _role("lo", "x", salience=1)})
    day = _variant("day", {
        "hi": _trace("hi", "day", 0.7, 0.02, 245, mc=0.20, salience_family="x"),
        "lo": _trace("lo", "day", 0.7, 0.18, 245, mc=0.20, salience_family="x"),
    })
    st = family_stability_build({"day": day}, mini)
    revs = st["salience_proxy_reversals"]
    assert revs, "expected a salience-proxy reversal (hi salience, low chroma)"
    r = revs[0]
    assert {r["lower_salience"], r["higher_salience"]} == {"lo", "hi"}


# ===========================================================================
# (4) total hue drift includes adjustments
# ===========================================================================


def test_drift_uses_post_adjustment_realized_hue(spec):
    """Drift is measured on the realized (post-adjustment) hue, so an adjustment
    that moves hue counts toward the drift total."""
    mini = _mini_spec({"a": _role("a", "azure")})
    day = _variant("day", {
        "a": _trace("a", "day", 0.7, 0.10, 245, salience_family="azure"),
    })
    night = _variant("night", {
        # realized hue pushed 15deg by an adjustment -> over the 12deg cap
        "a": _trace("a", "night", 0.7, 0.10, 260, salience_family="azure"),
    })
    st = family_stability_build({"day": day, "night": night}, mini)
    assert any(d["role"] == "a" for d in st["drift_violations"])
    assert st["max_hue_drift_deg"] > 12.0


def test_real_build_drift_is_within_cap(spec):
    fb = build_family(_binding(), spec)
    assert fb.stability["drift_violations"] == []
    assert fb.stability["max_hue_drift_deg"] <= 12.0 + 1e-6


# ===========================================================================
# systematic stability integration
# ===========================================================================


def test_systematic_build_stability_is_ok(spec):
    fb = build_family(_binding(), spec)
    st = fb.stability
    assert st["ok"] is True
    assert st["normalized_chroma_inversions"] == []
    assert st["cyclic_family_sequence_preserved"] is True


# ===========================================================================
# compare_families (beside build_family, not inside)
# ===========================================================================


def _palette_from_build(fb, variant):
    return fb.variants[variant].palette


def test_hand_tuned_build_wraps_partial_palettes(spec):
    from grotto.spec import load
    hand = {v: load(REPO / f"themes/fixtures/eval-{v}.yaml") for v in ("day", "evening", "night")}
    ht = hand_tuned_build(hand, spec, "eval-fixture")
    assert set(ht.variants) == {"day", "evening", "night"}
    # partial fixtures (no bg_overlay) must not crash the stability check
    assert ht.stability is not None
    assert ht.input_hash  # deterministic


def test_compare_families_reports_per_role_deltas(spec):
    fb = build_family(_binding(), spec)
    from grotto.spec import load
    hand = {v: load(REPO / f"themes/fixtures/eval-{v}.yaml") for v in ("day", "evening", "night")}
    ht = hand_tuned_build(hand, spec)
    cmp = compare_families(fb, ht, spec)
    s = cmp["summary"]
    assert s["n_roles_compared"] > 0
    assert s["threshold_de"] == COMPARE_DE_THRESHOLD
    assert "systematic_needed_hand_adjustment" in s
    # per-role rows carry deltas
    row = cmp["per_role"][0]
    for k in ("de", "dL", "dC", "dh", "needs_adjustment"):
        assert k in row


def test_compare_families_identical_builds_need_no_adjustment(spec):
    """A systematic build compared with itself needs zero hand adjustment."""
    fb = build_family(_binding(), spec)
    cmp = compare_families(fb, fb, spec)
    assert cmp["summary"]["de_mean"] == pytest.approx(0.0)
    assert cmp["summary"]["n_needing_adjustment"] == 0
    assert cmp["summary"]["systematic_needed_hand_adjustment"] is False


def test_compare_families_detects_divergence(spec):
    """When hand-tuned differs from systematic, the finding flags it."""
    fb = build_family(_binding(), spec)
    # build a second, deliberately different systematic family
    fb2 = build_family(_binding(candidate_scale=1.0, family_scales={"azure": 2.0}), spec)
    cmp = compare_families(fb, fb2, spec)
    assert cmp["summary"]["systematic_needed_hand_adjustment"] is True
    assert cmp["summary"]["n_needing_adjustment"] > 0


def test_comparison_and_build_outputs_are_json_serializable(spec):
    import json
    fb = build_family(_binding(), spec)
    from grotto.spec import load
    hand = {v: load(REPO / f"themes/fixtures/eval-{v}.yaml") for v in ("day", "evening", "night")}
    ht = hand_tuned_build(hand, spec)
    cmp = compare_families(fb, ht, spec)
    json.dumps(fb.to_dict())
    json.dumps(cmp)
