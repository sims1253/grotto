"""Regression tests for report invariants fixed after the Phase-6 review.

Covers: band membership on OVERLAPPING bands (name equality was a false
MISMATCH), salience-budget enforcement, display-model provenance, vacuous
seed values in the candidate matrix, the reference file_stem, and the
corrected stability-checker semantics (near-tie flips, equal-salience ties).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from grotto.environments import Environments
from grotto.report import palette_report_dict
from grotto.spec import (
    COVERAGE_MODELS,
    DistanceSpec,
    Palette,
    Role,
    RoleSpec,
    load,
    salience_coverage,
)

REPO = Path(__file__).resolve().parents[1]


def _load_all():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    return roles, dists, env


# ---------------------------------------------------------------------------
# band membership on overlapping bands
# ---------------------------------------------------------------------------


def test_overlap_zone_is_in_target_band_not_a_mismatch():
    """|Lc| 75-78 lies in BOTH comfortable and high.  The role targets
    comfortable; band_for_lc classifies it 'high' (first match, maximal ->
    minimal).  Name equality flagged MISMATCH; membership must not."""
    roles, dists, env = _load_all()
    fg = Role(
        name="fg", group="neutrals", description="", salience=2, family="neutral",
        chroma_class="trace", contrast_target="comfortable", cvd_priority="low",
        night_adaptation=1.0, area_class="major",
    )
    spec = RoleSpec(version=1, roles={"bg": roles.roles["bg"], "fg": fg})
    # #6b6b6b on #ffffff measures |Lc| ~ 76.5: inside comfortable AND high
    pal = Palette("t", "day", {"bg": "#ffffff", "fg": "#6b6b6b"})
    rep = palette_report_dict(pal, spec, _dists_for(spec), env)
    cr = rep["contrast_vs_bg"]["fg"]
    assert env.contrast_bands["comfortable"].contains(abs(cr["apca_lc"]))
    assert env.contrast_bands["high"].contains(abs(cr["apca_lc"]))
    assert cr["measured_band"] == "high"  # first-match classification
    assert cr["band_match"] is True       # but membership in the target band


def _dists_for(roles):
    # a minimal, all-satisfied distance spec for the synthetic palettes above
    d = DistanceSpec(version=1, thresholds={}, constraints=())
    return d


# ---------------------------------------------------------------------------
# salience budget
# ---------------------------------------------------------------------------


def test_salience_coverage_known_values():
    """Hand-computed from the declared 'code' plan: salience-3+ roles are
    keyword/string/function/type/number; denominator is every non-bg role
    present."""
    roles, _, _ = _load_all()
    pal = Palette("t", "night", {r: "#123456" for r in
                                 ("bg", "fg", "comment", "punctuation", "keyword",
                                  "string", "function", "type", "number")})
    plan = COVERAGE_MODELS["code"]
    num3 = sum(plan[r] for r in ("keyword", "string", "function", "type", "number"))
    # denominator: non-bg plan roles the palette renders as themselves
    # (bg_elevated is NOT in this palette, so its share is excluded too)
    den = sum(frac for r, frac in plan.items() if r != "bg" and r != "bg_elevated")
    sc = salience_coverage(pal, roles, "code")
    assert sc["at_or_above_3"] == pytest.approx(num3 / den, abs=1e-9)
    assert sc["at_or_above_5"] == 0.0  # nothing at alert level in the plan
    assert sc["at_or_above_0"] == pytest.approx(1.0, abs=1e-9)


def test_salience_coverage_excludes_absent_roles_from_both_sides():
    roles, _, _ = _load_all()
    plan = COVERAGE_MODELS["code"]
    pal = Palette("t", "night", {"bg": "#000000", "fg": "#ffffff", "keyword": "#ff0000"})
    den = plan["fg"] + plan["keyword"]
    sc = salience_coverage(pal, roles, "code")
    assert sc["at_or_above_3"] == pytest.approx(plan["keyword"] / den, abs=1e-9)


def test_palette_report_carries_budget_check():
    """The budget ships recalibrated at 0.22 (the hierarchy measures ~19%
    under the 'code' estimate; the original 0.10 was a pre-measurement
    judgment that contradicted the hierarchy -- see environments.yaml).  The
    committed candidates must PASS the shipped budget, and a tighter budget
    must produce a reported violation with the same machinery."""
    from dataclasses import replace

    from grotto.report import to_text

    roles, dists, env = _load_all()
    pal = load(REPO / "themes/candidates/candidate-b-balanced.evening.yaml")

    # shipped budget: candidates sit just under it
    rep = palette_report_dict(pal, roles, dists, env)
    sal = rep["salience_budget"]
    assert sal["fractions"]["at_or_above_3"] <= env.salience_budget["max_fraction_at_or_above_3"]
    assert sal["ok"] is True and sal["violations"] == []
    assert "within budget" in to_text(rep)

    # the original 0.10 judgment must still be enforced as a violation when set
    tight = replace(
        env,
        salience_budget={"max_fraction_at_or_above_3": 0.10,
                         "max_fraction_at_or_above_5": 0.01},
    )
    rep_t = palette_report_dict(pal, roles, dists, tight)
    sal_t = rep_t["salience_budget"]
    assert sal_t["ok"] is False
    assert sal_t["violations"] and sal_t["violations"][0]["level"] == "at_or_above_3"
    assert "BUDGET VIOLATION" in to_text(rep_t)


# ---------------------------------------------------------------------------
# provenance: display model
# ---------------------------------------------------------------------------


def test_unknown_display_name_raises_instead_of_mislabelling():
    roles, dists, env = _load_all()
    pal = load(REPO / "themes/fixtures/eval-night-full.yaml")
    with pytest.raises(ValueError, match="unknown display model"):
        palette_report_dict(pal, roles, dists, env, display="oled2")


# ---------------------------------------------------------------------------
# candidate matrix seeds
# ---------------------------------------------------------------------------


def test_cvd_summary_worst_retention_is_none_when_nothing_measured():
    from grotto.candidate_report import cvd_summary
    from grotto.model import ModelSpec

    roles, dists, env = _load_all()
    spec = ModelSpec(roles, env, dists)
    # a palette missing every must_distinguish pair member
    pal = Palette("t", "night", {"bg": "#101010"})
    out = cvd_summary(pal, roles, spec)
    assert out["n_pairs"] == 0
    assert out["worst_retention"] is None  # not a vacuous 1.0


def test_min_wcag_is_none_without_body_text_roles():
    from grotto.candidate_report import _min_wcag
    from grotto.model import ModelSpec

    roles, dists, env = _load_all()
    spec = ModelSpec(roles, env, dists)
    pal = Palette("t", "night", {"bg": "#101010", "line_number": "#888888"})
    assert _min_wcag(pal, roles, spec) is None  # not a vacuous 0.0


def test_declared_area_covers_every_area_category_role():
    """DECLARED_AREA once silently omitted `property`, zeroing its pixel
    weight while AREA_CATEGORIES still listed it."""
    from grotto.candidate_report import AREA_CATEGORIES, DECLARED_AREA

    for cat, role_list in AREA_CATEGORIES.items():
        for r in role_list:
            assert r in DECLARED_AREA, f"{cat}.{r} missing from DECLARED_AREA"


# ---------------------------------------------------------------------------
# reference analysis provenance
# ---------------------------------------------------------------------------


def test_reference_analysis_reports_real_file_stem():
    from grotto.reference_analysis import analyze_reference, load_reference_file, primary_variant

    roles, dists, env = _load_all()
    variants = load_reference_file(REPO / "themes/references/nord.yaml")
    an = analyze_reference(primary_variant(variants), roles, dists, env)
    assert an["reference"]["file_stem"] == "nord"  # was always "" before


# ---------------------------------------------------------------------------
# stability checker: near ties and equal salience
# ---------------------------------------------------------------------------


def _family_with_near_tie_inversion():
    """Two same-family roles whose normalized chroma ordering flips between
    two variants, with one side inside the tie epsilon."""
    from grotto.model import (
        CandidateBinding, FamilyAnchor, ModelSpec, VariantBuild, family_stability_build,
    )
    from grotto.spec import DistanceSpec

    roles = RoleSpec(version=1, roles={
        "bg": _mk_role("bg", salience=0, family="neutral"),
        "a": _mk_role("a", salience=3, family="violet"),
        "b": _mk_role("b", salience=3, family="violet"),
    })
    dists = DistanceSpec(version=1, thresholds={}, constraints=())
    env = Environments.load(REPO / "spec/environments.yaml")
    spec = ModelSpec(roles, env, dists)

    def vb(variant, ca_a, ca_b):
        # realized C/max_chroma values hand-set through the trace tuples
        from grotto.model import RoleTrace
        traces = {}
        for name, C, L, h in (("bg", 0.0, 0.2, 70), ("a", ca_a, 0.7, 308), ("b", ca_b, 0.7, 308)):
            traces[name] = RoleTrace(
                role=name, paint="ink", variant=variant, family="violet",
                base_oklch=(L, C, h), requested=(L, C, h), capped=(L, C, h),
                realized=(L, C, h), final_hex="#123456", max_chroma_at_L=0.15,
                chroma_losses={"requested": C, "capped": C, "realized": C,
                               "cap_loss": 0.0, "gamut_loss": 0.0, "total_loss": 0.0,
                               "realized_fraction": 1.0},
                adjustments_applied={"L": 0.0, "C": 0.0, "h": 0.0},
                contrast={}, conflicts=[], winning_constraint="test",
                derivation=[], issues=[],
            )
        pal = Palette("t", variant, {})
        return VariantBuild(variant, pal, traces)

    # day: a clearly below b;  night: a marginally above b (inside 0.02)
    variants = {
        "day": vb("day", 0.050, 0.200),
        "night": vb("night", 0.202, 0.200),
    }
    return family_stability_build(variants, spec)


def _mk_role(name, salience, family):
    return Role(
        name=name, group="syntax", description="", salience=salience, family=family,
        chroma_class="medium", contrast_target="comfortable", cvd_priority="normal",
        night_adaptation=1.0, area_class="minor",
    )


def test_near_tie_flip_reported_but_not_a_failure():
    st = _family_with_near_tie_inversion()
    assert st["normalized_chroma_near_tie_flips"], "flip must still be visible"
    assert st["normalized_chroma_inversions"] == []
    assert st["ok"] is True


def test_material_inversion_still_fails_the_gate():
    st = _family_with_near_tie_inversion()
    # widen the night-side gap beyond the epsilon: now it is a real inversion
    from grotto.model import CHROMA_ORDER_TIE_EPS, family_stability_build

    day = st  # rebuild with a material night gap
    from grotto.model import CandidateBinding, ModelSpec, VariantBuild, RoleTrace
    from grotto.spec import DistanceSpec
    roles = RoleSpec(version=1, roles={
        "bg": _mk_role("bg", 0, "neutral"),
        "a": _mk_role("a", 3, "violet"),
        "b": _mk_role("b", 3, "violet"),
    })
    spec = ModelSpec(roles, Environments.load(REPO / "spec/environments.yaml"),
                     DistanceSpec(version=1, thresholds={}, constraints=()))

    def vb(variant, ca_a, ca_b):
        traces = {}
        for name, C in (("bg", 0.0), ("a", ca_a), ("b", ca_b)):
            L, h = (0.2, 70) if name == "bg" else (0.7, 308)
            traces[name] = RoleTrace(
                role=name, paint="ink", variant=variant, family="violet",
                base_oklch=(L, C, h), requested=(L, C, h), capped=(L, C, h),
                realized=(L, C, h), final_hex="#123456", max_chroma_at_L=0.15,
                chroma_losses={"requested": C, "capped": C, "realized": C,
                               "cap_loss": 0.0, "gamut_loss": 0.0, "total_loss": 0.0,
                               "realized_fraction": 1.0},
                adjustments_applied={"L": 0.0, "C": 0.0, "h": 0.0},
                contrast={}, conflicts=[], winning_constraint="test",
                derivation=[], issues=[],
            )
        return VariantBuild(variant, Palette("t", variant, {}), traces)

    st2 = family_stability_build(
        {"day": vb("day", 0.050, 0.200),
         "night": vb("night", 0.200 + 2 * CHROMA_ORDER_TIE_EPS, 0.200)},
        spec,
    )
    assert st2["normalized_chroma_inversions"]
    assert st2["ok"] is False


def test_equal_salience_pairs_are_not_reversals():
    """constant and decorator both sit at salience 3 -- no ordering is implied
    between them, so their chroma order is not a 'reversal'."""
    from grotto.model import ModelSpec, VariantBuild, family_stability_build, RoleTrace
    from grotto.spec import DistanceSpec

    roles = RoleSpec(version=1, roles={
        "bg": _mk_role("bg", 0, "neutral"),
        "constant": _mk_role("constant", 3, "sand"),
        "decorator": _mk_role("decorator", 3, "sand"),
        "warning": _mk_role("warning", 5, "sand"),   # genuinely higher
    })
    spec = ModelSpec(roles, Environments.load(REPO / "spec/environments.yaml"),
                     DistanceSpec(version=1, thresholds={}, constraints=()))

    def vb(variant):
        # chroma values must stay above the 0.02 chromatic floor; warning (5)
        # carries LESS normalized chroma than the level-3 roles -> a real
        # cross-level reversal, while constant/decorator are an equal-level
        # pair that must NOT be flagged.
        vals = {"bg": (0.2, 0.0, 70), "constant": (0.7, 0.10, 78),
                "decorator": (0.7, 0.03, 78), "warning": (0.7, 0.025, 78)}
        traces = {}
        for name, (L, C, h) in vals.items():
            traces[name] = RoleTrace(
                role=name, paint="ink", variant=variant, family="sand",
                base_oklch=(L, C, h), requested=(L, C, h), capped=(L, C, h),
                realized=(L, C, h), final_hex="#123456", max_chroma_at_L=0.15,
                chroma_losses={"requested": C, "capped": C, "realized": C,
                               "cap_loss": 0.0, "gamut_loss": 0.0, "total_loss": 0.0,
                               "realized_fraction": 1.0},
                adjustments_applied={"L": 0.0, "C": 0.0, "h": 0.0},
                contrast={}, conflicts=[], winning_constraint="test",
                derivation=[], issues=[],
            )
        return VariantBuild(variant, Palette("t", variant, {}), traces)

    st = family_stability_build({"day": vb("day")}, spec)
    reversals = [(r["lower_salience"], r["higher_salience"])
                 for r in st["salience_proxy_reversals"]]
    # decorator(3) > constant(3) chroma-wise: NOT a reversal (equal salience)
    assert ("constant", "decorator") not in reversals
    # warning(5) < constant(3) chroma-wise: IS a reversal (different levels)
    assert any(hi == "warning" for _, hi in reversals)
