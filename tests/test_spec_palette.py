"""Tests for palette loading, validation and the per-role colour audit.

Covers the OKLCH-first (canonical) loader, hex validation, gamut-loss
provenance, the candidate flag, and cross-validation of the OKLCH->hex
conversion against coloraide.
"""

from pathlib import Path

import pytest
from coloraide import Color

from grotto.color import gamut_status, hex_to_oklch, oklch_to_hex
from grotto.spec import Palette, RoleSpec, audit_palette, load, missing_roles, validate_hex

REPO = Path(__file__).resolve().parents[1]


# --------------------------------------------------------------------------
# OKLCH-first loader
# --------------------------------------------------------------------------


def test_oklch_fixture_loads_with_provenance():
    p = load(REPO / "themes/fixtures/eval-night-full.yaml")
    assert p.source == "oklch"
    assert p.is_candidate is False
    assert p.variant == "night"
    # perceptual coords preserved verbatim
    assert p.perceptual["bg"] == (0.205, 0.007, 70.0)
    # hex derived and lower-cased
    assert p["bg"].startswith("#") and p["bg"] == p["bg"].lower()
    assert len(p) >= 35


def test_oklch_hex_matches_coloraide():
    """The fixture's OKLCH->hex conversion must agree with coloraide."""
    p = load(REPO / "themes/fixtures/eval-night-full.yaml")
    for role in ("bg", "fg", "keyword", "error"):
        L, C, h = p.perceptual[role]
        # coloraide's oklch->srgb, gamut-clipped to srgb, 8-bit hex
        ref = (
            Color("oklch", [L, C, h])
            .convert("srgb")
            .fit("srgb")
            .to_string(hex=True)
            .lower()
        )
        assert p[role] == ref, f"{role}: grotto {p[role]} vs coloraide {ref}"


def test_gamut_loss_is_recorded_for_oog_role():
    """`focus` is deliberately past sRGB; the loader must map it and report loss."""
    p = load(REPO / "themes/fixtures/eval-night-full.yaml")
    assert p.gamut_losses["focus"] > 0.01
    # after mapping it is in gamut
    assert gamut_status(hex_to_oklch(p["focus"])).in_srgb
    # in-gamut roles lose nothing
    assert p.gamut_losses["bg"] == pytest.approx(0.0, abs=1e-9)


def test_hex_reference_theme_still_loads():
    """Reference themes use 'roles:' hex maps with nulls -- must keep working."""
    p = load(REPO / "themes/references/nord.yaml")
    assert p.source == "hex"
    assert p.is_candidate is False
    assert "bg" in p
    # null roles are dropped, not stored as the string 'none'
    assert all(v.startswith("#") for v in p.colors.values())


def test_partial_palette_missing_roles_reported():
    p = Palette("partial", "night", {"bg": "#111111", "fg": "#eeeeee"})
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    miss = missing_roles(p, roles)
    assert "bg" not in miss and "fg" not in miss
    assert "keyword" in miss and "error" in miss


# --------------------------------------------------------------------------
# validation
# --------------------------------------------------------------------------


def test_validate_hex_rejects_garbage():
    bad = Palette("bad", "night", {"bg": "#111111", "fg": "nope"})
    with pytest.raises(ValueError, match="not #rrggbb"):
        validate_hex(bad)


def test_validate_hex_accepts_good_palette():
    p = load(REPO / "themes/fixtures/eval-night-full.yaml")
    validate_hex(p)  # must not raise


def test_variant_must_be_nonempty_string():
    # variant is a free label (grotto: day/evening/night; references: dark/light),
    # but it must be a non-empty string.
    with pytest.raises(ValueError, match="variant"):
        Palette("x", "", {"bg": "#000000"})
    with pytest.raises(ValueError, match="variant"):
        Palette("x", None, {"bg": "#000000"})  # type: ignore[arg-type]
    # an arbitrary editor-style variant is accepted
    assert Palette("x", "dark", {"bg": "#000000"}).variant == "dark"


# --------------------------------------------------------------------------
# audit
# --------------------------------------------------------------------------


def test_audit_covers_every_role_with_full_data():
    p = load(REPO / "themes/fixtures/eval-night-full.yaml")
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    au = audit_palette(p, roles)
    assert set(au) == set(p.roles())
    a = au["focus"]
    # focus was gamut-mapped -> chroma_lost recorded
    assert a.chroma_lost > 0
    assert a.source == "oklch"
    # gamut status reported explicitly on both spaces
    assert isinstance(a.in_srgb, bool)
    assert isinstance(a.in_p3, bool)
    # OKLCH and OKLab are consistent
    assert a.oklch[0] == pytest.approx(a.oklab[0], abs=1e-9)


def test_audit_order_follows_spec():
    p = load(REPO / "themes/fixtures/eval-night-full.yaml")
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    au = audit_palette(p, roles)
    spec_order = [n for n in roles.roles if n in p]
    assert list(au)[: len(spec_order)] == spec_order


def test_audit_round_trips_through_as_dict():
    p = load(REPO / "themes/fixtures/eval-night-full.yaml")
    roles = RoleSpec.load(REPO / "spec/roles.yaml")
    d = audit_palette(p, roles)["bg"].as_dict()
    assert set(d) == {"role", "hex", "oklch", "oklab", "gamut", "chroma_lost", "source"}
    assert set(d["gamut"]) == {"in_srgb", "in_p3", "srgb_excursion", "p3_excursion"}
    # no numpy scalars leak into the dict (would break YAML)
    assert type(d["oklch"]["L"]) is float
