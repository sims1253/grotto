"""Phase 4 semantic-schema corrections (commit 1).

Every role now declares ``paint`` (canvas|ink|surface|border),
``accessibility_floor`` (body_text|non_text|none) and ``contrast_reference``.
The environments loader now retains the elevated/overlay backgrounds, the
hue-rotation-weight control points and the warm anchor.  These tests pin the
corrections so the transform (commit 2) can branch on ``paint`` safely.
"""

from pathlib import Path

import pytest

from grotto.environments import DEFAULT_WARM_ANCHOR, Environments, hue_weight
from grotto.spec import (
    ACCESSIBILITY_FLOORS,
    PAINT_TYPES,
    RoleSpec,
)

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# roles.yaml: every role carries the Phase 4 semantic fields
# --------------------------------------------------------------------------


def test_every_role_has_paint_floor_and_reference():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    for r in roles:
        assert r.paint in PAINT_TYPES, f"{r.name}: paint {r.paint!r}"
        assert r.accessibility_floor in ACCESSIBILITY_FLOORS, f"{r.name}: floor"
        # canvas is the only null reference; every other role names a surface
        if r.paint == "canvas":
            assert r.contrast_reference is None
        else:
            assert r.contrast_reference is not None


def test_paint_distribution_is_complete_and_distinct():
    """paint partitions the role set into the four derivation paths."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    by_paint = {p: [] for p in PAINT_TYPES}
    for r in roles:
        by_paint[r.paint].append(r.name)
    assert by_paint["canvas"] == ["bg"], "exactly one canvas: bg"
    assert by_paint["border"], "at least one border role"
    assert by_paint["surface"], "at least one surface role"
    assert by_paint["ink"], "at least one ink role"
    # surfaces include the diff/search/selection/active-line/debug highlights
    surfaces = set(by_paint["surface"])
    assert {"selection", "diff_added", "diff_removed", "active_line",
            "search_match", "debug_current"} <= surfaces


def test_accessibility_floor_matches_role_intent():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    r = {x.name: x for x in roles}
    # body-text reading roles carry the 4.5 floor
    for name in ("fg", "keyword", "string", "error", "operator"):
        assert r[name].accessibility_floor == "body_text"
    # deliberately de-emphasised chrome still carries a (non-text) floor
    assert r["fg_muted"].accessibility_floor == "non_text"
    assert r["line_number"].accessibility_floor == "non_text"
    # borders are graphical -> non-text floor
    assert r["focus"].accessibility_floor == "non_text"
    assert r["ui_inactive"].accessibility_floor == "non_text"
    # canvas and surface washes carry no WCAG floor
    assert r["bg"].accessibility_floor == "none"
    assert r["selection"].accessibility_floor == "none"
    assert r["diff_added"].accessibility_floor == "none"


def test_contrast_reference_is_internally_consistent():
    """Every non-null contrast_reference must name a real role (loader check)."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    names = set(roles.roles)
    for r in roles:
        if r.contrast_reference is not None:
            assert r.contrast_reference in names


def test_dangling_contrast_reference_is_rejected(tmp_path):
    bad = (REPO / "spec/roles.yaml").read_text().replace(
        'contrast_reference: "bg"\n    description: Editor canvas.',
        'contrast_reference: "ghost"\n    description: Editor canvas.',
    ) if False else None  # bg reference is null; mutate an ink role instead
    # mutate the fg role's reference to a non-existent role
    src = (REPO / "spec/roles.yaml").read_text()
    src = src.replace(
        '  fg:\n    paint: ink\n    accessibility_floor: body_text\n    contrast_reference: "bg"',
        '  fg:\n    paint: ink\n    accessibility_floor: body_text\n    contrast_reference: "nope"',
        1,
    )
    p = tmp_path / "roles-bad.yaml"
    p.write_text(src)
    with pytest.raises(ValueError, match="contrast_reference"):
        RoleSpec.load(p)


def test_two_canvases_rejected(tmp_path):
    src = (REPO / "spec/roles.yaml").read_text()
    # promote an ink role to a second canvas
    src = src.replace(
        '  fg:\n    paint: ink',
        '  fg:\n    paint: canvas',
        1,
    )
    p = tmp_path / "roles-two-canvas.yaml"
    p.write_text(src)
    with pytest.raises(ValueError, match="canvas"):
        RoleSpec.load(p)


# --------------------------------------------------------------------------
# environments.yaml: retained parameters for the transform
# --------------------------------------------------------------------------


def test_environments_retain_elevated_overlay_backgrounds():
    env = Environments.load(REPO / "spec/environments.yaml")
    night = env.environments["night"]
    # elevated and overlay are distinct from the canvas and authored verbatim
    assert night.background_elevated.L == pytest.approx(0.238)
    assert night.background_overlay.L == pytest.approx(0.265)
    assert night.background_elevated.L > night.background.L
    day = env.environments["day"]
    # light polarity: elevated is lighter than canvas
    assert day.background_elevated.L > day.background.L


def test_environments_retain_hue_rotation_weight_and_warm_anchor():
    env = Environments.load(REPO / "spec/environments.yaml")
    assert env.hue_rotation_weight, "hue_rotation_weight control points retained"
    keys = [h for h, _ in env.hue_rotation_weight]
    assert keys == sorted(keys), "control points sorted ascending"
    assert env.warm_anchor == pytest.approx(70.0)


def test_hue_weight_interpolation_is_monotonic_at_control_points():
    env = Environments.load(REPO / "spec/environments.yaml")
    # exact control-point hues interpolate to their declared weight
    assert env.hue_weight(0) == pytest.approx(0.15)
    assert env.hue_weight(240) == pytest.approx(1.00)   # azure carries it all
    assert env.hue_weight(300) == pytest.approx(0.70)   # violet
    # midpoints interpolate linearly: 240->300 goes 1.00 -> 0.70, at 270 -> 0.85
    assert env.hue_weight(270) == pytest.approx(0.85)
    # warm hues barely move
    assert env.hue_weight(30) < 0.20


def test_hue_weight_wraps_modulo_360():
    env = Environments.load(REPO / "spec/environments.yaml")
    assert env.hue_weight(360 + 30) == pytest.approx(env.hue_weight(30))
    assert env.hue_weight(-10) == pytest.approx(env.hue_weight(350))


def test_hue_weight_pure_function_without_instance():
    pts = ((0.0, 0.15), (240.0, 1.0), (360.0, 0.15))
    assert hue_weight(pts, 240.0) == pytest.approx(1.0)
    assert hue_weight(pts, 120.0) == pytest.approx(0.575)  # midpoint 0..240


def test_rotation_cap_is_magnitude():
    env = Environments.load(REPO / "spec/environments.yaml")
    # the YAML sign is vestigial for direction; the cap is the absolute value
    assert env.environments["night"].rotation_cap_deg == pytest.approx(8.0)
    assert env.environments["day"].rotation_cap_deg == pytest.approx(0.0)
