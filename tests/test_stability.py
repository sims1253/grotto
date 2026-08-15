"""Cross-variant stability reporting (DESIGN.md D-5)."""

from pathlib import Path

import pytest

from grotto.spec import Palette, RoleSpec, load
from grotto.stability import (
    DEFAULT_CHROMA_FLOOR,
    circular_drift,
    cross_variant_report,
)

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# geometry helpers
# --------------------------------------------------------------------------


def test_circular_drift_wraps_and_is_symmetric():
    assert circular_drift(0.0, 0.0) == pytest.approx(0.0)
    assert circular_drift(10.0, 350.0) == pytest.approx(20.0)  # across the wrap
    assert circular_drift(0.0, 180.0) == pytest.approx(180.0)
    assert circular_drift(30.0, 90.0) == pytest.approx(circular_drift(90.0, 30.0))


# --------------------------------------------------------------------------
# achromatic suppression -- the central correctness property
# --------------------------------------------------------------------------


def test_achromatic_role_hue_drift_is_suppressed():
    """A neutral bg with chroma ~0.007 can swing hue hugely between variants
    while looking identical. Reporting that as 'drift' would be a bug."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    trio = {v: load(REPO / f"themes/fixtures/eval-{v}.yaml") for v in ("day", "evening", "night")}
    rep = cross_variant_report(trio, roles)
    bg = rep.roles["bg"]
    assert bg.hue_meaningful is False
    assert bg.max_hue_drift is None
    # and therefore it never appears in drift violations even though its raw
    # hue spans ~70..265 degrees across the trio
    assert "bg" not in {r for r, _ in rep.drift_violations}


def test_chromatic_role_drift_is_measured():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    trio = {v: load(REPO / f"themes/fixtures/eval-{v}.yaml") for v in ("day", "evening", "night")}
    rep = cross_variant_report(trio, roles)
    kw = rep.roles["keyword"]
    assert kw.hue_meaningful is True
    assert kw.max_hue_drift == pytest.approx(3.0, abs=0.5)


# --------------------------------------------------------------------------
# rank / order inversion detection
# --------------------------------------------------------------------------


def test_synthetic_hue_order_inversion_is_detected():
    """Two chromatic roles whose relative hue order flips between variants."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    a = Palette("a", "day", {"bg": "#101010", "string": "#33aa33", "keyword": "#aa33aa"})
    b = Palette("b", "night", {"bg": "#101010", "string": "#aa33aa", "keyword": "#33aa33"})
    rep = cross_variant_report({"day": a, "night": b}, roles)
    assert any(i.kind == "hue_order" for i in rep.hue_order_inversions)
    assert rep.ok is False


def test_synthetic_chroma_rank_inversion_is_detected():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    a = Palette("a", "day", {"bg": "#101010", "string": "#88dd88", "keyword": "#cc66cc"})
    b = Palette("b", "night", {"bg": "#101010", "string": "#cc66cc", "keyword": "#88dd88"})
    rep = cross_variant_report({"day": a, "night": b}, roles)
    assert any(i.kind == "chroma_rank" for i in rep.chroma_rank_inversions)


def test_no_inversion_when_order_is_stable():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    a = Palette("a", "day", {"bg": "#101010", "string": "#33aa33", "keyword": "#aa33aa"})
    b = Palette("b", "night", {"bg": "#101010", "string": "#44bb44", "keyword": "#bb44bb"})
    rep = cross_variant_report({"day": a, "night": b}, roles)
    assert rep.hue_order_inversions == ()
    assert rep.chroma_rank_inversions == ()


# --------------------------------------------------------------------------
# drift gate + informational dE
# --------------------------------------------------------------------------


def test_drift_violation_flagged_over_threshold():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    a = Palette("a", "day", {"bg": "#101010", "string": "#33aa33"})   # green
    b = Palette("b", "night", {"bg": "#101010", "string": "#aaa333"})  # olive -- large hue shift
    rep = cross_variant_report({"day": a, "night": b}, roles, max_hue_drift_deg=12.0)
    flagged = {r: d for r, d in rep.drift_violations}
    assert "string" in flagged
    assert flagged["string"] > 12.0  # well over the gate
    assert rep.ok is False


def test_cross_variant_de_is_informational_not_a_gate():
    """A large cross-variant dE (lightness inversion) must NOT make ok=False."""
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    a = Palette("a", "day", {"bg": "#101010", "fg": "#202020"})     # dark fg (light theme)
    b = Palette("b", "night", {"bg": "#101010", "fg": "#e0e0e0"})   # light fg (dark theme)
    rep = cross_variant_report({"day": a, "night": b}, roles)
    fg = rep.roles["fg"]
    # dE is large (lightness inverted) ...
    assert fg.cross_variant_de[0][2] > 0.5
    # ... but the report is still ok, because dE is not a stability gate.
    assert rep.ok is True


def test_salience_rank_preserved_flag_rejects_unknown_roles():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    a = Palette("a", "day", {"bg": "#101010", "bogus_role": "#ff00ff"})
    b = Palette("b", "night", {"bg": "#101010", "bogus_role": "#00ffff"})
    rep = cross_variant_report({"day": a, "night": b}, roles)
    assert rep.salience_rank_preserved is False
    assert rep.ok is False


def test_report_needs_two_variants():
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    with pytest.raises(ValueError):
        cross_variant_report({"day": Palette("a", "day", {"bg": "#000"})}, roles)


def test_to_dict_roundtrip_is_jsonable():
    import json

    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    trio = {v: load(REPO / f"themes/fixtures/eval-{v}.yaml") for v in ("day", "evening", "night")}
    rep = cross_variant_report(trio, roles)
    s = json.dumps(rep.to_dict())  # must not raise
    assert "cross_variant_de_informational" in s
