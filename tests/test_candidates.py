"""Phase 5 candidate bindings: three strategies, one shared transform.

Covers the Phase 5 acceptance points:
  * exactly three candidate bindings live under spec/bindings/;
  * each is a real candidate (meta.candidate true) and builds ok=True (hard WCAG
    floors pass; soft distance/CVD/legibility issues stay visible);
  * the three are ONE binding each -> day/evening/night via the SAME shared
    transform (no per-variant hand palettes; backgrounds identical);
  * the three strategies are measurably distinct in realised chroma/salience and
    cannot accidentally collapse (strict ordering A < B < C);
  * candidate-specific chroma classes + per-category caps are FIRST-CLASS
    inputs: they change the solve, appear in the trace, and are part of the
    input hash / canonical binding;
  * family overrides work (tag hue differs per candidate) while the derivation
    path identity (paint/name) stays protected.
"""

from __future__ import annotations

import glob
import statistics
from pathlib import Path

import pytest

from grotto.color import hex_to_oklch
from grotto.model import (
    CHROMA_CATEGORIES,
    BindingError,
    CandidateBinding,
    FamilyAnchor,
    ModelSpec,
    build_family,
    chroma_category,
    effective_ceiling,
    validate_binding,
)
from grotto.spec import DistanceSpec, RoleSpec
from grotto.environments import Environments

REPO = Path(__file__).resolve().parents[1]
BINDING_GLOB = "spec/bindings/candidate-*.yaml"

# ordered strategy -> binding stem (alphabetical = A, B, C by design)
STRATEGIES = ("a-restrained", "b-balanced", "c-expressive")


@pytest.fixture(scope="module")
def spec() -> ModelSpec:
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    return ModelSpec(roles, env, dists)


@pytest.fixture(scope="module")
def families(spec) -> dict[str, "object"]:
    out = {}
    for s in STRATEGIES:
        b = CandidateBinding.load(REPO / "spec/bindings" / f"candidate-{s}.yaml")
        out[s] = build_family(b, spec)
    return out


# ===========================================================================
# 1. exactly three candidates, all real candidates, all build
# ===========================================================================


def test_exactly_three_candidate_bindings_exist():
    paths = sorted(glob.glob(str(REPO / BINDING_GLOB)))
    stems = {Path(p).stem for p in paths}
    assert len(paths) == 3, f"expected exactly 3 candidate bindings, found {len(paths)}"
    assert stems == {
        "candidate-a-restrained",
        "candidate-b-balanced",
        "candidate-c-expressive",
    }


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_each_binding_is_a_candidate_and_builds_ok(strategy, spec):
    b = CandidateBinding.load(REPO / "spec/bindings" / f"candidate-{strategy}.yaml")
    assert b.is_candidate is True
    assert b.meta.get("strategy"), f"{strategy}: meta.strategy must document the hypothesis"
    assert b.meta.get("purpose"), f"{strategy}: meta.purpose must document the hypothesis"
    assert b.meta.get("tradeoffs"), f"{strategy}: meta.tradeoffs must be flagged"
    fb = build_family(b, spec)
    # hard WCAG floors must pass or generation fails; ok=True is the gate
    assert fb.ok is True, f"{strategy}: a hard WCAG floor was breached"
    # soft issues (distance/CVD/legibility) stay visible and are NOT massaged away
    assert isinstance(fb.issues, list)


# ===========================================================================
# 2. one binding -> three variants; shared environment (no hand palettes)
# ===========================================================================


@pytest.mark.parametrize("strategy", STRATEGIES)
def test_one_binding_produces_three_variants_with_all_roles(strategy, families, spec):
    fb = families[strategy]
    assert set(fb.variants) == {"day", "evening", "night"}
    for v in ("day", "evening", "night"):
        assert len(fb.variants[v].palette) == len(spec.roles)
        for r in spec.roles:
            assert r.name in fb.variants[v].palette


def test_backgrounds_are_identical_across_candidates(families):
    """The shared environment transform must produce the same canvas/elevated/
    overlay for every candidate -- candidates differ only in chromatic budget,
    never in the contrast reference."""
    for role in ("bg", "bg_elevated", "bg_overlay"):
        for v in ("day", "evening", "night"):
            hexes = {families[s].variants[v].palette[role] for s in STRATEGIES}
            assert len(hexes) == 1, f"{role}@{v} differs across candidates: {hexes}"


def test_candidate_scale_is_one_so_class_fractions_are_the_lever(families):
    """The brief's class fractions are the primary lever; candidate_scale stays
    at 1.0 (no hidden global multiplier on top of the declared fractions)."""
    for s in STRATEGIES:
        assert families[s].binding.candidate_scale == pytest.approx(1.0)


# ===========================================================================
# 3. measurably distinct: strict chroma/salience ordering A < B < C
# ===========================================================================


def _mean_realized_chroma(fb) -> float:
    cs = [
        hex_to_oklch(fb.variants[v].palette[r.name])[1]
        for v in ("day", "evening", "night")
        for r in fb.spec.roles
    ]
    return statistics.mean(cs)


def test_strict_chroma_ordering_restrained_to_expressive(families):
    """The three strategies must be measurably distinct and cannot collapse."""
    a, b, c = (_mean_realized_chroma(families[s]) for s in STRATEGIES)
    assert a < b < c, f"expected A < B < C mean realized chroma, got A={a:.4f} B={b:.4f} C={c:.4f}"
    # non-trivial separation (not a rounding artifact)
    assert (c - a) > 0.005


def test_palettes_are_not_identical(families):
    """Distinct budgets must yield distinct final hex sets."""
    night_sets = {
        s: {fb.variants["night"].palette[r.name] for r in families[s].spec.roles}
        for s, fb in families.items()
    }
    assert night_sets["a-restrained"] != night_sets["c-expressive"]


def test_hashes_are_distinct(families):
    hashes = {families[s].input_hash for s in STRATEGIES}
    assert len(hashes) == 3


# ===========================================================================
# 4. candidate chroma classes + category caps are first-class inputs
# ===========================================================================


def test_candidate_chroma_classes_and_caps_are_in_canonical(spec):
    """The candidate budget is part of the binding's canonical (hashable) form,
    so it flows into provenance and the input hash."""
    for s in STRATEGIES:
        b = CandidateBinding.load(REPO / "spec/bindings" / f"candidate-{s}.yaml")
        canon = b.canonical()
        assert canon["chroma_classes"], f"{s}: chroma_classes missing from canonical"
        assert canon["category_caps"], f"{s}: category_caps missing from canonical"
        # the four documented categories are all declared
        assert set(canon["category_caps"]) == set(CHROMA_CATEGORIES)


def test_chroma_classes_change_the_hash(spec):
    """Removing a candidate's own class fractions must change its identity hash,
    proving the budget is a first-class input and not faked after the fact."""
    b = CandidateBinding.load(REPO / "spec/bindings/candidate-a-restrained.yaml")
    h_with = build_family(b, spec).input_hash
    b_without = CandidateBinding(
        b.name, b.candidate_scale, b.anchors, role_scales=dict(b.role_scales),
        role_overrides={k: dict(v) for k, v in b.role_overrides.items()},
        warm_anchor_override=b.warm_anchor_override, meta=dict(b.meta),
    )  # chroma_classes / category_caps default to empty -> shared environment
    h_without = build_family(b_without, spec).input_hash
    assert h_with != h_without


def test_category_caps_affect_the_solve(families, spec):
    """A role's trace must record the per-category ceiling it was solved under,
    matching the candidate's declared cap for that category."""
    b = families["a-restrained"].binding
    # error is a diagnostics role -> diagnostics cap (.160 for A)
    t_err = families["a-restrained"].trace("night", "error")
    assert t_err.chroma_losses["category"] == "diagnostics"
    assert t_err.chroma_losses["ceiling"] == pytest.approx(b.category_caps["diagnostics"])
    # a syntax role is ordinary -> A's ordinary cap (.075)
    t_kw = families["a-restrained"].trace("night", "keyword")
    assert t_kw.chroma_losses["category"] == "ordinary"
    assert t_kw.chroma_losses["ceiling"] == pytest.approx(b.category_caps["ordinary"])
    # the class fraction came from the candidate, not the shared environment
    assert t_kw.chroma_losses["class_fraction_source"] == "candidate"


def test_category_caps_actually_bound_realized_chroma(families):
    """The ordinary cap must actually limit realized chroma where it bites:
    every ordinary-category role's realized C is <= the candidate's ordinary cap."""
    b = families["a-restrained"].binding
    cap = b.category_caps["ordinary"]
    for v in ("day", "evening", "night"):
        for r in families["a-restrained"].spec.roles:
            t = families["a-restrained"].variants[v].traces[r.name]
            if t.chroma_losses["category"] == "ordinary":
                assert t.realized[1] <= cap + 1e-6, (
                    f"{r.name}@{v} realized C {t.realized[1]:.4f} > ordinary cap {cap}"
                )


def test_diagnostics_exempt_from_restraint(families, spec):
    """Candidate A restrains ordinary syntax (.075) but diagnostics keep a
    much higher ceiling (.150) -- safety signals are not muted by the
    restraint."""
    b = families["a-restrained"].binding
    assert b.category_caps["ordinary"] < b.category_caps["diagnostics"]
    t_err = families["a-restrained"].trace("night", "error")
    assert t_err.chroma_losses["ceiling"] == pytest.approx(0.150)


# ===========================================================================
# 5. chroma_category / effective_ceiling helpers
# ===========================================================================


def test_chroma_category_partition(spec):
    cases = {
        "fg": "neutral",            # neutral family
        "comment": "neutral",       # neutral family (default)
        "error": "diagnostics",     # diagnostics group
        "diff_added": "diagnostics",
        "keyword": "ordinary",      # violet
        "function": "ordinary",     # azure
        "string": "ordinary",       # sage
    }
    for role, want in cases.items():
        assert chroma_category(spec.roles[role]) == want, role


def test_effective_ceiling_falls_back_to_global(spec):
    b = CandidateBinding(
        "x", 1.0, {f: FamilyAnchor(f, 0.0, 1.0) for f in (
            "neutral", "warm-neutral", "sand", "rose", "violet", "azure", "sage", "teal")}
    )
    for role in spec.roles:
        assert effective_ceiling(role, b, spec) == pytest.approx(
            spec.environments.chroma_absolute_ceiling
        )


def test_invalid_chroma_budget_is_rejected(spec):
    anchors = {f: FamilyAnchor(f, 0.0, 1.0) for f in (
        "neutral", "warm-neutral", "sand", "rose", "violet", "azure", "sage", "teal")}
    with pytest.raises(BindingError, match="unknown class"):
        validate_binding(
            CandidateBinding("x", 1.0, anchors, chroma_classes={"bogus": 0.5}), spec
        )
    with pytest.raises(BindingError, match="not in"):
        validate_binding(
            CandidateBinding("x", 1.0, anchors, chroma_classes={"low": 1.5}), spec
        )
    with pytest.raises(BindingError, match="unknown category"):
        validate_binding(
            CandidateBinding("x", 1.0, anchors, category_caps={"nope": 0.1}), spec
        )


# ===========================================================================
# 6. family overrides work; derivation-path identity stays protected
# ===========================================================================


def test_family_override_changes_hue(spec):
    """A role_override on family reassigns the anchor the role reads, keeping it
    in the same derivation path. tag is azure by default."""
    anchors = {f: FamilyAnchor(f, h, 1.0) for f, h in {
        "neutral": 0, "warm-neutral": 70, "sand": 80, "rose": 25,
        "violet": 300, "azure": 245, "sage": 145, "teal": 195}.items()}
    base = build_family(CandidateBinding("x", 1.0, anchors), spec)
    override = build_family(
        CandidateBinding("x", 1.0, anchors, role_overrides={"tag": {"family": "violet"}}),
        spec,
    )
    # day has zero hue rotation, so the realized hue reflects the anchor directly
    h_base = base.trace("day", "tag").realized[2]
    h_over = override.trace("day", "tag").realized[2]
    assert abs(((h_over - h_base + 180) % 360) - 180) > 50.0


def test_tag_family_follows_the_candidate_strategy(families):
    """Each candidate documents a distinct tag family (A neutral, B azure,
    C violet); the realized hues must reflect that."""
    hues = {s: families[s].trace("day", "tag").realized[2] for s in STRATEGIES}
    # A: neutral anchor h70 ; B: azure h250 ; C: violet h318
    assert abs(hues["a-restrained"] - 70) < 5
    assert abs(hues["b-balanced"] - 250) < 5
    assert abs(hues["c-expressive"] - 318) < 5


def test_role_scales_are_applied_in_provenance(families):
    """Candidate C's function/keyword boosts and string/builtin restraints are
    real inputs recorded in the chroma-chain components."""
    b = families["c-expressive"].binding
    # keyword/string at parity: the old 1.10/0.90 split inverted the chroma
    # hierarchy across variants (13 material D-5 inversions); see the binding.
    assert b.role_scales["function"] == pytest.approx(1.20)
    assert b.role_scales["keyword"] == pytest.approx(1.0)
    assert b.role_scales["string"] == pytest.approx(1.0)
    assert b.role_scales["builtin"] == pytest.approx(0.90)


def test_balanced_day_accents_do_not_regress_to_muted_revision(families):
    """Phase-7 feedback: keep each medium accent above its observed floor."""
    fb = families["b-balanced"]
    floors = {"keyword": 0.14, "string": 0.099, "type": 0.059, "function": 0.072}
    for role, floor in floors.items():
        assert fb.trace("day", role).realized[1] >= floor


def test_family_override_cannot_change_paint_or_name(spec):
    """family is overridable; paint (the derivation path) and name are not."""
    anchors = {f: FamilyAnchor(f, 0.0, 1.0) for f in (
        "neutral", "warm-neutral", "sand", "rose", "violet", "azure", "sage", "teal")}
    with pytest.raises(BindingError, match="unknown key"):
        validate_binding(
            CandidateBinding("x", 1.0, anchors, role_overrides={"fg": {"paint": "surface"}}),
            spec,
        )
