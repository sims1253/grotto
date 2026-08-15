"""Direct unit tests for the distance-matrix constraint engine ``spec.check``.

Phase 2's checker was previously covered only incidentally, through fixtures
whose naturally occurring violations exercised two branches.  These tests
drive every constraint kind and every severity rule with synthetic palettes,
including the CVD error->warning downgrade when a redundant channel exists.
"""

from __future__ import annotations

from grotto.spec import (
    Constraint,
    DistanceSpec,
    Palette,
    Role,
    RoleSpec,
    check,
)


def _role(name, **kw):
    base = dict(
        group="syntax", description="", salience=2, family="neutral",
        chroma_class="trace", contrast_target="comfortable", cvd_priority="low",
        night_adaptation=1.0, area_class="minor", paint="ink",
        accessibility_floor="body_text", contrast_reference="bg",
    )
    base.update(kw)
    return Role(name=name, **base)


def _spec(pairs_extra=()):
    """Minimal spec: bg/fg plus any extra roles/constraints the test needs."""
    roles = RoleSpec(version=1, roles={
        "bg": _role("bg", group="neutrals", salience=0, paint="canvas",
                    accessibility_floor="none", contrast_reference=None),
        "fg": _role("fg", group="neutrals"),
    })
    for r in pairs_extra:
        roles.roles[r.name] = r
    return roles


def _dists(constraints, thresholds=None):
    th = thresholds or {
        "must_distinguish": {"normal_vision": 0.13, "cvd_dichromat": 0.09},
        "should_distinguish": {"normal_vision": 0.08},
        "same_family": {"max_distance": 0.14, "min_distance": 0.03},
        "differentiated_by": {"max_distance": 0.05, "requires_channel": True},
    }
    return DistanceSpec(version=1, thresholds=th, constraints=tuple(constraints))


def _pal(**colors):
    return Palette("t", "night", colors)


# far apart, close together, and the canonical collapsing pair under deutan
FAR_A, FAR_B = "#101010", "#e8e8e8"
CLOSE_A, CLOSE_B = "#808080", "#818181"
RED, GREEN = "#c04c4c", "#4c9c4c"


def test_all_pass_when_constraints_satisfied():
    roles = _spec()
    dists = _dists([Constraint("fg", "bg", "must_distinguish")])
    v = check(_pal(bg="#101010", fg="#e8e8e8"), roles, dists)
    assert v == []


def test_must_distinguish_below_normal_threshold_is_error():
    roles = _spec()
    dists = _dists([Constraint("fg", "bg", "must_distinguish")])
    v = check(_pal(bg="#808080", fg="#818181"), roles, dists)
    assert [(x.constraint.kind, x.condition, x.severity) for x in v][0] == (
        "must_distinguish", "normal", "error"
    )


def test_cvd_collapse_without_redundancy_is_error_with_redundancy_is_warning():
    # red/green: the pair that collapses under deutan but not protan
    roles = _spec([
        _role("error", group="diagnostics", family="rose", salience=6,
              cvd_priority="critical"),  # NO redundant channel declared
        _role("success", group="diagnostics", family="sage", salience=4),
    ])
    dists = _dists([Constraint("error", "success", "must_distinguish")])
    pal = _pal(bg="#101010", fg="#e8e8e8", error=RED, success=GREEN)

    bare = check(pal, roles, dists)
    kinds = {(x.condition, x.severity) for x in bare}
    assert ("deutan@1.0", "error") in kinds  # neither role declares a channel

    roles_warn = RoleSpec(version=1, roles={
        **roles.roles,
        "success": _role("success", group="diagnostics", family="sage",
                         salience=4, cvd_priority="critical",
                         redundant_channels=("gutter_icon",)),
    })
    soft = check(pal, roles_warn, dists)
    kinds_soft = {(x.condition, x.severity) for x in soft}
    assert ("deutan@1.0", "warning") in kinds_soft  # downgraded, still reported


def test_should_distinguish_is_warning_only_and_never_runs_cvd():
    roles = _spec()
    dists = _dists([Constraint("fg", "bg", "should_distinguish")])
    v = check(_pal(bg=CLOSE_A, fg=CLOSE_B), roles, dists)
    assert len(v) == 1
    assert v[0].severity == "warning"
    assert v[0].condition == "normal"


def test_same_family_enforced_from_both_sides():
    roles = _spec([
        _role("number", family="sand", salience=3),
        _role("constant", family="sand", salience=3),
    ])
    dists = _dists([Constraint("number", "constant", "same_family")])
    too_far = check(_pal(bg="#101010", number=FAR_A, constant=FAR_B), roles, dists)
    assert too_far and too_far[0].condition == "upper"
    too_close = check(_pal(bg="#101010", number=CLOSE_A, constant=CLOSE_B), roles, dists)
    assert too_close and too_close[0].condition == "lower"


def test_differentiated_by_requires_channel_and_distance_bound():
    roles = _spec([
        _role("parameter", salience=2),
        _role("variable_x", salience=2),
    ])
    with_channel = _dists([Constraint("parameter", "variable_x", "differentiated_by",
                                      channel="italic")])
    without = _dists([Constraint("parameter", "variable_x", "differentiated_by")])
    pal = _pal(bg="#101010", parameter="#e0e0e0", variable_x="#e8e8e8")
    assert check(pal, roles, with_channel) == []          # within 0.05, channel present
    v = check(pal, roles, without)                         # channel missing -> error
    assert any(x.condition == "channel" and x.severity == "error" for x in v)


def test_redundant_encoding_without_channel_is_error():
    roles = _spec([
        _role("diff_added", group="diagnostics", family="sage", salience=3,
              cvd_priority="critical", redundant_channels=("gutter_sign",)),
        _role("diff_removed", group="diagnostics", family="rose", salience=3,
              cvd_priority="critical", redundant_channels=("gutter_sign",)),
    ])
    missing = _dists([Constraint("diff_added", "diff_removed", "redundant_encoding")])
    present = _dists([Constraint("diff_added", "diff_removed", "redundant_encoding",
                                 channel="lightness_and_gutter_sign")])
    pal = _pal(bg="#101010", diff_added="#123d12", diff_removed="#3d1212")
    assert any(x.condition == "channel" for x in check(pal, roles, missing))
    assert all(x.condition != "channel" for x in check(pal, roles, present))


def test_partial_palette_pairs_are_skipped_silently():
    roles = _spec([
        _role("error", group="diagnostics", family="rose", salience=6),
    ])
    dists = _dists([
        Constraint("error", "fg", "must_distinguish"),
        Constraint("error", "success", "must_distinguish"),  # success absent
    ])
    # error absent too -> every constraint involving it is skipped
    assert check(_pal(bg="#101010", fg="#e8e8e8"), roles, dists) == []
    # error present, success still absent -> only the error/fg pair evaluated
    v = check(_pal(bg="#101010", fg="#e8e8e8", error=RED), roles, dists)
    assert all("success" not in str(x.constraint) for x in v)
