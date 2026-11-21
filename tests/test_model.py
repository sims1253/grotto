"""Phase 4 core transform: build_family solver and provenance (commit 2).

Covers the solver acceptance points: validation/order determinism, all
roles/variants, all direct backgrounds, light/dark target solve, WCAG-vs-APCA
and ceiling conflicts, infeasible floor, exact zero chroma, independent
losses, final sRGB, warm attraction for azure/violet with bounds, bounded
adjustments, distinct paint logic, ink-on-surface checks, and overrides.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from grotto.color import (
    gamut_map,
    gamut_status,
    hex_to_oklch,
    max_chroma,
    oklch_to_hex,
)
from grotto.contrast import wcag_contrast
from grotto.environments import (
    EnvironmentBackground,
    Environments,
    Environment,
)
from grotto.model import (
    ADJUSTMENT_LIMITS,
    CO_OCCURRING_SURFACES,
    NORMAL_SALIENCE,
    BindingError,
    CandidateBinding,
    FamilyAnchor,
    ModelSpec,
    RoleAdjustment,
    TransformError,
    _contrast_block,
    _evaluate_legibility,
    _solve_contrast_role,
    adapt_hue,
    build_family,
    chroma_components,
    circular_drift,
    signed_shortest_arc,
    validate_binding,
)
from grotto.spec import DistanceSpec, RoleSpec

REPO = Path(__file__).resolve().parents[1]

FAMILY_HUES = {
    "neutral": 0, "warm-neutral": 70, "sand": 80, "rose": 25,
    "violet": 300, "azure": 245, "sage": 145, "teal": 195,
}


@pytest.fixture(scope="module")
def spec() -> ModelSpec:
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    return ModelSpec(roles, env, dists)


def binding(name="test", candidate_scale=1.0, **kw) -> CandidateBinding:
    family_scales = kw.pop("family_scales", {})
    anchors = {f: FamilyAnchor(f, h, family_scales.get(f, 1.0))
               for f, h in FAMILY_HUES.items()}
    return CandidateBinding(name, candidate_scale, anchors, **kw)


# ===========================================================================
# 1. validation / order determinism
# ===========================================================================


def test_missing_anchor_for_used_family_is_rejected(spec):
    anchors = {f: FamilyAnchor(f, h, 1.0) for f, h in FAMILY_HUES.items() if f != "violet"}
    b = CandidateBinding("x", 1.0, anchors)
    with pytest.raises(BindingError, match="violet"):
        validate_binding(b, spec)


def test_unknown_family_in_anchor_is_rejected(spec):
    anchors = {**{f: FamilyAnchor(f, h, 1.0) for f, h in FAMILY_HUES.items()},
               "bogus": FamilyAnchor("bogus", 50, 1.0)}
    b = CandidateBinding("x", 1.0, anchors)
    with pytest.raises(BindingError, match="unknown families"):
        validate_binding(b, spec)


def test_out_of_range_scale_is_rejected(spec):
    b = binding(candidate_scale=0.0)
    with pytest.raises(BindingError, match="candidate_scale"):
        validate_binding(b, spec)
    b2 = binding(role_scales={"fg": 99.0})
    with pytest.raises(BindingError, match="role_scale"):
        validate_binding(b2, spec)


def test_unknown_role_in_adjustment_is_rejected(spec):
    b = binding(adjustments={"nope": RoleAdjustment("nope", L=0.01)})
    with pytest.raises(BindingError, match="unknown roles"):
        validate_binding(b, spec)


def _anchors_with_violet_hue(h: float) -> CandidateBinding:
    anchors = {f: FamilyAnchor(f, h if f == "violet" else hue, 1.0)
               for f, hue in FAMILY_HUES.items()}
    return CandidateBinding("x", 1.0, anchors)


def test_anchor_hue_outside_circle_is_rejected(spec):
    """h=-10 and h=360 are malformed bindings.  The old nested modulo fallback
    silently accepted both (-10 as 350, 360 as 0) while the error message
    claimed "not in [0, 360)".  Anchors must arrive canonical."""
    import re
    for bad in (-10.0, 360.0):
        with pytest.raises(BindingError, match=re.escape("not in [0, 360)")):
            validate_binding(_anchors_with_violet_hue(bad), spec)


def test_anchor_hue_circle_bounds_accept_zero_and_just_under_360(spec):
    for good in (0.0, 359.9):
        validate_binding(_anchors_with_violet_hue(good), spec)  # no raise


def test_canonical_binding_is_deterministic_and_sorted(spec):
    b = binding()
    c1 = b.canonical()
    c2 = b.canonical()
    assert c1 == c2
    # anchors sorted by family
    assert list(c1["anchors"]) == sorted(c1["anchors"])
    assert list(c1["role_scales"]) == sorted(c1["role_scales"])


def test_build_is_a_pure_function(spec):
    fb1 = build_family(binding("a"), spec)
    fb2 = build_family(binding("a"), spec)
    assert fb1.input_hash == fb2.input_hash
    # byte-identical serialisation
    import json
    assert json.dumps(fb1.to_dict(), sort_keys=True) == json.dumps(fb2.to_dict(), sort_keys=True)


def test_different_bindings_have_different_hashes(spec):
    h1 = build_family(binding("a"), spec).input_hash
    h2 = build_family(binding("b", candidate_scale=1.1), spec).input_hash
    assert h1 != h2


def test_hash_includes_role_overrides_meta_and_full_spec(spec):
    base = build_family(binding("same"), spec).input_hash
    override = build_family(
        binding("same", role_overrides={"keyword": {"contrast_target": "high"}}),
        spec,
    ).input_hash
    metadata = build_family(
        binding("same", meta={"candidate": True, "strategy": "audit"}), spec
    ).input_hash
    floors = {
        **spec.environments.accessibility_floors,
        "body_text_wcag": 4.6,
    }
    changed_env = replace(spec.environments, accessibility_floors=floors)
    changed_spec = replace(spec, environments=changed_env)
    spec_hash = build_family(binding("same"), changed_spec).input_hash
    assert len({base, override, metadata, spec_hash}) == 4


# ===========================================================================
# 2. all roles / variants
# ===========================================================================


def test_builds_all_three_variants_and_all_roles(spec):
    fb = build_family(binding(), spec)
    assert set(fb.variants) == {"day", "evening", "night"}
    for v in ("day", "evening", "night"):
        pal = fb.variants[v].palette
        assert len(pal) == len(spec.roles), f"{v} missing roles"
        for r in spec.roles:
            assert r.name in pal, f"{v} missing {r.name}"


# ===========================================================================
# 3. all direct backgrounds are authored verbatim
# ===========================================================================


def test_direct_backgrounds_match_environment_verbatim(spec):
    fb = build_family(binding(), spec)
    for v in ("day", "evening", "night"):
        env = spec.environments.environments[v]
        pal = fb.variants[v].palette
        for role, src in (("bg", "background"),
                          ("bg_elevated", "background_elevated"),
                          ("bg_overlay", "background_overlay")):
            want = getattr(env, src)
            L, C, h = hex_to_oklch(pal[role])
            # 8-bit quantization tolerance
            assert L == pytest.approx(want.L, abs=2e-3)
            assert C == pytest.approx(want.C, abs=2e-3)
            # hue is meaningless for near-achromatic authored backgrounds
            # (C < 0.02): it is noise after the sRGB round-trip, not a real
            # authoring error. Compare it only when the canvas has real chroma.
            if want.C >= 0.02:
                assert ((h - want.h + 180) % 360 - 180) == pytest.approx(0, abs=3.0)
        # the three direct backgrounds are all paint=surface-or-canvas authored
        for role in ("bg", "bg_elevated", "bg_overlay"):
            assert fb.trace(v, role).winning_constraint == "authored"


# ===========================================================================
# 4. light/dark target solve
# ===========================================================================


def test_polarity_inverts_ink_lightness(spec):
    """Day (light bg): ink is DARKER than bg. Night (dark bg): ink LIGHTER."""
    fb = build_family(binding(), spec)
    for v, sign in (("day", -1), ("night", +1)):
        bg_L = hex_to_oklch(fb.variants[v].palette["bg"])[0]
        fg_L = hex_to_oklch(fb.variants[v].palette["fg"])[0]
        assert (fg_L - bg_L) * sign > 0, f"{v}: fg/bg lightness polarity wrong"


def test_ink_hits_apca_centre_when_unconstrained(spec):
    """fg (comfortable, centre 68) should land near its APCA band centre."""
    fb = build_family(binding(), spec)
    from grotto.contrast import apca_lc
    for v in ("day", "night"):
        lc = abs(apca_lc(fb.variants[v].palette["fg"], fb.variants[v].palette["bg"]))
        # centre 68; allow generous tolerance (ceiling/floor may nudge it)
        assert 55 < lc < 90, f"{v} fg |Lc|={lc:.1f} not near centre"


# ===========================================================================
# 5. WCAG-vs-APCA conflict and ceiling conflicts
# ===========================================================================


def test_wcag_overrides_apca_and_records_conflict(spec):
    # fg is body_text (4.5 floor); force its target band down to 'minimal'
    # (APCA centre 24) so the APCA preference would violate WCAG.
    b = binding(role_overrides={"fg": {"contrast_target": "minimal"}})
    fb = build_family(b, spec)
    t = fb.trace("night", "fg")
    assert "wcag_apca_conflict" in t.conflicts
    assert t.winning_constraint == "wcag_floor"
    # and the final fg still meets the body-text floor
    assert wcag_contrast(fb.variants["night"].palette["fg"],
                         fb.variants["night"].palette["bg"]) >= 4.5 - 1e-6


def test_foreground_ceiling_overridden_when_wcag_requires_it(spec):
    """A night bg so light that meeting 4.5 forces ink above the 0.88 ceiling."""
    fb = build_family(binding(), spec)
    bg = fb.variants["night"].palette["bg"]
    # sanity: normal night does not override for fg
    assert "foreground_ceiling_overridden" not in fb.trace("night", "fg").conflicts

    # construct a night environment with a light canvas + a tight ceiling so
    # that meeting 4.5 forces body-text inks above the ceiling (but white can
    # still reach 4.5, so it is an override, not infeasible).
    env = spec.environments
    night = env.environments["night"]
    light_night = replace(
        night,
        background=EnvironmentBackground(0.50, 0.005, 70.0),
        background_elevated=EnvironmentBackground(0.52, 0.005, 70.0),
        background_overlay=EnvironmentBackground(0.54, 0.005, 70.0),
        foreground_ceiling=0.86,
    )
    new_env = replace(env, environments={**env.environments, "night": light_night})
    spec2 = replace(spec, environments=new_env)
    # day/evening build fine; night's body-text inks must blow past the ceiling
    fb2 = build_family(binding(), spec2)
    overridden = [r for r in spec.roles
                  if "foreground_ceiling_overridden" in (fb2.trace("night", r.name).conflicts
                                                         if r.name in fb2.variants["night"].traces else [])]
    assert overridden, "expected at least one foreground_ceiling_overridden role"
    # those roles still meet WCAG (the override means WCAG won)
    for r in overridden:
        hx = fb2.variants["night"].palette[r.name]
        assert wcag_contrast(hx, fb2.variants["night"].palette["bg"]) >= 4.5 - 1e-6


def test_night_ceiling_wins_between_wcag_floor_and_apca_preference(spec):
    """Isolated night_ceiling branch of the lexicographic solve (priority 3).

    Construct a synthetic night environment whose foreground ceiling sits
    strictly BETWEEN the WCAG-solved floor lightness and the APCA-solved
    preference: the ceiling must cap the preference (winning constraint
    night_ceiling, L_final == ceiling) WITHOUT becoming the WCAG-override
    branch, and the body-text floor must still hold at the capped L.
    """
    env = spec.environments
    night = env.environments["night"]
    bg = night.background
    # the exact reference the transform solves against (model._build_variant)
    bg_hex = oklch_to_hex(gamut_map((bg.L, bg.C, bg.h), "srgb")[0])
    fg = spec.roles.roles["fg"]
    h, _ = adapt_hue(spec, "night", fg, FAMILY_HUES[fg.family], None)

    # probe solve with the ceiling removed -> L_pref is the pure WCAG/APCA
    # resolution, so the test self-calibrates instead of hard-coding an L
    open_env = replace(env, environments={
        **env.environments, "night": replace(night, foreground_ceiling=None)})
    _, probe = _solve_contrast_role(
        fg, h, bg_hex, bg.L, "night", replace(spec, environments=open_env),
        binding(),
    )
    L_wcag, L_pref = probe["L_wcag"], probe["L_pref"]
    assert L_pref > L_wcag + 0.1, "no headroom to place a ceiling between them"
    ceiling = (L_wcag + L_pref) / 2.0
    assert L_wcag <= ceiling < L_pref  # ceiling feasible for WCAG, under APCA pref

    capped_env = replace(env, environments={
        **env.environments, "night": replace(night, foreground_ceiling=ceiling)})
    fb = build_family(binding(), replace(spec, environments=capped_env))
    t = fb.trace("night", "fg")
    assert t.winning_constraint == "night_ceiling"
    assert t.contrast["solve"]["winning_constraint"] == "night_ceiling"
    # the ceiling won over the preference: L_final is exactly the ceiling
    assert t.requested[0] == pytest.approx(ceiling, abs=1e-6)
    # ... and it is NOT the WCAG-override branch (that would be wcag_floor)
    assert "foreground_ceiling_overridden" not in t.conflicts
    # the WCAG floor still holds at the ceiling-capped lightness
    assert wcag_contrast(fb.variants["night"].palette["fg"],
                         fb.variants["night"].palette["bg"]) >= 4.5 - 1e-6


def test_configured_body_text_floor_is_not_hard_coded(spec):
    floors = {
        **spec.environments.accessibility_floors,
        "body_text_wcag": 5.0,
    }
    spec2 = replace(
        spec,
        environments=replace(spec.environments, accessibility_floors=floors),
    )
    fb = build_family(binding(), spec2)
    assert wcag_contrast(
        fb.variants["night"].palette["fg"], fb.variants["night"].palette["bg"]
    ) >= 5.0 - 1e-6


# ===========================================================================
# 6. infeasible floor -> TransformError
# ===========================================================================


def test_infeasible_wcag_floor_raises_transform_error(spec):
    """A night canvas so light that even white ink cannot reach 4.5:1."""
    env = spec.environments
    night = env.environments["night"]
    light_night = replace(
        night,
        background=EnvironmentBackground(0.92, 0.0, 70.0),
        background_elevated=EnvironmentBackground(0.93, 0.0, 70.0),
        background_overlay=EnvironmentBackground(0.94, 0.0, 70.0),
    )
    new_env = replace(env, environments={**env.environments, "night": light_night})
    spec2 = replace(spec, environments=new_env)
    with pytest.raises(TransformError, match="unreachable"):
        build_family(binding(), spec2)


def test_transform_error_only_for_hard_constraints(spec):
    """Distance/legibility misses must NOT raise -- they become issues."""
    fb = build_family(binding(), spec)
    # a default-scale calibration binding produces many distance issues ...
    assert any("must_distinguish" in i for i in fb.issues)
    # ... but the build still succeeds and the floors hold: issues are
    # informational, so ok must be True (WCAG is a hard gate, distance is not)
    assert fb.ok is True


# ===========================================================================
# 7. exact zero chroma for chroma_class none
# ===========================================================================


def test_chroma_class_none_is_exactly_zero(spec):
    fb = build_family(binding(), spec)
    for role in ("punctuation", "operator", "line_number"):
        for v in ("day", "night"):
            t = fb.trace(v, role)
            assert t.chroma_losses["requested"] == pytest.approx(0.0, abs=1e-12)
            assert t.realized[1] == pytest.approx(0.0, abs=1e-9)


# ===========================================================================
# 8. independent cap/gamut losses
# ===========================================================================


def test_cap_and_gamut_losses_are_independent(spec):
    # boost the sand family so a high-chroma role exceeds both the absolute
    # ceiling (cap loss) and the gamut at its solved L (gamut loss)
    b = binding(family_scales={"sand": 2.5})
    fb = build_family(b, spec)
    found = False
    for r in spec.roles:
        t = fb.trace("night", r.name)
        loss = t.chroma_losses
        # structural invariants always hold
        assert loss["total_loss"] == pytest.approx(loss["cap_loss"] + loss["gamut_loss"])
        assert loss["realized_fraction"] == pytest.approx(
            loss["realized"] / loss["requested"] if loss["requested"] > 1e-9 else 1.0)
        if loss["cap_loss"] > 1e-6 and loss["gamut_loss"] > 1e-6:
            found = True
    assert found, "no role exhibited both cap and gamut loss independently"


def test_cap_loss_bounded_by_absolute_ceiling(spec):
    ceiling = spec.environments.chroma_absolute_ceiling
    b = binding(family_scales={"sand": 3.0, "rose": 3.0})
    fb = build_family(b, spec)
    for r in spec.roles:
        t = fb.trace("night", r.name)
        # capped chroma never exceeds the ceiling
        assert t.chroma_losses["capped"] <= ceiling + 1e-9


# ===========================================================================
# 8b. chroma chain factorization (direct unit)
# ===========================================================================


def test_chroma_components_factorisation_identity(spec):
    """requested == max_chroma * class_fraction * candidate * family * role *
    environment_gain * night_term, verified from the returned dict alone with
    every factor non-unit so the identity cannot pass vacuously."""
    b = binding(
        candidate_scale=1.1,
        family_scales={"violet": 0.9},
        role_scales={"keyword": 1.2},
    )
    role = spec.roles.roles["keyword"]  # violet, medium class, night_adaptation 0.8
    env_name, L, h = "night", 0.72, 300.0
    comps = chroma_components(spec, b, role, L, h, env_name)
    env = spec.environments.environments[env_name]

    assert comps["max_chroma"] == pytest.approx(max_chroma(L, h, "srgb"))
    assert comps["class_fraction"] == pytest.approx(
        spec.environments.chroma_classes["medium"])
    assert comps["class_fraction_source"] == "environment"  # no candidate classes
    assert comps["candidate_scale"] == pytest.approx(1.1)
    assert comps["family_scale"] == pytest.approx(0.9)
    assert comps["role_scale"] == pytest.approx(1.2)
    assert comps["environment_gain"] == pytest.approx(env.chroma_gain)
    # night term identity straight from the environment + role
    assert comps["night_term"] == pytest.approx(
        1.0 - env.chroma_attenuation * role.night_adaptation)

    product = (
        comps["max_chroma"] * comps["class_fraction"] * comps["candidate_scale"]
        * comps["family_scale"] * comps["role_scale"] * comps["environment_gain"]
        * comps["night_term"]
    )
    assert comps["requested"] == pytest.approx(product, rel=1e-12)


def test_chroma_components_candidate_classes_override_with_fallback(spec):
    """Phase 5 override path: a binding with chroma_classes set replaces the
    shared fractions for the classes it declares; UNDECLARED classes fall back
    to the environment value while the source flag still reports 'candidate'
    for the whole binding."""
    b = binding(chroma_classes={"medium": 0.33})
    keyword = spec.roles.roles["keyword"]  # chroma_class medium
    fg = spec.roles.roles["fg"]            # chroma_class trace

    med = chroma_components(spec, b, keyword, 0.72, 300.0, "night")
    assert med["class_fraction_source"] == "candidate"
    assert med["class_fraction"] == pytest.approx(0.33)  # declared -> replaced

    trace_cls = chroma_components(spec, b, fg, 0.6, 0.0, "night")
    assert trace_cls["class_fraction_source"] == "candidate"
    assert trace_cls["class_fraction"] == pytest.approx(
        spec.environments.chroma_classes["trace"])  # undeclared -> environment


# ===========================================================================
# 9. final sRGB gamut
# ===========================================================================


def test_every_final_color_is_in_srgb_gamut(spec):
    fb = build_family(binding(), spec)
    for v in ("day", "evening", "night"):
        for role, hx in fb.variants[v].palette.items():
            assert gamut_status(hex_to_oklch(hx)).in_srgb, f"{v}/{role} {hx} out of sRGB"


def test_final_hex_is_six_digit_lowercase(spec):
    import re
    fb = build_family(binding(), spec)
    for v in ("day", "evening", "night"):
        for hx in fb.variants[v].palette.colors.values():
            assert re.fullmatch(r"#[0-9a-f]{6}", hx)


# ===========================================================================
# 10. warm attraction for azure/violet with bounds
# ===========================================================================


def test_violet_moves_warm_not_cool(spec):
    """The senior-review correction: violet (h300) must warm (h increase toward
    magenta/red), NOT cool (a plain negative rotation would move it toward blue)."""
    fb = build_family(binding(), spec)
    t = fb.trace("night", "keyword")  # keyword family is violet, h0=300
    h_night = t.realized[2]
    assert h_night > 300.0, f"violet warmed to {h_night:.1f} (negative rotation bug?)"


def test_azure_also_moves_toward_warm(spec):
    fb = build_family(binding(), spec)
    t = fb.trace("night", "function")  # azure, h0=245
    # azure's shortest arc to the warm anchor goes through teal/green -> hue drops
    assert t.realized[2] < 245.0


def test_day_has_zero_hue_rotation(spec):
    fb = build_family(binding(), spec)
    for role in ("keyword", "function", "string"):
        h0 = FAMILY_HUES[spec.roles.roles[role].family]
        h_day = fb.trace("day", role).realized[2]
        assert ((h_day - h0 + 180) % 360 - 180) == pytest.approx(0.0, abs=1e-6)


def test_hue_drift_is_bounded_by_cap_times_adaptation_times_weight(spec):
    env = spec.environments.environments["night"]
    cap = env.rotation_cap_deg
    fb = build_family(binding(), spec)
    for role in ("keyword", "function", "string", "type"):
        r = spec.roles.roles[role]
        h0 = FAMILY_HUES[r.family]
        h = fb.trace("night", role).realized[2]
        drift = abs(((h - h0 + 180) % 360) - 180)
        bound = cap * r.night_adaptation * spec.environments.hue_weight(h0) + 1e-6
        assert drift <= bound, f"{role} drift {drift:.3f} > bound {bound:.3f}"


def test_signed_shortest_arc_wrap_sign_and_drift_symmetry():
    """Direct unit test for the circular-hue primitive the transform relies on:
    wrap behaviour at 0/360, the [-180, 180) sign convention, and agreement
    with circular_drift (its absolute value)."""
    # wrap: 350 -> 10 crosses 0/360 and is +20, not -340
    assert signed_shortest_arc(350.0, 10.0) == pytest.approx(20.0)
    assert signed_shortest_arc(10.0, 350.0) == pytest.approx(-20.0)
    # sign convention: positive = b clockwise from a (increasing hue)
    assert signed_shortest_arc(100.0, 110.0) == pytest.approx(10.0)
    assert signed_shortest_arc(110.0, 100.0) == pytest.approx(-10.0)
    # exactly antipodal folds to -180 (documented in the model docstring);
    # equivalent spellings across the wrap are zero apart
    assert signed_shortest_arc(0.0, 180.0) == pytest.approx(-180.0)
    assert signed_shortest_arc(0.0, 360.0) == pytest.approx(0.0)
    assert signed_shortest_arc(359.9, 0.1) == pytest.approx(0.2)
    # circular_drift is the absolute value, everywhere on the circle
    for a, b in ((350.0, 10.0), (100.0, 240.0), (0.0, 180.0), (300.0, 70.0)):
        assert circular_drift(a, b) == pytest.approx(abs(signed_shortest_arc(a, b)))


def test_adapt_hue_unit_function():
    """adapt_hue direction = sign of shortest arc to the warm anchor."""
    h, info = adapt_hue(_dummy_env_spec_for_hue(), "night",
                        _dummy_role(0.8), 300.0)
    assert info["direction"] > 0  # violet -> toward warm is + (increasing hue)
    h2, info2 = adapt_hue(_dummy_env_spec_for_hue(), "night",
                          _dummy_role(0.8), 245.0)
    assert info2["direction"] < 0  # azure -> toward warm is - (decreasing hue)


def _dummy_env_spec_for_hue() -> ModelSpec:
    """A throwaway spec just to exercise adapt_hue with the real environment."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    dists = DistanceSpec.load(REPO / "spec/distance-matrix.yaml", roles)
    env = Environments.load(REPO / "spec/environments.yaml")
    return ModelSpec(roles, env, dists)


def _dummy_role(na: float):
    from grotto.spec import Role
    return Role(name="x", group="syntax", description="", salience=3, family="violet",
                chroma_class="medium", contrast_target="comfortable", cvd_priority="normal",
                night_adaptation=na, area_class="minor", paint="ink",
                accessibility_floor="body_text", contrast_reference="bg")


# ===========================================================================
# 11. bounded adjustments
# ===========================================================================


def test_adjustment_within_bounds_is_applied_and_recorded(spec):
    b = binding(adjustments={"fg": RoleAdjustment("fg", L=-0.03, rationale="nudge")})
    fb = build_family(b, spec)
    applied = fb.trace("night", "fg").adjustments_applied
    assert applied["L"] == pytest.approx(-0.03, abs=1e-6)


def test_adjustment_that_breaks_wcag_is_rejected(spec):
    b = binding(
        role_overrides={"fg": {"contrast_target": "minimal"}},
        adjustments={"fg": RoleAdjustment("fg", L=-0.03, rationale="probe floor")},
    )
    fb = build_family(b, spec)
    trace = fb.trace("night", "fg")
    assert trace.adjustments_applied == {"L": 0.0, "C": 0.0, "h": 0.0}
    assert "adjustment_rejected_wcag" in trace.conflicts
    assert wcag_contrast(
        fb.variants["night"].palette["fg"], fb.variants["night"].palette["bg"]
    ) >= spec.environments.accessibility_floors["body_text_wcag"] - 1e-6


def test_adjustment_exceeding_bounds_is_rejected(spec):
    b = binding(adjustments={"fg": RoleAdjustment("fg", L=ADJUSTMENT_LIMITS["L"] + 0.01)})
    with pytest.raises(BindingError, match="exceeds bound"):
        validate_binding(b, spec)


def test_adjustment_bound_violation_raises_binding_error(spec):
    """Out-of-bounds adjustments are a MALFORMED binding (BindingError at
    validation), never clamped or extrapolated by the transform."""
    b = binding(adjustments={"keyword": RoleAdjustment("keyword", h=999.0)})
    with pytest.raises(BindingError, match="exceeds bound"):
        validate_binding(b, spec)


def test_adjusted_role_max_chroma_is_evaluated_at_final_coordinates(spec):
    """A lightness adjustment moves a role's solved L AFTER the chroma chain
    was computed; the trace's max_chroma_at_L must be the gamut ceiling at the
    FINAL (post-adjustment) coordinates -- it is the denominator of the
    normalized C/max_chroma stability check, and a pre-adjustment value is a
    stale denominator.  The swap is recorded, not silent."""
    b = binding(adjustments={"fg": RoleAdjustment("fg", L=-0.03, rationale="probe")})
    fb = build_family(b, spec)
    for v in ("day", "evening", "night"):
        t = fb.trace(v, "fg")
        assert t.adjustments_applied["L"] == pytest.approx(-0.03, abs=1e-6), (
            f"{v}: nudge rejected -- test no longer probes an applied adjustment"
        )
        L_final, _, h_final = t.requested
        assert t.max_chroma_at_L == pytest.approx(
            max_chroma(L_final, h_final, "srgb"), abs=1e-9), v
        assert t.chroma_losses["max_chroma_reevaluated"] is True, v
        assert any("re-evaluated" in d for d in t.derivation), v


# ===========================================================================
# 12. distinct paint logic
# ===========================================================================


def test_each_paint_type_uses_its_own_derivation(spec):
    fb = build_family(binding(), spec)
    # canvas -> authored; surface -> perceptual step; ink/border -> solved
    assert fb.trace("night", "bg").winning_constraint == "authored"
    assert fb.trace("night", "selection").winning_constraint == "perceptual_step"
    assert fb.trace("night", "active_line").winning_constraint == "perceptual_step"
    assert fb.trace("night", "fg").winning_constraint in (
        "apca_centre", "wcag_floor", "night_ceiling")
    assert fb.trace("night", "focus").winning_constraint in (
        "apca_centre", "wcag_floor", "night_ceiling")


def test_surfaces_step_away_from_canvas(spec):
    fb = build_family(binding(), spec)
    bg_L = hex_to_oklch(fb.variants["night"].palette["bg"])[0]
    sel_L = hex_to_oklch(fb.variants["night"].palette["selection"])[0]
    # dark variant: surface highlights step LIGHTER than the canvas
    assert sel_L > bg_L
    bg_day = hex_to_oklch(fb.variants["day"].palette["bg"])[0]
    sel_day = hex_to_oklch(fb.variants["day"].palette["selection"])[0]
    # light variant: surface tints step DARKER than the canvas
    assert sel_day < bg_day


# ===========================================================================
# 13. ink-on-co-occurring-surface legibility checks
# ===========================================================================


def test_legibility_evaluator_flags_low_contrast_ink_over_surface(spec):
    """Directly: an ink that is illegible over a surface records an issue."""
    colors = {"fg": "#777777", "selection": "#707070", "bg": "#111111",
              "diff_added": "#101010", "diff_removed": "#101010",
              "search_match": "#101010", "search_match_current": "#101010",
              "active_line": "#101010", "diff_changed": "#101010",
              "debug_current": "#101010"}
    issues = _evaluate_legibility(colors, spec.roles, spec, "night")
    # fg (#777) over selection (#707070) is well below 4.5
    assert any("fg@night over selection" in i for i in issues)
    assert all("over" in i for i in issues)


def test_legibility_covers_all_co_occurring_surfaces(spec):
    surfaces_present = [s for s in CO_OCCURRING_SURFACES]
    # every co-occurring surface is considered when present in the palette
    colors = {"fg": "#ffffff"}
    for s in surfaces_present:
        colors[s] = "#ffffff"  # white on white -> every pair fails
    colors["bg"] = "#000000"
    issues = _evaluate_legibility(colors, spec.roles, spec, "night")
    covered = {s for i in issues for s in surfaces_present if f"over {s}" in i}
    assert surfaces_present and set(surfaces_present) <= covered


def test_build_records_legibility_issues_when_present(spec):
    # the default systematic output surfaces some legibility tensions: an ink
    # role over a light surface wash (selection / search / debug) drops below
    # the body-text floor, and the evaluator must say so with a WCAG value.
    fb = build_family(binding(), spec)
    legibility = [i for i in fb.issues if "WCAG" in i and "over " in i]
    assert legibility, "expected at least one ink-on-surface legibility warning"
    assert all("ink-on-surface legibility" in i for i in legibility)


# ===========================================================================
# 14. overrides
# ===========================================================================


def test_role_override_changes_the_solve(spec):
    fb_plain = build_family(binding(), spec)
    fb_ov = build_family(
        binding(role_overrides={"keyword": {"contrast_target": "high"}}), spec)
    # raising keyword's target band should increase its |APCA|
    from grotto.contrast import apca_lc
    lc_plain = abs(apca_lc(fb_plain.variants["night"].palette["keyword"],
                           fb_plain.variants["night"].palette["bg"]))
    lc_ov = abs(apca_lc(fb_ov.variants["night"].palette["keyword"],
                        fb_ov.variants["night"].palette["bg"]))
    assert lc_ov > lc_plain


def test_binding_warm_anchor_override_changes_hue_attraction(spec):
    default = build_family(binding(), spec)
    overridden = build_family(binding(warm_anchor_override=300.0), spec)
    h_default = default.trace("night", "function").realized[2]
    h_override = overridden.trace("night", "function").realized[2]
    assert h_default < FAMILY_HUES["azure"]
    assert h_override > FAMILY_HUES["azure"]
    assert overridden.trace("night", "function").derivation


def test_target_band_membership_handles_overlapping_bands(monkeypatch, spec):
    from types import SimpleNamespace
    import grotto.model as model

    monkeypatch.setattr(
        model,
        "contrast_report",
        lambda *_: SimpleNamespace(apca=76.0, wcag=7.0, dl=0.5),
    )
    role = replace(spec.roles["fg"], contrast_target="comfortable")
    block = _contrast_block(role, "#ffffff", "#000000", spec, "night")
    assert block["measured_band"] == "high"
    assert block["in_target_band"] is True


def test_invalid_role_override_value_is_rejected(spec):
    b = binding(role_overrides={"fg": {"contrast_target": "nonsense"}})
    with pytest.raises(BindingError, match="contrast_target"):
        validate_binding(b, spec)


def test_override_cannot_change_paint_or_name(spec):
    """The derivation PATH (paint) and name are protected; they are never
    overridable.  family IS overridable (Phase 5) because reassigning a hue
    family keeps the role in the same derivation path while changing only the
    anchor it reads."""
    b = binding(role_overrides={"fg": {"paint": "surface"}})
    with pytest.raises(BindingError, match="unknown key"):
        validate_binding(b, spec)
    b2 = binding(role_overrides={"fg": {"name": "x"}})
    with pytest.raises(BindingError, match="unknown key"):
        validate_binding(b2, spec)


# ===========================================================================
# 15. salience-driven APCA centre boost (Phase-7 feedback)
# ===========================================================================
# Day carries salience_apca_step=2.0 (softened from the first revision's 5.0,
# which over-weighted lightness and darkened moderate syntax by ~.04 L):
# each salience level above the normal reading level (NORMAL_SALIENCE=2) adds
# 2 APCA Lc to the band centre, clamped to the band max.  Targets: fg 68,
# keyword/string/type 70, function 86 (no clamps).  These tests read the
# STRUCTURED solve provenance in trace.contrast["solve"], never the
# human-readable derivation strings.


def _solve_provenance(fb, variant: str, role: str) -> dict:
    return fb.trace(variant, role).contrast["solve"]


def test_day_apca_centres_fg68_medium70_function86_without_clamp(spec):
    fb = build_family(binding(), spec)
    fg = _solve_provenance(fb, "day", "fg")
    medium = {
        r: _solve_provenance(fb, "day", r)
        for r in ("keyword", "string", "type")
    }
    function = _solve_provenance(fb, "day", "function")

    # fg: salience 2 == NORMAL_SALIENCE -> no boost, comfortable centre 68
    assert fg["salience"] == NORMAL_SALIENCE == 2
    assert fg["base_apca_centre"] == pytest.approx(68.0)
    assert fg["salience_boost_requested"] == pytest.approx(0.0)
    assert fg["salience_boost_applied"] == pytest.approx(0.0)
    assert fg["effective_apca_centre"] == pytest.approx(68.0)
    assert fg["clamped_to_band_max"] is False

    # keyword/string/type: salience 3, comfortable 68 -> 68 + 1*2 = 70,
    # under the comfortable band max 78 -- a MODEST step, not the earlier 73
    for r, prov in medium.items():
        assert prov["base_apca_centre"] == pytest.approx(68.0), r
        assert prov["salience_boost_requested"] == pytest.approx(2.0), r
        assert prov["salience_boost_applied"] == pytest.approx(2.0), r
        assert prov["effective_apca_centre"] == pytest.approx(70.0), r
        assert prov["band_max"] == pytest.approx(78.0), r
        assert prov["clamped_to_band_max"] is False, r

    # function: salience 4, high 82 -> 82 + 2*2 = 86, under band max 90
    # (the earlier 5.0 step clamped it to 90 and darkened it by ~.08 L)
    assert function["base_apca_centre"] == pytest.approx(82.0)
    assert function["salience_boost_requested"] == pytest.approx(4.0)
    assert function["salience_boost_applied"] == pytest.approx(4.0)
    assert function["effective_apca_centre"] == pytest.approx(86.0)
    assert function["band_max"] == pytest.approx(90.0)
    assert function["clamped_to_band_max"] is False


def test_effective_apca_centres_never_exceed_their_band(spec):
    fb = build_family(binding(), spec)
    for v in ("day", "evening", "night"):
        step = spec.environments.environments[v].salience_apca_step
        for r in spec.roles:
            if r.paint not in ("ink", "border"):
                continue
            prov = _solve_provenance(fb, v, r.name)
            band = spec.environments.contrast_bands[r.contrast_target]
            # the clamp holds whatever the salience and step
            assert prov["effective_apca_centre"] <= band.max + 1e-9
            assert prov["salience_boost_applied"] <= prov["salience_boost_requested"] + 1e-9
            assert prov["salience_boost_requested"] == pytest.approx(
                max(0, r.salience - NORMAL_SALIENCE) * step
            )
            assert prov["effective_apca_centre"] == pytest.approx(
                prov["base_apca_centre"] + prov["salience_boost_applied"]
            )


def test_day_salient_syntax_only_modestly_darker_than_fg(spec):
    """Phase-7 follow-up: salient syntax stays visibly DARKER than `fg` on the
    light canvas, but only MODESTLY so -- the first revision's 5.0 step put
    keyword/string/type .030/.049/.047 L below fg (a separate, muted weight
    class) and function .204 below.  With step 2.0 the observed deltas are
    .004/.029/.026 and function .162: modest, and function clearly darker
    without the earlier extreme."""
    fb = build_family(binding(), spec)
    pal = fb.variants["day"].palette
    fg_L = hex_to_oklch(pal["fg"])[0]
    for r in ("keyword", "string", "type"):
        L = hex_to_oklch(pal[r])[0]
        assert fg_L - L > 0.003, f"{r} L {L:.4f} not below fg {fg_L:.4f}"
        assert fg_L - L < 0.035, (
            f"{r} L {L:.4f} darker than fg by {fg_L - L:.4f} (was ~.04-.05)"
        )
    fn_L = hex_to_oklch(pal["function"])[0]
    assert fn_L < fg_L - 0.05, "function must remain meaningfully darker than fg"
    assert fg_L - fn_L < 0.17, (
        f"function L {fn_L:.4f} still near the earlier ~.20 extreme"
    )


def test_zero_step_dark_variants_record_no_boost(spec):
    """evening/night carry step 0.0: every solve shows a zero boost and an
    effective centre equal to the base band centre."""
    fb = build_family(binding(), spec)
    for v in ("evening", "night"):
        for r in spec.roles:
            if r.paint not in ("ink", "border"):
                continue
            prov = _solve_provenance(fb, v, r.name)
            assert prov["salience_apca_step"] == pytest.approx(0.0)
            assert prov["salience_boost_requested"] == pytest.approx(0.0)
            assert prov["salience_boost_applied"] == pytest.approx(0.0)
            assert prov["effective_apca_centre"] == pytest.approx(
                prov["base_apca_centre"]
            )


def test_zero_step_dark_variant_palettes_are_byte_identical_without_knob(spec):
    """With the day step removed entirely, evening/night builds are unchanged:
    the dark variants are untouched by the feature, not merely re-solved to
    the same numbers."""
    envs = spec.environments
    without = replace(
        envs,
        environments={
            name: replace(e, salience_apca_step=0.0)
            for name, e in envs.environments.items()
        },
    )
    fb_zero = build_family(binding(), replace(spec, environments=without))
    fb_real = build_family(binding(), spec)
    for v in ("evening", "night"):
        assert fb_zero.variants[v].palette.colors == fb_real.variants[v].palette.colors
    # and the day variant DOES move under the knob (it is not a no-op)
    assert fb_zero.variants["day"].palette.colors != fb_real.variants["day"].palette.colors
